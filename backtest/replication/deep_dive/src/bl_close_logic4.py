"""Buy-back study, step 5: which variables carry the multivariable signal for D-1 buy-backs at r_low < 1.2? Leave-one-variable-out and single-variable-plus-baseline LOCO gradient boosting (D-1)."""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from joblib import Parallel, delayed
P = pd.read_csv(f'{OUT}/bl_close_panel2.csv.gz'); Q = P[(P.day == 'D-1') & (P.r_low < 1.2)].reset_index(drop=True); Q['abs_itm'] = Q.itm_steps.abs(); Q['o_r'] = Q.o_r_avg; Q['tod_min'] = Q.j
y = (Q.bb_lots > 0).astype(int).values; g = (Q.und + Q.expiry).values; ucy = np.unique(g)
FE = ['r_avg', 'r_low', 'r_fifo', 'abs_itm', 'itm_steps', 'hold_min', 'price', 'n_open', 'o_n_open', 'o_r', 'straddle_r', 'tod_min']
def fold(X, c):
    tr = g != c; m = HistGradientBoostingClassifier(max_depth=3, max_iter=120, learning_rate=0.06, min_samples_leaf=50, random_state=0).fit(X[tr], y[tr]); return np.where(~tr)[0], m.predict_proba(X[~tr])[:, 1]
def loco(cols):
    X = Q[cols].astype(float); X = X.fillna(X.median()).values; o = np.zeros(len(y))
    for i, p in Parallel(n_jobs=4)(delayed(fold)(X, c) for c in ucy): o[i] = p
    return roc_auc_score(y, o)
full = loco(FE); print('all', round(full, 3)); out = [('all', full)]
for f in FE: a = loco([c for c in FE if c != f]); out.append(('drop ' + f, a)); print(f'drop {f:10s} {a:.3f}  (loss {full - a:+.3f})')
for f in FE: a = loco(['r_low', f]) if f != 'r_low' else loco(['r_low']); out.append(('r_low + ' + f, a)); print(f'r_low + {f:10s} {a:.3f}')
pd.DataFrame(out, columns=['model', 'LOCO_AUC']).round(4).to_csv(f'{OUT}/bl_close_E_gb.csv', index=False)
