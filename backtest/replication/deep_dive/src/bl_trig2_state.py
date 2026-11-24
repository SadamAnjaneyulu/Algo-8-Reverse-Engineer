"""Late-sale trigger investigation, part 2 (plan: reports/LATE_SALE_TRIGGER_PLAN.md). EXPLORATORY.
O: 12 portfolio-state hazard features (stratified AUC within (cycle, side), curveball null, BH over the 24 primary tests together with part 1).
R1: package counterfactual: remove the late sales AND re-size the overnight lump with the cycle's realised ratio; compare premium, theta, worst D0-gap loss, |delta|.
Output outputs/trig2/state_hazard.csv, package.csv, tests_part2.json"""
import sys, os, json, warnings; sys.path.insert(0, '.'); sys.path.insert(0, '../..'); sys.path.insert(0, '../../..'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
import bl_bt3_sim as S, bl_d0x_diag as DG, bl_risk_book as B, bl_risk_tests as RT
OUT = S.OUT; T2 = f'{OUT}/trig2'; W0 = 54900; CAS = '2026-08-03'; OUTLIER = ('NIFTY', '2026-10-16')
NEW = ['sold_deficit', 'net_deficit', 'cover_same_5', 'cover_other_5', 'mtm_pnl', 'mtm_change_15', 'decay_same', 'peak_deficit_same', 'mins_since_sale', 'mins_since_cover', 'straddle_chg_15', 'straddle_vs_0920']
def run():
    O = DG.real_orders(); O = O.assign(jj=(O.t_first // 60 - 555).astype(int)); Tc = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv'); Tc = Tc[Tc.ok]; Bk = pd.read_csv(f'{OUT}/d0x/book_compare.csv'); keep = set(zip(Bk.und, Bk.expiry)); rows = []; pk = []
    for r in Tc.itertuples():
        if (r.und, r.expiry) not in keep or r.d0 < CAS or (r.und, r.d1) == OUTLIER: continue
        g = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 0)].sort_values(['t_first', 'row']).reset_index(drop=True)
        if not len(g): continue
        cx = pd.read_pickle(f'{OUT}/bt3x/{r.und}_{r.expiry}.pkl.gz'); op = cx['opt1']; Kc = op['K']; kidx = {int(k): i for i, k in enumerate(Kc)}; nmin = op[('CE', 'close')].shape[1]; spot = cx['spot1'].close.values; unit = float(r.unit)
        cyc = f'{r.und}|{r.expiry}'; t = g.t_first.values.astype(float); k = np.array([kidx.get(int(s), -1) for s in g.strike]); c = (g.cp == 'PE').astype(int).values; q = (g.sg * g.lots).values.astype(float); px = g.px_avg.values; role = g.role.values
        Pcl, Ppl = op[('CE', 'close')], op[('PE', 'close')]; Fprev = spot[300]
        def prices(j): jp = min(max(j - 1, 0), nmin - 1); return Pcl[:, jp], Ppl[:, jp]
        def straddle(j):
            nonlocal Fprev
            Pc, Pp = prices(j); F = B.parity_forward(Kc, Pc, Pp, Fprev)
            if F is None: return np.nan
            Fprev = F; i = int(np.argmin(np.abs(Kc - F))); return float(Pc[i] + Pp[i])
        def book_at(ts):
            pos = np.zeros((len(Kc), 2)); cash = 0.0
            for ti, ki, ci, qi, pi_ in zip(t, k, c, q, px):
                if ti >= ts: break
                if ki >= 0: pos[ki, ci] += qi; cash += -qi * pi_ * unit
            return pos, cash
        def mtm(ts, j):
            pos, cash = book_at(ts); Pc, Pp = prices(j); val = np.nansum(pos[:, 0] * np.nan_to_num(Pc)) + np.nansum(pos[:, 1] * np.nan_to_num(Pp)); return cash + val * unit
        st0920 = np.nanmean([straddle(j) for j in (4, 5, 6)]); Fprev = spot[300]; stg = {j: straddle(j) for j in range(300, nmin)}; peak = {0: 0.0, 1: 0.0}
        for j in range(300, nmin):
            ts = (555 + j) * 60.0; pos, cash = book_at(ts); sh = lambda ci: float(-pos[pos[:, ci] < 0, ci].sum())
            for ci in (0, 1): peak[ci] = max(peak[ci], sh(ci))
            if j < 360: continue
            sold = g[(role == 'open_short') & (t < ts)]; cov = g[(role == 'cover_short') & (t < ts)]; Pc, Pp = prices(j)
            m15 = mtm(ts - 900, j - 15); y = {cp: int(((g.role == 'open_short') & (g.cp == cp) & (g.jj == j)).any()) for cp in ('CE', 'PE')}
            for cp, ci in (('CE', 0), ('PE', 1)):
                o = 1 - ci; ss = sold[sold.cp == cp].lots.sum(); so = sold[sold.cp != cp].lots.sum(); price_now = (Pc if ci == 0 else Pp); ks = np.where(pos[:, ci] < 0)[0]
                if len(ks):
                    ent = []
                    for kk in ks:
                        sk = sold[(sold.cp == cp) & (sold.strike == Kc[kk])]; ent.append(float((sk.lots * sk.px_avg).sum() / sk.lots.sum()) if len(sk) else np.nan)
                    ent = np.array(ent); w = -pos[ks, ci]; ok = np.isfinite(ent) & np.isfinite(price_now[ks]); decay = float((w[ok] * price_now[ks][ok]).sum() / (w[ok] * ent[ok]).sum()) if ok.any() else np.nan
                else: decay = np.nan
                rows.append(dict(cyc=cyc, und=r.und, d1=r.d1, era='after', outlier=0, j=j, side=cp, y=y[cp], sold_deficit=so - ss, net_deficit=sh(o) - sh(ci), cover_same_5=float(cov[(cov.cp == cp) & (cov.t_first >= ts - 300)].lots.sum()), cover_other_5=float(cov[(cov.cp != cp) & (cov.t_first >= ts - 300)].lots.sum()),
                                 mtm_pnl=cash + (np.nansum(pos[:, 0] * np.nan_to_num(Pc)) + np.nansum(pos[:, 1] * np.nan_to_num(Pp))) * unit, mtm_change_15=(cash + (np.nansum(pos[:, 0] * np.nan_to_num(Pc)) + np.nansum(pos[:, 1] * np.nan_to_num(Pp))) * unit) - m15, decay_same=decay, peak_deficit_same=peak[ci] - sh(ci),
                                 mins_since_sale=float((ts - sold.t_first.max()) / 60) if len(sold) else float(j), mins_since_cover=float((ts - cov.t_first.max()) / 60) if len(cov) else float(j), straddle_chg_15=float(stg[j] / stg[j - 15] - 1) if np.isfinite(stg[j]) and np.isfinite(stg[j - 15]) else np.nan, straddle_vs_0920=float(stg[j] / st0920) if np.isfinite(stg[j]) else np.nan))
        # ---------------- R1 package counterfactual
        jend = nmin - 1; vv = B.parity_forward(Kc, Pcl[:, jend - 1], Ppl[:, jend - 1], spot[jend - 1])
        if vv is None: continue
        F = vv; now = pd.Timestamp(r.d1) + pd.Timedelta(hours=9, minutes=15 + jend); Tt = max((pd.Timestamp(r.d0) + pd.Timedelta(hours=15, minutes=30) - now).total_seconds() / 86400 / 365, 1e-5); V = B.leg_values(Kc, Pcl[:, jend - 1], Ppl[:, jend - 1], F, Tt)
        late = (role == 'open_short') & (t >= W0); lump = (g.module.values == 'v_') & (role == 'open_long'); pos_a = np.zeros((len(Kc), 2)); pos_c = np.zeros((len(Kc), 2))
        for ii in range(len(g)):
            if k[ii] < 0: continue
            pos_a[k[ii], c[ii]] += q[ii]
            if not late[ii] and not lump[ii]: pos_c[k[ii], c[ii]] += q[ii]
        n_a = float(g.lots.values[lump].sum()); extra = np.nan
        if n_a > 0:
            lside = int(np.round(np.average(c[lump], weights=g.lots.values[lump]))); t_l = t[lump].min(); sh_a = float(-sum(q[ii] for ii in range(len(g)) if t[ii] < t_l and c[ii] == lside and q[ii] != 0 and (role[ii] in ('open_short', 'cover_short')) and not lump[ii]))
            sh_c = float(-sum(q[ii] for ii in range(len(g)) if t[ii] < t_l and c[ii] == lside and (role[ii] in ('open_short', 'cover_short')) and not (late[ii] and role[ii] == 'open_short')))
            ratio = n_a / sh_a if sh_a > 0 else np.nan; n_c = max(round(ratio * sh_c), 0) if np.isfinite(ratio) else n_a; f = n_c / n_a
            for ii in np.where(lump)[0]:
                if k[ii] >= 0: pos_c[k[ii], c[ii]] += q[ii] * f
            lump_px = float(np.average(px[lump], weights=g.lots.values[lump])); extra = (n_a - n_c) * lump_px * unit
        else: n_c = 0
        sA, sC = B.state(pos_a, V, F, unit), B.state(pos_c, V, F, unit); late_prem = float((g.lots.values[late] * px[late]).sum() * unit)
        pk.append(dict(cyc=cyc, und=r.und, d1=r.d1, late_lots=float(g.lots.values[late].sum()), lump_actual=n_a, lump_counterfactual=float(n_c), late_premium=late_prem, extra_lump_cost=float(extra) if np.isfinite(extra) else np.nan,
                       d_theta=sA['theta'] - sC['theta'], d_gap=sA['gap_worst'] - sC['gap_worst'], gap_cf=sC['gap_worst'], d_absdelta=abs(sA['delta_rs_pct']) - abs(sC['delta_rs_pct']), d_net_premium=late_prem - (float(extra) if np.isfinite(extra) else 0.0)))
        print(cyc, 'rows', len(rows), flush=True)
    M = pd.DataFrame(rows); M.to_csv(f'{T2}/state_minutes.csv', index=False); PKG = pd.DataFrame(pk); PKG.to_csv(f'{T2}/package.csv', index=False)
    RT.FEATS = NEW; RT.NPERM = int(os.environ.get('NPERM', 1000)); H, meta = RT.hazard(M, 360, 384, 'post 15:15-15:39'); H['p_bh'] = RT.bh(H.p.values); H.to_csv(f'{T2}/state_hazard.csv', index=False)
    P = PKG[PKG.late_lots > 0]; ok = P.extra_lump_cost.notna(); out = dict(hazard_meta=meta, package=dict(cycles=int(len(P)), theta_up=int((P.d_theta > 0).sum()), median_d_theta=float(P.d_theta.median()), median_d_gap=float(P.d_gap.median()), median_gap_relative=float((P.d_gap / P.gap_cf.abs()).median()), gap_not_worse_5pct=int((P.d_gap / P.gap_cf.abs() >= -0.05).sum()), gap_improved=int((P.d_gap > 0).sum()),
                                                               median_d_absdelta=float(P.d_absdelta.median()), median_late_premium=float(P.late_premium.median()), median_extra_lump_cost=float(P.extra_lump_cost[ok].median()), net_premium_positive=int((P.d_net_premium > 0).sum()), lump_actual_vs_cf=[float(P.lump_actual.median()), float(P.lump_counterfactual.median())]))
    json.dump(out, open(f'{T2}/tests_part2.json', 'w'), indent=1, default=float); print(H.round(3).to_string(index=False)); print(json.dumps(out['package'], default=lambda z: round(float(z), 3)))
if __name__ == '__main__': run()
