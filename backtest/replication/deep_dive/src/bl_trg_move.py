"""Trigger study step 5 (plan block C/E, added after the drill-down showed time-since-last-pair carries the signal): is it elapsed time or the spot/ATM move since the last reactive pair?
Outputs bl_trg_move.csv, bl_summary_trg4.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy.stats import rankdata
from sklearn.linear_model import LogisticRegression
rng = np.random.default_rng(55); R = {}; P = pd.read_pickle(f'{OUT}/bl_trg_panel.pkl.gz').reset_index(drop=True); Pr = pd.read_csv(f'{OUT}/bl_react_pairs.csv'); Pr = Pr[Pr.reactive].sort_values(['und', 'expiry', 'te']); ch = Chain()
def auc(s, y):
    m = ~np.isnan(s); s = s[m]; y = y[m]; n1 = y.sum(); n0 = len(y) - n1; return np.nan if n1 < 5 or n0 < 5 else (rankdata(s)[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
mv = np.full(len(P), np.nan); am = np.full(len(P), np.nan); mv_abs = np.full(len(P), np.nan)
for (u, e), idx in P.groupby(['und', 'expiry']).groups.items():
    c = ch.cyc(u, e); K = np.array(c['strikes'], dtype=float); sp = pd.Series(np.array(c[(0, 'spot')], dtype=float)).ffill().bfill().values; step = ref.STEP[u]; near = lambda s: K[np.argmin(np.abs(K - s))]; ts = np.sort(Pr[(Pr.und == u) & (Pr.expiry == e)].te.values)
    for i in idx:
        r = P.loc[i]; T0 = 33300 + 60 * int(r.j); k = np.searchsorted(ts, T0 - 3) - 1
        if k < 0: continue
        jl = int((ts[k] - 33300) // 60); f = ((ts[k] - 33300) % 60) / 60; s_last = sp[max(jl - 1, 0)] + f * (sp[min(jl, 374)] - sp[max(jl - 1, 0)]); cl = sp[int(r.j) - 1]
        mv[i] = r.side * (cl - s_last) / step; mv_abs[i] = abs(cl - s_last) / step; am[i] = r.side * (near(cl) - near(s_last)) / step
P['move_since_pair'] = mv; P['abs_move_since_pair'] = mv_abs; P['atm_move_since_pair'] = am
d = P[(P.bkLA60 != 0) & P.move_since_pair.notna()].copy(); y = d.y.values; half = d.cid.values % 2 == 0; rows = []
for f in ('age_react', 'move_since_pair', 'abs_move_since_pair', 'atm_move_since_pair'): rows.append(dict(feature=f, AUC=auc(d[f].values.astype(float), y), AUC_even=auc(d[f].values[half].astype(float), y[half]), AUC_odd=auc(d[f].values[~half].astype(float), y[~half]), n=len(d), pairs=int(y.sum())))
print(pd.DataFrame(rows).round(3).to_string(index=False)); R['uni'] = rows
bm = pd.cut(d.move_since_pair, [-100, -1, 0, 1, 2, 3, 100], labels=['<-1 (against)', '-1..0', '0..1', '1..2', '2..3', '>3 steps (with side)']); t = d.groupby(bm, observed=True).agg(minutes=('y', 'size'), pair_minutes=('y', 'sum')); t['per1000'] = 1000 * t.pair_minutes / t.minutes; print(t.round(1)); R['move_bins'] = {str(k): [int(v.minutes), int(v.pair_minutes), float(v.per1000)] for k, v in t.iterrows()}
bm = pd.cut(d.atm_move_since_pair, [-100, -1.5, -0.5, 0.5, 1.5, 100], labels=['<=-2 ATM steps', '-1', '0', '+1', '>=+2']); t2 = d.groupby(bm, observed=True).agg(minutes=('y', 'size'), pair_minutes=('y', 'sum')); t2['per1000'] = 1000 * t2.pair_minutes / t2.minutes; print(t2.round(1)); R['atm_bins'] = {str(k): [int(v.minutes), int(v.pair_minutes), float(v.per1000)] for k, v in t2.iterrows()}
# does elapsed time or the move carry the information? LOCO logistic, paired cluster bootstrap on the AUC difference
cid = d.cid.values; ucy = np.unique(cid)
def loco(cols):
    X = d[cols].values.astype(float); X = (X - X.mean(0)) / X.std(0); p = np.zeros(len(y))
    for c_ in ucy:
        te = cid == c_; p[te] = LogisticRegression(C=0.3).fit(X[~te], y[~te]).predict_proba(X[te])[:, 1]
    return p
pt = loco(['age_react']); pm = loco(['move_since_pair', 'abs_move_since_pair', 'atm_move_since_pair']); pb = loco(['age_react', 'move_since_pair', 'abs_move_since_pair', 'atm_move_since_pair']); gi = {c_: np.where(cid == c_)[0] for c_ in ucy}; bs = [np.concatenate([gi[c_] for c_ in rng.choice(ucy, len(ucy))]) for _ in range(800)]
rows2 = []
for nm, p, q in (('time + move vs time only', pb, pt), ('time + move vs move only', pb, pm), ('move only vs time only', pm, pt)):
    dd = np.array([auc(p[b], y[b]) - auc(q[b], y[b]) for b in bs]); rows2.append(dict(comparison=nm, AUC_a=auc(p, y), AUC_b=auc(q, y), diff=auc(p, y) - auc(q, y), lo=np.quantile(dd, .025), hi=np.quantile(dd, .975)))
M = pd.DataFrame(rows2); print(M.round(3).to_string(index=False)); R['compare'] = M.round(4).to_dict('list'); pd.concat([pd.DataFrame(rows).assign(kind='univariate AUC in look-ahead breakout minutes'), M.assign(kind='LOCO logistic comparison')]).round(4).to_csv(f'{OUT}/bl_trg_move.csv', index=False); rec('trg4', R)
