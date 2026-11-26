"""Phase A G1b (Addendum 1 of reports/PHASE_A_G1_G6_PLAN.md, written before this ran): candle-end close breakout at 15:30 vs the closing pair bursts. Output outputs/phaseA/g1b.json, g1b_table.csv"""
import sys, os, json, warnings; sys.path.insert(0, '.'); sys.path.insert(0, '../..'); sys.path.insert(0, '../../..'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from scipy.stats import fisher_exact
import bl_bt3_sim as S
OUT = S.OUT; PA = f'{OUT}/phaseA'; CAS = '2026-08-03'; OUTLIER = ('NIFTY', '2026-10-16')
def run():
    B = pd.read_csv(f'{PA}/g1_bursts.csv'); Tc = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv'); Tc = Tc[Tc.ok]; Bk = pd.read_csv(f'{OUT}/d0x/book_compare.csv'); keep = set(zip(Bk.und, Bk.expiry)); rows = []
    for r in Tc.itertuples():
        if (r.und, r.expiry) not in keep or (r.und, r.d1) == OUTLIER: continue
        post = r.d0 >= CAS; p = f'{OUT}/{"bt3u" if post else "bt3x"}/{r.und}_{r.expiry}.pkl.gz'
        if not os.path.exists(p): continue
        x = pd.read_pickle(p)['spot1']; h, l, c = (x[k].values.astype(float) for k in ('high', 'low', 'close'))
        if len(c) < 375: continue
        a1, e1 = 285, 315; a2, e2 = 315, 345                        # 14:00-14:30 and 14:30-15:00 (minute index from 09:15: 14:00 = 285)
        top = max(h[a1:e1].max(), h[a2:e2].max()); bot = min(l[a1:e1].min(), l[a2:e2].min()); cl = c[374]; up = cl > top; dn = cl < bot
        cyc = f'{r.und}|{r.d1}'; burst = B[(B.cyc == cyc) & (B.j0 >= 368)]; rows.append(dict(cyc=cyc, post=post, cond=bool(up or dn), side='up' if up else ('down' if dn else ''), burst=int(len(burst) > 0), close=cl, top=top, bottom=bot))
    T = pd.DataFrame(rows); T.to_csv(f'{PA}/g1b_table.csv', index=False)
    a = int((T.cond & (T.burst == 1)).sum()); b = int((T.cond & (T.burst == 0)).sum()); c_ = int((~T.cond & (T.burst == 1)).sum()); d = int((~T.cond & (T.burst == 0)).sum()); odds, p = fisher_exact([[a, b], [c_, d]], alternative='greater')
    res = dict(cycles=len(T), burst_cycles=int(T.burst.sum()), condition_holds=int(T.cond.sum()), table=dict(cond_burst=a, cond_noburst=b, nocond_burst=c_, nocond_noburst=d), burst_cycles_with_condition=a, fisher_p_one_sided=float(p), odds_ratio=float(odds), success_rule='condition holds in >= 5 of the burst cycles and Fisher p <= 0.05', supported=bool(a >= 5 and p <= 0.05))
    json.dump(res, open(f'{PA}/g1b.json', 'w'), indent=1, default=float); print(json.dumps(res, indent=1)); print(T[T.burst == 1].round(1).to_string(index=False))
if __name__ == '__main__': run()
