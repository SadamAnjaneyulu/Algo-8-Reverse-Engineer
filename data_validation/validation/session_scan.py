"""Stage 2/5/7: scans every committed session file (options, spot, futures) and compares raw JSON with normalized CSV. Pure read; results go to reports/tables.
Usage: python3 -m validation.session_scan <commit> <out_dir> [--only nifty|sensex] [--limit N] [--no-raw]"""
import csv, hashlib, io, json, os, re, sys, collections
from datetime import date, datetime, time
from multiprocessing import Pool
import numpy as np, pandas as pd
from .gitsrc import GitSource

STEP = {'nifty': 50, 'sensex': 100}; CAS_START = date(2026, 8, 3)
_G = None; _PLAN = None


def _init(commit):
    global _G, _PLAN
    _G = GitSource(commit); _PLAN = collections.defaultdict(set)
    for r in csv.reader(io.StringIO(_G.text('manifests/checkpoint.csv'))):
        if r[1] == 'option': _PLAN[(r[0], r[2], r[3])].add((int(r[4]), 'CE' if r[5] == 'call' else 'PE'))


def expected_last(day): return time(15, 39) if day >= CAS_START else time(15, 29)


from .checks import ohlc_flags


def scan_option(args):
    idx, exp, day, with_raw = args; rel = f'normalized/{idx}/options/exp{exp}_{day}.csv'; D = date.fromisoformat(day); E = date.fromisoformat(exp)
    out = dict(index=idx, expiry=exp, day=day, file=rel, bytes=_G.tree()[rel][1])
    txt = _G.read(rel)
    try: x = pd.read_csv(io.BytesIO(txt))
    except pd.errors.EmptyDataError: x = pd.DataFrame(columns=['datetime', 'expiry_date', 'strike', 'right', 'open', 'high', 'low', 'close', 'volume', 'open_interest', 'stock_code', 'exchange_code'])
    out['rows'] = len(x); out['columns'] = ','.join(x.columns); out['bytes_sha256'] = hashlib.sha256(txt).hexdigest()
    plan = _PLAN[(idx, exp, day)]; out['planned_contracts'] = len(plan)
    if not len(x): out['empty'] = True; return out, []
    ts = pd.to_datetime(x.datetime, errors='coerce'); out['ts_unparseable'] = int(ts.isna().sum()); out['ts_has_tz'] = bool(x.datetime.astype(str).str.contains(r'[+Z]').any())
    x['ts'] = ts; x['dt'] = ts.dt.date; x['tm'] = ts.dt.time
    out['date_mismatch_rows'] = int((x.dt != D).sum()); out['weekend_rows'] = int((ts.dt.weekday >= 5).sum())
    out['before_0915'] = int((x.tm < time(9, 15)).sum()); out['after_expected_last'] = int((x.tm > expected_last(D)).sum()); out['after_1530'] = int((x.tm > time(15, 30)).sum()); out['seconds_nonzero'] = int((ts.dt.second != 0).sum())
    out['dup_rows_full'] = int(x.duplicated().sum()); out['dup_keys'] = int(x.duplicated(['datetime', 'strike', 'right']).sum())
    out['expiry_field_values'] = ','.join(sorted(x.expiry_date.astype(str).unique())[:5]); ed = pd.to_datetime(x.expiry_date, format='%d-%b-%Y', errors='coerce'); out['expiry_unparseable'] = int(ed.isna().sum()); out['expiry_mismatch_rows'] = int((ed.dt.date != E).sum())
    out['right_values'] = ','.join(sorted(x.right.astype(str).unique())); out['stock_codes'] = ','.join(sorted(x.stock_code.astype(str).unique())); out['exchange_codes'] = ','.join(sorted(x.exchange_code.astype(str).unique()))
    out.update({'ohlc_' + k: v for k, v in ohlc_flags(x).items()})
    for c in ('volume', 'open_interest'): out[c + '_nan'] = int(x[c].isna().sum()); out[c + '_neg'] = int((x[c] < 0).sum()); out[c + '_nonint'] = int((x[c].dropna() % 1 != 0).sum())
    out['strike_off_grid_rows'] = int((x.strike % STEP[idx] != 0).sum()); strikes = sorted(x.strike.unique()); out['n_strikes_with_rows'] = len(strikes)
    ce = set(x.loc[x.right == 'CE', 'strike']); pe = set(x.loc[x.right == 'PE', 'strike']); out['ce_strikes'] = len(ce); out['pe_strikes'] = len(pe); out['ce_not_pe'] = len(ce - pe); out['pe_not_ce'] = len(pe - ce)
    have = set(zip(x.strike.astype(int), x.right)); out['planned_without_rows'] = len(plan - have); out['rows_outside_plan'] = len(have - plan)
    pstrikes = sorted({s for s, _ in plan}); out['plan_strike_min'] = pstrikes[0] if pstrikes else None; out['plan_strike_max'] = pstrikes[-1] if pstrikes else None
    out['plan_strikes'] = len(pstrikes); out['plan_center'] = (pstrikes[0] + pstrikes[-1]) // 2 if pstrikes else None
    steps = np.diff(pstrikes) if len(pstrikes) > 1 else []; out['plan_step_values'] = ','.join(map(str, sorted(set(steps))))
    # per-contract table
    x['key'] = x.strike.astype(int).astype(str) + x.right
    g = x.groupby(['strike', 'right'], sort=False); rows = []
    gridn = 375 if D < CAS_START else 385; mins = (x.ts.dt.hour * 60 + x.ts.dt.minute)
    x['m'] = mins - 555
    for (s, r), d in g:
        m = d.m.values; inside = m[(m >= 0) & (m < gridn)]; ordered = bool((np.diff(d.ts.values.astype('int64')) > 0).all()) if len(d) > 1 else True
        pr = d[['open', 'high', 'low', 'close', 'volume', 'open_interest']].round(4).values
        flat = ((d.open == d.high) & (d.high == d.low) & (d.low == d.close))
        rows.append(dict(index=idx, expiry=exp, day=day, strike=int(s), right=r, bars=len(d), bars_in_grid=len(np.unique(inside)), grid=gridn, first=d.ts.min().strftime('%H:%M'), last=d.ts.max().strftime('%H:%M'), ordered=ordered, dup_ts=int(d.datetime.duplicated().sum()),
                         zero_vol=int((d.volume == 0).sum()), oi_zero=int((d.open_interest == 0).sum()), oi_nunique=int(d.open_interest.nunique()), vol_sum=int(d.volume.sum()), flat_bars=int(flat.sum()), close_nunique=int(d.close.nunique()), close_first=float(d.close.iloc[0]), close_last=float(d.close.iloc[-1]),
                         max_gap=int(np.diff(np.sort(np.unique(inside))).max()) if len(np.unique(inside)) > 1 else 0, series_hash=hashlib.md5(pr.tobytes()).hexdigest()))
    # raw comparison
    if with_raw:
        raw = json.loads(_G.read(f'raw/{idx}/options/exp{exp}_{day}.json')); rr = raw.get('rows', []); out['raw_keys'] = ','.join(sorted(k for k in raw if k != 'rows')); out['raw_status'] = str(raw.get('status')); out['raw_rows'] = len(rr)
        if rr:
            R = pd.DataFrame(rr); out['raw_columns'] = ','.join(sorted(R.columns)); R['right'] = R['right'].astype(str)
            cols = ['datetime', 'strike', 'right', 'open', 'high', 'low', 'close', 'volume', 'open_interest']
            out['raw_dup_rows_full'] = int(R[cols].duplicated().sum()); out['raw_dup_keys'] = int(R.duplicated(['datetime', 'strike', 'right']).sum())
            Ru = R.drop_duplicates(cols); N = x[cols]
            mR = Ru.merge(N, on=['datetime', 'strike', 'right'], how='outer', suffixes=('_r', '_n'), indicator=True, validate='one_to_one' if not Ru.duplicated(['datetime', 'strike', 'right']).any() else 'one_to_many')
            out['raw_only_rows'] = int((mR._merge == 'left_only').sum()); out['norm_only_rows'] = int((mR._merge == 'right_only').sum()); b = mR[mR._merge == 'both']
            out['value_mismatch_rows'] = int(sum(((b[c + '_r'] != b[c + '_n']) & ~(b[c + '_r'].isna() & b[c + '_n'].isna())).sum() for c in cols[3:]))
            out['raw_strike_price_vs_strike_mismatch'] = int((R['strike_price'].astype(float) != R['strike'].astype(float)).sum()) if 'strike_price' in R else None
            out['raw_expiry_values'] = ','.join(sorted(R.expiry_date.astype(str).unique())[:3])
        out['raw_sha256'] = hashlib.sha256(_G.read(f'raw/{idx}/options/exp{exp}_{day}.json')).hexdigest()
    return out, rows


