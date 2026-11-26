"""Placebo (labels shuffled within each cycle) for the BEST feature set of every buy-back outcome, so the gate compares like with like (plan reports/D0_BURST_LONG_PLAN.md). Output bl_d0w_burst_placebo.csv"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
import bl_d0w_burst as Z
from multiprocessing import Pool
if __name__ == '__main__':
    G = pd.read_csv(f'{Z.OUT}/bl_d0w_burst_gate.csv'); inv = {v: k for k, v in Z.OUTC.items()}; jobs = [(inv[r.outcome], r.best_set, 'placebo', int(c)) for r in G.itertuples() for c in Z.cids]
    with Pool(4) as pool: res = list(pool.imap_unordered(Z.task, jobs, chunksize=4))
    P = {}
    for (o, s, k, c), idx, p in res: P.setdefault((o, s), np.full(len(Z.B), np.nan))[idx] = p
    out = [dict(outcome=Z.OUTC[o], best_set=s, placebo_auc=Z.auc(Z.B[o].values, p)) for (o, s), p in P.items()]; pd.DataFrame(out).round(4).to_csv(f'{Z.OUT}/bl_d0w_burst_placebo.csv', index=False); print(pd.DataFrame(out).round(3).to_string())
