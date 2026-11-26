"""D0 quantity, Part C: position (inventory) management (plan reports/D0_QTY_PLAN.md).
C1 level and shape of the short / long book per right, C2 ceiling test, C3 does the book state feed back on selling (family AUC, leave-one-cycle-out), C4 CE-PE balance after solo sales,
C5 hedge ratio and wing cost, C6 exposure at the stop and at 15:09.
Outputs bl_d0u_c1_book.csv, bl_d0u_c2_cap.csv, bl_d0u_c3_feedback.csv, bl_d0u_c4_balance.csv, bl_d0u_c5_hedge.csv, bl_d0u_c6_exposure.csv, bl_d0u_timeline.pkl.gz, bl_summary_d0u_c.json"""
import sys, json, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy import stats
from sklearn.ensemble import HistGradientBoostingClassifier as HGB
R = {}; CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); CY['cid'] = np.arange(len(CY)); key = {(r.und, r.expiry): r.cid for r in CY.itertuples()}
D = pd.read_pickle(f'{OUT}/bl_d0u_orders.pkl.gz'); D['cid'] = [key.get((u, e), -1) for u, e in zip(D.und, D.expiry)]; D = D[D.cid >= 0].copy(); SPT = pd.read_pickle(f'{OUT}/bl_d0_spot.pkl.gz')
UNIT = {'NIFTY': 65, 'SENSEX': 20}; NJ = 376
ver = pd.read_pickle(f'{OUT}/bl_d0n_orders.pkl.gz').groupby('cid').version.first(); stop_cids = set(D[D.module == 's_'].cid)
# ---------- timeline: S, L per right at the end of each minute j (state after the last order of the minute, forward filled; the carry is the state before the first D0 order)
D = D.sort_values(['cid', 'cp', 'tt_first', 'row']); TL = {}
for (c, cp), z in D.groupby(['cid', 'cp']):
    S0 = z.S_after.iloc[0] - (z.lots.iloc[0] if z.klass.iloc[0] == 'body sell' else 0); L0 = z.L_after.iloc[0] - (z.lots.iloc[0] if z.klass.iloc[0] in ('wing buy', 'body long buy') else 0)
    s = np.full(NJ, np.nan); l = np.full(NJ, np.nan); last = z.groupby('jm').agg(S=('S_after', 'last'), L=('L_after', 'last')); jj = last.index.values; ok = (jj >= 0) & (jj < NJ)
    s[jj[ok]] = last.S.values[ok]; l[jj[ok]] = last.L.values[ok]
    s = pd.Series(s).ffill().fillna(S0).values; l = pd.Series(l).ffill().fillna(L0).values; TL[(c, cp)] = dict(S=s, L=l, S0=S0, L0=L0)
pd.to_pickle(TL, f'{OUT}/bl_d0u_timeline.pkl.gz')
# ---------- C1 level and shape
rows = []
for c in sorted(set(k[0] for k in TL)):
    u = CY.und[c]; sp = SPT.get((u, CY.expiry[c])); op = float(sp.open.iloc[0]) if sp is not None else np.nan; nl = op * UNIT[u] / 1e5
    for cp in ('CE', 'PE'):
        t = TL.get((c, cp));
        if t is None: continue
        s = t['S'][:354]; jp = int(np.argmax(s))
        rows.append(dict(cid=c, und=u, version=ver.get(c, ''), cp=cp, stop_cycle=c in stop_cids, carry_S=t['S0'], carry_L=t['L0'], peak_S=s.max(), peak_min=jp, S_1000=t['S'][105], S_1200=t['S'][165], S_1500=t['S'][345], S_1509=t['S'][354],
                         S_final=t['S'][min(NJ - 1, 375)], L_final=t['L'][min(NJ - 1, 375)], lot_notional_lakh=nl, peak_notional_lakh=s.max() * nl, carry_notional_lakh=t['S0'] * nl))
