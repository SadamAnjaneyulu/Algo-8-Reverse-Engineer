"""Settlement check for the real-log cycle totals: expiring positions settled at the 15:29 index bar (as before) vs at the official closing value
(last raw index close of the expiry day; equal to NSE's published close on all 126 NIFTY sessions checked). Output outputs/xs/settlement_check.csv."""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from collections import defaultdict
import bl_bt3_sim as S, bl_d0x_diag as DG
OUT = S.OUT
if __name__ == '__main__':
    O = DG.real_orders(); T = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv'); T = T[T.ok]; rows = []
    for r in T.itertuples():
        g = O[(O.und == r.und) & (O.expiry == r.expiry)]
        if not len(g[g.dayno == 0]) or not len(g[g.dayno == 1]): continue
        a = pd.read_pickle(f'{OUT}/bt3/{r.und}_{r.expiry}.pkl.gz'); b = pd.read_pickle(f'{OUT}/bt3x/{r.und}_{r.expiry}.pkl.gz'); unit = float(r.unit)
        pos = defaultdict(int); cash = 0.0
        for q in g.itertuples(): pos[(q.cp, int(q.strike))] += int(q.sg * q.lots); cash += -q.sg * q.px_avg * q.lots * unit
        val = lambda S0: cash + sum(n * (max(S0 - k, 0) if cp == 'CE' else max(k - S0, 0)) * unit for (cp, k), n in pos.items())
        s29, sl = float(a['spot0'].close.iloc[374]), float(b['spot_last0'])
        rows.append(dict(und=r.und, expiry=r.expiry, era='after' if r.d0 >= '2026-08-03' else 'before', s1529=s29, s_official=sl, open_lots_at_expiry=int(sum(abs(n) for n in pos.values())), total_1529=val(s29), total_official=val(sl)))
    X = pd.DataFrame(rows); X['diff'] = X.total_official - X.total_1529; X.to_csv(f'{OUT}/xs/settlement_check.csv', index=False)
    print(X.groupby('era').agg(n=('diff', 'size'), mean_diff=('diff', 'mean'), max_abs=('diff', lambda s: s.abs().max()), open_lots=('open_lots_at_expiry', 'mean')).round(0))
