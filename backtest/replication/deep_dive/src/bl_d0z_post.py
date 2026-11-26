"""Post-hoc / gating checks for Part R (plan addendum): (1) placebo and forward for the PRE-REGISTERED roll-out set 'REF + sale clock' (the R-H1 set, not the best of four);
(2) POST-HOC class-specific clocks (learned share of other cycles with a roll-out / an 'other' buy-back in this minute +-1) on top of REF + sale clock + decayed/age. Output bl_d0z_post.csv"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
import bl_d0z_roll as Z
from multiprocessing import Pool
if __name__ == '__main__':
    Z.ARR['ck_roll'] = (Z.arrays('y_roll_out', True), 0); Z.ARR['ck_other'] = (Z.arrays('y_other_bb', True), 0); Z.CKN[:] = list(Z.ARR)
    Z.SETS['POST-HOC: REF + sale clock + decayed/age + class clocks'] = Z.SETS['REF + sale clock + decayed/age'] + ['ck_roll', 'ck_other']
    cids = Z.cids; ver = Z.B.groupby('cid').version.first(); exp_ = Z.B.groupby('cid').expiry.first(); fw_tr = []; fw_te = []
    for v in ver.unique(): cv = sorted([c for c in cids if ver[c] == v], key=lambda c: exp_[c]); n = int(np.ceil(len(cv) * 2 / 3)); fw_tr += cv[:n]; fw_te += cv[n:]
    Z.CKF.update({int(c): Z.clocks(set(cids) - {c}) for c in cids}); Z.CKF['fw'] = Z.clocks(set(fw_tr))
    todo = [('y_roll_out', 'REF + sale clock'), ('y_roll_out', 'POST-HOC: REF + sale clock + decayed/age + class clocks'), ('y_other_bb', 'REF + sale clock + decayed/age'), ('y_other_bb', 'POST-HOC: REF + sale clock + decayed/age + class clocks')]
    jobs = [(o, s, k, int(c)) for o, s in todo for k in ('loco', 'placebo') for c in cids] + [(o, s, 'forward', fw_te) for o, s in todo]
    with Pool(4) as pool: res = list(pool.imap_unordered(Z.task, jobs, chunksize=4))
    P = {}
    for (o, s, k, c), idx, p in res: P.setdefault((o, s, k), np.full(len(Z.B), np.nan))[idx] = p
    CID = Z.CID; rng = np.random.default_rng(3); idxc = {c: np.where(CID == c)[0] for c in cids}; rows = []; tm = np.isin(CID, fw_te)
    for o, s in todo:
        y = Z.B[o].values; p = P[(o, s, 'loco')]; bs = []
        for _ in range(300):
            ii = np.concatenate([idxc[c] for c in rng.choice(cids, len(cids))]); yy = y[ii]
            if 0 < yy.sum() < len(yy): bs.append(Z.auc(yy, p[ii]))
        wc = [Z.auc(y[idxc[c]], p[idxc[c]]) for c in cids if 0 < y[idxc[c]].sum() < len(idxc[c])]
        rows.append(dict(outcome=Z.OUTC[o], set=s, auc=Z.auc(y, p), lo=float(np.quantile(bs, .025)), hi=float(np.quantile(bs, .975)), forward=Z.auc(y[tm], P[(o, s, 'forward')][tm]), within_cycle=float(np.mean(wc)), placebo=Z.auc(y, P[(o, s, 'placebo')])))
    d = pd.DataFrame(rows); d['gate'] = np.where((d.auc >= 0.85) & (d.lo > 0.82) & (d.forward >= 0.80) & (d.placebo < 0.65), 'met', 'not met'); d.round(4).to_csv(f'{Z.OUT}/bl_d0z_post.csv', index=False); pd.set_option('display.width', 250); print(d.round(3).to_string())
