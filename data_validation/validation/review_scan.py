"""Second-pass checks added after the independent review: int32 wrap-around volumes of either sign, intraday outages (runs of minutes in which no contract trades although prices move or contracts are active),
truncated option sessions, closing-window spot vs futures deviation, raw atm_ref value. Usage: python3 -m validation.review_scan <commit> <out_dir>"""
import io, json, os, re, sys
from datetime import date
from multiprocessing import Pool
import numpy as np, pandas as pd
from .gitsrc import GitSource
CAS = date(2026, 8, 3); _G = None


def _init(c):
    global _G; _G = GitSource(c)


def one(a):
    idx, exp, day = a; D = date.fromisoformat(day); x = pd.read_csv(io.BytesIO(_G.read(f'normalized/{idx}/options/exp{exp}_{day}.csv')), usecols=['datetime', 'strike', 'right', 'close', 'volume', 'open_interest'])
    out = dict(index=idx, expiry=exp, day=day, wrap_neg=int((x.volume < 0).sum()), wrap_pos=int((x.volume > 2 ** 31).sum()))
    raw = _G.read(f'raw/{idx}/options/exp{exp}_{day}.json'); m = re.search(rb'"atm_ref":\s*(-?\d+)', raw[-400:] if b'"atm_ref"' in raw[-400:] else raw[:400]); out['raw_atm_ref'] = int(m.group(1)) if m else None
    if not len(x): return out, []
    reg_last = pd.Timestamp('15:39').time() if D >= CAS else pd.Timestamp('15:29').time(); t = pd.to_datetime(x.datetime); x['hm'] = t.dt.strftime('%H:%M'); reg = x[(t.dt.time >= pd.Timestamp('09:15').time()) & (t.dt.time <= reg_last)]
    out['first_option_minute'] = reg.hm.min() if len(reg) else None; out['last_option_minute'] = reg.hm.max() if len(reg) else None
    ok = reg[(reg.volume >= 0) & (reg.volume < 2 ** 31)]; v = ok.groupby('hm').volume.sum(); n = reg.groupby('hm').size(); grid = pd.date_range(f'{day} 09:15', f'{day} {reg_last.strftime("%H:%M")}', freq='min').strftime('%H:%M')
    v = v.reindex(grid).fillna(0); n = n.reindex(grid).fillna(0); zero = ((v == 0) & (n >= 20)).values   # many contracts have bars (carried prices) but nobody traded
    runs = []; i = 0
    while i < len(zero):
        if zero[i]:
            j = i
            while j < len(zero) and zero[j]: j += 1
            if j - i >= 10: runs.append((grid[i], grid[j - 1], j - i))
            i = j
        else: i += 1
    out['zero_volume_runs_ge10'] = json.dumps(runs); out['zero_volume_run_minutes'] = int(sum(r[2] for r in runs))
    missing = grid[(n == 0).values]; gaps = []; i = 0; mm = (n == 0).values
    while i < len(mm):
        if mm[i]:
            j = i
            while j < len(mm) and mm[j]: j += 1
            if j - i >= 10: gaps.append((grid[i], grid[j - 1], j - i))
            i = j
        else: i += 1
    out['no_option_data_runs_ge10'] = json.dumps(gaps); out['no_option_data_minutes'] = int(sum(g[2] for g in gaps))
    sp = pd.read_csv(io.BytesIO(_G.read(f'normalized/{idx}/underlying/spot/{day}.csv'))); fu = pd.read_csv(io.BytesIO(_G.read(f'normalized/{idx}/underlying/futures/{day}.csv')))
    sp['hm'] = sp.datetime.str.slice(11, 16); fu['hm'] = fu.datetime.str.slice(11, 16); s = sp.set_index('hm').close; f = fu.set_index('hm').close
    if '15:14' in s.index and '15:14' in f.index:
        b = f['15:14'] - s['15:14']
        for k in ('15:20', '15:25', '15:29'):
            if k in s.index and k in f.index: out[f'basis_dev_bp_{k}'] = float(((f[k] - s[k]) - b) / s['15:14'] * 1e4)
    return out, []


if __name__ == '__main__':
    commit, tab = sys.argv[1], sys.argv[2]; g = GitSource(commit); jobs = []
    for p in sorted(g.tree()):
        m = re.match(r'normalized/(nifty|sensex)/options/exp(\S{10})_(\S{10})\.csv', p)
        if m: jobs.append((m[1], m[2], m[3]))
    with Pool(4, initializer=_init, initargs=(commit,)) as pool: res = [o for o, _ in pool.imap(one, jobs, chunksize=2)]
    pd.DataFrame(res).to_csv(os.path.join(tab, 'review_scan_sessions.csv'), index=False); print('done', len(res))
