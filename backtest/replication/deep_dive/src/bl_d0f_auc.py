"""D0 selling, every type, scored on unseen cycles (plan reports/D0_FULL_AUC_PLAN.md).
S1 leave-one-cycle-out, S2 forward in time, S3 version change, S4 30 random cycle halves; clock features learned on training cycles only. Type assignment among sale cells.
Outputs bl_d0f_auc.csv (S1/S2/S3), bl_d0f_s4.csv, bl_d0f_types.csv, bl_d0f_confusion.csv, bl_d0f_pred_s1.pkl.gz, bl_summary_d0f1.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from multiprocessing import Pool
from bl_common import *
from sklearn.ensemble import HistGradientBoostingClassifier as HGB
from sklearn.metrics import roc_auc_score, average_precision_score
PN = pd.read_pickle(f'{OUT}/bl_d0f_panel.pkl.gz').reset_index(drop=True); PN['row'] = np.arange(len(PN)); S = pd.read_pickle(f'{OUT}/bl_d0s_orders.pkl.gz'); T = pd.read_pickle(f'{OUT}/bl_d0t_orders.pkl.gz'); PR = pd.read_csv(f'{OUT}/bl_d0e_str_pairs.csv'); R = {}
rng = np.random.default_rng(211)
# ---------------- labels: one type per order
STR = PR[PR.dk == 2]; leg = set(STR.ce_idx) | set(STR.pe_idx); S['type0'] = T.type.values; S['off'] = T.off_steps.values
S['type3'] = [('strangle pair' if ix in leg else ('far-OTM solo' if (pid < 0 and t0 != 'opening solo' and off >= 3) else t0)) for ix, pid, t0, off in zip(S.index, S.pid, S.type0, S.off)]
TYPES = ['scheduled pair', 'opening pair', 're-centre pair', 'breakout pair', 'other pair', 'strangle pair', 'opening solo', 'counter-sell solo', 'replacement solo', 'extreme solo', 'late solo', 'far-OTM solo', 'other solo']
print(S.groupby('type3').lots.sum().reindex(TYPES).to_string())
key = pd.Series(PN.row.values, index=pd.MultiIndex.from_arrays([PN.cid, PN.j, PN.cp])); S['row'] = [key.get((c, j, p), -1) for c, j, p in zip(S.cid, S.j, S.cp)]
R['lots_total'] = int(S.lots.sum()); R['lots_in_panel'] = int(S[S.row >= 0].lots.sum()); PN['y_any'] = PN.row.isin(set(S[S.row >= 0].row)).astype(float); POS = {'y_any': 'any D0 sell'}
for t in TYPES:
    PN['y_' + t] = PN.row.isin(set(S[(S.row >= 0) & (S.type3 == t)].row)).astype(float); POS['y_' + t] = t
print({k: int(PN[k].sum()) for k in POS})
# ---------------- clock indicators per cycle (kinds: any, pair, strangle, solo) and groups
cycles = sorted(PN.cid.unique()); cidx = {c: n for n, c in enumerate(cycles)}; grp = {c: (PN[PN.cid == c].und.iloc[0], PN[PN.cid == c].version.iloc[0]) for c in cycles}; NJ = 380
KINDS = ['any', 'pair', 'strangle', 'solo']; I = {k: np.zeros((len(cycles), NJ, 2)) for k in KINDS}
for q in S[S.cid.isin(cycles)].itertuples():
    n = cidx[q.cid]; r = 0 if q.cp == 'CE' else 1; j = int(q.j)
    if not 0 <= j < NJ: continue
    I['any'][n, j, r] = 1
    if q.type3 == 'strangle pair': I['strangle'][n, j, r] = 1
    elif q.pid >= 0: I['pair'][n, j, r] = 1
    else: I['solo'][n, j, r] = 1
rowc = PN.cid.map(cidx).values; rowj = PN.j.values.astype(int); rowr = (PN.cp == 'PE').astype(int).values; rowg = np.array([hash(grp[c]) for c in PN.cid]); G_OF = {n: grp[c] for n, c in enumerate(cycles)}
def clock_features(ref_mask):
    """share of reference cycles of the same group that sold in the minute on that right; a row never uses its own cycle. ref_mask: boolean over cycles."""
    out = {}
    for k in KINDS:
        tot = {}; cnt = {}
        for n in range(len(cycles)):
            if ref_mask[n]: tot[G_OF[n]] = tot.get(G_OF[n], 0) + I[k][n]; cnt[G_OF[n]] = cnt.get(G_OF[n], 0) + 1
        sh = np.zeros((len(cycles), NJ, 2))
        for n in range(len(cycles)):
            g = G_OF[n]
            if g not in tot: continue
            if ref_mask[n]: sh[n] = (tot[g] - I[k][n]) / max(cnt[g] - 1, 1) if cnt[g] > 1 else 0.0
            else: sh[n] = tot[g] / cnt[g]
        out[k] = sh
    f = pd.DataFrame({f'clk_{k}': out[k][rowc, rowj, rowr] for k in KINDS})
    a = out['any']; f['clk_any_pm1'] = np.maximum(np.maximum(a[rowc, np.clip(rowj - 1, 0, NJ - 1), rowr], a[rowc, rowj, rowr]), a[rowc, np.clip(rowj + 1, 0, NJ - 1), rowr]); return f
CLK = ['clk_any', 'clk_pair', 'clk_strangle', 'clk_solo', 'clk_any_pm1']
sys.path.insert(0, '../../../../d1_strategy'); from algo8_d1 import breakout_fires, Config            # the D-1 two-candle breakout machine, run on the D0 bars; features use fires in minutes before j only
SPT = pd.read_pickle(f'{OUT}/bl_d0_spot.pkl.gz'); CYd = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); fm = {}
for c in cycles:
    r = CYd.iloc[c]; sp = SPT[(r.und, r.expiry)]; fm[c] = sorted({j for j, _, _ in breakout_fires(sp.high.values, sp.low.values, Config(strike_step=float(ref.STEP[r.und])))})
def brk(c, j):
    f = fm[c]; prev = [x for x in f if x < j]; return float((j - 1) in f), float((j - 2) in f), float(min(j - prev[-1], 99)) if prev else 99.0
B3 = np.array([brk(c, j) for c, j in zip(PN.cid, PN.j.astype(int))]); PN['brk_m1'], PN['brk_m2'], PN['brk_since'] = B3[:, 0], B3[:, 1], B3[:, 2]
FAM = dict(base=['hour', 'min_in_15', 'min_in_5', 'is_ce', 'und_nifty', 'v2', 'j', 'gap_fav', 'carried_own', 'carried_other'],
    spot=['fav_ret_1', 'fav_ret_3', 'fav_ret_5', 'fav_ret_15', 'fav_ret_30', 'fav_ret_60', 'fresh_15', 'fresh_30', 'fresh_60', 'fresh_120', 'fresh_day', 'dist_day_ext', 'from_open', 'vol15', 'bars_since_fresh60'],
    prem=['atm_px', 'prem_chg_1', 'prem_chg_3', 'prem_chg_5', 'prem_chg_15', 'prem_vs_daymax', 'prem_vs_daymin', 'prem_vs_open', 'mark_own', 'mark_other', 'phx_prem_low_15', 'phx_prem_low_30', 'phx_prem_low_60', 'phx_prem_low_day'],
    book=['n_own', 'n_other', 'share_own', 'expo_own', 'expo_other', 'expo_share_own', 'mtm_lakh', 'mtm_to_stop', 'sell_own_1', 'sell_own_5', 'sell_own_15', 'sell_other_1', 'sell_other_5', 'sell_other_15', 'since_sale_own'],
    brk=['brk_m1', 'brk_m2', 'brk_since'],
    bb=['bb_other_1', 'bb_other_5', 'bb_other_15', 'bb_own_1', 'bb_own_5', 'bb_own_15', 'sl_other_1', 'sl_other_5', 'sl_other_15', 'sl_own_1', 'sl_own_5', 'sl_own_15', 'since_bb_other'])
PN['y_event pairs'] = ((PN['y_re-centre pair'] + PN['y_breakout pair'] + PN['y_other pair']) > 0).astype(float); POS['y_event pairs'] = 'event pairs (re-centre + breakout + other pair; post-hoc group)'
BASEC = sum(FAM.values(), []); COLS = BASEC + CLK; OUTC = list(POS)
CONT = ['fav_ret_1_c', 'fav_ret_3_c', 'fresh_60_c', 'range_c', 'prem_chg_1_c', 'phx_prem_newlow_c', 'phx_plow_bar_c']; SAME = ['bb_own_same_min', 'bb_other_same_min', 'sl_other_same_min']
mk = lambda: HGB(max_iter=200, max_depth=3, learning_rate=0.05, min_samples_leaf=50, l2_regularization=1.0, random_state=0)
XMV = {'causal': PN[BASEC].values.astype(float), 'plus the minute\'s own bar and same-minute buy-backs': PN[BASEC + CONT + SAME].values.astype(float)}; VARS = list(XMV); Y = {o: PN[o].values for o in OUTC}; CIDS = PN.cid.values
def fit_predict(task):
    tr, te, var = task; trn = np.isin(CIDS, tr); ten = np.isin(CIDS, te); ref = np.array([c in set(tr) for c in cycles]); F = clock_features(ref).values; X = np.hstack([XMV[var], F]); res = {}
    for o in OUTC:
        y = Y[o]
        if y[trn].sum() < 5 or y[ten].size == 0: res[o] = (np.where(ten)[0], np.full(ten.sum(), np.nan)); continue
        res[o] = (np.where(ten)[0], mk().fit(X[trn], y[trn]).predict_proba(X[ten])[:, 1])
    return res
def boot_auc(idx, p, y, nb=200):
    d = pd.DataFrame(dict(c=CIDS[idx], y=y[idx], p=p)); d = d[d.p.notna()]
    if d.y.nunique() < 2: return np.nan, np.nan, np.nan, np.nan, np.nan, 0
    u = d.c.unique(); ix = {c_: np.where(d.c.values == c_)[0] for c_ in u}; b = []
    for _ in range(nb):
        k = np.concatenate([ix[c_] for c_ in rng.choice(u, len(u))]); v = d.y.values[k]
        if v.min() != v.max(): b.append(roc_auc_score(v, d.p.values[k]))
    cyc = [roc_auc_score(d.y.values[ix[c_]], d.p.values[ix[c_]]) for c_ in u if 5 <= d.y.values[ix[c_]].sum() < len(ix[c_])]
    return roc_auc_score(d.y, d.p), np.percentile(b, 2.5), np.percentile(b, 97.5), average_precision_score(d.y, d.p), (float(np.mean(cyc)) if cyc else np.nan), len(cyc)
def collect(results):
    P = {o: np.full(len(PN), np.nan) for o in OUTC}
    for res in results:
        for o, (ix, p) in res.items(): P[o][ix] = p
    return P
if __name__ == '__main__':
    import time; t0 = time.time(); order = PN.groupby('cid').expiry.first().sort_values(); allc = list(order.index); pool = Pool(4); rows = []; XM = XMV['causal']
    v1 = [c for c in allc if grp[c][1] == 'V1']; v2 = [c for c in allc if grp[c][1] != 'V1']; k2 = int(len(allc) * 2 / 3); trb = []; teb = []
    for v in ('V1', 'V2'):
        cv = [c for c in allc if (grp[c][1] == 'V1') == (v == 'V1')]; kk = int(round(len(cv) * 2 / 3)); trb += cv[:kk]; teb += cv[kk:]
    PR_ = {}
    for var in VARS:
        PR_[(var, 'S1')] = collect(pool.map(fit_predict, [([c for c in allc if c != h], [h], var) for h in allc])); PR_[(var, 'S2b')] = collect([fit_predict((trb, teb, var))]); print(var, 'S1,S2b done', round(time.time() - t0))
    PR_[('causal', 'S2')] = collect([fit_predict((allc[:k2], allc[k2:], 'causal'))]); PR_[('causal', 'S3')] = collect([fit_predict((v1, v2, 'causal'))]); PR_[('causal', 'S3b')] = collect([fit_predict((v1 + v2[:3], v2[3:], 'causal'))])
    R['split_sizes'] = dict(S2b_train=len(trb), S2b_test=len(teb), S3_train=len(v1), S3_test=len(v2), S3b_train=len(v1) + 3, S3b_test=len(v2) - 3)
    MASK = {'S1': ('S1 leave-one-cycle-out', np.ones(len(PN), bool)), 'S2': ('S2 forward in time (first 2/3 -> last 1/3; the test cycles are all new-timetable cycles)', np.isin(CIDS, allc[k2:])), 'S2b': ('S2b forward in time inside each timetable version', np.isin(CIDS, teb)), 'S3': ('S3 version change (before 16 Sep -> from 16 Sep)', np.isin(CIDS, v2)), 'S3b': ('S3b version change with the first 3 new-version cycles added', np.isin(CIDS, v2[3:]))}
    for (var, sc), P in PR_.items():
        nm, mask = MASK[sc]
        for o in OUTC:
            idx = np.where(mask)[0]; a = boot_auc(idx, P[o][idx], Y[o]); rows.append(dict(scheme=nm, variant=var, outcome=POS[o], cells=int(Y[o][idx].sum()), auc=a[0], lo=a[1], hi=a[2], prauc=a[3], within_cycle_auc=a[4], cycles_scored=a[5], test_cells=len(idx)))
    A = pd.DataFrame(rows); A.round(4).to_csv(f'{OUT}/bl_d0f_auc.csv', index=False); P1 = PR_[('causal', 'S1')]
    pd.to_pickle({f'{k[0]}|{k[1]}': v for k, v in PR_.items()}, f'{OUT}/bl_d0f_pred.pkl.gz')
    pc = []
    for c_ in allc:
        ix = np.where(CIDS == c_)[0]; y = Y['y_any'][ix]
        if 5 <= y.sum() < len(y): pc.append(dict(cid=int(c_), und=grp[c_][0], version=grp[c_][1], cells=len(ix), positives=int(y.sum()), auc=roc_auc_score(y, P1['y_any'][ix])))
    PC = pd.DataFrame(pc); PC.round(4).to_csv(f'{OUT}/bl_d0f_cycles.csv', index=False); R['per_cycle_any'] = dict(n=len(PC), min=float(PC.auc.min()), median=float(PC.auc.median()), max=float(PC.auc.max()), share_ge_085=float((PC.auc >= .85).mean()))
    # S4: 30 random halves, both variants
    tasks = []
    for var in VARS:
        for s_ in range(30):
            pm = np.random.default_rng(1000 + s_).permutation(allc); tasks.append((list(pm[:len(pm) // 2]), list(pm[len(pm) // 2:]), var))
    res4 = pool.map(fit_predict, tasks); s4 = []
    for n_, ((trc, tec, var), res) in enumerate(zip(tasks, res4)):
        for o in OUTC:
            ix, p = res[o]; y = Y[o][ix]
            if y.sum() >= 5 and y.sum() < len(y) and not np.isnan(p).any(): s4.append(dict(variant=var, split=n_ % 30, outcome=POS[o], auc=roc_auc_score(y, p), cells=int(y.sum())))
    S4 = pd.DataFrame(s4); S4s = S4.groupby(['variant', 'outcome']).agg(splits=('auc', 'size'), mean_auc=('auc', 'mean'), sd=('auc', 'std'), min_auc=('auc', 'min'), p10=('auc', lambda x: x.quantile(.1)), mean_cells=('cells', 'mean')).reset_index(); S4s.round(4).to_csv(f'{OUT}/bl_d0f_s4.csv', index=False)
    # placebo (any sell): features shuffled within cycle, S1
    global_rng = np.random.default_rng(5); Xp = XM.copy()
    for c_ in cycles:
        m = np.where(CIDS == c_)[0]; Xp[m] = Xp[global_rng.permutation(m)]
    pp = np.full(len(PN), np.nan)
    for h in allc:
        trn = CIDS != h; ten = CIDS == h; ref = np.array([c != h for c in cycles]); F = clock_features(ref).values; Fp = F.copy()
        for c_ in cycles:
            m = np.where(CIDS == c_)[0]; Fp[m] = Fp[global_rng.permutation(m)]
        Xa = np.hstack([Xp, Fp]); pp[ten] = mk().fit(Xa[trn], Y['y_any'][trn]).predict_proba(Xa[ten])[:, 1]
    pl = boot_auc(np.arange(len(PN)), pp, Y['y_any']); R['placebo_any'] = dict(auc=pl[0], lo=pl[1], hi=pl[2], within=pl[4])
    # type assignment among sale cells (S1, causal)
    sale = np.where(PN.y_any.values > 0)[0]; Lt = S[S.row >= 0].groupby(['row', 'type3']).lots.sum().unstack().reindex(columns=TYPES).fillna(0)
    true = Lt.idxmax(axis=1).reindex(PN.row.values[sale]).values; M = np.vstack([P1['y_' + t][sale] for t in TYPES]).T; pred = np.array(TYPES)[np.nanargmax(M, axis=1)]
    CF = pd.crosstab(pd.Series(true, name='true type'), pd.Series(pred, name='predicted type')).reindex(index=TYPES, columns=TYPES).fillna(0).astype(int); CF.to_csv(f'{OUT}/bl_d0f_confusion.csv')
    TY = pd.DataFrame([dict(type=t, sale_cells=int((true == t).sum()), recall=float((pred[true == t] == t).mean()) if (true == t).sum() else np.nan, precision=float((true[pred == t] == t).mean()) if (pred == t).sum() else np.nan) for t in TYPES]); TY.round(4).to_csv(f'{OUT}/bl_d0f_types.csv', index=False)
    R['type_top1_accuracy'] = float((pred == true).mean()); R['sale_cells'] = int(len(sale)); R['majority_type_share'] = float(pd.Series(true).value_counts(normalize=True).iloc[0]); R['lots_total'] = int(S.lots.sum()); R['lots_in_panel'] = int(S[S.row >= 0].lots.sum()); R['cycles'] = len(cycles); R['runtime_s'] = round(time.time() - t0)
    R['auc'] = A.round(4).to_dict('records'); R['s4'] = S4s.round(4).to_dict('records'); rec('d0f1', R); print(R['per_cycle_any'], R['type_top1_accuracy'], 'done')
