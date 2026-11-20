"""Buy-back (close) triggers per contract (plan D): univariate AUC (cluster bootstrap), hazard curves, LOCO incremental value over the premium-move baseline with permutation nulls, and a flexible-model importance. D-1 and D0."""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from joblib import Parallel, delayed
P = pd.read_csv(f'{OUT}/bl_close_panel.csv.gz'); rng = np.random.default_rng(0)
FE = ['ratio', 'loss_inr_lot', 'abs_delta', 'itm_steps', 'abs_steps', 'spot_move_adv', 'hold_min', 'gamma', 'lots', 'book_nd', 'price', 'j']
def auc(x, y): m = ~np.isnan(x); x, y = x[m], y[m]; n1 = y.sum(); n0 = len(y) - n1; r = stats.rankdata(x); return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
def prep(Q, cols): X = Q[cols].copy(); X = X.fillna(X.median()); X = (X - X.mean()) / X.std().replace(0, 1); return X.values
def fold(X, y, g, c, kind):
    tr = g != c; m = LogisticRegression(C=1.0, max_iter=300).fit(X[tr], y[tr]) if kind == 'lr' else HistGradientBoostingClassifier(max_depth=3, max_iter=150, learning_rate=0.06, min_samples_leaf=60, random_state=0).fit(X[tr], y[tr]); return np.where(~tr)[0], m.predict_proba(X[~tr])[:, 1]
def loco(X, y, g, kind='lr'):
    o = np.zeros(len(y))
    for i, p in Parallel(n_jobs=4)(delayed(fold)(X, y, g, c, kind) for c in np.unique(g)): o[i] = p
    return o
BINS = {'ratio': [0, .4, .6, .8, 1.0, 1.2, 1.4, 1.55, 1.7, 2.0, 3, 20], 'abs_delta': [0, .2, .35, .5, .6, .7, .8, 1.01], 'itm_steps': [-100, -3, -1.5, -.5, .5, 1.5, 3, 100], 'loss_inr_lot': [-1e5, -3000, -1000, 0, 1000, 3000, 1e5], 'spot_move_adv': [-10, -.5, -.2, 0, .2, .5, 10], 'hold_min': [-1, 30, 60, 120, 180, 240, 400], 'j': [0, 60, 120, 180, 240, 300, 375]}
U = []; HZ = []; INC = []
for day in ('D-1', 'D0'):
    Q = P[P.day == day].reset_index(drop=True); y = Q.event.values; g = (Q.und + Q.expiry).values; ucy = np.unique(g); idx = {c: np.where(g == c)[0] for c in ucy}; base = y.mean(); print(f'\n== {day}: rows {len(Q):,}, buy-back contract-minutes {int(y.sum())}, base rate {base * 1000:.1f} per 1000')
    for f in FE:
        x = Q[f].values.astype(float); a = auc(x, y); bs = [auc(x[ii], y[ii]) for ii in (np.concatenate([idx[c] for c in rng.choice(ucy, len(ucy))]) for _ in range(150))]; U.append((day, f, a, np.quantile(bs, .025), np.quantile(bs, .975)))
    for f, b in BINS.items():
        t = Q.groupby(pd.cut(Q[f], b)).event.agg(['size', 'sum']); t['rate_per_1000'] = (t['sum'] / t['size'] * 1000).round(1); t['lift'] = (t['sum'] / t['size'] / base).round(2); t = t.reset_index().rename(columns={f: 'bin'}); t.insert(0, 'feature', f); t.insert(0, 'day', day); HZ.append(t)
    print('single-variable AUC:', {u[1]: round(u[2], 3) for u in U if u[0] == day})
    pb = loco(prep(Q, ['ratio']), y, g); ab = roc_auc_score(y, pb); print(f'baseline (price/entry only) LOCO AUC {ab:.3f}')
    for f in [c for c in FE if c != 'ratio']:
        p1 = loco(prep(Q, ['ratio', f]), y, g); a1 = roc_auc_score(y, p1); nul = []
        for _ in range(3): Qp = Q.copy(); Qp[f] = Qp.groupby(g)[f].transform(lambda s: rng.permutation(s.values)); nul.append(roc_auc_score(y, loco(prep(Qp, ['ratio', f]), y, g)) - ab)
        INC.append((day, f, a1 - ab, np.median(nul), max(nul)))
    allf = loco(prep(Q, FE), y, g, 'gb'); print(f'flexible model with all variables LOCO AUC {roc_auc_score(y, allf):.3f}')
    INC.append((day, '[all variables, GB]', roc_auc_score(y, allf) - ab, np.nan, np.nan))
    print(pd.DataFrame([i for i in INC if i[0] == day], columns=['day', 'feature', 'gain', 'perm_median', 'perm_max']).round(4).sort_values('gain', ascending=False).head(8).to_string(index=False))
pd.DataFrame(U, columns=['day', 'feature', 'AUC', 'lo', 'hi']).round(4).to_csv(f'{OUT}/bl_close_univariate.csv', index=False); pd.concat(HZ).assign(bin=lambda d: d.bin.astype(str)).to_csv(f'{OUT}/bl_close_hazard.csv', index=False); pd.DataFrame(INC, columns=['day', 'feature', 'AUC_gain', 'perm_null_median', 'perm_null_max']).round(4).to_csv(f'{OUT}/bl_close_incremental.csv', index=False)
H = pd.concat(HZ).assign(bin=lambda d: d.bin.astype(str))
for day in ('D-1', 'D0'):
    for f in ('ratio', 'abs_delta', 'itm_steps', 'loss_inr_lot', 'hold_min'): print('\n', day, f); print(H[(H.day == day) & (H.feature == f)][['bin', 'size', 'sum', 'rate_per_1000', 'lift']].to_string(index=False))
