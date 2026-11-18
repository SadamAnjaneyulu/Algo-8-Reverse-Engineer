"""Follow-up to sections 4/6: is the per-lot stop referenced to the NEWEST open lot's entry (LIFO) rather than the cheapest / average?
Per contract-minute hazard of an unscheduled buy-back (labels outside SCHEDULED and clock exits) by px/reference bins, D-1 vs D0, DEV+VAL only.
Also: stop-like exits vs the newest lot's age.  python3 analysis/exit_engine/newest_ref.py -> results/newest_ref_results.csv"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
import numpy as np, pandas as pd
from common import replay_book, RES, SCHEDULED
import bookstate
EXCL = SCHEDULED + ('8 clock-B rebalance', '6 clock-based exit (clock B, no replacement)', '8b grid rebalance (A/:00 clock)')
CM, BM = bookstate.load(); CM = CM[CM.split != 'TEST'].copy()
out = []
for conv in ('cheap', 'lifo'):
    Lt = replay_book(conv); sh = Lt[Lt.sgn < 0]
    newest = {}
    for (u, e, cp, k), g in sh.groupby(['und', 'expiry', 'cp', 'strike']):
        ent = g.entry_mi.values; ex = g.exit_mi.values; px = g.entry_px.values
        newest[(u, e, cp, k)] = (ent, ex, px)
    def e_new(r):
        ent, ex, px = newest[(r.und, r.expiry, r.cp, r.strike)]; ok = (ent < r.mi) & (ex >= r.mi)
        if not ok.any(): return np.nan
        j = np.where(ok)[0]; j = j[np.argmax(ent[j])]; return px[j]
    CM['e_new'] = [e_new(r) for r in CM.itertuples()]
    CM['r_new'] = CM.px / CM.e_new
    CM['y'] = (CM.closed > 0) & ~CM.close_label.isin(EXCL)
    for ref in ('r_cheap', 'r_avg', 'r_new'):
        for d, g in CM.groupby('day'):
            for b, z in g.groupby(pd.cut(g[ref], [0, 1, 1.3, 1.45, 1.55, 1.7, 2, 3, 100]), observed=True):
                out.append(dict(convention=conv, reference=ref, day='D-1' if d == 0 else 'D0', bin=str(b), n=len(z), hazard=z.y.mean()))
R = pd.DataFrame(out); R.to_csv(os.path.join(RES, 'newest_ref_results.csv'), index=False)
pd.set_option('display.width', 250)
print(R.pivot_table(index=['convention', 'reference', 'day'], columns='bin', values='hazard').round(3).to_string())
