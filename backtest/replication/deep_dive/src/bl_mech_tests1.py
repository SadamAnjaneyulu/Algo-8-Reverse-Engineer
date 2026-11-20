"""Reactive-pair mechanism study, step 2 (plan tests A and B): onset/stop vs spot excursion and volume; London-open check; clock vs proxies (leave-one-cycle-out GB); stratified hazards.
Outputs bl_mech_onset.csv, bl_mech_hazard_block.csv, bl_mech_strata.csv, bl_mech_gb.csv, bl_summary_mech1.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy import stats
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from joblib import Parallel, delayed
rng = np.random.default_rng(201); R = {}; P = pd.read_csv(f'{OUT}/bl_mech_panel.csv.gz'); C = pd.read_csv(f'{OUT}/bl_mech_cycle.csv'); B = pd.read_csv(f'{OUT}/bl_mech_block.csv'); hm = lambda s: f'{int(s // 3600)}:{int((s % 3600) // 60):02d}'
# ---- A1: onset vs spot excursion (Spearman across cycles, with permutation p)
rows = []
for c in ('t_dev1', 't_dev15', 't_dev2', 't_dev3', 't_range02', 't_range03'):
    m = C[['first_react', c]].dropna(); rho = stats.spearmanr(m.first_react, m[c])[0]; nul = [stats.spearmanr(m.first_react, rng.permutation(m[c].values))[0] for _ in range(500)]; rows.append((c, len(m), rho, float(np.mean(np.abs(nul) >= abs(rho))), hm(m[c].median()), float((m[c] > m.first_react).mean())))
O1 = pd.DataFrame(rows, columns=['excursion_threshold', 'n', 'spearman_with_first_reactive', 'perm_p', 'median_time_reached', 'share_reached_AFTER_first_reactive']); O1.round(3).to_csv(f'{OUT}/bl_mech_onset.csv', index=False); print(O1.round(3).to_string(index=False)); R['onset'] = O1.round(4).to_dict('list')
R['first_q'] = [hm(x) for x in C.first_react.quantile([.1, .25, .5, .75, .9])]; R['last_q'] = [hm(x) for x in C.last_react.quantile([.1, .25, .5, .75, .9])]; R['first_react_before_1100'] = float((C.first_react < 11 * 3600).mean()); R['first_react_before_1030'] = float((C.first_react < 10.5 * 3600).mean()); R['last_after_1500'] = float((C.last_react >= 15 * 3600).mean()); R['last_after_1525'] = float((C.last_react >= 15.42 * 3600).mean())
# ---- A2: hazard per 15-min block and volume/volatility per block
P['blk'] = ((P.j - 1) // 15).astype(int); Hb = P.groupby('blk').agg(n=('yR', 'size'), ev=('yR', 'sum'), solo=('yS', 'sum'), bb=('yBB', 'sum')); Hb['R_per1000'] = Hb.ev / Hb.n * 1000; Hb['solo_per1000'] = Hb.solo / Hb.n * 1000; Hb['bb_per1000'] = Hb.bb / Hb.n * 1000
Bm = B.groupby('block').agg(tot_vol_med=('tot_vol', 'median'), atm_vol_med=('atm_vol', 'median'), rv_med=('rv', 'median'), dev_med=('dev_open', 'median')); Hb = Hb.join(Bm); Hb['clock'] = [f'{9 + (15 + 15 * b) // 60}:{(15 + 15 * b) % 60:02d}' for b in Hb.index]; Hb.round(2).to_csv(f'{OUT}/bl_mech_hazard_block.csv'); print(Hb[['clock', 'n', 'ev', 'R_per1000', 'solo_per1000', 'bb_per1000', 'tot_vol_med', 'rv_med', 'dev_med']].round(1).to_string())
vol = Bm.tot_vol_med; i1230 = 1 + (12 * 60 + 30 - 9 * 60 - 15) // 15; R['london_block'] = int(i1230); R['vol_ratio_1230_vs_prev'] = float(vol.loc[i1230] / vol.loc[i1230 - 1]); R['react_rate_1230_vs_prev'] = [float(Hb.loc[i1230, 'R_per1000']), float(Hb.loc[i1230 - 1, 'R_per1000'])]; R['rv_ratio_1230_vs_prev'] = float(Bm.rv_med.loc[i1230] / Bm.rv_med.loc[i1230 - 1])
# ---- B: clock vs proxies, leave-one-cycle-out GB
P['g'] = P.und + P.expiry; g = P.g.values; ucy = np.unique(g); y = P.yR.values
BLK = {'clock': ['j'], 'ids': ['v2', 'nifty'], 'volume': ['atm_vol1', 'atm_vol15', 'tot_vol15'], 'realised_vol': ['rv5', 'rv15'], 'range_open': ['dev_open', 'maxdev_open', 'range_pct2'], 'progress': ['n_sched', 'S_tot', 'age_sell']}
def fold(X, c):
    tr = g != c; m = HistGradientBoostingClassifier(max_depth=3, max_iter=120, learning_rate=0.06, min_samples_leaf=40, random_state=0).fit(X[tr], y[tr]); return np.where(~tr)[0], m.predict_proba(X[~tr])[:, 1]
def loco(cols, Q=P):
    X = Q[cols].astype(float); X = X.fillna(X.median()).values; o = np.zeros(len(y))
    for i, p in Parallel(n_jobs=4)(delayed(fold)(X, c) for c in ucy): o[i] = p
    return roc_auc_score(y, o)
ids = BLK['ids']; res = {'clock only (j)': loco(BLK['clock'] + ids), 'no clock, ids only': loco(ids)}
for b in ('volume', 'realised_vol', 'range_open', 'progress'): res[f'no clock + {b}'] = loco(BLK[b] + ids); res[f'clock + {b}'] = loco(BLK['clock'] + BLK[b] + ids)
noclock = sum([BLK[b] for b in ('volume', 'realised_vol', 'range_open', 'progress')], []) + ids; res['all proxies, no clock'] = loco(noclock); res['all proxies + clock'] = loco(BLK['clock'] + noclock); z = []
for _ in range(3): Qp = P.copy(); Qp['j'] = Qp.groupby('g').j.transform(lambda s: rng.permutation(s.values)); z.append(loco(BLK['clock'] + noclock, Qp))
res['all proxies + clock, clock shuffled within cycle'] = float(np.median(z)); G = pd.DataFrame(list(res.items()), columns=['model', 'LOCO_AUC']); G.round(4).to_csv(f'{OUT}/bl_mech_gb.csv', index=False); print(G.round(3).to_string(index=False)); R['gb'] = {k: float(v) for k, v in res.items()}
# ---- stratified hazard: hour x tercile of max excursion from open and of volume
P['hour'] = (P.j // 60 + 9 + (P.j % 60 + 15 >= 60).astype(int)).clip(9, 15)
P['t_exc'] = pd.qcut(P.maxdev_open, 3, labels=['low excursion', 'mid', 'high excursion'], duplicates='drop'); P['t_vol'] = pd.qcut(P.tot_vol15, 3, labels=['low volume', 'mid', 'high volume'], duplicates='drop')
for k in ('t_exc', 't_vol'):
    t = P.groupby(['hour', k], observed=True).yR.agg(['size', 'sum']); t['per1000'] = (t['sum'] / t['size'] * 1000).round(1); print('\nreactive per 1000 cycle-minutes by clock hour x', k); print(t.per1000.unstack().to_string()); t.reset_index().assign(strat=k).rename(columns={k: 'level'}).to_csv(f'{OUT}/bl_mech_strata_{k}.csv', index=False)
rec('mech1', R)
