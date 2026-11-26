"""Book-state study step 3 (plan tests C; pace block added POST-HOC): leave-one-cycle-out logistic / gradient boosting on the cycle-minute panel (table M) with blocks: edge, book greeks/exposure, premium/vol, P&L, other-order activity, PACE (cumulative-pair deficit vs the other cycles' mean curve).
Outputs bl_bk_blocks.csv, bl_bk_pace_uni.csv, bl_summary_bk2.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy.stats import rankdata
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
rng = np.random.default_rng(404); R = {}; M = pd.read_pickle(f'{OUT}/bl_bk_M.pkl.gz'); Pr = pd.read_csv(f'{OUT}/bl_react_pairs.csv'); CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); cyc = [(r.und, r.expiry) for r in CY.itertuples()]; cid_of = {k: i for i, k in enumerate(cyc)}
RT = {k: np.sort(Pr[(Pr.und == k[0]) & (Pr.expiry == k[1]) & Pr.reactive].te.values) for k in cyc}; TT = {k: np.sort(Pr[(Pr.und == k[0]) & (Pr.expiry == k[1])].te.values) for k in cyc}; ST = {k: np.sort(Pr[(Pr.und == k[0]) & (Pr.expiry == k[1]) & Pr.sched].te.values) for k in cyc}
mins = np.arange(75, 361); cumR = {k: np.array([np.sum(RT[k] < 33300 + 60 * j - 3) for j in mins]) for k in cyc}; cumT = {k: np.array([np.sum(TT[k] < 33300 + 60 * j - 3) for j in mins]) for k in cyc}; cumS = {k: np.array([np.sum(ST[k] < 33300 + 60 * j - 3) for j in mins]) for k in cyc}
loo = lambda D, k: np.mean([D[q] for q in cyc if q != k], axis=0)
LR, LT, LS = {k: loo(cumR, k) for k in cyc}, {k: loo(cumT, k) for k in cyc}, {k: loo(cumS, k) for k in cyc}
rows = []
for r in M.itertuples():
    k = (r.und, r.expiry); i = r.j - 75; rows.append((cumR[k][i], cumT[k][i], LR[k][i] - cumR[k][i], LT[k][i] - cumT[k][i], LS[k][i] - cumS[k][i]))
M[['n_react', 'n_tot', 'def_react', 'def_tot', 'def_sched']] = np.array(rows); M['cidx'] = [cid_of[(u, e)] for u, e in zip(M.und, M.expiry)]
def auc(s, y):
    m = ~np.isnan(s); s = s[m]; yy = y[m]; n1 = yy.sum(); n0 = len(yy) - n1; return np.nan if n1 < 5 or n0 < 5 else (rankdata(s)[yy == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
BLK = dict(edge=['depth60', 'run60', 'side', 'width60', 'posprev60', 'bk45', 'bk90'], clock=['min_since_1030', 'v2'], activity=['age_pair', 'age_react', 'age_sell', 'age_bb', 'age_oth'],
           book=['delta', 'delta_vs_move', 'delta_vs_move_norm', 'gamma', 'short_lots', 'itm_short', 'net_lots', 'dist_out_move', 'dist_out_opp', 'dist_in_move', 'dist_in_opp', 'delta_chg5', 'delta_chg15'], premium=['sig', 'sig_chg5', 'sig_chg15', 'sig_chg30', 'prem_tgt', 'prem_ratio_atm', 'prem_pos60', 'prem_chg15'], pnl=['pnl_pct', 'pnl_chg5', 'pnl_chg15', 'pnl_chg30'], pace=['n_react', 'n_tot', 'def_react', 'def_tot', 'def_sched'])
M['side'] = M.side if 'side' in M else 1
def loco(X, y, cid, kind):
    p = np.zeros(len(y))
    for c_ in np.unique(cid):
        te = cid == c_; tr = ~te
        if kind == 'lr':
            med = np.nanmedian(X[tr], axis=0); med = np.where(np.isnan(med), 0, med); Xt = np.where(np.isnan(X), med, X); sc = StandardScaler().fit(Xt[tr]); p[te] = LogisticRegression(C=0.3, max_iter=300).fit(sc.transform(Xt[tr]), y[tr]).predict_proba(sc.transform(Xt[te]))[:, 1]
        else: p[te] = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=120, min_samples_leaf=20, l2_regularization=1.0, random_state=0).fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
    return p
out = []
for tag, df in (('all minutes 10:30-15:15', M), ('LOOK-AHEAD breakout minutes', M[M.bkLA60 != 0])):
    df = df.reset_index(drop=True); y = df.y.values; cid = df.cidx.values; ucy = np.unique(cid); gi = {c_: np.where(cid == c_)[0] for c_ in ucy}; bs = [np.concatenate([gi[c_] for c_ in rng.choice(ucy, len(ucy))]) for _ in range(500)]; half = cid % 2 == 0
    sets = {'edge only': BLK['edge'], 'edge + activity (order ages)': BLK['edge'] + BLK['activity'], 'edge + book greeks/exposure': BLK['edge'] + BLK['book'], 'edge + premium/vol': BLK['edge'] + BLK['premium'], 'edge + P&L': BLK['edge'] + BLK['pnl'], 'edge + pace deficit': BLK['edge'] + BLK['pace'], 'edge + activity + pace': BLK['edge'] + BLK['activity'] + BLK['pace'], 'edge + book + premium + P&L (no pace, no activity)': BLK['edge'] + BLK['book'] + BLK['premium'] + BLK['pnl'], 'everything': sum(BLK.values(), [])}
    pr = {(nm, kd): loco(df[c].values.astype(float), y, cid, kd) for nm, c in sets.items() for kd in ('lr', 'gb')}
    for kd in ('lr', 'gb'):
        base = pr[('edge only', kd)]; bb = np.array([auc(base[b], y[b]) for b in bs])
        for nm in sets:
            p = pr[(nm, kd)]; dd = np.array([auc(p[b], y[b]) for b in bs]) - bb; out.append(dict(population=tag, model=kd, features=nm, n=len(df), pair_minutes=int(y.sum()), AUC=auc(p, y), AUC_even=auc(p[half], y[half]), AUC_odd=auc(p[~half], y[~half]), gain=auc(p, y) - auc(base, y), gain_lo=np.quantile(dd, .025), gain_hi=np.quantile(dd, .975)))
Bk = pd.DataFrame(out); Bk.round(4).to_csv(f'{OUT}/bl_bk_blocks.csv', index=False); print(Bk.round(3).to_string(index=False))
# univariate pace variables inside look-ahead breakout minutes and all minutes
rows = []
for tag, df in (('all minutes', M), ('LOOK-AHEAD breakout minutes', M[M.bkLA60 != 0]), ('causal breakout minutes', M[M.bk60 != 0])):
    y = df.y.values; half = df.cidx.values % 2 == 0
    for v in BLK['pace'] + ['age_react', 'delta_vs_move', 'itm_short', 'pnl_pct', 'prem_pos60']: x = df[v].values.astype(float); rows.append(dict(population=tag, variable=v, AUC=auc(x, y), AUC_even=auc(x[half], y[half]), AUC_odd=auc(x[~half], y[~half])))
PU = pd.DataFrame(rows); PU.round(3).to_csv(f'{OUT}/bl_bk_pace_uni.csv', index=False); print(PU.round(3).to_string(index=False)); rec('bk2', R); M.to_pickle(f'{OUT}/bl_bk_M2.pkl.gz')
