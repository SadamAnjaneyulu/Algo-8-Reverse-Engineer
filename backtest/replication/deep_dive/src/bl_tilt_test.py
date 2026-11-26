"""Tilt-gap hypothesis: the CE/PE composition of the short book tracks the cumulative market move; a solo sale fires when the own side is under-weighted relative to that target.
tilt = (S_own - S_other)/(S_own + S_other). Target tilt = LOCO fit of tilt on the favourable move (fav_open, or dd_ext, or fav60) with a flexible (binned-mean) curve estimated on training cycles only. gap = target - actual (+ = own side under-weighted). Slot minutes dropped (design leak). Outputs outputs/bl_tilt_results.csv"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, log_loss
from sklearn.isotonic import IsotonicRegression
from joblib import Parallel, delayed
F = pd.read_csv(f'{OUT}/bl_feat_panel.csv'); F = F[F.tslot != 0].reset_index(drop=True); F['tilt'] = (F.S_own - F.S_other) / (F.S_own + F.S_other); rng = np.random.default_rng(0)
BASE = ['fav30', 'own_ratio', 'other_ratio']
def prep(Q, cols): X = Q[cols].copy(); X = X.fillna(X.median()); X = (X - X.mean()) / X.std().replace(0, 1); return X.values
def fold(X, y, g, c):
    tr = g != c; m = LogisticRegression(C=1.0, max_iter=300).fit(X[tr], y[tr]); return np.where(~tr)[0], m.predict_proba(X[~tr])[:, 1]
def loco(X, y, g):
    o = np.zeros(len(y)); 
    for i, p in Parallel(n_jobs=4)(delayed(fold)(X, y, g, c) for c in np.unique(g)): o[i] = p
    return o
def loco_gap(Q, mv, g):
    out = np.full(len(Q), np.nan)
    for c in np.unique(g):
        tr = (g != c) & (Q.ep.values == 0); te = g == c; iso = IsotonicRegression(out_of_bounds='clip').fit(Q.loc[tr, mv].values, Q.loc[tr, 'tilt'].values); out[te] = iso.predict(Q.loc[te, mv].values) - Q.loc[te, 'tilt'].values
    return out
def boot(p1, p0, y, g, n=150):
    ucy = np.unique(g); idx = {c: np.where(g == c)[0] for c in ucy}; d = []
    for _ in range(n): ii = np.concatenate([idx[c] for c in rng.choice(ucy, len(ucy))]); d.append(roc_auc_score(y[ii], p1[ii]) - roc_auc_score(y[ii], p0[ii]))
    return np.quantile(d, .025), np.quantile(d, .975)
rows = []
for day, Q in F.groupby('day'):
    Q = Q.reset_index(drop=True); y = Q.ep.values; g = (Q.und + Q.expiry).values; pb = loco(prep(Q, BASE), y, g); ab = roc_auc_score(y, pb); print(f'\n== {day}: baseline LOCO AUC {ab:.3f}')
    for mv in ('fav_open', 'dd_ext', 'fav60', 'fav30'):
        Q['gap_' + mv] = loco_gap(Q, mv, g); x = Q['gap_' + mv].values; a = roc_auc_score(y, x)
        p1 = loco(prep(Q, BASE + ['gap_' + mv]), y, g); a1 = roc_auc_score(y, p1); lo, hi = boot(p1, pb, y, g); rows.append((day, mv, 'tilt gap alone AUC', a, np.nan, np.nan)); rows.append((day, mv, 'baseline + tilt gap: AUC gain', a1 - ab, lo, hi)); print(f'target = f({mv}): tilt-gap alone AUC {a:.3f} | baseline + gap AUC {a1:.3f} (gain {a1 - ab:+.3f}, CI {lo:+.3f}..{hi:+.3f})')
    for nm, cols in (('S_own+S_other (inventory only)', BASE + ['S_own', 'S_other']), ('tilt', BASE + ['tilt']), ('tilt + fav_open', BASE + ['tilt', 'fav_open']), ('tilt gap(fav_open) + tilt + fav_open', BASE + ['gap_fav_open', 'tilt', 'fav_open'])):
        p1 = loco(prep(Q, cols), y, g); a1 = roc_auc_score(y, p1); lo, hi = boot(p1, pb, y, g); rows.append((day, nm, 'baseline + ...: AUC gain', a1 - ab, lo, hi)); print(f'baseline + {nm}: AUC {a1:.3f} (gain {a1 - ab:+.3f}, CI {lo:+.3f}..{hi:+.3f})')
    # permutation null for the best gap definition
    nul = []
    for _ in range(4):
        Qp = Q.copy(); Qp['gap_fav_open'] = Qp.groupby([Qp.und + Qp.expiry, Qp.cp]).gap_fav_open.transform(lambda s: rng.permutation(s.values)); nul.append(roc_auc_score(y, loco(prep(Qp, BASE + ['gap_fav_open']), y, g)) - ab)
    print('permutation null gain for gap_fav_open: median %.4f max %.4f' % (np.median(nul), max(nul))); rows.append((day, 'gap_fav_open permutation null', 'median/max gain', np.median(nul), np.nan, max(nul)))
    Q.to_pickle(f'{OUT}/bl_tilt_{day}.pkl.gz')
pd.DataFrame(rows, columns=['day', 'item', 'metric', 'value', 'lo', 'hi']).round(4).to_csv(f'{OUT}/bl_tilt_results.csv', index=False)
