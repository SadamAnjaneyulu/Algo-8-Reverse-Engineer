"""Learned policies, step 2 (plan D1_ML_PLAN.md): train the solo-sell and buy-back policies on training cycles, choose their thresholds by an inner 2-fold cross-fit inside the training cycles, run the free-running simulator on the test cycles.
Setups: out-of-fold cycle halves; forward A (same version); forward B (version change). Variants: baseline (decoded rules), + sell policy, + buy-back policy, + both.
Outputs bl_ml_fit.csv, bl_ml_classes.csv, bl_ml_full.pkl.gz, bl_summary_ml1.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
src = open('bl_fr_score.py').read(); exec(src[:src.index("CLS_ROWS = []")])
fw = open('bl_fwd.py').read(); exec(fw[fw.index("CYd = CY.reset_index()"):fw.index("rows = []; cls_rows = []")])
from sklearn.ensemble import HistGradientBoostingClassifier
XS = pd.read_pickle(f'{OUT}/bl_ml_sell.pkl.gz'); MKT = pd.read_pickle(f'{OUT}/bl_ml_mkt.pkl.gz'); LB = pd.read_pickle(f'{OUT}/bl_ml_bb.pkl.gz')
SC = ['is_ce'] + MKT['cols'] + ['own_ratio', 'other_ratio', 'own_lots', 'other_lots']; BC = ['ratio_c', 'ratio_h', 'held', 'typ_code', 'adv', 'vel3', 'don30', 'right_ratio', 'n_open', 'j']
XS['yc'] = XS.y.clip(upper=5)
gb = lambda: HistGradientBoostingClassifier(max_depth=4, learning_rate=0.05, max_iter=200, min_samples_leaf=20, l2_regularization=1.0, random_state=0)
def sell_lots(pp, cls_, t):
    cum = np.stack([pp[:, cls_ >= k].sum(1) for k in range(1, int(cls_.max()) + 1)], 1); return (cum >= t).sum(1)
def fit_sell(train):
    d = XS[XS.cid.isin(train)]; oof = np.zeros((len(d), 6)); cls_all = np.arange(6); pos = {c: n % 2 for n, c in enumerate(sorted(train))}; inner = d.cid.map(pos).values
    for h_ in (0, 1):
        tr = inner == h_; m = gb().fit(d.loc[tr, SC].values.astype(float), d.yc.values[tr]); pr = m.predict_proba(d.loc[~tr, SC].values.astype(float)); full = np.zeros((pr.shape[0], 6)); full[:, m.classes_] = pr; oof[~tr] = full
    best = None
    for t in np.arange(0.15, 0.71, 0.025):
        n = sell_lots(oof, cls_all, t); tp = np.minimum(n, d.y.values).sum(); f = 2 * tp / (n.sum() + d.y.sum())
        if best is None or f > best[0]: best = (f, t)
    return dict(model=gb().fit(d[SC].values.astype(float), d.yc.values), t=float(best[1]), mkt=MKT['arr'], cv_f1=float(best[0]))
def bb_f1(d, p, tau):
    f = d[p >= tau].groupby('lid').j.min(); L_ = d.groupby('lid').bb_j.first(); pred = L_.index.map(f); ok = (~pd.isna(pred)) & (~L_.isna()) & (np.abs(pd.Series(pred, index=L_.index).astype(float) - L_) <= 1)
    tp = int(ok.sum()); return 2 * tp / max(int((~pd.isna(pred)).sum()) + int((~L_.isna()).sum()), 1)
def fit_bb(train):
    d = LB[LB.cid.isin(train)].reset_index(drop=True); oof = np.zeros(len(d)); pos = {c: n % 2 for n, c in enumerate(sorted(train))}; inner = d.cid.map(pos).values
    for h_ in (0, 1):
        tr = inner == h_; m = gb().fit(d.loc[tr, BC].values.astype(float), d.y.values[tr]); oof[~tr] = m.predict_proba(d.loc[~tr, BC].values.astype(float))[:, 1]
    best = max(((bb_f1(d, oof, tau), tau) for tau in (0.05, 0.08, 0.1, 0.12, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5)), key=lambda x: x[0])
    return dict(model=gb().fit(d[BC].values.astype(float), d.y.values), tau=float(best[1]), cv_f1=float(best[0]))
def tbl(orders, cids, label):
    global ids
    keep = ids; ids = cids; T, ov = table(orders, label); ids = keep; return T, ov
R = {}; rows = []; crow = []; FULLS = {}
SETUPS = [('out-of-fold halves', [([i for i in ids if i % 2 == h_], [i for i in ids if i % 2 != h_], None) for h_ in (0, 1)])] + [(nm, [(tr, te, nm)]) for nm, (tr, te) in SPL.items()]
for setup, folds in SETUPS:
    res = {v: {} for v in ('baseline', '+ sell policy', '+ buy-back policy', '+ both policies')}; info = []
    for tr, te, nm in folds:
        if nm:
            vmap = {'V1': 'V1', 'V2': 'V2'} if nm.startswith('A') else {'V1': 'V1', 'V2': 'V1'}; S.W = timetable(tr, vmap); P = fit_train(tr); P['lump_t'] = lump_t_from(tr)[0]
        else:
            P = fit_params(tr); P.update(bb_price='high', bb_vel=None, bb_mkt=None, bb_lo=None, bb_cluster=None, theta=1.6, tp=0.4)
        ms = fit_sell(tr); mb = fit_bb(tr); info.append(dict(setup=setup, sell_t=ms['t'], sell_cv_f1=round(ms['cv_f1'], 4), bb_tau=mb['tau'], bb_cv_f1=round(mb['cv_f1'], 4))); print(info[-1], flush=True)
        for v, add in (('baseline', {}), ('+ sell policy', dict(ml_sell=ms)), ('+ buy-back policy', dict(ml_bb=mb)), ('+ both policies', dict(ml_sell=ms, ml_bb=mb))):
            full = {i: S.sim_cycle(i, dict(P, **add), 'free') for i in te}; res[v].update({i: t[0] for i, t in full.items()})
            if setup.startswith('out-of-fold'): FULLS.setdefault(v, {}).update(full)
        S.W = W_full
    cids = sorted(res['baseline'])
    for v in res:
        T, ov = tbl(res[v], cids, f'{setup} | {v}'); crow.append(T.assign(setup=setup, model=v)); rows.append(dict(setup=setup, model=v, cycles=len(cids), F1=ov['F1'], precision=ov['precision'], recall=ov['recall'], F1_within1=ov['F1_within1'], F1_strict=ov['F1_strict'])); print(rows[-1], flush=True)
    R[setup] = info
pd.DataFrame(rows).round(4).to_csv(f'{OUT}/bl_ml_fit.csv', index=False); pd.concat(crow).round(4).to_csv(f'{OUT}/bl_ml_classes.csv', index=False); pd.to_pickle(FULLS, f'{OUT}/bl_ml_full.pkl.gz'); rec('ml1', dict(info=R, rows=pd.DataFrame(rows).round(4).to_dict('records')))
