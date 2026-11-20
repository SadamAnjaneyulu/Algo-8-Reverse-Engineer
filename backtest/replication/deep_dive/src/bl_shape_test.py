"""LOCO test of the shape variables (non-slot minutes): univariate AUC, incremental gain over the baseline (fav30, own_ratio, other_ratio), permutation null, and the hour-of-day profile."""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, log_loss
from joblib import Parallel, delayed
F = pd.read_csv(f'{OUT}/bl_shape_panel.csv'); F = F[F.tslot != 0].reset_index(drop=True); rng = np.random.default_rng(0)
BASE = ['fav30', 'own_ratio', 'other_ratio']; NEW = ['dev_pair', 'dev_pair_pct', 'dev_slotref', 'bk15', 'bk30', 'bk60', 'tsext30', 'persist15', 'accel', 'fav5', 'fav15', 'fav60', 'mins']
def prep(Q, cols): X = Q[cols].copy(); X = X.fillna(X.median()); X = (X - X.mean()) / X.std().replace(0, 1); return X.values
def fold(X, y, g, c): tr = g != c; m = LogisticRegression(C=1.0, max_iter=300).fit(X[tr], y[tr]); return np.where(~tr)[0], m.predict_proba(X[~tr])[:, 1]
def loco(X, y, g):
    o = np.zeros(len(y))
    for i, p in Parallel(n_jobs=4)(delayed(fold)(X, y, g, c) for c in np.unique(g)): o[i] = p
    return o
def boot(p1, p0, y, g, n=150):
    ucy = np.unique(g); idx = {c: np.where(g == c)[0] for c in ucy}; d = []
    for _ in range(n): ii = np.concatenate([idx[c] for c in rng.choice(ucy, len(ucy))]); d.append(roc_auc_score(y[ii], p1[ii]) - roc_auc_score(y[ii], p0[ii]))
    return np.quantile(d, .025), np.quantile(d, .975)
rows = []
for day in ('D-1', 'D0'):
    Q = F[F.day == day].reset_index(drop=True); y = Q.ep.values; g = (Q.und + Q.expiry).values; pb = loco(prep(Q, BASE), y, g); ab = roc_auc_score(y, pb); print(f'\n== {day} baseline LOCO AUC {ab:.3f}')
    for f in NEW:
        cols = BASE + [f] if f not in BASE else BASE; p1 = loco(prep(Q, cols), y, g); a1 = roc_auc_score(y, p1); lo, hi = boot(p1, pb, y, g)
        nul = []
        for _ in range(4): Qp = Q.copy(); Qp[f] = Qp.groupby([Qp.und + Qp.expiry, Qp.cp])[f].transform(lambda s: rng.permutation(s.values)); nul.append(roc_auc_score(y, loco(prep(Qp, BASE + [f]), y, g)) - ab)
        ua = roc_auc_score(y[~Q[f].isna()], Q[f].dropna()); rows.append((day, f, ua, a1 - ab, lo, hi, np.median(nul), max(nul)))
    for nm, cols in (('baseline + all shape', BASE + ['dev_pair', 'dev_slotref', 'bk15', 'bk60', 'tsext30', 'persist15', 'accel', 'fav5', 'fav15', 'fav60']), ('baseline + all shape + mins', BASE + ['dev_pair', 'dev_slotref', 'bk15', 'bk60', 'tsext30', 'persist15', 'accel', 'fav5', 'fav15', 'fav60', 'mins']), ('baseline + multi-horizon moves + mins', BASE + ['fav5', 'fav15', 'fav60', 'mins']), ('baseline + mins', BASE + ['mins'])):
        p1 = loco(prep(Q, cols), y, g); a1 = roc_auc_score(y, p1); lo, hi = boot(p1, pb, y, g); rows.append((day, f'[{nm}]', np.nan, a1 - ab, lo, hi, np.nan, np.nan)); print(f'{nm}: AUC {a1:.3f} (gain {a1 - ab:+.3f}, {lo:+.3f}..{hi:+.3f})')
    Q['hour'] = (9 * 60 + 15 + Q.j) // 60; t = Q.groupby('hour').ep.agg(['size', 'sum']); t['rate_per_1000'] = (t['sum'] / t['size'] * 1000).round(1); print('episode-start rate by hour:', t.rate_per_1000.to_dict()); t.to_csv(f'{OUT}/bl_shape_hour_{day}.csv')
R = pd.DataFrame(rows, columns=['day', 'feature', 'univariate_AUC', 'AUC_gain', 'lo', 'hi', 'perm_null_median', 'perm_null_max']).round(4); R.to_csv(f'{OUT}/bl_shape_results.csv', index=False)
for day in ('D-1', 'D0'): print('\n', day); print(R[R.day == day].drop(columns='day').to_string(index=False))
