"""Forward (unseen-cycle) test of the complete D-1 reconstruction. Everything learned from earlier cycles only: scheduled timetable (minutes with a scheduled sale in >= 50% of training cycles of that version, waves per minute = median), lump time (the regime of the latest training cycle), reactive size / extras / buy-back stop / lump ratio / opening offset (fit_params + grids on training cycles), and for the AUC a gradient-boosting model trained on training cycles only (timetable share recomputed from training cycles).
Split A (same version, chronological): V1 first 14 / last 7, V2 first 7 / last 4. Split B (version change): train all V1 (21), test all V2 (11), V1 timetable applied to V2.
Compared with the out-of-fold (cycle halves) scores on the same test cycles. Outputs bl_fwd.csv, bl_fwd_classes.csv, bl_summary_fwd1.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
src = open('bl_fr_score.py').read(); exec(src[:src.index("CLS_ROWS = []")])
from sklearn.metrics import roc_auc_score
from sklearn.ensemble import HistGradientBoostingClassifier
CYd = CY.reset_index().rename(columns={'index': 'cid'}); R = {}
v1 = CYd[CYd.version == 'V1'].sort_values('d1').cid.tolist(); v2 = CYd[CYd.version == 'V2'].sort_values('d1').cid.tolist()
SPL = {'A same version (V1 14->7, V2 7->4)': (v1[:14] + v2[:7], v1[14:] + v2[7:]), 'B version change (train V1, test V2)': (v1, v2)}
SDo = pd.read_pickle(f'{OUT}/bl_sd_orders.pkl.gz'); W_full = S.W.copy()
def timetable(train, version_map):
    rows = []
    for ver, src_ver in version_map.items():
        tc = [i for i in train if CY.iloc[i].version == src_ver]
        if not tc: continue
        z = SDo[SDo.cid.isin(tc) & (SDo.typ == 'scheduled') & (SDo.cp == 'CE')]; cnt = z.groupby(['cid', 'j']).lots.sum().unstack(fill_value=0).reindex(tc, fill_value=0)
        share = (cnt > 0).mean(); med = cnt.median()
        for j in share.index[share >= 0.5]:
            for _ in range(max(int(round(med[j])), 1)): rows.append(dict(version=ver, sec_after_0916=(j - 1) * 60 + 30))
    return pd.DataFrame(rows)
def lump_t_from(train):
    last = CY.iloc[max(train, key=lambda i: CY.iloc[i].d1)]; rg = S.regime(last.d1); LP = pd.read_csv(f'{OUT}/bl_lp_dec.csv'); m = LP[(LP.main == 1) & LP.cid.isin([i for i in train if S.regime(CY.iloc[i].d1) == rg])]
    t = int(np.median((m.t - 33300) // 60)); return {'r1': t, 'r2': t, 'r3': t}, rg
def fit_train(train):
    P = fit_params(train); P.update(bb_price='high', bb_vel=None, bb_mkt=None, bb_lo=None, bb_cluster=None); best = None
    for tp in (0.25, 0.4, 0.5, 0.75, 1.0):
        P['tp'] = tp; P['theta'] = 1.6; rr = score(OO(run(train, P, 'free')), train, step_of)['body_sell']; v = f1(rr['tp'], rr['sim'], rr['real'])
        if best is None or v > best[0]: best = (v, tp)
    P['tp'] = best[1]; best = None
    for th in (1.5, 1.55, 1.6, 1.65, 1.7):
        P['theta'] = th; rr = score(OO(run(train, P, 'free')), train, step_of)['body_buyback']; v = f1(rr['tp'], rr['sim'], rr['real'])
        if best is None or v > best[0]: best = (v, th)
    P['theta'] = best[1]; return P
rows = []; cls_rows = []
# out-of-fold reference: the primary free-running orders (cycle halves) from bl_fr_score
REF = pd.read_pickle(f'{OUT}/bl_fr_orders.pkl.gz')['FR free-running (primary)']
FP = pd.read_pickle(f'{OUT}/bl_full_panel.pkl.gz'); BASE = [c for c in ['sched_share', 'react_fire', 'react_fav', 'react_depth', 'pl5_itm', 'pl15_itm', 'pl30_itm', 'pl5_atm', 'pl15_atm', 'pl30_atm', 'fav5', 'bk5', 'bkhl5', 'fav15', 'bk15', 'bkhl15', 'fav30', 'bk30', 'bkhl30', 'fav60', 'bk60', 'bkhl60', 'pos15', 'S', 'L', 'gap', 'excess', 'S_other', 'heavy', 'numlong', 'maxratio_c', 'maxratio_h', 'minute', 'opening', 'lump_win', 'after_1530', 'is_ce', 'adv1', 'adv5'] if c in FP.columns]
for name, (train, test) in SPL.items():
    vmap = {'V1': 'V1', 'V2': 'V2'} if name.startswith('A') else {'V1': 'V1', 'V2': 'V1'}
    S.W = timetable(train, vmap); P = fit_train(train); lt, rg = lump_t_from(train); P['lump_t'] = lt
    orders = OO(run(test, P, 'free')); S.W = W_full
    ids_all = ids; ids = test
    T, ov = table(orders, name); cls_rows.append(T.assign(split=name))
    Tr, ovr = table({i: REF[i] for i in test}, 'ref'); ids = ids_all
    # AUC: any-activity model trained on training cycles only, timetable share from training cycles of the mapped version
    X = FP.copy(); share = {}
    for ver, srcv in vmap.items():
        tc = [i for i in train if CY.iloc[i].version == srcv]; g = X[X.cid.isin(tc)].groupby(['j', 'cp']).y_body_sell.mean()
        share[ver] = g
    X['sched_tr'] = [share.get(CY.iloc[c].version, pd.Series(dtype=float)).get((j, cp), 0.0) for c, j, cp in zip(X.cid, X.j, X.cp)]
    cols = [c for c in BASE if c != 'sched_share'] + ['sched_tr']; tr = X.cid.isin(train).values; te = X.cid.isin(test).values
    m = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=150, min_samples_leaf=20, l2_regularization=1.0, random_state=0).fit(X.loc[tr, cols].values.astype(float), X.y_any.values[tr])
    auc_fwd = roc_auc_score(X.y_any.values[te], m.predict_proba(X.loc[te, cols].values.astype(float))[:, 1])
    PR = pd.read_pickle(f'{OUT}/bl_full_pred.pkl.gz'); key = [k for k in PR if k[1] == 'any' and k[0].startswith('A same')][0]; Xs = FP.sort_values(['cid', 'cp', 'j']).reset_index(drop=True)
    auc_ref = roc_auc_score(Xs.y_any.values[Xs.cid.isin(test).values], PR[key][Xs.cid.isin(test).values])
    rows.append(dict(split=name, train_cycles=len(train), test_cycles=len(test), lump_regime_used=rg, F1_forward=ov['F1'], precision_forward=ov['precision'], recall_forward=ov['recall'], F1_within1_forward=ov['F1_within1'], F1_out_of_fold_same_cycles=ovr['F1'], AUC_any_forward=auc_fwd, AUC_any_out_of_fold_same_cycles=auc_ref, theta=P['theta'], tp=P['tp']))
    print(rows[-1], flush=True); print(T[['cls', 'real_lots', 'sim_lots', 'precision', 'recall', 'F1']].round(3).to_string(index=False), flush=True)
F_ = pd.DataFrame(rows); F_.round(4).to_csv(f'{OUT}/bl_fwd.csv', index=False); pd.concat(cls_rows).round(4).to_csv(f'{OUT}/bl_fwd_classes.csv', index=False); R['rows'] = F_.round(4).to_dict('records'); rec('fwd1', R)