C1 = pd.DataFrame(rows); C1.to_csv(f'{OUT}/bl_d0u_c1_book.csv', index=False)
ns = C1[~C1.stop_cycle]
R['c1_cycles'] = int(C1.cid.nunique()); R['c1_non_stop_cycles'] = int(ns.cid.nunique()); R['c1_lot_notional_lakh_med'] = float(C1.lot_notional_lakh.median())
R['c1_by_und'] = {u: dict(carry_S_med=float(z.carry_S.median()), peak_S_med=float(z.peak_S.median()), peak_S_iqr=[float(z.peak_S.quantile(.25)), float(z.peak_S.quantile(.75))], peak_min_med=float(z.peak_min.median()), S_1509_med=float(z.S_1509.median()),
                       S_final_med=float(z.S_final.median()), peak_notional_lakh_med=float(z.peak_notional_lakh.median())) for u, z in ns.groupby('und')}
R['c1_final_short_zero_share_non_stop'] = float((ns.S_final == 0).mean()); R['c1_final_long_zero_share_non_stop'] = float((ns.L_final == 0).mean()); R['c1_stop_cycles_final_short_zero_share'] = float((C1[C1.stop_cycle].S_final == 0).mean())
# ---------- C2 ceiling test (non-stop cycles, per underlying x version x right): spread of the peak across cycles, and the sale hazard near a leave-one-out cap
cap = []
for (u, v, cp), z in ns.groupby(['und', 'version', 'cp']):
    for nm, col in (('lots', 'peak_S'), ('notional (lakh)', 'peak_notional_lakh')):
        m = z[col].median(); cap.append(dict(und=u, version=v, cp=cp, measure=nm, cycles=len(z), median_peak=float(m), cv=float(z[col].std() / z[col].mean()), min=float(z[col].min()), max=float(z[col].max()), share_within_10pct_of_median=float((np.abs(z[col] - m) <= 0.1 * m).mean())))
CP = pd.DataFrame(cap); CP.to_csv(f'{OUT}/bl_d0u_c2_cap.csv', index=False)
R['c2_share_within_10pct_by_group_lots'] = {f'{r.und}|{r.version}|{r.cp}': r.share_within_10pct_of_median for r in CP[CP.measure == 'lots'].itertuples()}
R['c2_best_share_within_10pct_lots'] = float(CP[CP.measure == 'lots'].share_within_10pct_of_median.max()); R['c2_best_share_within_10pct_notional'] = float(CP[CP.measure != 'lots'].share_within_10pct_of_median.max())
R['c2_median_cv_lots'] = float(CP[CP.measure == 'lots'].cv.median()); R['c2_median_cv_notional'] = float(CP[CP.measure != 'lots'].cv.median())
PN = pd.read_pickle(f'{OUT}/bl_d0f_panel.pkl.gz').reset_index(drop=True); PN = PN[~PN.cid.isin(stop_cids)].copy()
S_start = []; capv = []
for r in PN.itertuples():
    t = TL.get((r.cid, r.cp)); j = int(r.j); S_start.append(t['S'][j - 1] if (t is not None and j >= 1) else (t['S0'] if t is not None else np.nan))
    z = ns[(ns.und == r.und) & (ns.version == r.version) & (ns.cp == r.cp) & (ns.cid != r.cid)]; capv.append(z.peak_S.median() if len(z) >= 3 else np.nan)
PN['S_start'] = S_start; PN['cap_loo'] = capv; PN['any_sell'] = (PN.sell_all_lots > 0).astype(float); z = PN.dropna(subset=['S_start', 'cap_loo'])
z = z.assign(near=z.S_start >= 0.9 * z.cap_loo, mid=(z.S_start >= 0.7 * z.cap_loo) & (z.S_start < 0.9 * z.cap_loo))
hz = z.groupby(['near']).any_sell.agg(['mean', 'size']); R['c2_hazard_by_near_cap'] = {str(k): dict(rate=float(v['mean']), cells=int(v['size'])) for k, v in hz.iterrows()}
z['hbin'] = z.hour.astype(int); strat = z.groupby(['hbin', 'near']).any_sell.mean().unstack(); R['c2_hazard_ratio_near_vs_not_hour_matched_med'] = float((strat[True] / strat[False]).median()) if True in strat and False in strat else np.nan
R['c2_cells_near_cap'] = int(z.near.sum())
# ---------- C3 does the book feed back on selling (any body sell in the cell)? family AUC leave-one-cycle-out
FAM = dict(base=['hour', 'min_in_15', 'min_in_5', 'is_ce', 'und_nifty', 'v2', 'j', 'gap_fav'],
           spot=['fav_ret_1', 'fav_ret_3', 'fav_ret_5', 'fav_ret_15', 'fav_ret_30', 'fav_ret_60', 'fresh_15', 'fresh_30', 'fresh_60', 'fresh_120', 'fresh_day', 'dist_day_ext', 'from_open', 'vol15', 'bars_since_fresh60'],
           book=['n_own', 'n_other', 'share_own', 'expo_own', 'expo_other', 'expo_share_own', 'mtm_lakh', 'mtm_to_stop', 'sell_own_1', 'sell_own_5', 'sell_own_15', 'sell_other_1', 'sell_other_5', 'sell_other_15', 'since_sale_own', 'carried_own', 'carried_other'],
           inv=['S_start', 'S_imb', 'S_vs_cap'])
