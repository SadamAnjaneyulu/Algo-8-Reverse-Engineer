"""What carries the D0 selling AUC: leave-one-cycle-out with (a) market, book and past buy-backs only, (b) the learned clock features and the time position only, against all causal features (bl_d0f_auc.py). Outputs bl_d0f_abl.csv, bl_summary_d0f2.json"""
import sys, os; os.environ['OMP_NUM_THREADS'] = '1'; sys.path.insert(0, '.')
from bl_d0f_auc import *
TIME = ['hour', 'min_in_15', 'min_in_5', 'j', 'is_ce', 'und_nifty', 'v2']
def fp(task):
    tr, te, cfg = task; trn = np.isin(CIDS, tr); ten = np.isin(CIDS, te); ref = np.array([c in set(tr) for c in cycles]); F = clock_features(ref); res = {}
    cols_m = [c for c in BASEC if c not in TIME[:0]]; Xm = PN[cols_m].values.astype(float)
    if cfg == 'market, book and past buy-backs only (no clock features)': X = Xm
    elif cfg == 'learned clock features + time position only': X = np.hstack([PN[TIME].values.astype(float), F.values])
    for o in OUTC:
        y = Y[o]
        res[o] = (np.where(ten)[0], np.full(ten.sum(), np.nan) if y[trn].sum() < 5 else mk().fit(X[trn], y[trn]).predict_proba(X[ten])[:, 1])
    return res
if __name__ == '__main__':
    order = PN.groupby('cid').expiry.first().sort_values(); allc = list(order.index); pool = Pool(4); rows = []
    for cfg in ('market, book and past buy-backs only (no clock features)', 'learned clock features + time position only'):
        P = collect(pool.map(fp, [([c for c in allc if c != h], [h], cfg) for h in allc]))
        for o in OUTC:
            a = boot_auc(np.arange(len(PN)), P[o], Y[o], nb=50); rows.append(dict(model=cfg, outcome=POS[o], cells=int(Y[o].sum()), auc=a[0], within_cycle_auc=a[4]))
    A = pd.DataFrame(rows); A.round(4).to_csv(f'{OUT}/bl_d0f_abl.csv', index=False); print(A.pivot(index='outcome', columns='model', values='auc').round(3).to_string())
