"""Activation study step 2 (plan test B/C): events vs controls. Univariate AUC (cluster bootstrap over cycles, within-cycle permutation null), leave-one-cycle-out gradient boosting by feature block with within-cycle permutations, second-level inter-arrival lags vs shifted null.
Outputs bl_act_auc.csv, bl_act_gb.csv, bl_act_lags.csv, bl_summary_act2.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy import stats
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from joblib import Parallel, delayed
rng = np.random.default_rng(511); R = {}; T = pd.read_pickle(f'{OUT}/bl_act_table.pkl.gz'); g = T.cid.values; y = T.y.values; ucy = np.unique(g); idx = {c: np.where(g == c)[0] for c in ucy}; yrs = sorted(T.expiry.unique()); med = yrs[len(yrs) // 2]; half = np.where(T.expiry < med, 1, 2)
BL = {'clock': ['sec_since_1030', 'nifty', 'v2'], 'ages': ['age_react', 'age_sell', 'age_sched', 'age_bb', 'age_oth'], 'spot_position': ['d_last_pair', 'd_last_react', 'd_last_sell', 'd_centre', 'd_open_atm', 'abs_d_last_pair', 'abs_d_last_react', 'abs_d_last_sell', 'abs_d_centre', 'abs_d_open_atm', 'd_sma10', 'd_sma30', 'd_sma60', 'd_mid', 'd_hi', 'd_lo', 'age_hi', 'age_lo', 'range_steps'],
      'atm_dynamics': ['frac_atm', 'atm_chg5', 'atm_chg15', 'since_atm_chg'], 'move': ['m15', 'm5', 'm1', 'abs_m15', 'abs_m5']}
BLC = {'clock': BL['clock'], 'ages': BL['ages'], 'spot_position': ['c_d_last_pair', 'c_d_last_react', 'c_d_last_sell', 'c_d_centre', 'c_d_open_atm', 'abs_c_d_last_pair', 'abs_c_d_last_react', 'abs_c_d_last_sell', 'abs_c_d_centre', 'abs_c_d_open_atm', 'c_d_sma10', 'c_d_sma30', 'c_d_sma60', 'c_d_mid', 'c_d_hi', 'c_d_lo', 'age_hi', 'age_lo', 'range_steps'], 'atm_dynamics': ['c_frac_atm', 'atm_chg5', 'atm_chg15', 'since_atm_chg'], 'move': ['c_m15', 'c_m5', 'c_m1', 'abs_c_m15', 'abs_c_m5', 'abs_c_m1', 'abs_pm_prev']}
ALL = sum(BL.values(), []); ALLC = sum(BLC.values(), [])
def auc(x, y_): m = ~np.isnan(x); x, y_ = x[m], y_[m]; n1 = y_.sum(); n0 = len(y_) - n1; r = stats.rankdata(x); return (r[y_ == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0) if n1 and n0 else np.nan
rows = []; bs_idx = [np.concatenate([idx[c] for c in rng.choice(ucy, len(ucy))]) for _ in range(100)]
for f in ALL:
    x = T[f].values.astype(float); a = auc(x, y); bs = [auc(x[ii], y[ii]) for ii in bs_idx]; nul = [auc(pd.Series(x).groupby(g).transform(lambda s: rng.permutation(s.values)).values, y) for _ in range(10)]; rows.append((f, a, np.nanquantile(bs, .025), np.nanquantile(bs, .975), np.nanmax(nul), auc(x[half == 1], y[half == 1]), auc(x[half == 2], y[half == 2])))
for f in sorted(set(ALLC) - set(ALL) | {'cm_now', 'abs_cm_now'}):
    if f not in T.columns: continue
    x = T[f].values.astype(float); a = auc(x, y); bs = [auc(x[ii], y[ii]) for ii in bs_idx]; nul = [auc(pd.Series(x).groupby(g).transform(lambda s: rng.permutation(s.values)).values, y) for _ in range(10)]; rows.append((f, a, np.nanquantile(bs, .025), np.nanquantile(bs, .975), np.nanmax(nul), auc(x[half == 1], y[half == 1]), auc(x[half == 2], y[half == 2])))
A = pd.DataFrame(rows, columns=['feature', 'AUC', 'lo', 'hi', 'null_max', 'half1', 'half2']); A['dev'] = (A.AUC - .5).abs(); A = A.sort_values('dev', ascending=False); A.drop(columns='dev').round(4).to_csv(f'{OUT}/bl_act_auc.csv', index=False); print(A.head(18).drop(columns='dev').round(3).to_string(index=False)); R['auc_top'] = A.head(10).drop(columns='dev').round(4).to_dict('list'); R['auc_max_dev'] = float(A.dev.max())
def fold(X, c):
    tr = g != c; m = HistGradientBoostingClassifier(max_depth=3, max_iter=120, learning_rate=0.06, min_samples_leaf=40, random_state=0).fit(X[tr], y[tr]); return np.where(~tr)[0], m.predict_proba(X[~tr])[:, 1]
def loco(cols, Q=T):
    X = Q[cols].astype(float); X = X.fillna(X.median()).values; o = np.zeros(len(y))
    for i, p in Parallel(n_jobs=4)(delayed(fold)(X, c) for c in ucy): o[i] = p
    return roc_auc_score(y, o)
res = {'clock only': loco(BL['clock'])}; res['clock + ages'] = loco(BL['clock'] + BL['ages'])
for b in ('spot_position', 'atm_dynamics', 'move'): res[f'CAUSAL (completed bars only): clock + ages + {b}'] = loco(BLC['clock'] + BLC['ages'] + BLC[b])
res['CAUSAL: all blocks'] = loco(ALLC); res['CAUSAL: all blocks + current-minute move (look-ahead)'] = loco(ALLC + ['abs_cm_now', 'cm_now'])
for b in ('spot_position', 'atm_dynamics', 'move'): res[f'LIVE-PROXY clock + ages + {b}'] = loco(BL['clock'] + BL['ages'] + BL[b])
res['LIVE-PROXY all blocks'] = loco(ALL)
for b in ('ages', 'spot_position', 'atm_dynamics', 'move'):
    z = []
    for _ in range(3): Qp = T.copy(); Qp[BL[b]] = Qp.groupby('cid')[BL[b]].transform(lambda s: rng.permutation(s.values)); z.append(loco(ALL, Qp))
    res[f'LIVE-PROXY all blocks, {b} shuffled'] = float(np.median(z))
G = pd.DataFrame(list(res.items()), columns=['model', 'LOCO_AUC']); G.round(4).to_csv(f'{OUT}/bl_act_gb.csv', index=False); print(G.round(3).to_string(index=False)); R['gb'] = {k: float(v) for k, v in res.items()}
# second-level lags: seconds since previous event of each type, events vs controls
rows = []
for f in ('age_react', 'age_sell', 'age_sched', 'age_bb', 'age_oth'):
    e = T[T.y == 1][f].dropna().values; c = T[T.y == 0][f].dropna().values; qs = [5, 10, 30, 60, 120, 300, 600, 900]; rows.append((f, len(e), *[float(np.mean(e <= q)) for q in qs], *[float(np.mean(c <= q)) for q in qs]))
Lg = pd.DataFrame(rows, columns=['age_of', 'n_events'] + [f'ev<= {q}s' for q in (5, 10, 30, 60, 120, 300, 600, 900)] + [f'ctl<= {q}s' for q in (5, 10, 30, 60, 120, 300, 600, 900)]); Lg.round(3).to_csv(f'{OUT}/bl_act_lags.csv', index=False); print(Lg.round(3).to_string(index=False)); R['lags'] = Lg.round(4).to_dict('list')
# exact-lag spikes: histogram of seconds since the previous body sell (events), 15-s bins up to 300 s vs controls
ev = T[(T.y == 1)].age_sell.dropna(); ct = T[(T.y == 0)].age_sell.dropna(); b = np.arange(0, 301, 15); he = np.histogram(ev[ev <= 300], b)[0] / len(ev); hc = np.histogram(ct[ct <= 300], b)[0] / len(ct); R['sell_lag_hist_events'] = he.round(4).tolist(); R['sell_lag_hist_controls'] = hc.round(4).tolist()
rec('act2', R)
