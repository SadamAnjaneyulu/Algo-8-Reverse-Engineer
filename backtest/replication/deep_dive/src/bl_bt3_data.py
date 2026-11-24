"""3-year backtest, phase 0 (plan reports/BACKTEST3Y_PLAN.md): full option-chain minute arrays for D-1 and D0 of every Complete cycle, from the pinned dataset commit.
Same layout as the live-cycle builder (bl_d0_data.py): index j = minute 09:15 + j (375 minutes), spot DataFrame j/open/high/low/close, options {'K', (cp, field): K x 375 float32} with forward fill.
Units: gcd-of-volume lot from backtest/cache (value 1 = artefact -> neighbouring session's unit). Output outputs/bt3/<UND>_<expiry>.pkl.gz (git-ignored) and outputs/bl_bt3_cycles.csv (cycle table)."""
import sys, os, json, warnings, time; sys.path.insert(0, '.'); sys.path.insert(0, '../..'); sys.path.insert(0, '../../..'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from multiprocessing import Pool
import data as D
from bt.cycles import cycle_list
OUT = os.path.join(os.path.dirname(os.path.abspath('.')), 'outputs'); BT3 = f'{OUT}/bt3'; os.makedirs(BT3, exist_ok=True); CACHE = '/home/user/Algo-8-Reverse-Engineer/backtest/cache'
S_ = None
def init():
    global S_; S_ = D.Src()
def spot_df(x):
    h = x.datetime.str.slice(11, 16).map(D.MI); x = x[h.notna()].assign(j=h[h.notna()].astype(int)); return pd.DataFrame({'j': range(375)}).merge(x[['j', 'open', 'high', 'low', 'close']], on='j', how='left').ffill().bfill().astype('float32')
def opt_dict(x):
    h = x.datetime.str.slice(11, 16).map(D.MI); x = x[h.notna()].assign(j=h[h.notna()].astype(int)); K = np.array(sorted(x.strike.unique()), float); ki = {k: i for i, k in enumerate(K)}; o = {'K': K}
    for cp in ('CE', 'PE'):
        z = x[x.right == cp]
        for col in ('open', 'high', 'low', 'close'):
            a = np.full((len(K), 375), np.nan, dtype='float32'); a[z.strike.map(ki).values, z.j.values] = z[col].values; o[(cp, col)] = pd.DataFrame(a).T.ffill().T.values.astype('float32')
    return o
def build(args):
    und, expiry, d1, d0 = args; idx = und.lower(); r = dict(und=und, expiry=expiry, d1=d1, d0=d0, ok=False, why='')
    try:
        s1 = spot_df(S_.csv(f'normalized/{idx}/underlying/spot/{d1}.csv')); s0 = spot_df(S_.csv(f'normalized/{idx}/underlying/spot/{d0}.csv'))
        f1 = S_.csv(f'normalized/{idx}/options/exp{expiry}_{d1}.csv'); f0 = S_.csv(f'normalized/{idx}/options/exp{expiry}_{d0}.csv'); o1 = opt_dict(f1); o0 = opt_dict(f0)
        miss = lambda o: float(np.mean(~np.isfinite(o[('CE', 'close')])))
        pd.to_pickle(dict(und=und, expiry=expiry, d1=d1, d0=d0, spot1=s1, spot0=s0, opt1=o1, opt0=o0), f'{BT3}/{und}_{expiry}.pkl.gz'); r.update(ok=True, n_strikes_d1=len(o1['K']), n_strikes_d0=len(o0['K']), nan_share_d1=miss(o1), nan_share_d0=miss(o0), spot_open_d1=float(s1.open.iloc[0]), spot_open_d0=float(s0.open.iloc[0]))
    except Exception as e: r['why'] = str(e)[:120]
    return r
if __name__ == '__main__':
    C = cycle_list(); C = C[C.status == 'Complete'].reset_index(drop=True); t0 = time.time(); jobs = [(r.und, r.expiry, r.d1, r.d0) for r in C.itertuples()]
    with Pool(4, initializer=init) as p: res = list(p.imap_unordered(build, jobs, chunksize=2))
    R = pd.DataFrame(res); T = C.merge(R, on=['und', 'expiry', 'd1', 'd0'])
    # units from the earlier cache (gcd of volumes); 1 is an artefact
    lots = {}
    for f in os.listdir(CACHE):
        if f.endswith('.pkl'): d = pd.read_pickle(f'{CACHE}/{f}'); lots[(d['und'], d['expiry'])] = (d.get('lot_d1'), d.get('lot_d0'))
    T['lot_d1'] = [lots.get((u, e), (np.nan, np.nan))[0] for u, e in zip(T.und, T.expiry)]; T['lot_d0'] = [lots.get((u, e), (np.nan, np.nan))[1] for u, e in zip(T.und, T.expiry)]
    T = T.sort_values(['und', 'expiry']).reset_index(drop=True)
    for col in ('lot_d1', 'lot_d0'): T.loc[T[col] <= 1, col] = np.nan
    for u in T.und.unique():
        m = T.und == u; T.loc[m, 'unit'] = T.loc[m, 'lot_d0'].fillna(T.loc[m, 'lot_d1']); T.loc[m, 'unit'] = T.loc[m, 'unit'].ffill().bfill()
    T.to_csv(f'{OUT}/bl_bt3_cycles.csv', index=False); print('built', int(T.ok.sum()), 'of', len(T), 'in', round(time.time() - t0), 's'); print(T[~T.ok][['und', 'expiry', 'why']].head(10).to_string()); print(T.groupby(['und', 'unit']).expiry.agg(['min', 'max', 'size']).to_string()); print(T.groupby('subset').size().to_dict())
