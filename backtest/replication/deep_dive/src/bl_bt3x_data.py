"""Extended cache (reports/LATE_D1_RULE.md, step 2): same layout as bl_bt3_data.py, but a trading day on or after the closing auction session
(3 Aug 2026) keeps its minutes 15:30-15:39 (index j = 375..384; options trade until 15:40, the index is frozen at its close). Earlier days keep
375 minutes (their session ended 15:30), so pre-auction cycles are unchanged. Also stores spot_last1 / spot_last0 = the last raw index close of
the day (the official closing value; before the auction it differs from the 15:29 bar). Output outputs/bt3x/<UND>_<expiry>.pkl.gz (git-ignored)."""
import sys, os, warnings, time; sys.path.insert(0, '.'); sys.path.insert(0, '../..'); sys.path.insert(0, '../../..'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from multiprocessing import Pool
import data as D
OUT = os.path.join(os.path.dirname(os.path.abspath('.')), 'outputs'); BX = f'{OUT}/bt3x'; os.makedirs(BX, exist_ok=True); CAS = '2026-08-03'
MI = {f'{(555 + j) // 60:02d}:{(555 + j) % 60:02d}': j for j in range(385)}; S_ = None
def init():
    global S_; S_ = D.Src()
def spot_df(x, n):
    h = x.datetime.str.slice(11, 16).map(MI); x = x[h.notna() & (h < n)].assign(j=h[h.notna() & (h < n)].astype(int))
    return pd.DataFrame({'j': range(n)}).merge(x[['j', 'open', 'high', 'low', 'close']], on='j', how='left').ffill().bfill().astype('float64')
def opt_dict(x, n):
    h = x.datetime.str.slice(11, 16).map(MI); m = h.notna() & (h < n); x = x[m].assign(j=h[m].astype(int)); K = np.array(sorted(x.strike.unique()), float); ki = {k: i for i, k in enumerate(K)}; o = {'K': K}
    for cp in ('CE', 'PE'):
        z = x[x.right == cp]
        for col in ('open', 'high', 'low', 'close'):
            a = np.full((len(K), n), np.nan, dtype='float64'); a[z.strike.map(ki).values, z.j.values] = z[col].values; o[(cp, col)] = pd.DataFrame(a).T.ffill().T.values.astype('float64')
    return o
def build(args):
    und, expiry, d1, d0 = args; idx = und.lower(); r = dict(und=und, expiry=expiry, ok=False)
    try:
        out = dict(und=und, expiry=expiry, d1=d1, d0=d0)
        for tag, d in (('1', d1), ('0', d0)):
            n = 385 if d >= CAS else 375; sr = S_.csv(f'normalized/{idx}/underlying/spot/{d}.csv'); sr = sr.sort_values('datetime')
            out[f'spot{tag}'] = spot_df(sr, n); out[f'opt{tag}'] = opt_dict(S_.csv(f'normalized/{idx}/options/exp{expiry}_{d}.csv'), n); out[f'spot_last{tag}'] = float(sr.close.iloc[-1])
            r[f'n{tag}'] = n; r[f'last_bar{tag}'] = sr.datetime.iloc[-1][11:16]
        pd.to_pickle(out, f'{BX}/{und}_{expiry}.pkl.gz'); r['ok'] = True
    except Exception as e: r['why'] = str(e)[:120]
    return r
if __name__ == '__main__':
    T = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv'); T = T[T.ok]; t0 = time.time(); jobs = [(r.und, r.expiry, r.d1, r.d0) for r in T.itertuples()]
    with Pool(4, initializer=init) as p: res = list(p.imap_unordered(build, jobs, chunksize=2))
    R = pd.DataFrame(res); R.to_csv(f'{OUT}/bt3x_manifest.csv', index=False); print('built', int(R.ok.sum()), 'of', len(R), 'in', round(time.time() - t0), 's'); print(R.groupby(['n1', 'n0']).size())
