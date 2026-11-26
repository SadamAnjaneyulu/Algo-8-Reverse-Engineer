"""Trigger study step 3 (plan BODY_REACTIVE_TRIGGER_PLAN.md blocks C-F) on Panel B (outputs/bl_trg_panel.pkl.gz).
Outputs bl_trg_blocks.csv, bl_trg_episode.csv, bl_trg_refract.csv, bl_trg_tree.csv, bl_summary_trg2.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy.stats import rankdata
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier
rng = np.random.default_rng(909); R = {}; P = pd.read_pickle(f'{OUT}/bl_trg_panel.pkl.gz').reset_index(drop=True)
def auc(s, y):
    n1 = y.sum(); n0 = len(y) - n1
    return np.nan if n1 == 0 or n0 == 0 else (rankdata(s)[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
BL = dict(edge=['depth60', 'run60', 'side', 'width60', 'posprev60', 'depth45', 'depth90', 'bk45', 'bk90', 'run45', 'run90'], clock=['min_since_1030', 'v2'], activity=['age_pair', 'age_react', 'age_sell', 'age_bb', 'age_oth', 'n_react_sofar', 'n_sell_sofar', 'n_bb_sofar', 'last_react_same_side'],
          book=['short_ce', 'short_pe', 'short_tot', 'tgt_short_ce', 'tgt_short_pe', 'tgt_pair_open', 'centre_d'], option=['prem_tgt', 'prem_atm', 'prem_ratio', 'vol_tgt', 'vol_rel'], market=['absm1', 'absm5', 'vol30'])
def loco(X, y, cid, kind):
    p = np.zeros(len(y))
    for c_ in np.unique(cid):
        te = cid == c_; tr = ~te
        if kind == 'lr':
            med = np.nanmedian(X[tr], axis=0); med = np.where(np.isnan(med), 0, med); Xt = np.where(np.isnan(X), med, X); sc = StandardScaler().fit(Xt[tr]); m = LogisticRegression(C=0.3, max_iter=300).fit(sc.transform(Xt[tr]), y[tr]); p[te] = m.predict_proba(sc.transform(Xt[te]))[:, 1]
        else:
            m = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=120, min_samples_leaf=20, l2_regularization=1.0, random_state=0).fit(X[tr], y[tr]); p[te] = m.predict_proba(X[te])[:, 1]
    return p
def study(df, tag, blocks_extra=None, nboot=500):
    df = df.reset_index(drop=True); y = df.y.values; cid = df.cid.values; ucy = np.unique(cid); gi = {c_: np.where(cid == c_)[0] for c_ in ucy}; bs = [np.concatenate([gi[c_] for c_ in rng.choice(ucy, len(ucy))]) for _ in range(nboot)]; half = cid % 2 == 0
    sets = {'edge only': BL['edge']}
    for b in ('clock', 'activity', 'book', 'option', 'market'): sets['edge + ' + b] = BL['edge'] + BL[b]
    sets['all blocks'] = sum(BL.values(), [])
    out = []; pred = {}
    for nm, cols in sets.items():
        for kind in ('lr', 'gb'): pred[(nm, kind)] = loco(df[cols].values.astype(float), y, cid, kind)
    for kind in ('lr', 'gb'):
        base = pred[('edge only', kind)]; bb = np.array([auc(base[b], y[b]) for b in bs])
        for nm in sets:
            p = pred[(nm, kind)]; d = np.array([auc(p[b], y[b]) for b in bs]) - bb
            out.append(dict(population=tag, model=kind, features=nm, n=len(df), pair_minutes=int(y.sum()), AUC=auc(p, y), AUC_half_even=auc(p[half], y[half]), AUC_half_odd=auc(p[~half], y[~half]), gain_vs_edge_only=auc(p, y) - auc(base, y), gain_lo=np.quantile(d, .025), gain_hi=np.quantile(d, .975)))
    return pd.DataFrame(out), pred
B1 = P[P.bk60 != 0]; B2 = P[P.bkLA60 != 0]
r1, p1 = study(B1, 'causal breakout minutes (completed bar beyond prior 60 closes)'); r2, p2 = study(B2, 'LOOK-AHEAD breakout minutes (current minute close beyond prior 60 closes)')
r3, p3 = study(P, 'all minutes 10:30-15:15 (causal features)')
BLK = pd.concat([r1, r2, r3]); BLK.round(4).to_csv(f'{OUT}/bl_trg_blocks.csv', index=False); print(BLK.round(3).to_string(index=False))
# D episodes
rows = []
for (c_, g) in P.groupby('cid'):
    g = g.sort_values('j').reset_index(drop=True); b = g.bk60.values
    for i in range(len(g)):
        if b[i] != 0 and (i == 0 or b[i - 1] != b[i]):
            nxt = g.iloc[i:i + 3]; r = g.iloc[i].to_dict(); r['y'] = int(nxt.y.sum() > 0); r['y_any_in_episode'] = int(g.iloc[i:i + int(g.iloc[i].run60 if False else 1)].y.sum() > 0); rows.append(r)
EP = pd.DataFrame(rows); r4, p4 = study(EP, 'episode starts (causal breakout, pair within 3 minutes)', nboot=300); r4.round(4).to_csv(f'{OUT}/bl_trg_episode.csv', index=False); print(r4.round(3).to_string(index=False)); R['episodes'] = dict(n=len(EP), pos=int(EP.y.sum()))
# E refractory
rows = []
def haz(df, grp, tag):
    t = df.groupby(grp, observed=True).agg(minutes=('y', 'size'), pair_minutes=('y', 'sum')); t['per1000'] = 1000 * t.pair_minutes / t.minutes; t['population'] = tag; return t.reset_index().rename(columns={grp: 'bin'}).astype({'bin': str})
bins = pd.cut(P.age_react / 60, [-1, 2, 5, 10, 20, 40, 1000], labels=['<2 min', '2-5', '5-10', '10-20', '20-40', '40+']).astype(object).where(P.age_react.notna(), 'no pair yet')
P['age_bin'] = bins; P['n_bin'] = pd.cut(P.n_react_sofar, [-1, 0, 1, 2, 100], labels=['0', '1', '2', '3+'])
for nm, df in (('all minutes', P), ('causal breakout minutes', P[P.bk60 != 0]), ('LOOK-AHEAD breakout minutes', P[P.bkLA60 != 0]), ('inside range (no LA breakout)', P[P.bkLA60 == 0])):
    rows += [haz(df, 'age_bin', nm + ': minutes since last reactive pair'), haz(df, 'n_bin', nm + ': reactive pairs so far'), haz(df[df.last_react_same_side.notna()], 'last_react_same_side', nm + ': last pair on the same side as the current breakout side')]
RF = pd.concat(rows); RF.round(2).to_csv(f'{OUT}/bl_trg_refract.csv', index=False); print(RF.round(1).to_string(index=False))
# refractory ratio with cluster bootstrap, LA breakout minutes: pair within 5 min vs later
def ratio(df, nboot=1000):
    df = df[df.age_react.notna()]; ucy = df.cid.unique(); gi = {c_: df[df.cid == c_] for c_ in ucy}; v = []
    for _ in range(nboot):
        d = pd.concat([gi[c_] for c_ in rng.choice(ucy, len(ucy))]); a = d[d.age_react < 300].y.mean(); b = d[d.age_react >= 300].y.mean(); v.append(a / b if b > 0 else np.nan)
    d = df; return float(d[d.age_react < 300].y.mean() / d[d.age_react >= 300].y.mean()), float(np.nanquantile(v, .025)), float(np.nanquantile(v, .975)), int((d.age_react < 300).sum())
R['refract_ratio_LA_breakout_lt5_vs_ge5'] = ratio(P[P.bkLA60 != 0]); R['refract_ratio_all'] = ratio(P); R['refract_ratio_causal_breakout'] = ratio(P[P.bk60 != 0])
# F simplest rule: depth<=3 tree LOCO, F1-optimal threshold chosen on the training folds
def tree(cols, tag):
    X = P[cols].values.astype(float); X = np.where(np.isnan(X), -1, X); y = P.y.values; cid = P.cid.values; pr = np.zeros(len(y)); thr = {}
    for c_ in np.unique(cid):
        te = cid == c_; tr = ~te; m = DecisionTreeClassifier(max_depth=3, min_samples_leaf=20, random_state=0).fit(X[tr], y[tr]); ptr = m.predict_proba(X[tr])[:, 1]; best = (0, .5)
        for t in np.unique(ptr):
            tp = ((ptr >= t) & (y[tr] == 1)).sum(); pp = (ptr >= t).sum(); f = 2 * tp / (pp + y[tr].sum()) if pp else 0
            if f > best[0]: best = (f, t)
        pr[te] = (m.predict_proba(X[te])[:, 1] >= best[1]).astype(float)
    tp = ((pr == 1) & (y == 1)).sum(); return dict(rule=tag, predicted_minutes=int(pr.sum()), precision=float(tp / max(pr.sum(), 1)), recall=float(tp / y.sum()), pair_minutes=int(y.sum()))
cols_c = sum([BL[k] for k in BL], []); T_ = []
T_.append(tree(cols_c, 'depth<=3 tree, all causal features')); T_.append(tree(BL['edge'], 'depth<=3 tree, edge features only'))
for nm, sel in (('completed-bar breakout (N=60)', P.bk60 != 0), ('LOOK-AHEAD breakout (current close beyond prior 60 closes)', P.bkLA60 != 0)):
    tp = int((sel & (P.y == 1)).sum()); T_.append(dict(rule=nm + ' (no learning)', predicted_minutes=int(sel.sum()), precision=tp / sel.sum(), recall=tp / P.y.sum(), pair_minutes=int(P.y.sum())))
TR = pd.DataFrame(T_); TR.round(4).to_csv(f'{OUT}/bl_trg_tree.csv', index=False); print(TR.round(3).to_string(index=False))
R['tree'] = TR.round(4).to_dict('list'); rec('trg2', R); print(json.dumps(R, default=float)[:1500])
