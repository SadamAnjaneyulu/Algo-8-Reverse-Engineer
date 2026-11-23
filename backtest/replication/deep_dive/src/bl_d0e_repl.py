"""D0 solo slices after the counter-sells: replacement, other solo, far-OTM roll-out (plan reports/D0_REPL_PLAN.md).
E1 replacement mechanics (same-right buy-back -> sale), E2 distinct-or-same-engine, E3 AUC gate on minute cells.
Outputs bl_d0e_e1.csv, bl_d0e_e1_lag.csv, bl_d0e_e1_mech.csv, bl_d0e_e2.csv, bl_d0e_e3.csv, bl_d0e_e3_fwd.csv, bl_summary_d0e1.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
exec(open('bl_d0c_auc.py').read().split("rows = []; PP = {}")[0])          # panel PN, orders SO, feature families G, variants VAR, mk(), loco(), score()
T = pd.read_pickle(f'{OUT}/bl_d0t_orders.pkl.gz'); X = pd.read_pickle(f'{OUT}/bl_d0y_lots.pkl.gz'); CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv')
SO = SO.copy(); SO['off_steps'] = T.loc[SO.index, 'off_steps'].values
SO['slice'] = np.where((SO.type != 'opening solo') & (SO.off_steps >= 3), 'far-OTM solo', SO.type)
print(SO.groupby('slice').lots.agg(['size', 'sum']).to_string())
other = lambda c: 'PE' if c == 'CE' else 'CE'
# ---------------- E1: same-right buy-back -> sale
EV = X.groupby(['cid', 'cp', 'tod']).agg(lots=('lid', 'size'), reason=('type', lambda s: s.value_counts().idxmax()), strike=('strike', 'median'), px=('px', 'median')).reset_index()
def first_after(q, shift=0, W=60):
    s = SO[(SO.cid == q.cid) & (SO.cp == q.cp) & (SO.tod > q.tod + shift) & (SO.tod <= q.tod + shift + W)].sort_values('tod'); return s
def rate(ev, shift):
    return float(np.mean([len(first_after(q, shift)) > 0 for q in ev.itertuples()]))
rows = []
for rs, g in EV.groupby('reason'):
    r0 = rate(g, 0); n10 = np.mean([rate(g, s) for s in (600, -600)]); n15 = np.mean([rate(g, s) for s in (900, -900)]); rows.append(dict(reason=rs, events=len(g), share_with_same_right_sale_0_60s=r0, null_10min=n10, null_15min=n15, ratio_10=r0 / max(n10, 1e-9), ratio_15=r0 / max(n15, 1e-9)))
E1 = pd.DataFrame(rows); E1['kept'] = (E1.ratio_10 >= 1.5) & (E1.ratio_15 >= 1.5); E1.round(4).to_csv(f'{OUT}/bl_d0e_e1.csv', index=False); print(E1.round(3).to_string(index=False))
kept = list(E1[E1.kept].reason); EK = EV[EV.reason.isin(kept)]
lag = []; mech = []
for q in EK.itertuples():
    s = first_after(q)
    if len(s):
        a = s.iloc[0]; lag.append(a.tod - q.tod); sg = 1 if q.cp == 'CE' else -1; stp = float(CY.iloc[q.cid].und == 'NIFTY') * 50 + float(CY.iloc[q.cid].und != 'NIFTY') * 100
        mech.append(dict(reason=q.reason, off_vs_bought_steps=sg * (a.strike - q.strike) / stp, px_ratio=a.px / q.px if q.px > 0 else np.nan, lots_ratio=s.lots.sum() / q.lots, same_strike=float(a.strike == q.strike)))
bins = np.arange(0, 65, 5); LG = pd.DataFrame(dict(lag_from_s=bins[:-1], lag_to_s=bins[1:], first_sales=np.histogram(lag, bins)[0])); LG.to_csv(f'{OUT}/bl_d0e_e1_lag.csv', index=False)
M = pd.DataFrame(mech)
# chance: random same-right solo sale of the same cycle paired with the event
rng2 = np.random.default_rng(7); ch = []
for q in EK.itertuples():
    s = SO[(SO.cid == q.cid) & (SO.cp == q.cp)]
    if len(s):
        a = s.iloc[int(rng2.integers(len(s)))]; sg = 1 if q.cp == 'CE' else -1; stp = 50.0 if CY.iloc[q.cid].und == 'NIFTY' else 100.0
        ch.append(dict(off_vs_bought_steps=sg * (a.strike - q.strike) / stp, px_ratio=a.px / q.px if q.px > 0 else np.nan, same_strike=float(a.strike == q.strike)))
CH = pd.DataFrame(ch)
MS = pd.DataFrame([dict(group='sales within 60 s after a kept buy-back', n=len(M), off_median=M.off_vs_bought_steps.median(), off_q25=M.off_vs_bought_steps.quantile(.25), off_q75=M.off_vs_bought_steps.quantile(.75), further_otm_share=float((M.off_vs_bought_steps > 0).mean()), same_strike_share=M.same_strike.mean(), px_ratio_median=M.px_ratio.median(), lots_ratio_median=M.lots_ratio.median()),
                   dict(group='random same-right solo sale of the cycle (chance)', n=len(CH), off_median=CH.off_vs_bought_steps.median(), off_q25=CH.off_vs_bought_steps.quantile(.25), off_q75=CH.off_vs_bought_steps.quantile(.75), further_otm_share=float((CH.off_vs_bought_steps > 0).mean()), same_strike_share=CH.same_strike.mean(), px_ratio_median=CH.px_ratio.median(), lots_ratio_median=np.nan)])
MS.round(4).to_csv(f'{OUT}/bl_d0e_e1_mech.csv', index=False); print(MS.round(3).to_string(index=False))
# ---------------- E2: distinct or the same engine (market and book state only)
D = SO[(SO.row >= 0) & (SO.type != 'counter-sell solo') & (SO.slice != 'counter-sell solo')].copy(); Dp = PN.set_index('row').loc[D.row.values].reset_index(); Dp['cid'] = D.cid.values; Dp['slice'] = D.slice.values
cols = G['base'] + G['spot'] + G['prem'] + G['book']; e2 = []
for sl in ('replacement solo', 'other solo', 'far-OTM solo', 'extreme solo', 'late solo'):
    Dp['t'] = (Dp.slice == sl).astype(float)
    if Dp.t.sum() < 40: continue
    p = loco(Dp, cols, 't'); sc = score(Dp, p, 't'); e2.append(dict(slice=sl, orders=int(Dp.t.sum()), others=int((1 - Dp.t).sum()), auc=sc['auc'], lo=sc['lo'], hi=sc['hi'], distinct=bool(sc['lo'] > 0.65))); print('E2', sl, round(sc['auc'], 3), round(sc['lo'], 3))
E2 = pd.DataFrame(e2); E2.round(4).to_csv(f'{OUT}/bl_d0e_e2.csv', index=False)
# ---------------- E3: AUC gate on cells
slices = {'replacement solo': 'y_repl', 'other solo': 'y_other', 'far-OTM solo': 'y_far'}
for sl, yc in slices.items():
    cs = SO[(SO.row >= 0) & (SO.slice == sl)].groupby('row').lots.sum(); PN[yc] = PN.row.map(cs).fillna(0).gt(0).astype(float); print(sl, 'cells', int(PN[yc].sum()))
PN['same_bb'] = PN.bb_own_same_min; rows = []; fw = []
order = PN.groupby('cid').expiry.first().sort_values(); tr = list(order.index[:int(len(order) * 2 / 3)]); te = list(order.index[int(len(order) * 2 / 3):])
for sl, yc in slices.items():
    if PN[yc].sum() < 20: continue
    for nm, gs in VAR.items():
        cols = sum([G[g] for g in gs], []); p = loco(PN, cols, yc); sc = score(PN, p, yc); rows.append(dict(slice=sl, cells=int(PN[yc].sum()), variant=nm, features=len(cols), **sc)); print(sl, nm, round(sc['auc'], 3), round(sc['within_cycle_auc'], 3))
        m = mk().fit(PN[PN.cid.isin(tr)][cols].values, PN[PN.cid.isin(tr)][yc].values); d = PN[PN.cid.isin(te)]; fw.append(dict(slice=sl, variant=nm, auc=roc_auc_score(d[yc], m.predict_proba(d[cols].values)[:, 1]) if d[yc].nunique() > 1 else np.nan))
    cols = sum([G[g] for g in VAR[list(VAR)[0]]], []); sc = score(PN, loco(PN, cols, yc, perm=True), yc); rows.append(dict(slice=sl, cells=int(PN[yc].sum()), variant='placebo (V1 features shuffled within cycle)', features=len(cols), **sc))
E3 = pd.DataFrame(rows); E3.round(4).to_csv(f'{OUT}/bl_d0e_e3.csv', index=False); FW = pd.DataFrame(fw); FW.round(4).to_csv(f'{OUT}/bl_d0e_e3_fwd.csv', index=False)
print(E3[['slice', 'variant', 'cells', 'auc', 'lo', 'hi', 'within_cycle_auc']].round(3).to_string(index=False)); print(FW.round(3).to_string(index=False))
rec('d0e1', dict(e1=E1.round(4).to_dict('records'), mech=MS.round(4).to_dict('records'), e2=E2.round(4).to_dict('records'), e3=E3.round(4).to_dict('records'), fwd=FW.round(4).to_dict('records'), slices=SO.groupby('slice').lots.agg(['size', 'sum']).to_dict('index')))
