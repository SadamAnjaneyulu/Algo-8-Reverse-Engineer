"""Part B of reports/D0_PAIR_PLAN.md: what triggers the body buy-back. Builds the lot-state panel (cid, minute j, right) and runs B1-B5.
Outputs bl_d0p_lotpanel.pkl.gz, bl_d0p_b1.csv, bl_d0p_b2.csv, bl_d0p_b3.csv, bl_d0p_b3_abl.csv, bl_d0p_b3_imp.csv, bl_d0p_b4.csv, bl_d0p_b5.csv, bl_d0p_b5_tree.txt, bl_summary_d0p3.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from sklearn.ensemble import HistGradientBoostingClassifier as HGB
from sklearn.tree import DecisionTreeClassifier as DT, export_text
from sklearn.metrics import roc_auc_score, average_precision_score
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); PN = pd.read_pickle(f'{OUT}/bl_d0n_panel.pkl.gz'); BK = pd.read_pickle(f'{OUT}/bl_d0b_book.pkl.gz'); SP = pd.read_pickle(f'{OUT}/bl_d0_spot.pkl.gz'); OPT = pd.read_pickle(f'{OUT}/bl_d0_opt.pkl.gz'); X = pd.read_pickle(f'{OUT}/bl_d0y_lots.pkl.gz')
rng = np.random.default_rng(173); R = {}; other = lambda c: 'PE' if c == 'CE' else 'CE'; K0 = PN.set_index(['cid', 'j', 'cp'])
rows = []; LOT = []
for i in sorted(PN.cid.unique()):
    r = CY.iloc[i]; und = r.und; unit = float(r.unit); op = OPT[(und, r.expiry)]; Kk = op['K']; kidx = {int(k): n for n, k in enumerate(Kk)}; sp = SP[(und, r.expiry)]; c = sp.close.values; shi = sp.high.values; slo = sp.low.values
    book = BK[i]; opn = {l['lid'] for l in book['at_open']}; L = pd.DataFrame([l for l in book['lots'] if l['lid'] in opn or l['entry_day'] == 1])
    L = L[L.strike.isin(kidx)]; L['em'] = np.where(L.entry_day == 0, -1, ((L.entry_tod - 33300) // 60).astype(int)); L['xm'] = np.where(L.exit_tod.notna(), ((L.exit_tod - 33300) // 60), 9999).astype(int); L['ki'] = L.strike.map(kidx)
    je = int(PN[PN.cid == i].j.max()); HI = {cp: op[(cp, 'high')] for cp in ('CE', 'PE')}; CL = {cp: op[(cp, 'close')] for cp in ('CE', 'PE')}
    for cp in ('CE', 'PE'):
        Lc = L[L.cp == cp]; ki = Lc.ki.values; en = Lc.entry.values; em = Lc.em.values; xm = Lc.xm.values; carried = (Lc.entry_day.values == 0)
        # B1: first crossing per lot
        for th in (1.2, 1.4, 1.6):
            for n_ in range(len(Lc)):
                h = HI[cp][ki[n_], max(em[n_], 0):je + 1] / en[n_]; w = np.where(h >= th)[0]; fm = (max(em[n_], 0) + w[0]) if len(w) else -1
                LOT.append(dict(cid=i, cp=cp, lid=int(Lc.lid.values[n_]), th=th, first_cross=fm, exit_min=int(xm[n_]), carried=bool(carried[n_]), je=je))
        for j in range(4, je + 1):
            k = (i, j, cp)
            if k not in K0.index: continue
            op_m = (em < j) & (xm >= j)
            f = dict(cid=i, j=j, cp=cp, n_open=int(op_m.sum()))
            if op_m.any():
                kk = ki[op_m]; e = en[op_m]; hj = HI[cp][kk, j]; hp = HI[cp][kk, j - 1]; cj = CL[cp][kk, j]; cpv = CL[cp][kk, j - 1]; age = np.where(carried[op_m], 600, j - em[op_m])
                rj = hj / e; rp = hp / e; f['max_ratio_hi_j'] = np.nanmax(rj); f['max_ratio_hi_prev'] = np.nanmax(rp); f['max_ratio_close_prev'] = np.nanmax(cpv / e)
                for th in (1.2, 1.4, 1.6): f[f'n_cross_{th}'] = int((rj >= th).sum())
                f['n_cross_prev_1.4'] = int((rp >= 1.4).sum()); f['share_cross_1.4'] = float((rj >= 1.4).mean()); cr = rj >= 1.4; f['age_cross_mean'] = float(age[cr].mean()) if cr.any() else np.nan; f['carried_share_cross'] = float(carried[op_m][cr].mean()) if cr.any() else np.nan
                # reference: strike-average entry
                su = pd.DataFrame(dict(k=kk, e=e, h=hj, hp=hp)).groupby('k').agg(e=('e', 'mean'), h=('h', 'first'), hp=('hp', 'first')); f['ref_strike_j'] = float((su.h / su.e).max()); f['ref_strike_prev'] = float((su.hp / su.e).max())
                # side mark ratio
                f['ref_side_j'] = float(np.nansum(hj) / np.nansum(e)); f['ref_side_prev'] = float(np.nansum(cpv) / np.nansum(e)); f['ref_side_close_j'] = float(np.nansum(cj) / np.nansum(e))
                f['side_loss_rs'] = float(np.nansum(cpv - e) * unit); f['side_loss_share'] = float(np.nansum(cpv - e) / np.nansum(e))
            adv = (1.0 if cp == 'CE' else -1.0)
            hh = shi if cp == 'CE' else slo
            f['adv_fresh60_prev'] = float((hh[j - 1] > hh[max(j - 61, 0):j - 1].max()) if cp == 'CE' else (hh[j - 1] < hh[max(j - 61, 0):j - 1].min())) if j > 1 else 0.0
            f['adv_fresh60_c'] = float((hh[j] > hh[max(j - 60, 0):j].max()) if cp == 'CE' else (hh[j] < hh[max(j - 60, 0):j].min()))
            for kx in (1, 5, 15, 30, 60): f[f'adv_move_{kx}'] = adv * (c[j - 1] - c[max(j - 1 - kx, 0)]) / float(ref.STEP[und])
            f['adv_move_1_c'] = adv * (c[j] - c[j - 1]) / float(ref.STEP[und]); f['adv_dist_day_ext'] = abs(c[j - 1] - (shi[:j].max() if cp == 'CE' else slo[:j].min())) / float(ref.STEP[und])
            atm = int(Kk[np.argmin(np.abs(Kk - c[j - 1]))]); pa = CL[cp][kidx[atm]]; ha = HI[cp][kidx[atm]]
            f['prem_high60_prev'] = float(pa[j - 1] >= np.nanmax(pa[max(j - 61, 0):j - 1])) if j > 1 else 0.0; f['prem_high60_c'] = float(ha[j] > np.nanmax(ha[max(j - 60, 0):j])); f['prem_chg_1_cp'] = pa[j - 1] / pa[j - 2] - 1 if j > 1 and pa[j - 2] > 0 else np.nan; f['prem_chg_5_cp'] = pa[j - 1] / pa[max(j - 6, 0)] - 1 if pa[max(j - 6, 0)] > 0 else np.nan
            p = K0.loc[k]; po = K0.loc[(i, j, other(cp))]
            for q_ in ('mtm_lakh', 'mtm_to_stop', 'n_own', 'n_other', 'expo_share_own', 'hour', 'min_in_15', 'min_in_5', 'is_ce', 'und_nifty', 'v2', 'bb_own_1', 'bb_own_5', 'bb_own_15', 'bb_other_5', 'since_bb_other', 'y_lots'): f[q_] = p[q_]
            f['oth_prem_low60'] = po.phx_prem_low_60; f['oth_sales_5'] = po.sell_own_5; f['y_bb'] = float(p.bb_own_same_min > 0); f['bb_lots'] = p.bb_own_same_min
            rows.append(f)
LP = pd.DataFrame(rows); LP['row'] = np.arange(len(LP))
# stop-like outcome: any buy-back lot in the cell with decision ratio >= 1.2
sl_cells = set(zip(X[(X.ratio >= 1.2)].cid, X[(X.ratio >= 1.2)].j, X[(X.ratio >= 1.2)].cp)); LP['y_loss'] = [float((a, b, c_) in sl_cells) for a, b, c_ in zip(LP.cid, LP.j, LP.cp)]
LP.to_pickle(f'{OUT}/bl_d0p_lotpanel.pkl.gz'); LT = pd.DataFrame(LOT); print(LP.shape, LP.y_bb.mean().round(3), LP.y_loss.mean().round(3), 'crossing present', (LP['n_cross_1.4'] > 0).mean().round(3)); R['panel'] = dict(cells=len(LP), y_bb=float(LP.y_bb.mean()), y_loss=float(LP.y_loss.mean()), crossing_share=float((LP['n_cross_1.4'] > 0).mean()))
# ---------- B1
b1 = []
for th, g in LT.groupby('th'):
    g = g[(g.first_cross >= 0) & (g.first_cross <= g.je)].copy(); g['lag'] = g.exit_min - g.first_cross; ins = g.exit_min <= g.je
    for nm, m in (('all lots', g.index == g.index), ('carried from D-1', g.carried), ('entered on D0', ~g.carried)):
        h = g[m]; n = len(h); b1.append(dict(theta=th, group=nm, lots_that_crossed=n, bought_before_crossing=float((h.lag < 0).mean()), lag0=float(((h.lag == 0) & (h.exit_min <= h.je)).mean()), lag1=float(((h.lag == 1) & (h.exit_min <= h.je)).mean()), lag2_5=float(((h.lag >= 2) & (h.lag <= 5) & (h.exit_min <= h.je)).mean()), lag6_15=float(((h.lag >= 6) & (h.lag <= 15) & (h.exit_min <= h.je)).mean()), later_in_scope=float(((h.lag > 15) & (h.exit_min <= h.je)).mean()), clearance_stop_or_never=float((h.exit_min > h.je).mean())))
B1 = pd.DataFrame(b1); B1.to_csv(f'{OUT}/bl_d0p_b1.csv', index=False); print(B1.round(3).to_string(index=False))
# ---------- B2 reference rules (exact-cell F1, LOCO threshold)
GR = {k: np.where((LP.cid.values == k[0]) & (LP.cp.values == k[1]))[0] for k in LP.groupby(['cid', 'cp']).groups}
def f1(flag, y, groups, shift=0):
    tp = fp = fn = 0
    for ix in groups.values():
        f = flag[ix].astype(bool); a = y[ix].astype(bool)
        if shift: f = np.roll(f, shift)
        tp += int((f & a).sum()); fp += int((f & ~a).sum()); fn += int((~f & a).sum())
    pr = tp / max(tp + fp, 1); rc = tp / max(tp + fn, 1); return pr, rc, 2 * pr * rc / max(pr + rc, 1e-9)
GRID = np.round(np.arange(1.1, 2.01, 0.1), 2); b2 = []
for y in ('y_bb', 'y_loss'):
    yv = LP[y].values
    for nm, col in (('own entry, bar j', 'max_ratio_hi_j'), ('own entry, bar j-1', 'max_ratio_hi_prev'), ('strike-average entry, bar j', 'ref_strike_j'), ('strike-average entry, bar j-1', 'ref_strike_prev'), ('side mark ratio (highs), bar j', 'ref_side_j'), ('side mark ratio (close), bar j-1', 'ref_side_prev')):
        s = LP[col].values; fl = np.zeros(len(LP), bool); ths = []
        for c_ in LP.cid.unique():
            te = LP.cid.values == c_; best = (-1, 1.4)
            for th in GRID:
                g = {k: v for k, v in GR.items() if k[0] != c_}; flt = np.zeros(len(LP), bool); flt[~te] = np.nan_to_num(s[~te], nan=0) >= th; sc = f1(flt, yv, g)[2]
                if sc > best[0]: best = (sc, th)
            fl[te] = np.nan_to_num(s[te], nan=0) >= best[1]; ths.append(best[1])
        pr, rc, F = f1(fl, yv, GR); sh = np.mean([f1(fl, yv, GR, s_)[2] for s_ in (15, -15)]); fa = f1(np.ones(len(LP), bool), yv, GR)[2]
        b2.append(dict(outcome=y, rule=nm, theta_median=float(np.median(ths)), precision=pr, recall=rc, F1=F, shifted_15min_F1=sh, flag_all_F1=fa, base_rate=float(yv.mean()), flagged=int(fl.sum())))
B2 = pd.DataFrame(b2); B2.to_csv(f'{OUT}/bl_d0p_b2.csv', index=False); print(B2.round(3).to_string(index=False))
# ---------- B3 conditional model
SUB = LP[LP['n_cross_1.4'] > 0].reset_index(drop=True); y = 'y_bb'
FM = dict(
    G0=['hour', 'min_in_15', 'min_in_5', 'is_ce', 'und_nifty', 'v2'],
    G1=['max_ratio_hi_j', 'n_cross_1.4', 'n_cross_1.2', 'n_cross_1.6', 'share_cross_1.4', 'age_cross_mean', 'carried_share_cross', 'n_open'],
    G2=['adv_move_1', 'adv_move_5', 'adv_move_15', 'adv_move_30', 'adv_move_60', 'adv_fresh60_prev', 'adv_fresh60_c', 'adv_move_1_c', 'adv_dist_day_ext'],
    G3=['prem_high60_prev', 'prem_high60_c', 'prem_chg_1_cp', 'prem_chg_5_cp'],
    G4=['side_loss_rs', 'side_loss_share', 'ref_side_prev', 'ref_side_j', 'ref_strike_j', 'expo_share_own', 'n_own'],
    G5=['mtm_lakh', 'mtm_to_stop', 'n_other', 'bb_own_1', 'bb_own_5', 'bb_own_15'], G6=['oth_prem_low60', 'oth_sales_5', 'bb_other_5'])
mk = lambda: HGB(max_iter=200, max_depth=3, learning_rate=0.05, min_samples_leaf=50, l2_regularization=1.0, random_state=0)
def loco(df, cols, yy, perm=False):
    Xm = df[cols].values.copy(); yv = df[yy].values; p = np.full(len(df), np.nan)
    if perm:
        for c_ in df.cid.unique(): m = np.where((df.cid == c_).values)[0]; Xm[m] = Xm[rng.permutation(m)]
    for c_ in df.cid.unique():
        te = (df.cid == c_).values
        if len(set(yv[~te])) < 2: continue
        p[te] = mk().fit(Xm[~te], yv[~te]).predict_proba(Xm[te])[:, 1]
    return p
def sc(df, p, yy, nb=300):
    ok = ~np.isnan(p); d = df[ok].reset_index(drop=True); pp = p[ok]; u = d.cid.unique(); idx = {c_: np.where(d.cid.values == c_)[0] for c_ in u}; b = []
    for _ in range(nb):
        k = np.concatenate([idx[c_] for c_ in rng.choice(u, len(u))]); v = d[yy].values[k]
        if v.min() != v.max(): b.append(roc_auc_score(v, pp[k]))
    return dict(auc=roc_auc_score(d[yy], pp), lo=np.percentile(b, 2.5), hi=np.percentile(b, 97.5), prauc=average_precision_score(d[yy], pp))
combos = {'G0 baseline': ['G0'], 'G0+G1 lot state': ['G0', 'G1'], '+G2 spot against the right': ['G0', 'G1', 'G2'], '+G3 premium of the right': ['G0', 'G1', 'G3'], '+G4 side loss': ['G0', 'G1', 'G4'], '+G5 book': ['G0', 'G1', 'G5'], '+G6 other right': ['G0', 'G1', 'G6'], 'all families': ['G0', 'G1', 'G2', 'G3', 'G4', 'G5', 'G6']}
b3 = []
for nm, gs in combos.items():
    cols = sum([FM[g] for g in gs], []); s_ = sc(SUB, loco(SUB, cols, y), y); b3.append(dict(model=nm, features=len(cols), cells=len(SUB), positive_rate=float(SUB[y].mean()), **s_)); print(nm, round(s_['auc'], 3))
B3 = pd.DataFrame(b3); B3['gain_over_G0_G1'] = B3.auc - B3.auc[1]; allc = sum([FM[g] for g in FM], []); B3.loc[len(B3)] = dict(model='placebo (all families, shuffled within cycle)', features=len(allc), cells=len(SUB), positive_rate=float(SUB[y].mean()), **sc(SUB, loco(SUB, allc, y, perm=True), y), gain_over_G0_G1=np.nan)
B3.to_csv(f'{OUT}/bl_d0p_b3.csv', index=False)
ab = []
for g in ('G1', 'G2', 'G3', 'G4', 'G5', 'G6'):
    cols = [c_ for c_ in allc if c_ not in FM[g]]; s_ = sc(SUB, loco(SUB, cols, y), y); ab.append(dict(dropped=g, **s_))
pd.DataFrame(ab).to_csv(f'{OUT}/bl_d0p_b3_abl.csv', index=False)
order = SUB.groupby('cid').j.size().index.tolist(); expo = {c_: CY.expiry.iloc[c_] for c_ in order}; od = sorted(order, key=lambda c_: expo[c_]); tr = od[:int(len(od) * 2 / 3)]; te_ = od[int(len(od) * 2 / 3):]; fw = []
for nm, gs in combos.items():
    cols = sum([FM[g] for g in gs], []); m = mk().fit(SUB[SUB.cid.isin(tr)][cols].values, SUB[SUB.cid.isin(tr)][y].values); d = SUB[SUB.cid.isin(te_)]; fw.append(dict(model=nm, auc=roc_auc_score(d[y], m.predict_proba(d[cols].values)[:, 1]), train_cycles=len(tr), test_cycles=len(te_)))
pd.DataFrame(fw).to_csv(f'{OUT}/bl_d0p_b3_fwd.csv', index=False)
imp = {c_: [] for c_ in allc}
for c_cid in SUB.cid.unique():
    te = (SUB.cid == c_cid).values; yt = SUB[te][y].values
    if yt.min() == yt.max(): continue
    m = mk().fit(SUB[~te][allc].values, SUB[~te][y].values); Xt = SUB[te][allc].values.copy(); b0 = roc_auc_score(yt, m.predict_proba(Xt)[:, 1])
    for k, f_ in enumerate(allc): Xs = Xt.copy(); Xs[:, k] = rng.permutation(Xs[:, k]); imp[f_].append(b0 - roc_auc_score(yt, m.predict_proba(Xs)[:, 1]))
IM = pd.DataFrame([dict(feature=f_, drop_in_auc=np.mean(v), family=[g for g in FM if f_ in FM[g]][0]) for f_, v in imp.items()]).sort_values('drop_in_auc', ascending=False); IM.to_csv(f'{OUT}/bl_d0p_b3_imp.csv', index=False); print(IM.head(12).round(4).to_string(index=False))
# ---------- B4 delay (stop-loss-typed lots)
Z = X[X.type == '3 stop-loss'][['lid', 'cid', 'j', 'cp']].merge(LT[LT.th == 1.4][['lid', 'first_cross', 'carried']], on='lid', how='left'); Z = Z[Z.first_cross >= 0]; Z['lag'] = Z.j - Z.first_cross
B4 = Z.lag.describe(percentiles=[.1, .25, .5, .75, .9]).to_frame('minutes_from_first_crossing_to_buy_back'); B4.to_csv(f'{OUT}/bl_d0p_b4.csv'); R['b4'] = dict(lots=len(Z), lag0=float((Z.lag == 0).mean()), lag_le1=float((Z.lag <= 1).mean()), lag_le5=float((Z.lag <= 5).mean()), lag_gt15=float((Z.lag > 15).mean()), median=float(Z.lag.median()), carried_share=float(Z.carried.mean()))
# ---------- B5 rule: depth-3 tree in crossing-present cells, exact-cell F1 over all cells
cols = sum([FM[g] for g in ('G0', 'G1', 'G2', 'G3', 'G4', 'G5', 'G6')], []); Xm = np.nan_to_num(LP[cols].values, nan=-9.0); cr = (LP['n_cross_1.4'] > 0).values; yv = LP.y_bb.values; fl = np.zeros(len(LP), bool)
for c_ in LP.cid.unique():
    te = LP.cid.values == c_; trn = ~te & cr; t = DT(max_depth=3, min_samples_leaf=50, random_state=0).fit(Xm[trn], yv[trn]); ptr = t.predict_proba(Xm[trn])[:, 1]; best = (-1, 0.5)
    for th in np.arange(0.1, 0.8, 0.05):
        flt = np.zeros(len(LP), bool); flt[np.where(trn)[0]] = ptr >= th; s_ = f1(flt, yv, {k: v for k, v in GR.items() if k[0] != c_})[2]
        if s_ > best[0]: best = (s_, th)
    tei = np.where(te & cr)[0]
    if len(tei): fl[tei] = t.predict_proba(Xm[tei])[:, 1] >= best[1]
pr, rc, F = f1(fl, yv, GR); fc = f1(cr, yv, GR); b5 = dict(tree_precision=pr, tree_recall=rc, tree_F1=F, crossing_only_precision=fc[0], crossing_only_recall=fc[1], crossing_only_F1=fc[2], precision_ratio=pr / max(fc[0], 1e-9), flagged=int(fl.sum()), crossing_cells=int(cr.sum()))
pd.DataFrame([b5]).to_csv(f'{OUT}/bl_d0p_b5.csv', index=False); t = DT(max_depth=3, min_samples_leaf=50, random_state=0).fit(Xm[cr], yv[cr]); open(f'{OUT}/bl_d0p_b5_tree.txt', 'w').write(export_text(t, feature_names=cols)); print(b5); print(export_text(t, feature_names=cols))
R['b1'] = B1.round(4).to_dict('records'); R['b2'] = B2.round(4).to_dict('records'); R['b3'] = B3.round(4).to_dict('records'); R['b5'] = b5; rec('d0p3', R)
