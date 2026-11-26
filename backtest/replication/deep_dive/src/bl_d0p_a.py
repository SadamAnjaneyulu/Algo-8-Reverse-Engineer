"""Part A of reports/D0_PAIR_PLAN.md: what else decides the sale of the other right after a stop-loss buy-back.
Outputs bl_d0p_a0.csv, bl_d0p_a0_lag.csv, bl_d0p_a2.csv, bl_d0p_a2_imp.csv, bl_d0p_a3.csv, bl_d0p_a4.csv, bl_d0p_events.pkl.gz, bl_summary_d0p1.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from sklearn.ensemble import HistGradientBoostingClassifier as HGB
from sklearn.tree import DecisionTreeClassifier as DT, export_text
from sklearn.metrics import roc_auc_score
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); SO = pd.read_pickle(f'{OUT}/bl_d0n_orders.pkl.gz'); PN = pd.read_pickle(f'{OUT}/bl_d0n_panel.pkl.gz'); X = pd.read_pickle(f'{OUT}/bl_d0y_lots.pkl.gz'); OPT = pd.read_pickle(f'{OUT}/bl_d0_opt.pkl.gz'); O = load_orders()
rng = np.random.default_rng(151); R = {}; other = lambda c: 'PE' if c == 'CE' else 'CE'
EV = X[X.type == '3 stop-loss'].groupby(['cid', 'cp', 'tod']).agg(lots=('lid', 'size'), j=('j', 'min')).reset_index(); K = PN.set_index(['cid', 'j', 'cp'])
mk = lambda: HGB(max_iter=200, max_depth=3, learning_rate=0.05, min_samples_leaf=50, l2_regularization=1.0, random_state=0)
# ---------- A0: excess over chance, lag histogram (all stop-loss events, including those outside the panel)
def lagsets(ev, shift=0):
    out = []
    for q in ev.itertuples():
        s = SO[(SO.cid == q.cid) & (SO.cp == other(q.cp))].tod.values; out.append(s - (q.tod + shift))
    return out
L0 = lagsets(EV); LN = [lagsets(EV, s) for s in (900, -900)]; rows = []
for W in (2, 5, 10, 60):
    real = np.mean([bool((np.abs(d) <= W).any()) for d in L0]); nul = np.mean([np.mean([bool((np.abs(d) <= W).any()) for d in LL]) for LL in LN]); rows.append(dict(window_s=W, share_events_real=real, share_events_null=nul, excess=real - nul, ratio=real / max(nul, 1e-9)))
A0 = pd.DataFrame(rows); A0.to_csv(f'{OUT}/bl_d0p_a0.csv', index=False); print(A0.round(3).to_string(index=False))
edges = [0, 1, 2, 5, 10, 30, 60, 120]; rows = []
first = [d[np.argmin(np.abs(d))] if len(d) and np.abs(d).min() <= 120 else np.nan for d in L0]; fn = [np.array([d[np.argmin(np.abs(d))] if len(d) and np.abs(d).min() <= 120 else np.nan for d in LL]) for LL in LN]; first = np.array(first)
for a, b in zip(edges[:-1], edges[1:]):
    for sg, nm in ((-1, 'sale before'), (1, 'sale after')):
        m = (sg * first >= a) & (sg * first < b) if a > 0 else (sg * first >= 0) & (sg * first < b) & ((first != 0) | (sg == 1))
        mn = np.mean([((sg * f >= a) & (sg * f < b)).mean() for f in fn]); rows.append(dict(bin=f'{a}-{b} s', side=nm, share_events=float(np.mean(m)), null=float(mn)))
pd.DataFrame(rows).to_csv(f'{OUT}/bl_d0p_a0_lag.csv', index=False)
# ---------- event features (events inside the panel)
body = O[(O.module == 'num') & (O.dayno == 1) & (O.role == 'open_short')].copy(); cmap = {(u, str(e)): i for i, (u, e) in enumerate(zip(CY.und, CY.expiry))}; body['cid'] = [cmap.get((a, str(b)), -1) for a, b in zip(body.und, body.expiry)]; body = body[body.cid >= 0]
feat = []
for q in EV.itertuples():
    o = other(q.cp); a = (q.cid, int(q.j), o)
    if a not in K.index: continue
    p = K.loc[a]; r = CY.iloc[q.cid]; op = OPT[(r.und, r.expiry)]; Kk = op['K']; kidx = {int(k): n for n, k in enumerate(Kk)}; j1 = int(q.j) - 1; P = op[(o, 'close')]
    b = body[(body.cid == q.cid) & (body.cp == o) & (body.tod < q.tod)].sort_values('tod'); s_ = SO[(SO.cid == q.cid) & (SO.cp == o) & (SO.tod < q.tod)].sort_values('tod'); atm = int(Kk[np.argmin(np.abs(Kk - SP_close)) ]) if False else None
    f = dict(cid=q.cid, cp=q.cp, tod=q.tod, j=int(q.j), lots_bought=q.lots)
    for W in (2, 10, 60):
        d = SO[(SO.cid == q.cid) & (SO.cp == o)].tod.values - q.tod; f[f'sale_{W}'] = float(((d >= 0) & (d <= W)).any()); f[f'salepm_{W}'] = float((np.abs(d) <= W).any())     # sale_W = at or after the buy-back (outcome of the models); salepm = either side (descriptive only)
    if len(b):
        l = b.iloc[-1]; f['ladder_same_contract'] = P[kidx[int(l.strike)], j1] / l.px_avg if int(l.strike) in kidx and l.px_avg > 0 else np.nan; f['ladder_atm_vs_last_sale'] = p.atm_px / l.px_avg if l.px_avg > 0 else np.nan; f['secs_since_any_R_sale'] = min(q.tod - l.tod, 3600)
    else: f['ladder_same_contract'] = np.nan; f['ladder_atm_vs_last_sale'] = np.nan; f['secs_since_any_R_sale'] = 3600
    if len(s_):
        l = s_.iloc[-1]; f['ladder_same_contract_solo'] = P[kidx[int(l.strike)], j1] / l.px if int(l.strike) in kidx and l.px > 0 else np.nan; f['secs_since_solo_R_sale'] = min(q.tod - l.tod, 3600)
    else: f['ladder_same_contract_solo'] = np.nan; f['secs_since_solo_R_sale'] = 3600
    f['R_solo_sales_prev60s'] = float(((s_.tod >= q.tod - 60)).sum()) if len(s_) else 0.0
    for k_ in ('phx_prem_low_60', 'prem_vs_daymin', 'prem_chg_1', 'prem_chg_3', 'prem_chg_5', 'n_own', 'n_other', 'share_own', 'expo_share_own', 'fav_ret_1', 'fav_ret_5', 'fav_ret_15', 'min_in_15', 'hour', 'und_nifty', 'v2', 'sell_own_5', 'sell_own_15'): f[k_] = p[k_]
    feat.append(f)
E = pd.DataFrame(feat); E.to_pickle(f'{OUT}/bl_d0p_events.pkl.gz'); print(len(E), E[['sale_2', 'sale_10', 'sale_60', 'salepm_2', 'salepm_10', 'salepm_60']].mean().round(3).to_dict()); R['events_in_panel'] = len(E); R['sale_rates'] = E[['sale_2', 'sale_10', 'sale_60', 'salepm_2', 'salepm_10', 'salepm_60']].mean().to_dict()
FAM = dict(
    F1_premium_low=['phx_prem_low_60', 'prem_vs_daymin', 'prem_chg_1', 'prem_chg_3', 'prem_chg_5'],
    F2_ladder_step=['ladder_same_contract', 'ladder_atm_vs_last_sale', 'ladder_same_contract_solo'],
    F3_recent_sales=['R_solo_sales_prev60s', 'secs_since_any_R_sale', 'secs_since_solo_R_sale', 'sell_own_5', 'sell_own_15'],
    F4_lots=['n_own', 'n_other', 'share_own', 'expo_share_own'], F5_size=['lots_bought'], F6_spot=['fav_ret_1', 'fav_ret_5', 'fav_ret_15'], F7_clock=['min_in_15', 'hour'], F8_cycle=['und_nifty', 'v2'])
def loco(df, cols, y, perm=False):
    Xm = df[cols].values.copy(); yv = df[y].values; p = np.full(len(df), np.nan)
    if perm:
        for c_ in df.cid.unique(): m = np.where((df.cid == c_).values)[0]; Xm[m] = Xm[rng.permutation(m)]
    for c_ in df.cid.unique():
        te = (df.cid == c_).values
        if len(set(yv[~te])) < 2: continue
        p[te] = mk().fit(Xm[~te], yv[~te]).predict_proba(Xm[te])[:, 1]
    return p
def auc_ci(df, p, y, nb=300):
    ok = ~np.isnan(p); d = df[ok].reset_index(drop=True); pp = p[ok]; u = d.cid.unique(); idx = {c_: np.where(d.cid.values == c_)[0] for c_ in u}; b = []
    for _ in range(nb):
        k = np.concatenate([idx[c_] for c_ in rng.choice(u, len(u))]); yy = d[y].values[k]
        if yy.min() != yy.max(): b.append(roc_auc_score(yy, pp[k]))
    return roc_auc_score(d[y], pp), np.percentile(b, 2.5), np.percentile(b, 97.5)
allc = sum(FAM.values(), []); rows = []; imp_all = {}
for y in ('sale_2', 'sale_10', 'sale_60'):
    a = auc_ci(E, loco(E, allc, y), y); rows.append(dict(outcome=y, model='all factors', auc=a[0], lo=a[1], hi=a[2], positive_rate=E[y].mean()))
    pl = auc_ci(E, loco(E, allc, y, perm=True), y); rows.append(dict(outcome=y, model='placebo (features shuffled within cycle)', auc=pl[0], lo=pl[1], hi=pl[2], positive_rate=E[y].mean()))
    for fam, cols in FAM.items():
        a = auc_ci(E, loco(E, cols, y), y); rows.append(dict(outcome=y, model=f'only {fam}', auc=a[0], lo=a[1], hi=a[2], positive_rate=E[y].mean()))
        a = auc_ci(E, loco(E, [c_ for c_ in allc if c_ not in cols], y), y); rows.append(dict(outcome=y, model=f'all minus {fam}', auc=a[0], lo=a[1], hi=a[2], positive_rate=E[y].mean()))
    print(y, 'done')
A2 = pd.DataFrame(rows); A2.to_csv(f'{OUT}/bl_d0p_a2.csv', index=False)
imp = {c_: [] for c_ in allc}
for c_cid in E.cid.unique():
    te = (E.cid == c_cid).values; yt = E[te].sale_10.values
    if yt.min() == yt.max(): continue
    m = mk().fit(E[~te][allc].values, E[~te].sale_10.values); Xt = E[te][allc].values.copy(); b0 = roc_auc_score(yt, m.predict_proba(Xt)[:, 1])
    for k, f_ in enumerate(allc): Xs = Xt.copy(); Xs[:, k] = rng.permutation(Xs[:, k]); imp[f_].append(b0 - roc_auc_score(yt, m.predict_proba(Xs)[:, 1]))
IM = pd.DataFrame([dict(feature=f_, drop_in_auc=np.mean(v), family=[g for g in FAM if f_ in FAM[g]][0]) for f_, v in imp.items()]).sort_values('drop_in_auc', ascending=False); IM.to_csv(f'{OUT}/bl_d0p_a2_imp.csv', index=False); print(IM.head(10).round(4).to_string(index=False))
# ---------- A3 gate test: LOCO stump on the top feature; and a depth-2 tree on the top two
def gate(cols, y='sale_10', depth=1):
    on = np.zeros(len(E), bool); pr = np.zeros(len(E)); Xm = np.nan_to_num(E[cols].values, nan=-9.0)
    for c_ in E.cid.unique():
        te = (E.cid == c_).values; t = DT(max_depth=depth, min_samples_leaf=40, random_state=0).fit(Xm[~te], E[~te][y].values); pr[te] = t.predict_proba(Xm[te])[:, 1]
    on = pr >= 0.5; return on, pr
top = list(IM.feature[:2]); rows = []
for nm, cols, dp in ((f'stump on {top[0]}', [top[0]], 1), (f'stump on {top[1]}', [top[1]], 1), (f'depth-2 tree on {top[0]} + {top[1]}', top, 2)):
    on, pr = gate(cols, depth=dp); rows.append(dict(rule=nm, share_events_on=float(on.mean()), p_sale_10s_on=float(E.sale_10[on].mean()) if on.any() else np.nan, p_sale_10s_off=float(E.sale_10[~on].mean()), p_sale_2s_on=float(E.sale_2[on].mean()) if on.any() else np.nan, p_sale_2s_off=float(E.sale_2[~on].mean()), p_sale_60s_on=float(E.sale_60[on].mean()) if on.any() else np.nan, p_sale_60s_off=float(E.sale_60[~on].mean())))
A3 = pd.DataFrame(rows); A3['gate_accepted'] = (A3.p_sale_10s_on >= 0.60) & (A3.p_sale_10s_off <= 0.20); A3.to_csv(f'{OUT}/bl_d0p_a3.csv', index=False); print(A3.round(3).to_string(index=False))
t = DT(max_depth=2, min_samples_leaf=40, random_state=0).fit(np.nan_to_num(E[top].values, nan=-9.0), E.sale_10.values); R['a3_tree'] = export_text(t, feature_names=top)
# ladder-step rate table
E['ladder_bin'] = pd.cut(E.ladder_same_contract, [0, 0.7, 0.8, 0.9, 1.0, 1.1, 5]); R['ladder_bins'] = {str(k): dict(n=int(g.shape[0]), sale_2=float(g.sale_2.mean()), sale_10=float(g.sale_10.mean()), sale_60=float(g.sale_60.mean())) for k, g in E.groupby('ladder_bin', observed=True)}
R['low60_rates'] = {str(k): dict(n=int(g.shape[0]), sale_2=float(g.sale_2.mean()), sale_10=float(g.sale_10.mean()), sale_60=float(g.sale_60.mean())) for k, g in E.groupby('phx_prem_low_60')}
R['recent_sale_rates'] = {str(k): dict(n=int(g.shape[0]), sale_2=float(g.sale_2.mean()), sale_10=float(g.sale_10.mean()), sale_60=float(g.sale_60.mean())) for k, g in E.groupby(E.R_solo_sales_prev60s > 0)}
# ---------- A4 late sales: events with no sale within +-60 s
rows = []
for q in E[E.sale_60 == 0].itertuples():
    s = SO[(SO.cid == q.cid) & (SO.cp == other(q.cp)) & (SO.tod > q.tod + 60)]; rows.append(dict(wait_min=(s.tod.min() - q.tod) / 60 if len(s) else np.nan, has_next=len(s) > 0))
W = pd.DataFrame(rows); W.to_csv(f'{OUT}/bl_d0p_a4.csv', index=False); R['a4'] = dict(events_no_sale_60=len(W), share_with_a_later_sale=float(W.has_next.mean()), wait_min_q=W.wait_min.quantile([.25, .5, .75, .9]).tolist(), within_5min=float((W.wait_min <= 5).mean()), within_15min=float((W.wait_min <= 15).mean()))
R['a0'] = A0.round(4).to_dict('records'); R['a2_top'] = IM.head(10).round(4).to_dict('records'); R['a3'] = A3.round(4).to_dict('records'); rec('d0p1', R); print(R['a4']); print(R['ladder_bins']); print(R['low60_rates'], R['recent_sale_rates'])
print(A2[A2.outcome == 'sale_10'].round(3).to_string(index=False))
