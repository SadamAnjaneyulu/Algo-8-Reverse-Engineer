"""Follow-up to bl_d0e_repl.py (post-hoc, labelled in the report): hours by slice, what the other-solo and replacement slices meet, what separates replacement from other solo,
premium ratio detail of re-sales after a buy-back, and a re-run of the AUC gate with ladder-state features (price of the contract of the last same-right sale now / its sale price).
Outputs bl_d0e_hours.csv, bl_d0e_cond.csv, bl_d0e_sep.csv, bl_d0e_px.csv, bl_d0e_ladder.csv, bl_summary_d0e2.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
exec(open('bl_d0e_repl.py').read().split("# ---------------- E1")[0])          # PN, SO (with slice), G, VAR, mk, loco, score, X, CY, T
O = load_orders(); OPT = pd.read_pickle(f'{OUT}/bl_d0_opt.pkl.gz'); R = {}
order = PN.groupby('cid').expiry.first().sort_values(); tr = list(order.index[:int(len(order) * 2 / 3)]); te = list(order.index[int(len(order) * 2 / 3):])
# ---- hours by slice (lots)
SO['hour'] = (SO.tod // 3600).astype(int); HR = SO.pivot_table(index='hour', columns='slice', values='lots', aggfunc='sum').fillna(0).astype(int); HR.to_csv(f'{OUT}/bl_d0e_hours.csv'); print(HR.to_string())
# ---- conditions met (decision-time), by slice, against all cells
D = SO[SO.row >= 0].copy(); P = PN.set_index('row').loc[D.row.values]
D['prem_low_60'] = P.phx_prem_low_60.values > 0; D['spot_fresh_60'] = P.fresh_60.values > 0; D['clock_min'] = P.min_in_15.isin([0, 1, 14]).values; D['bb_own_recent'] = (P.bb_own_5.values > 0); D['bb_other_recent'] = (P.bb_other_5.values > 0); D['late'] = P.hour.values >= 14
conds = ['prem_low_60', 'spot_fresh_60', 'clock_min', 'bb_own_recent', 'bb_other_recent', 'late']; chance = {'prem_low_60': PN.phx_prem_low_60.mean(), 'spot_fresh_60': PN.fresh_60.mean(), 'clock_min': PN.min_in_15.isin([0, 1, 14]).mean(), 'bb_own_recent': (PN.bb_own_5 > 0).mean(), 'bb_other_recent': (PN.bb_other_5 > 0).mean(), 'late': (PN.hour >= 14).mean()}
CD = pd.DataFrame([dict(slice=s, orders=len(g), **{c: g[c].mean() for c in conds}) for s, g in D.groupby('slice')] + [dict(slice='all cells (chance)', orders=len(PN), **chance)]); CD.round(4).to_csv(f'{OUT}/bl_d0e_cond.csv', index=False); print(CD.round(3).to_string(index=False))
# ---- what separates replacement from other solo (market/book only): permutation importance
Dn = SO[(SO.row >= 0) & SO.slice.isin(['replacement solo', 'other solo'])].copy(); Dp = PN.set_index('row').loc[Dn.row.values].reset_index(); Dp['cid'] = Dn.cid.values; Dp['t'] = (Dn.slice.values == 'replacement solo').astype(float)
cols = G['base'] + G['spot'] + G['prem'] + G['book']; p = loco(Dp, cols, 't'); sc = score(Dp, p, 't'); print('replacement vs other solo', round(sc['auc'], 3), round(sc['lo'], 3))
imp = {c_: [] for c_ in cols}
for c_cid in Dp.cid.unique():
    tmask = (Dp.cid == c_cid).values; yt = Dp[tmask].t.values
    if yt.min() == yt.max(): continue
    m = mk().fit(Dp[~tmask][cols].values, Dp[~tmask].t.values); Xt = Dp[tmask][cols].values.copy(); b0 = roc_auc_score(yt, m.predict_proba(Xt)[:, 1])
    for k, f_ in enumerate(cols): Xs = Xt.copy(); Xs[:, k] = rng.permutation(Xs[:, k]); imp[f_].append(b0 - roc_auc_score(yt, m.predict_proba(Xs)[:, 1]))
SEP = pd.DataFrame([dict(feature=f_, drop_in_auc=float(np.mean(v)), family=[g for g in G if f_ in G[g]][0]) for f_, v in imp.items()]).sort_values('drop_in_auc', ascending=False); SEP.round(5).to_csv(f'{OUT}/bl_d0e_sep.csv', index=False); print(SEP.head(8).round(4).to_string(index=False)); R['rep_vs_other'] = dict(auc=sc['auc'], lo=sc['lo'], hi=sc['hi'])
# ---- premium ratio detail of re-sales after a kept buy-back (partner, roll-out, cycle-stop): sold px / bought px
EV = X.groupby(['cid', 'cp', 'tod']).agg(lots=('lid', 'size'), reason=('type', lambda s: s.value_counts().idxmax()), px=('px', 'median')).reset_index(); EK = EV[EV.reason.isin(['5 partner', '6 roll-out', '1 cycle-stop window'])]; pr = []
for q in EK.itertuples():
    s = SO[(SO.cid == q.cid) & (SO.cp == q.cp) & (SO.tod > q.tod) & (SO.tod <= q.tod + 60)].sort_values('tod')
    if len(s) and q.px > 0: pr.append(dict(reason=q.reason, px_ratio=s.iloc[0].px / q.px))
PR = pd.DataFrame(pr); rnd = np.random.default_rng(11); ch = []
for q in EK.itertuples():
    s = SO[(SO.cid == q.cid) & (SO.cp == q.cp)]
    if len(s) and q.px > 0: ch.append(s.iloc[int(rnd.integers(len(s)))].px / q.px)
ch = np.array(ch); PXD = pd.DataFrame([dict(group=r, n=len(g), q25=g.px_ratio.quantile(.25), median=g.px_ratio.median(), q75=g.px_ratio.quantile(.75), within_10pct=float(((g.px_ratio > .9) & (g.px_ratio < 1.1)).mean())) for r, g in PR.groupby('reason')] +
    [dict(group='all kept reasons', n=len(PR), q25=PR.px_ratio.quantile(.25), median=PR.px_ratio.median(), q75=PR.px_ratio.quantile(.75), within_10pct=float(((PR.px_ratio > .9) & (PR.px_ratio < 1.1)).mean())), dict(group='chance: random same-right solo sale', n=len(ch), q25=np.quantile(ch, .25), median=np.median(ch), q75=np.quantile(ch, .75), within_10pct=float(((ch > .9) & (ch < 1.1)).mean()))])
PXD.round(4).to_csv(f'{OUT}/bl_d0e_px.csv', index=False); print(PXD.round(3).to_string(index=False))
# ---- ladder-state features: price now of the contract of the last same-right sale / its sale price; ATM premium / last sale price; seconds since; sales in the last 60 s
body = O[(O.module == 'num') & (O.dayno == 1) & (O.role == 'open_short')].copy(); cm = {(u, str(e)): i for i, (u, e) in enumerate(zip(CY.und, CY.expiry))}; body['cid'] = [cm.get((a, str(b)), -1) for a, b in zip(body.und, body.expiry)]; body = body[body.cid >= 0].sort_values('tod')
feats = []
for (cid, cp), g in PN.groupby(['cid', 'cp']):
    r = CY.iloc[cid]; op = OPT[(r.und, r.expiry)]; kidx = {int(k): n for n, k in enumerate(op['K'])}; C = op[(cp, 'close')]; b = body[(body.cid == cid) & (body.cp == cp)]; bt = b.tod.values; bp = b.px_avg.values; bk = b.strike.values
    for q in g.itertuples():
        start = 33300 + 60 * q.j; n = int(np.searchsorted(bt, start) )
        if n == 0: feats.append((q.row, np.nan, np.nan, 3600.0, 0.0)); continue
        k = int(bk[n - 1]); c_now = C[kidx[k], q.j - 1] if k in kidx else np.nan
        feats.append((q.row, c_now / bp[n - 1] if bp[n - 1] > 0 else np.nan, q.atm_px / bp[n - 1] if bp[n - 1] > 0 else np.nan, min(start - bt[n - 1], 3600.0), float(((bt < start) & (bt >= start - 60)).sum())))
LF = pd.DataFrame(feats, columns=['row', 'lad_same_contract', 'lad_atm_vs_last', 'secs_since_last_sale', 'sales_prev60s']); PN = PN.merge(LF, on='row', how='left'); G['ladder'] = ['lad_same_contract', 'lad_atm_vs_last', 'secs_since_last_sale', 'sales_prev60s']
V1 = ['base', 'spot', 'prem', 'book', 'bb']; rows = []
for sl, yc in (('replacement solo', 'y_repl'), ('other solo', 'y_other')):
    cs = SO[(SO.row >= 0) & (SO.slice == sl)].groupby('row').lots.sum(); PN[yc] = PN.row.map(cs).fillna(0).gt(0).astype(float)
    for nm, gs in (('V1 causal', V1), ('V1 + ladder-state features (post-hoc)', V1 + ['ladder'])):
        cols = sum([G[g] for g in gs], []); p = loco(PN, cols, yc); sc = score(PN, p, yc); m = mk().fit(PN[PN.cid.isin(tr)][cols].values, PN[PN.cid.isin(tr)][yc].values); d = PN[PN.cid.isin(te)]
        rows.append(dict(slice=sl, variant=nm, auc=sc['auc'], lo=sc['lo'], hi=sc['hi'], within_cycle_auc=sc['within_cycle_auc'], forward_auc=roc_auc_score(d[yc], m.predict_proba(d[cols].values)[:, 1]))); print(rows[-1])
LD = pd.DataFrame(rows); LD.round(4).to_csv(f'{OUT}/bl_d0e_ladder.csv', index=False)
rec('d0e2', dict(hours=HR.to_dict(), cond=CD.round(4).to_dict('records'), sep=SEP.head(8).round(5).to_dict('records'), px=PXD.round(4).to_dict('records'), ladder=LD.round(4).to_dict('records'), **R))
