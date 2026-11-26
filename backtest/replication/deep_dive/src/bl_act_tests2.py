"""Activation study step 3 (post-hoc, labelled): which causal spot-position feature carries the gain? Single-feature additions to clock + ages (leave-one-cycle-out GB), greedy forward selection (top 4), density ratio events/controls for the leading features. Outputs bl_act_single.csv, bl_act_forward.csv, bl_act_density.csv, bl_summary_act3.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from joblib import Parallel, delayed
R = {}; T = pd.read_pickle(f'{OUT}/bl_act_table.pkl.gz'); g = T.cid.values; y = T.y.values; ucy = np.unique(g)
CLK = ['sec_since_1030', 'nifty', 'v2']; AG = ['age_react', 'age_sell', 'age_sched', 'age_bb', 'age_oth']
CAND = ['c_d_last_pair', 'c_d_last_react', 'c_d_last_sell', 'c_d_centre', 'c_d_open_atm', 'abs_c_d_last_pair', 'abs_c_d_last_react', 'abs_c_d_last_sell', 'abs_c_d_centre', 'abs_c_d_open_atm', 'c_d_sma10', 'c_d_sma30', 'c_d_sma60', 'c_d_mid', 'c_d_hi', 'c_d_lo', 'age_hi', 'age_lo', 'range_steps', 'c_frac_atm', 'atm_chg5', 'since_atm_chg', 'c_m15', 'c_m5', 'abs_c_m15', 'abs_c_m5', 'abs_c_m1']
def fold(X, c):
    tr = g != c; m = HistGradientBoostingClassifier(max_depth=3, max_iter=100, learning_rate=0.07, min_samples_leaf=40, random_state=0).fit(X[tr], y[tr]); return np.where(~tr)[0], m.predict_proba(X[~tr])[:, 1]
def loco(cols):
    X = T[cols].astype(float); X = X.fillna(X.median()).values; o = np.zeros(len(y))
    for i, p in Parallel(n_jobs=4)(delayed(fold)(X, c) for c in ucy): o[i] = p
    return roc_auc_score(y, o)
base = loco(CLK + AG); R['base'] = base; rows = []
for f in CAND: rows.append((f, loco(CLK + AG + [f]) - base))
S = pd.DataFrame(rows, columns=['feature_added_to_clock_plus_ages', 'AUC_gain']).sort_values('AUC_gain', ascending=False); S.round(4).to_csv(f'{OUT}/bl_act_single.csv', index=False); print('base', round(base, 3)); print(S.round(3).head(12).to_string(index=False)); R['single_top'] = S.head(10).round(4).to_dict('list')
chosen = []; cur = base; fr = []
for step in range(4):
    best = max(((f, loco(CLK + AG + chosen + [f])) for f in S.feature_added_to_clock_plus_ages.head(10) if f not in chosen), key=lambda z: z[1]); chosen.append(best[0]); fr.append((step + 1, best[0], best[1], best[1] - cur)); cur = best[1]
F = pd.DataFrame(fr, columns=['step', 'feature_added', 'LOCO_AUC', 'gain']); F.round(4).to_csv(f'{OUT}/bl_act_forward.csv', index=False); print(F.round(3).to_string(index=False)); R['forward'] = F.round(4).to_dict('list')
# density ratio events vs controls for the leading features (quintiles of the control distribution)
dens = []
for f in S.feature_added_to_clock_plus_ages.head(4).tolist() + ['abs_c_m5']:
    ctl = T[(T.y == 0)][f].dropna(); ev = T[(T.y == 1)][f].dropna(); qs = np.quantile(ctl, [0, .2, .4, .6, .8, 1]); qs[0] -= 1e-9; qs[-1] += 1e-9; pe = np.histogram(ev, qs)[0] / len(ev); pc = np.histogram(ctl, qs)[0] / len(ctl)
    for i in range(5): dens.append((f, i + 1, qs[i], qs[i + 1], pe[i], pc[i], pe[i] / pc[i]))
Dn = pd.DataFrame(dens, columns=['feature', 'control_quintile', 'lo', 'hi', 'share_of_events', 'share_of_controls', 'ratio']); Dn.round(4).to_csv(f'{OUT}/bl_act_density.csv', index=False); print(Dn.round(3).to_string(index=False)); R['density'] = Dn.round(4).to_dict('list')
rec('act3', R)