PN['S_imb'] = [(TL[(c, cp)]['S'][int(j) - 1] - TL[(c, 'PE' if cp == 'CE' else 'CE')]['S'][int(j) - 1]) if int(j) >= 1 and (c, 'PE' if cp == 'CE' else 'CE') in TL and (c, cp) in TL else np.nan for c, cp, j in zip(PN.cid, PN.cp, PN.j)]
PN['S_vs_cap'] = PN.S_start / PN.cap_loo; PN = PN.replace([np.inf, -np.inf], np.nan); mk = lambda: HGB(max_iter=200, max_depth=3, learning_rate=0.05, min_samples_leaf=50, l2_regularization=1.0, random_state=0)
def auc(y, p):
    r = stats.rankdata(p); n1 = y.sum(); n0 = len(y) - n1; return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
def loco_auc(cols, ycol='any_sell'):
    X = PN[cols].values.astype(float); y = PN[ycol].values; cid = PN.cid.values; p = np.full(len(PN), np.nan)
    for c in np.unique(cid):
        tr = cid != c; m = mk(); m.fit(X[tr], y[tr]); p[~tr] = m.predict_proba(X[~tr])[:, 1]
    return p
def cb(p, y, cid, nb=300, seed=3):
    rng = np.random.default_rng(seed); u = np.unique(cid); idx = {c: np.where(cid == c)[0] for c in u}; out = []
    for _ in range(nb):
        ii = np.concatenate([idx[c] for c in rng.choice(u, len(u))]); yy = y[ii]
        if 0 < yy.sum() < len(yy): out.append(auc(yy, p[ii]))
    return float(np.quantile(out, .025)), float(np.quantile(out, .975))
y = PN.any_sell.values; cid = PN.cid.values; res = []; P_ = {}
for nm, cols in (('base (time of day, side, underlying)', FAM['base']), ('base + spot', FAM['base'] + FAM['spot']), ('base + spot + book (existing features)', FAM['base'] + FAM['spot'] + FAM['book']), ('base + spot + book + inventory (S, CE-PE imbalance, S vs cap)', FAM['base'] + FAM['spot'] + FAM['book'] + FAM['inv']), ('base + inventory only', FAM['base'] + FAM['inv'])):
    p = loco_auc(cols); P_[nm] = p; lo, hi = cb(p, y, cid); res.append(dict(model=nm, auc=auc(y, p), lo=lo, hi=hi, cells=len(PN), positives=int(y.sum())))
C3 = pd.DataFrame(res); b0 = C3.auc.iloc[0]; C3['gain_vs_base'] = C3.auc - b0
for nm in ('base + spot + book + inventory (S, CE-PE imbalance, S vs cap)', 'base + inventory only'):  # paired gain with CI (inventory added on top of spot+book / on base)
    ref_nm = 'base + spot + book (existing features)' if 'spot' in nm else C3.model.iloc[0]; d = auc(y, P_[nm]) - auc(y, P_[ref_nm]); rng = np.random.default_rng(7); u = np.unique(cid); idx = {c: np.where(cid == c)[0] for c in u}; bs = []
    for _ in range(300):
        ii = np.concatenate([idx[c] for c in rng.choice(u, len(u))]); yy = y[ii]
        if 0 < yy.sum() < len(yy): bs.append(auc(yy, P_[nm][ii]) - auc(yy, P_[ref_nm][ii]))
    R['c3_gain_' + ('inventory_on_top_of_spot_book' if 'spot' in nm else 'inventory_on_base')] = dict(gain=float(d), lo=float(np.quantile(bs, .025)), hi=float(np.quantile(bs, .975)))
