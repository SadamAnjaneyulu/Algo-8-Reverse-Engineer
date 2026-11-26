"""Final comparison: how much of the solo-sell episode-start signal do the candidate variable groups explain (LOCO, non-slot minutes) + chronological-halves replication of the breakout effect. Outputs outputs/bl_final_models.csv, bl_breakout_halves.csv"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score, log_loss
from joblib import Parallel, delayed
F = pd.read_csv(f'{OUT}/bl_breakout_panel.csv'); rng = np.random.default_rng(0)
BASE = ['fav30', 'own_ratio', 'other_ratio']; MULTI = ['fav5', 'fav15', 'fav60']; BK = ['bk5', 'bk10', 'bk15', 'bk20', 'bk30', 'bk45', 'bk60', 'pos15', 'range15', 'break_steps15']
GREEK = ['delta_need', 'nd_per_short', 'gamma', 'vega']; VOL = ['atm_iv', 'd_iv15', 'd_iv30', 'iv_rel', 'straddle', 'd_str15', 'd_str30']; POS = ['S_own', 'S_other', 'imb', 'L_own', 'L_other', 'own_share', 'dev_book']; ACT = ['tsl_own', 'tsl_other', 'solo_own30', 'solo_oth30', 'sched30']
def prep(Q, cs): X = Q[cs].copy(); X = X.fillna(X.median()); X = (X - X.mean()) / X.std().replace(0, 1); return X.values
def fold(X, y, g, c, kind):
    tr = g != c
    m = LogisticRegression(C=1.0, max_iter=400).fit(X[tr], y[tr]) if kind == 'lr' else HistGradientBoostingClassifier(max_depth=3, max_iter=150, learning_rate=0.06, min_samples_leaf=40, random_state=0).fit(X[tr], y[tr]); return np.where(~tr)[0], m.predict_proba(X[~tr])[:, 1]
def loco(X, y, g, kind):
    o = np.zeros(len(y))
    for i, p in Parallel(n_jobs=4)(delayed(fold)(X, y, g, c, kind) for c in np.unique(g)): o[i] = p
    return o
rows = []; MODELS = [('1 baseline (fav30, own, other ratio)', BASE), ('2 baseline + multi-horizon moves', BASE + MULTI), ('3 baseline + breakout variables', BASE + BK), ('4 baseline + multi-horizon + breakout', BASE + MULTI + BK), ('5 baseline + Greeks (delta, gamma, vega)', BASE + GREEK), ('6 baseline + vol (VIX-like) proxies', BASE + VOL), ('7 baseline + inventory', BASE + POS), ('8 baseline + activity history', BASE + ACT), ('9 market model: 4 + Greeks + vol + inventory', BASE + MULTI + BK + GREEK + VOL + POS), ('10 everything incl. activity + clock', BASE + MULTI + BK + GREEK + VOL + POS + ACT + ['mins'])]
for day in ('D-1', 'D0'):
    Q = F[(F.day == day) & (F.tslot != 0)].reset_index(drop=True); y = Q.ep.values; g = (Q.und + Q.expiry).values
    for nm, cols in MODELS:
        for kind in ('lr', 'gb'):
            p = loco(prep(Q, cols), y, g, kind); rows.append((day, nm, kind, roc_auc_score(y, p), log_loss(y, p)))
    print('\n', day); print(pd.DataFrame([r for r in rows if r[0] == day], columns=['day', 'model', 'kind', 'AUC', 'logloss']).pivot(index='model', columns='kind', values='AUC').round(3).to_string())
pd.DataFrame(rows, columns=['day', 'model', 'kind', 'AUC', 'logloss']).round(4).to_csv(f'{OUT}/bl_final_models.csv', index=False)
# chronological halves replication of the breakout effect (D-1 and D0)
hv = []
for day in ('D-1', 'D0'):
    Q = F[(F.day == day) & (F.tslot != 0)].copy(); order = sorted(Q.expiry.unique()); half = {e: (0 if i < len(order) / 2 else 1) for i, e in enumerate(order)}; Q['half'] = Q.expiry.map(half)
    for h, q in Q.groupby('half'):
        for f in ('bk5', 'bk15', 'bk30'): on = q[f] == 1; hv.append((day, f'half {h + 1} ({q.expiry.min()}..{q.expiry.max()})', f, on.mean(), q[on].ep.mean() * 1000, q[~on].ep.mean() * 1000, roc_auc_score(q.ep, q[f])))
H = pd.DataFrame(hv, columns=['day', 'sample', 'feature', 'share_flagged', 'rate_on', 'rate_off', 'AUC']).round(3); H.to_csv(f'{OUT}/bl_breakout_halves.csv', index=False); print(H.to_string(index=False))
