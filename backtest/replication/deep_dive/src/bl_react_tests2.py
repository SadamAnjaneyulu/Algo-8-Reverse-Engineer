"""Reactive-pair study, step 3 (plan tests 5, 7): which features predict a reactive-pair minute? Panel bl_react_panel.csv.gz (D-1 cycle-minutes without a timetable wave). Univariate AUC (cluster bootstrap), leave-one-cycle-out gradient boosting with feature blocks, within-cycle permutation of each block, chronological halves.
Targets: R (reactive pair), S (solo sell) and BB (buy-back) for contrast. Outputs bl_react_auc.csv, bl_react_gb.csv"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy import stats
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from joblib import Parallel, delayed
rng = np.random.default_rng(111); P = pd.read_csv(f'{OUT}/bl_react_panel.csv.gz'); P['g'] = P.und + P.expiry
BL = {'clock': ['j', 'v2', 'nifty', 'age_sell'], 'history': ['age_pair', 'age_react', 'age_sched', 'age_bb', 'age_stop', 'lots_bb5', 'lots_bb15', 'lots_sold5', 'lots_sold15', 'n_sched', 'n_react'],
      'market': ['ch1', 'ch3', 'ch5', 'ch15', 'ch30', 'a1', 'a3', 'a5', 'a15', 'a30', 'dist_hi', 'dist_lo', 'new_hi', 'new_lo', 'range_pct', 'drift_pair', 'absdrift_pair', 'drift_sell', 'strad', 'd_strad5', 'd_strad15'], 'book': ['B_total', 'B_day', 'DD'], 'inventory': ['S_CE', 'S_PE', 'imb', 'absimb', 'S_tot']}
ALL = sum(BL.values(), [])
def auc(x, y): m = ~np.isnan(x); x, y = x[m], y[m]; n1 = y.sum(); n0 = len(y) - n1; r = stats.rankdata(x); return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0) if n1 and n0 else np.nan
g = P.g.values; ucy = np.unique(g); idx = {c: np.where(g == c)[0] for c in ucy}; rows = []; gbr = []
yrs = sorted(P.expiry.unique()); med = yrs[len(yrs) // 2]; half = np.where(P.expiry < med, 1, 2)
for tn, yc in (('R', 'yR'), ('S', 'yS'), ('BB', 'yBB')):
    y = P[yc].values; print(f'\n=== target {tn}: events {y.sum()} of {len(P)}')
    for f in ALL:
        x = P[f].values.astype(float); a = auc(x, y); bs = [auc(x[ii], y[ii]) for ii in (np.concatenate([idx[c] for c in rng.choice(ucy, len(ucy))]) for _ in range(80))]; nul = [auc(pd.Series(x).groupby(g).transform(lambda s: rng.permutation(s.values)).values, y) for _ in range(10)]
        h1 = auc(x[half == 1], y[half == 1]); h2 = auc(x[half == 2], y[half == 2]); rows.append((tn, f, a, *np.nanquantile(bs, [.025, .975]), np.nanmax(nul), h1, h2))
    A = pd.DataFrame([r for r in rows if r[0] == tn], columns=['t', 'f', 'AUC', 'lo', 'hi', 'null_max', 'half1', 'half2']); A['dev'] = (A.AUC - .5).abs(); print(A.sort_values('dev', ascending=False).head(12).drop(columns=['t', 'dev']).round(3).to_string(index=False))
    def fold(X, c):
        tr = g != c; m = HistGradientBoostingClassifier(max_depth=3, max_iter=120, learning_rate=0.06, min_samples_leaf=40, random_state=0).fit(X[tr], y[tr]); return np.where(~tr)[0], m.predict_proba(X[~tr])[:, 1]
    def loco(cols, Q=P):
        X = Q[cols].astype(float); X = X.fillna(X.median()).values; o = np.zeros(len(y))
        for i, p in Parallel(n_jobs=4)(delayed(fold)(X, c) for c in ucy): o[i] = p
        return roc_auc_score(y, o)
    res = {'clock only': loco(BL['clock'])}
    for b in ('history', 'market', 'book', 'inventory'): res['clock + ' + b] = loco(BL['clock'] + BL[b])
    res['all blocks'] = loco(ALL); nul = {}
    for b in ('history', 'market', 'book', 'inventory'):
        z = []
        for _ in range(3): Qp = P.copy(); Qp[BL[b]] = Qp.groupby('g')[BL[b]].transform(lambda s: rng.permutation(s.values)); z.append(loco(ALL, Qp))
        res[f'all blocks, {b} shuffled'] = float(np.median(z))
    print({k: round(v, 3) for k, v in res.items()}); gbr += [(tn, k, v, v - res['clock only']) for k, v in res.items()]
pd.DataFrame(rows, columns=['target', 'variable', 'AUC', 'lo', 'hi', 'null_max', 'half1', 'half2']).round(4).to_csv(f'{OUT}/bl_react_auc.csv', index=False); pd.DataFrame(gbr, columns=['target', 'model', 'LOCO_AUC', 'delta_vs_clock']).round(4).to_csv(f'{OUT}/bl_react_gb.csv', index=False)
