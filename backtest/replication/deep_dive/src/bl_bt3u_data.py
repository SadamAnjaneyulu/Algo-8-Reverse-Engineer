"""Futures-based underlying during the closing auction (reports/D1_CLOSING_TIME.md): copy of outputs/bt3x where, on post-auction sessions only,
minutes j >= 360 (15:15 onwards) of the index bars are replaced by the near-month index future's OHLC minus its median basis to the index over
15:00-15:14 (real highs and lows, it trades to 15:40). Only post-auction cycles are written (the only ones scored). No fitted parameter.
Output outputs/bt3u/ (git-ignored), outputs/bt3u_basis.csv."""
import sys, os, warnings; sys.path.insert(0, '../..'); sys.path.insert(0, '../../..'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
import data as D
OUT = '../outputs'; CAS = '2026-08-03'; os.makedirs(f'{OUT}/bt3u', exist_ok=True)
MI = {f'{(555 + j) // 60:02d}:{(555 + j) % 60:02d}': j for j in range(385)}
if __name__ == '__main__':
    S_ = D.Src(); T = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv'); T = T[T.ok & (T.d0 >= CAS)]; rows = []
    for r in T.itertuples():
        c = pd.read_pickle(f'{OUT}/bt3x/{r.und}_{r.expiry}.pkl.gz'); cu = dict(c)
        for t, d in (('1', r.d1), ('0', r.d0)):
            if d < CAS: continue
            f = S_.csv(f'normalized/{r.und.lower()}/underlying/futures/{d}.csv'); f = f[f.expiry_date == sorted(f.expiry_date.unique(), key=lambda x: pd.to_datetime(x))[0]]
            j = f.datetime.str.slice(11, 16).map(MI); f = f[j.notna()].assign(j=j[j.notna()].astype(int)).drop_duplicates('j').set_index('j').reindex(range(385)).ffill()
            s = c[f'spot{t}']; n = len(s); basis = float(np.nanmedian(f.close.values[345:360] - s.close.values[345:360])); su = s.copy()
            for col in ('open', 'high', 'low', 'close'): su.loc[360:, col] = f[col].values[360:n] - basis
            cu[f'spot{t}'] = su; rows.append(dict(und=r.und, expiry=r.expiry, day=t, basis=basis, fut_range=float(f.high.values[360:n].max() - f.low.values[360:n].min())))
        pd.to_pickle(cu, f'{OUT}/bt3u/{r.und}_{r.expiry}.pkl.gz')
    B = pd.DataFrame(rows); B.to_csv(f'{OUT}/bt3u_basis.csv', index=False); print(B.groupby('und')[['basis', 'fut_range']].median().round(1)); print('cycles', len(T))
