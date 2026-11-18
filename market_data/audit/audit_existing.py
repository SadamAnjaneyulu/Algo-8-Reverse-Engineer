"""Independent audit of the Breeze market data already in the project (read-only).
Usage: python3 audit_existing.py <normalized_dir> <out_dir> [UNDERLYING ...]
<normalized_dir> holds indices/<UND>/<date>.<hash>.csv and options/<UND>/<expiry>/<strike><CE|PE>/<trade_date>.<hash>.csv (branch data/local-breeze-fetch).
Nothing is assumed from earlier manifests: every figure is recomputed here. Writes existing_inventory.json and three CSVs."""
import glob, json, os, sys
import numpy as np, pandas as pd
ND, OUT = sys.argv[1], sys.argv[2]; UNDS = sys.argv[3:] or ['NIFTY']; os.makedirs(OUT, exist_ok=True)
STEP = {'NIFTY': 50, 'SENSEX': 100}; R = {}


def load(pattern, usecols=None):
    parts = []
    for f in sorted(glob.glob(pattern)):
        x = pd.read_csv(f, usecols=usecols); x['_file'] = os.path.relpath(f, ND); parts.append(x)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


for und in UNDS:
    r = R[und] = {}
    ix = load(os.path.join(ND, 'indices', und, '*.csv'))
    ix['ts'] = pd.to_datetime(ix.timestamp_ist.str.slice(0, 19)); ix['tz'] = ix.timestamp_ist.str.slice(19); ix['date'] = ix.ts.dt.date
    g = ix.groupby('date').agg(bars=('ts', 'size'), first=('ts', 'min'), last=('ts', 'max'), lo=('low', 'min'), hi=('high', 'max'), o=('open', 'first'), c=('close', 'last'))
    r['index'] = dict(rows=len(ix), sessions=len(g), first_date=str(g.index.min()), last_date=str(g.index.max()), tz_values=sorted(ix.tz.unique()), duplicates=int(ix.duplicated(['ts']).sum()),
                      nulls=int(ix[['open', 'high', 'low', 'close']].isna().sum().sum()), ohlc_inconsistent=int(((ix.high < ix[['open', 'close', 'low']].max(axis=1)) | (ix.low > ix[['open', 'close', 'high']].min(axis=1))).sum()),
                      provider_volume_nonzero=int((ix.provider_volume != 0).sum()), bars_per_session=g.bars.value_counts().sort_index().to_dict(), sessions_short_of_375=int((g.bars < 375).sum()),
                      missing_calendar_weekdays=[str(d.date()) for d in pd.bdate_range(g.index.min(), g.index.max()) if d.date() not in set(g.index)])
    g.reset_index().to_csv(os.path.join(OUT, f'{und}_index_sessions.csv'), index=False)
    op = load(os.path.join(ND, 'options', und, '*', '*', '*.csv'))
    op['ts'] = pd.to_datetime(op.timestamp_ist.str.slice(0, 19)); op['date'] = op.ts.dt.date; op['tz'] = op.timestamp_ist.str.slice(19)
    op['expiry'] = pd.to_datetime(op.expiry_date).dt.date
    cd = op.groupby(['expiry', 'strike', 'option_type', 'date']).agg(bars=('ts', 'size'), first=('ts', 'min'), last=('ts', 'max'), vol=('volume', 'sum'), oi_max=('open_interest', 'max'), oi_nonzero=('open_interest', lambda s: int((s != 0).sum()))).reset_index()
    sess = g[['o', 'c', 'lo', 'hi']].copy(); sess.index = pd.to_datetime(sess.index)
    cd['dte_days'] = (pd.to_datetime(cd.expiry) - pd.to_datetime(cd.date)).dt.days
    cd['spot_open'] = pd.to_datetime(cd.date).map(sess.o)
    cd['offset_steps'] = ((cd.strike - cd.spot_open) / STEP[und]).round(1)
    cd.to_csv(os.path.join(OUT, f'{und}_option_contract_days.csv'), index=False)
    key = ['ts', 'expiry', 'strike', 'option_type']
    r['options'] = dict(rows=len(op), contract_days=len(cd), distinct_contracts=int(cd.groupby(['expiry', 'strike', 'option_type']).ngroups), trade_date_first=str(op.date.min()), trade_date_last=str(op.date.max()),
                        trade_sessions=int(op.date.nunique()), expiries=[str(e) for e in sorted(op.expiry.unique())], n_expiries=int(op.expiry.nunique()), tz_values=sorted(op.tz.unique()),
                        duplicates=int(op.duplicated(key).sum()), nulls=int(op[['open', 'high', 'low', 'close', 'volume']].isna().sum().sum()),
                        ohlc_inconsistent=int(((op.high < op[['open', 'close', 'low']].max(axis=1)) | (op.low > op[['open', 'close', 'high']].min(axis=1))).sum()),
                        zero_price_rows=int((op[['open', 'high', 'low', 'close']] == 0).any(axis=1).sum()), zero_volume_rows=int((op.volume == 0).sum()),
                        open_interest=dict(rows_nonzero=int((op.open_interest != 0).sum()), share_nonzero=float((op.open_interest != 0).mean()), max=float(op.open_interest.max())),
                        bars_in_session_09_15_to_15_29=int(((op.ts.dt.time >= pd.Timestamp('09:15').time()) & (op.ts.dt.time <= pd.Timestamp('15:29').time())).sum()),
                        bars_after_15_29=int((op.ts.dt.time > pd.Timestamp('15:29').time()).sum()), dte_days_counts=cd.dte_days.value_counts().sort_index().to_dict(),
                        strike_step_ok_share=float((op.strike % STEP[und] == 0).mean()), tick_005_ok_share=float((((op.close * 20).round(6) % 1) == 0).mean()),
                        contract_days_by_bars=dict(full_375_or_more=int((cd.bars >= 375).sum()), between_300_374=int(((cd.bars >= 300) & (cd.bars < 375)).sum()), below_300=int((cd.bars < 300).sum())))
    # chain completeness per (expiry, date): how many strikes and how wide, against that day's index range
    per = cd.groupby(['expiry', 'date']).agg(strikes=('strike', 'nunique'), kmin=('strike', 'min'), kmax=('strike', 'max'), ce=('option_type', lambda s: int((s == 'CE').sum())), pe=('option_type', lambda s: int((s == 'PE').sum()))).reset_index()
    per['day_lo'] = pd.to_datetime(per.date).map(sess.lo); per['day_hi'] = pd.to_datetime(per.date).map(sess.hi); per['spot_open'] = pd.to_datetime(per.date).map(sess.o)
    per['band_covers_day_range'] = (per.kmin <= per.day_lo) & (per.kmax >= per.day_hi)
    per.to_csv(os.path.join(OUT, f'{und}_option_chain_coverage_by_day.csv'), index=False)
    r['options']['chain_coverage'] = dict(session_expiry_pairs=len(per), strikes_per_pair=per.strikes.describe().round(1).to_dict(), pairs_whose_strike_band_covers_the_days_index_range=int(per.band_covers_day_range.sum()),
                                           offset_steps_from_open_quantiles=cd.offset_steps.quantile([0, .01, .05, .25, .5, .75, .95, .99, 1]).round(1).to_dict())
    r['options']['expiry_weekdays'] = pd.Series([pd.Timestamp(e).day_name() for e in sorted(op.expiry.unique())]).value_counts().to_dict()
    both = op.pivot_table(index=['expiry', 'strike', 'ts'], columns='option_type', values='close', aggfunc='size')
    r['options']['ce_and_pe_same_minute_share_of_contract_minutes'] = float(both.notna().all(axis=1).mean())
    r['coverage_gap_vs_3y_target'] = dict(target_start='2023-10-23', target_end='2026-10-22', have_first=str(op.date.min()), have_last=str(op.date.max()), calendar_days_have=int((pd.Timestamp(str(op.date.max())) - pd.Timestamp(str(op.date.min()))).days) + 1, calendar_days_target=int((pd.Timestamp('2026-10-22') - pd.Timestamp('2023-10-23')).days) + 1)
R['futures'] = dict(found=False, note='No futures bar data exists in the normalized tree; searched indices/ and options/ only. See the repository-wide search in the report.')
json.dump(R, open(os.path.join(OUT, 'existing_inventory.json'), 'w'), indent=1, default=str); print(json.dumps({u: {k: v for k, v in R[u].items() if k != 'coverage_gap_vs_3y_target'} for u in UNDS}, indent=1, default=str)[:6000])