C3.round(4).to_csv(f'{OUT}/bl_d0u_c3_feedback.csv', index=False)
# ---------- C4 balance: does a solo sale go to the right with fewer shorts?  (body sell orders that are not part of a pair; other-right S read at the order time)
SO = pd.read_pickle(f'{OUT}/bl_d0n_orders.pkl.gz'); SO = SO[SO.cid.isin(set(k[0] for k in TL))]; r4 = []
for r in SO.itertuples():
    j = int(r.tod // 60 - 555); oth = 'PE' if r.cp == 'CE' else 'CE'; a = TL.get((r.cid, r.cp)); b = TL.get((r.cid, oth))
    if a is None or b is None or j < 1 or j > 354: continue
    r4.append((r.cid, r.type, r.cp, a['S'][j - 1], b['S'][j - 1]))
B4 = pd.DataFrame(r4, columns=['cid', 'type', 'cp', 'S_own', 'S_oth']); B4['imb'] = B4.S_own - B4.S_oth; B4 = B4[B4.imb != 0]
out = []
for t, z in [('all solo sells', B4)] + list(B4.groupby('type')):
    k = int((z.imb < 0).sum()); n = len(z); p = stats.binomtest(k, n, 0.5).pvalue if n else np.nan
    out.append(dict(type=t, n=n, share_to_lighter_right=k / n if n else np.nan, binom_p=p, median_imbalance_before=float(z.imb.median()), share_cycles_ge_0_5=float((z.groupby('cid').imb.apply(lambda s: (s < 0).mean()) > .5).mean())))
C4 = pd.DataFrame(out); C4.round(4).to_csv(f'{OUT}/bl_d0u_c4_balance.csv', index=False)
Sx = np.array([[TL[(c, 'CE')]['S'][j] - TL[(c, 'PE')]['S'][j] for j in (60, 165, 300)] for c in sorted(set(k[0] for k in TL)) if (c, 'CE') in TL and (c, 'PE') in TL]); R['c4_imbalance_CE_minus_PE_med_at_10_16_12_00_14_15'] = [float(np.median(Sx[:, k])) for k in range(3)]
R['c4_imbalance_abs_med_lots'] = float(np.median(np.abs(Sx))); R['c4_share_CE_heavier'] = float((Sx > 0).mean())
# ---------- C5 hedge ratio and wing cost
def minute_ratio(c):
    out = []
    for cp in ('CE', 'PE'):
        t = TL.get((c, cp))
        if t is None: continue
        s = t['S'][1:354]; l = t['L'][1:354]; act = s > 0; out.append(((l == s)[act].mean() if act.any() else np.nan, ((l > s)[act]).mean() if act.any() else np.nan, ((l < s)[act]).mean() if act.any() else np.nan, (l[act] / s[act]).mean() if act.any() else np.nan))
    return np.nanmean(np.array(out, float), axis=0)
cids = sorted(set(k[0] for k in TL)); H = np.array([minute_ratio(c) for c in cids]); R['c5_share_minutes_L_equals_S_median_cycle'] = float(np.nanmedian(H[:, 0])); R['c5_share_L_gt_S'] = float(np.nanmedian(H[:, 1])); R['c5_share_L_lt_S'] = float(np.nanmedian(H[:, 2])); R['c5_mean_L_over_S'] = float(np.nanmean(H[:, 3]))
cost = []
for c, z in D[D.cid.isin(cids)].groupby('cid'):
    prem = (z[z.klass == 'body sell'].lots * z[z.klass == 'body sell'].px_avg).sum(); bb_ = (z[z.klass == 'body buy-back'].lots * z[z.klass == 'body buy-back'].px_avg).sum()
    wb = (z[z.klass == 'wing buy'].lots * z[z.klass == 'wing buy'].px_avg).sum(); ws = (z[z.klass == 'wing sell'].lots * z[z.klass == 'wing sell'].px_avg).sum() + (z[z.klass == 'lump salvage'].lots * z[z.klass == 'lump salvage'].px_avg).sum()
    cost.append(dict(cid=c, und=z.und.iloc[0], stop_cycle=c in stop_cids, premium_sold=prem, body_bought_back=bb_, wing_bought=wb, wing_sold=ws, wing_net_cost=wb - ws, wing_net_pct_of_premium_sold=(wb - ws) / prem if prem else np.nan, wing_bought_pct_of_premium_sold=wb / prem if prem else np.nan, gross_wing_lots=int(z[z.klass == 'wing buy'].lots.sum()), body_sell_lots=int(z[z.klass == 'body sell'].lots.sum())))
C5 = pd.DataFrame(cost); C5.round(4).to_csv(f'{OUT}/bl_d0u_c5_hedge.csv', index=False)
R['c5_wing_net_cost_pct_of_premium_sold_median'] = float(C5.wing_net_pct_of_premium_sold.median()); R['c5_wing_bought_pct_of_premium_sold_median'] = float(C5.wing_bought_pct_of_premium_sold.median()); R['c5_wing_lots_per_body_sell_lot_median'] = float((C5.gross_wing_lots / C5.body_sell_lots).median())
# ---------- C6 exposure at the stop and at 15:09
ex = []
for c in cids:
    u = CY.und[c]; sp = SPT.get((u, CY.expiry[c])); nl = float(sp.open.iloc[0]) * UNIT[u] / 1e5; st = D[(D.cid == c) & (D.module == 's_')]
    if len(st):
        j0 = int(st.jm.min()); jb = max(0, j0 - 1); ex.append(dict(cid=c, und=u, event='stop (minute before the first stop order)', minute=j0, S_CE=TL[(c, 'CE')]['S'][jb], S_PE=TL[(c, 'PE')]['S'][jb], L_CE=TL[(c, 'CE')]['L'][jb], L_PE=TL[(c, 'PE')]['L'][jb], stop_orders=len(st), stop_lots=int(st.lots.sum()), stop_lots_per_order_med=float(st.lots.median()), stop_span_s=float(st.tod.max() - st.tod.min()), lot_notional_lakh=nl))
    else:
        jb = 353; ex.append(dict(cid=c, und=u, event='15:08 close, no stop', minute=354, S_CE=TL[(c, 'CE')]['S'][jb], S_PE=TL[(c, 'PE')]['S'][jb], L_CE=TL[(c, 'CE')]['L'][jb], L_PE=TL[(c, 'PE')]['L'][jb], stop_orders=0, stop_lots=0, stop_lots_per_order_med=np.nan, stop_span_s=np.nan, lot_notional_lakh=nl))
E6 = pd.DataFrame(ex); E6['S_total'] = E6.S_CE + E6.S_PE; E6['L_total'] = E6.L_CE + E6.L_PE; E6['short_notional_lakh'] = E6.S_total * E6.lot_notional_lakh; E6.round(3).to_csv(f'{OUT}/bl_d0u_c6_exposure.csv', index=False)
for ev_, z in E6.groupby('event'): R['c6_' + ev_.split(' ')[0] + '_' + ('stop' if 'stop (' in ev_ else 'nostop')] = dict(n=len(z), S_total_med=float(z.S_total.median()), S_total_iqr=[float(z.S_total.quantile(.25)), float(z.S_total.quantile(.75))], notional_lakh_med=float(z.short_notional_lakh.median()), L_over_S_med=float((z.L_total / z.S_total.replace(0, np.nan)).median()))
R['c6_stop_liq_lots_over_S_total_med'] = float((E6[E6.stop_orders > 0].stop_lots / E6[E6.stop_orders > 0].S_total.replace(0, np.nan)).median())
rec('d0u_c', R); print(json.dumps(R, default=str, indent=1)); pd.set_option('display.width', 250)
for nm, d in (('C1', C1.groupby(['und', 'version', 'cp']).agg(n=('cid', 'size'), carry=('carry_S', 'median'), peak=('peak_S', 'median'), pk_min=('peak_min', 'median'), S1509=('S_1509', 'median'), Sfinal=('S_final', 'median'))), ('C2', CP), ('C3', C3), ('C4', C4), ('C5', C5.groupby('und').median(numeric_only=True)), ('C6', E6.groupby('event').median(numeric_only=True))): print(nm); print(d.round(3).to_string())