def scan_under(args):
    idx, kind, day = args; rel = f'normalized/{idx}/underlying/{kind}/{day}.csv'; D = date.fromisoformat(day)
    x = pd.read_csv(io.BytesIO(_G.read(rel))); out = dict(index=idx, kind=kind, day=day, rows=len(x))
    if not len(x): out['empty'] = True; return out
    ts = pd.to_datetime(x.datetime, errors='coerce'); x['ts'] = ts; x['tm'] = ts.dt.time; out['ts_unparseable'] = int(ts.isna().sum()); out['date_mismatch_rows'] = int((ts.dt.date != D).sum()); out['dup_ts'] = int(x.duplicated('datetime').sum()); out['ordered'] = bool(ts.is_monotonic_increasing)
    out.update({'ohlc_' + k: v for k, v in ohlc_flags(x).items()}); out['first'] = ts.min().strftime('%H:%M'); out['last'] = ts.max().strftime('%H:%M')
    out['before_0915'] = int((x.tm < time(9, 15)).sum()); out['after_1529'] = int((x.tm > time(15, 29)).sum()); out['volume_nonzero_rows'] = int((x.volume.fillna(0) != 0).sum()); out['volume_neg'] = int((x.volume < 0).sum())
    ses = x[(x.tm >= time(9, 15)) & (x.tm <= time(15, 29))]; mm = (ses.ts.dt.hour * 60 + ses.ts.dt.minute - 555).values; out['session_bars'] = int(len(np.unique(mm))); out['session_missing_minutes'] = int(375 - len(np.unique(mm[(mm >= 0) & (mm < 375)])))
    if len(ses): out.update(day_open=float(ses.open.iloc[0]), day_high=float(ses.high.max()), day_low=float(ses.low.min()), day_close=float(ses.close.iloc[-1]), close_last_any=float(x.close.iloc[-1]))
    if kind == 'futures': out['expiry_values'] = ','.join(sorted(x.expiry_date.astype(str).unique())[:4]); out['stock_codes'] = ','.join(sorted(x.stock_code.astype(str).unique())); out['exchange_codes'] = ','.join(sorted(x.exchange_code.astype(str).unique()))
    else: out['stock_codes'] = ','.join(sorted(x.stock_code.astype(str).unique())); out['exchange_codes'] = ','.join(sorted(x.exchange_code.astype(str).unique()))
    # raw check for underlying: same rows?
    raw = json.loads(_G.read(f'raw/{idx}/underlying/{kind}/{day}.json')); rr = raw.get('rows', []); out['raw_rows'] = len(rr); out['raw_status'] = str(raw.get('status', ''))
    if rr:
        R = pd.DataFrame(rr); m = R.merge(x, on='datetime', how='outer', suffixes=('_r', '_n'), indicator=True); out['raw_only_rows'] = int((m._merge == 'left_only').sum()); out['norm_only_rows'] = int((m._merge == 'right_only').sum()); b = m[m._merge == 'both']
        out['value_mismatch_rows'] = int(sum((b[c + '_r'] != b[c + '_n']).sum() for c in ('open', 'high', 'low', 'close', 'volume')))
    return out


