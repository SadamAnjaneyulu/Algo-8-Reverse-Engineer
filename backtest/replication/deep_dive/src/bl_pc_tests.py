"""Pace study checks (POST-HOC): (1) paired cycle bootstrap of out-of-fold F1, pace machine M10 vs refractory machine M1; (2) pace vs time-since-last-pair inside the range-edge seconds (LOCO logistic, paired cluster bootstrap); (3) catch-up signature (gap autocorrelation, gap after long gaps); (4) fires per cycle.
Outputs bl_pc_boot.csv, bl_pc_age.csv, bl_summary_pc2.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy.stats import rankdata, spearmanr
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
rng = np.random.default_rng(66); R = {}; Pr = pd.read_csv(f'{OUT}/bl_react_pairs.csv'); P = pd.read_pickle(f'{OUT}/bl_trg_panel.pkl.gz'); CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); cyc = [(r.und, r.expiry) for r in CY.itertuples()]
A = {i: set(P[(P.und == k[0]) & (P.expiry == k[1]) & (P.y == 1)].j.values.astype(int)) for i, k in enumerate(cyc)}
def match(F, Aset, tol=1):
    used = set(); tp = 0
    for f in sorted(F):
        best = None
        for a in Aset:
            if a in used or abs(a - f) > tol: continue
            if best is None or abs(a - f) < abs(best - f): best = a
        if best is not None: used.add(best); tp += 1
    return tp
def per_cycle(fires):
    out = {}
    for i in range(len(cyc)): f = [m for m in fires.get(i, [])]; out[i] = (match(f, A[i]), len(f), len(A[i]))
    return out
pc = pd.read_csv(f'{OUT}/bl_pc_fires.csv'); m10 = {i: g.minute.tolist() for i, g in pc[(pc.family == 'M10') & (pc['info'] == 'bar')].groupby('cid')}; m10i = {i: g.minute.tolist() for i, g in pc[(pc.family == 'M10') & (pc['info'] == 'intra')].groupby('cid')}
m1p = pd.read_csv(f'{OUT}/bl_trk_sim2_fires.csv'); m1 = {i: g.minute.tolist() for i, g in m1p.groupby('cid')}
T10, T10i, T1 = per_cycle(m10), per_cycle(m10i), per_cycle(m1); ids = list(range(len(cyc)))
def f1(T, cids): tp = sum(T[c][0] for c in cids); nf = sum(T[c][1] for c in cids); na = sum(T[c][2] for c in cids); return 2 * tp / (nf + na)
rows = []
for nm, a, b in (('M10 pace (completed bars) minus M1 refractory (completed bars)', T10, T1), ('M10 pace (current-minute close) minus M1 refractory (completed bars)', T10i, T1)):
    d = []
    for _ in range(2000): s = rng.choice(ids, len(ids)); d.append(f1(a, s) - f1(b, s))
    rows.append(dict(comparison=nm, F1_a=f1(a, ids), F1_b=f1(b, ids), diff=f1(a, ids) - f1(b, ids), lo=np.quantile(d, .025), hi=np.quantile(d, .975), share_of_cycles_a_better=float(np.mean([(2 * a[c][0] / (a[c][1] + a[c][2])) > (2 * b[c][0] / (b[c][1] + b[c][2])) for c in ids]))))
BO = pd.DataFrame(rows); BO.round(4).to_csv(f'{OUT}/bl_pc_boot.csv', index=False); print(BO.round(3).to_string(index=False)); R['boot'] = BO.round(4).to_dict('records')
# (2) pace vs age inside the edge seconds
B = pd.read_pickle(f'{OUT}/bl_bk_S.pkl.gz'); cum = lambda ts, t: np.searchsorted(ts, t - 3, 'left')
RT = {k: np.sort(Pr[(Pr.und == k[0]) & (Pr.expiry == k[1]) & Pr.reactive].te.values) for k in cyc}; TT = {k: np.sort(Pr[(Pr.und == k[0]) & (Pr.expiry == k[1])].te.values) for k in cyc}
g30 = np.arange(33300, 60000, 30); CR = {k: np.array([cum(RT[k], t) for t in g30]) for k in cyc}; CT = {k: np.array([cum(TT[k], t) for t in g30]) for k in cyc}
def lo2(D, k, t): i = int((t - 33300) // 30); return np.mean([D[q][i] for q in cyc if q != k])
B['n_react'] = [cum(RT[(r.und, r.expiry)], r.t) for r in B.itertuples()]; B['def_react'] = [lo2(CR, (r.und, r.expiry), r.t) - cum(RT[(r.und, r.expiry)], r.t) for r in B.itertuples()]; B['def_tot'] = [lo2(CT, (r.und, r.expiry), r.t) - cum(TT[(r.und, r.expiry)], r.t) for r in B.itertuples()]
def age(r): ts = RT[(r.und, r.expiry)]; ts = ts[ts < r.t - 3]; return (r.t - ts.max()) / 60 if len(ts) else np.nan
B['age_f'] = [age(r) for r in B.itertuples()]; B['age_f'] = B.age_f.fillna((B.t - 33300) / 60); B['lage'] = np.log1p(B.age_f); B['tsec'] = (B.t - 37800) / 3600
def auc(s, y): n1 = y.sum(); n0 = len(y) - n1; return (rankdata(s)[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
d = B[B.pos_N60.abs() > 0.5].reset_index(drop=True); y = d.y.values; cid = d.cid.values; ucy = np.unique(cid)
def loco(cols):
    X = d[cols].values.astype(float); p = np.zeros(len(y))
    for c in ucy: te = cid == c; sc = StandardScaler().fit(X[~te]); p[te] = LogisticRegression(C=1.0).fit(sc.transform(X[~te]), y[~te]).predict_proba(sc.transform(X[te]))[:, 1]
    return p
MS = {'time since the last reactive pair': ['age_f', 'lage'], 'pace deficit in reactive pairs': ['def_react'], 'pace deficit in all pairs': ['def_tot'], 'time since last pair + pace deficit (reactive)': ['age_f', 'lage', 'def_react'], 'time since last pair + pace deficit (all pairs)': ['age_f', 'lage', 'def_tot'], 'time since last pair + count so far + time of day': ['age_f', 'lage', 'n_react', 'tsec']}
PR = {k: loco(v) for k, v in MS.items()}; gi = {c: np.where(cid == c)[0] for c in ucy}; bs = [np.concatenate([gi[c] for c in rng.choice(ucy, len(ucy))]) for _ in range(800)]; rows = []
for k, p in PR.items():
    dd = [auc(p[b], y[b]) - auc(PR['time since the last reactive pair'][b], y[b]) for b in bs]; rows.append(dict(model=k, AUC=auc(p, y), gain_vs_age_only=auc(p, y) - auc(PR['time since the last reactive pair'], y), lo=np.quantile(dd, .025), hi=np.quantile(dd, .975), n=len(d), events=int(y.sum())))
AG = pd.DataFrame(rows); AG.round(4).to_csv(f'{OUT}/bl_pc_age.csv', index=False); print(AG.round(3).to_string(index=False)); R['age'] = AG.round(4).to_dict('records')
# (3) catch-up signature and fires per cycle
F = pd.read_csv(f'{OUT}/bl_trk_fires.csv'); a = []; b = []; G = []
for k, g in F.groupby(['und', 'expiry']):
    gp = np.diff(np.sort(g.t.values)) / 60
    for i in range(len(gp) - 1): a.append(gp[i]); b.append(gp[i + 1]); G.append((gp[i], gp[i + 1]))
rr = spearmanr(a, b); null = []
for _ in range(2000):
    aa = []; bb = []
    for k, g in F.groupby(['und', 'expiry']): gp = rng.permutation(np.diff(np.sort(g.t.values)) / 60); aa += list(gp[:-1]); bb += list(gp[1:])
    null.append(spearmanr(aa, bb)[0])
G = pd.DataFrame(G, columns=['gap', 'next']); R['gap_autocorr'] = dict(rho=float(rr[0]), null_mean=float(np.mean(null)), percentile=float(np.mean(np.array(null) <= rr[0])), n=len(a)); R['next_gap_after_long_gap_median'] = float(G[G.gap > 50].next.median()); R['next_gap_after_short_gap_median'] = float(G[G.gap <= 15].next.median())
nf = F.groupby(['und', 'expiry']).size(); R['fires_per_cycle'] = dict(mean=float(nf.mean()), sd=float(nf.std()), var_over_mean=float(nf.var() / nf.mean()), target_285min_over_30=285 / 30)

# (4) pace quintiles inside the range-edge seconds, and the deficit in open short lots / notional (count of entries vs exposure)
q = pd.qcut(d.def_react, 5, duplicates='drop'); t = d.groupby(q, observed=True).y.agg(['size', 'sum']); t['events_per_control_second'] = t['sum'] / (t['size'] - t['sum']); R['pace_quintiles'] = [dict(bin=str(i), seconds=int(r['size']), events=int(r['sum']), events_per_control_second=float(r.events_per_control_second)) for i, r in t.iterrows()]
q = pd.qcut(d.def_tot, 5, duplicates='drop'); t = d.groupby(q, observed=True).y.agg(['size', 'sum']); t['events_per_control_second'] = t['sum'] / (t['size'] - t['sum']); R['pace_quintiles_total'] = [dict(bin=str(i), seconds=int(r['size']), events=int(r['sum']), events_per_control_second=float(r.events_per_control_second)) for i, r in t.iterrows()]
src = open('bl_bk_build.py').read().split('def feats')[0]; exec(src)
unit = {(r.und, r.expiry): r.unit for r in CY.itertuples()}; grid = np.arange(33300 + 60, 33300 + 22500, 60); SHORT = {}
for k in cyc:
    cb = CycleBook(k[0], k[1], unit[k]); sl = []
    for tt_ in grid: j = int((tt_ - 33300) // 60); pm = min(max(j - 1, 0), 374); f = cb.state(tt_, cb.sp[max(j - 1, 0)], pm); sl.append(f.get('short_lots', np.nan))
    SHORT[k] = np.array(sl)
gi_ = lambda t_: min(max(int((t_ - 33300 - 60) // 60), 0), len(grid) - 1)
B['short_now'] = [SHORT[(r.und, r.expiry)][gi_(r.t)] for r in B.itertuples()]; B['short_exp'] = [np.nanmean([SHORT[q_][gi_(r.t)] for q_ in cyc if q_ != (r.und, r.expiry)]) for r in B.itertuples()]; B['def_short'] = B.short_exp - B.short_now
half_ = B.cid.values % 2 == 0; edge_ = (B.pos_N60.abs() > 0.5).values; yy = B.y.values; x = B.def_short.values.astype(float)
R['def_short_auc_within_edge'] = [float(auc(x[edge_], yy[edge_])), float(auc(x[edge_ & half_], yy[edge_ & half_])), float(auc(x[edge_ & ~half_], yy[edge_ & ~half_]))]; x2 = B.def_tot.values.astype(float); R['def_tot_auc_within_edge'] = [float(auc(x2[edge_], yy[edge_])), float(auc(x2[edge_ & half_], yy[edge_ & half_])), float(auc(x2[edge_ & ~half_], yy[edge_ & ~half_]))]; x3 = B.def_react.values.astype(float); R['def_react_auc_within_edge'] = [float(auc(x3[edge_], yy[edge_])), float(auc(x3[edge_ & half_], yy[edge_ & half_])), float(auc(x3[edge_ & ~half_], yy[edge_ & ~half_]))]
print('def_short', R['def_short_auc_within_edge'], 'def_tot', R['def_tot_auc_within_edge'], 'def_react', R['def_react_auc_within_edge']); print(R['pace_quintiles'])
print(json.dumps({k: v for k, v in R.items() if k in ('gap_autocorr',)}, default=float)); rec('pc2', R)
