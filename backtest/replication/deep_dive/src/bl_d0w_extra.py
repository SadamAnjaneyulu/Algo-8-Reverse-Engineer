"""Post-hoc checks (labelled in the report addendum): (1) long buys after the opening minutes only (j >= 5); (2) long sells with the placebo of the same set. Output bl_d0w_extra.csv"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
import bl_d0w_long as Z
from multiprocessing import Pool
B2 = Z.B[Z.B.j >= 5].reset_index(drop=True); B2['y_long_buy_intra'] = ((B2.long_buy_lots > 0)).astype(float); CID2 = B2.cid.values; cids = np.unique(CID2)
def fit(a):
    out, sname, c, plc = a; X = B2[Z.SETS[sname]].values.astype(float); y = B2[out].values.copy(); te = CID2 == c
    if plc:
        rng = np.random.default_rng(int(c) + 1)
        for cc in cids: m = np.where(CID2 == cc)[0]; y[m] = rng.permutation(y[m])
    m = Z.mk(); m.fit(X[~te], y[~te]); return (out, sname, plc), np.where(te)[0], m.predict_proba(X[te])[:, 1]
if __name__ == '__main__':
    jobs = [(o, s, int(c), p) for o in ('y_long_buy_intra', 'y_long_sell') for s in ('E existing families', 'E + book + state of held longs') for c in cids for p in (False, True)]
    with Pool(4) as pool: res = list(pool.imap_unordered(fit, jobs, chunksize=4))
    P = {}
    for k, idx, p in res: P.setdefault(k, np.full(len(B2), np.nan))[idx] = p
    rng = np.random.default_rng(3); idxc = {c: np.where(CID2 == c)[0] for c in cids}; rows = []
    for (o, s, plc), p in P.items():
        if plc: continue
        y = B2[o].values; a = Z.auc(y, p); bs = []
        for _ in range(300):
            ii = np.concatenate([idxc[c] for c in rng.choice(cids, len(cids))]); yy = y[ii]
            if 0 < yy.sum() < len(yy): bs.append(Z.auc(yy, p[ii]))
        rows.append(dict(outcome=o, set=s, auc=a, lo=float(np.quantile(bs, .025)), hi=float(np.quantile(bs, .975)), placebo_auc=Z.auc(y, P[(o, s, True)]), positives=int(y.sum()), cells=len(y)))
    pd.DataFrame(rows).round(4).to_csv(f'{Z.OUT}/bl_d0w_extra.csv', index=False); print(pd.DataFrame(rows).round(3).to_string())