def main():
    commit, out_dir = sys.argv[1], sys.argv[2]; only = sys.argv[sys.argv.index('--only') + 1] if '--only' in sys.argv else None; limit = int(sys.argv[sys.argv.index('--limit') + 1]) if '--limit' in sys.argv else None; with_raw = '--no-raw' not in sys.argv
    os.makedirs(out_dir, exist_ok=True); g = GitSource(commit); t = g.tree(); jobs_o, jobs_u = [], []
    for p in sorted(t):
        m = re.match(r'normalized/(nifty|sensex)/options/exp(\S{10})_(\S{10})\.csv', p)
        if m and (not only or only == m[1]): jobs_o.append((m[1], m[2], m[3], with_raw))
        m = re.match(r'normalized/(nifty|sensex)/underlying/(spot|futures)/(\S{10})\.csv', p)
        if m and (not only or only == m[1]): jobs_u.append((m[1], m[2], m[3]))
    if limit: jobs_o, jobs_u = jobs_o[:limit], jobs_u[:limit]
    with Pool(4, initializer=_init, initargs=(commit,)) as pool:
        res_u = pool.map(scan_under, jobs_u, chunksize=8); json.dump(res_u, open(os.path.join(out_dir, 'underlying_scan.json'), 'w'))
        res = []; contracts = []
        for i, (o, c) in enumerate(pool.imap(scan_option, jobs_o, chunksize=1)):
            res.append(o); contracts += c
            if i % 25 == 0: print(f'{i}/{len(jobs_o)}', flush=True)
    json.dump(res, open(os.path.join(out_dir, 'option_session_scan.json'), 'w')); pd.DataFrame(contracts).to_parquet(os.path.join(out_dir, 'contract_sessions.parquet')); print('done', len(res), len(contracts))


if __name__ == '__main__': main()
