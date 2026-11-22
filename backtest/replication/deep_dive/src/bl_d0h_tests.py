"""D0 chunk 3 (plan reports/D0_HEDGE_PLAN.md): H1 controller quantity (h_ waves vs gap S - L, all modules, D-1 carried position; variant without v_ positions), H2 wing strike
(premium nearest X% of the ATM same-right premium; X = 2.5% unchanged and refit out-of-fold), H3 release choice, H4 timing (seconds since the last body order on that right),
H5 h_ shorts/covers, H6 lump salvage (v_ close_long) description and simple rules, H7 body-stream longs on D0.
Outputs bl_d0h_waves.csv, bl_d0h_buys.csv, bl_d0h_release.csv, bl_d0h_bodylong.csv, bl_d0h_lump.csv, bl_d0h_h2.csv, bl_d0h_h6.csv, bl_summary_d0h1.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); O = load_orders(); OPT = pd.read_pickle(f'{OUT}/bl_d0_opt.pkl.gz'); SPT = pd.read_pickle(f'{OUT}/bl_d0_spot.pkl.gz'); R = {}
D0C = [i for i, r in enumerate(CY.itertuples()) if ((O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 1)).any()]
WV, BY, RL, BW, LP = [], [], [], [], []
for i in D0C:
    r = CY.iloc[i]; z = O[(O.und == r.und) & (O.expiry == r.expiry)].copy(); z['ts'] = np.where(z.dayno == 0, z.t_dec.fillna(z.te) - 100000 * 0, z.t_dec.fillna(z.tod)); z['sg'] = np.where(z.side.str.lower() == 'buy', 1, -1)
    z0 = z[z.dayno == 0]; z1 = z[z.dayno == 1].sort_values(['ts', 'row']); pos = {}; posv = {}; lumpe = {}
    for q in z0.itertuples():
        k = (q.cp, int(q.strike)); pos[k] = pos.get(k, 0) + q.sg * q.lots
        if q.module == 'v_': posv[k] = posv.get(k, 0) + q.sg * q.lots
        if q.module == 'v_' and q.sg > 0: lumpe.setdefault(k, []).append((q.px_avg, q.lots))
    op = OPT[(r.und, r.expiry)]; K = op['K']; c = SPT[(r.und, r.expiry)].close.values; st = ref.STEP[r.und]; first_buy = {}; last_buy = {}; last_body = {'CE': -1e9, 'PE': -1e9}
    def gap(cp, excl_v=False):
        p = {k: v - (posv.get(k, 0) if excl_v else 0) for k, v in pos.items()}; s = -sum(v for (c2, _), v in p.items() if c2 == cp and v < 0); l = sum(v for (c2, _), v in p.items() if c2 == cp and v > 0); return s, l
    rows = list(z1.itertuples()); n = len(rows); k_ = 0
    while k_ < n:
        q = rows[k_]; j = min(max(int((q.tod - 33300) // 60), 1), 374)
        if q.module == 'h_':
            grp = [q]; m = k_ + 1
            while m < n and rows[m].module == 'h_' and rows[m].cp == q.cp and rows[m].ts - q.ts <= 0.05: grp.append(rows[m]); m += 1
            s, l = gap(q.cp); s2, l2 = gap(q.cp, True); ls = sum(g.sg * g.lots for g in grp)
            WV.append(dict(cid=i, cp=q.cp, ts=q.ts, j=j, lots_signed=ls, gap=s - l, gap_excl_v=s2 - l2, n_orders=len(grp), kind='buy' if grp[0].sg > 0 else 'sell', roles='/'.join(sorted({g.role for g in grp})), dt_body=q.ts - last_body[q.cp]))
            for g in grp:
                jj = min(max(int((g.tod - 33300) // 60), 1), 374)
                if g.role == 'open_long':
                    ce = op[(g.cp, 'close')][:, jj - 1]; atmx = np.argmin(np.abs(K - c[jj - 1])); BY.append(dict(cid=i, cp=g.cp, j=jj, strike=float(g.strike), atm_px=ce[atmx], spot=c[jj - 1], lots=g.lots, ki=int(np.argmin(np.abs(K - g.strike)))))
                if g.role == 'close_long':
                    held = [(kk, v) for (c2, kk), v in pos.items() if c2 == g.cp and v > 0]
                    if len(held) >= 2:
                        hk = np.array([h_[0] for h_ in held], float); px = np.array([op[(g.cp, 'close')][np.argmin(np.abs(K - kk)), jj - 1] for kk in hk]); otm = (hk - c[jj - 1]) * (1 if g.cp == 'CE' else -1)
                        atm = op[(g.cp, 'close')][np.argmin(np.abs(K - c[jj - 1])), jj - 1]
                        cand = dict(outermost=hk[np.argmax(otm)], innermost=hk[np.argmin(otm)], cheapest=hk[np.nanargmin(px)] if np.isfinite(px).any() else np.nan, dearest=hk[np.nanargmax(px)] if np.isfinite(px).any() else np.nan,
                                    oldest=min(hk, key=lambda kk: first_buy.get((g.cp, kk), -1e9)), newest=max(hk, key=lambda kk: last_buy.get((g.cp, kk), -1e9)), near_2p5_atm=hk[np.nanargmin(np.abs(px - 0.025 * atm))] if np.isfinite(px).any() else np.nan)
                        RL.append(dict(cid=i, cp=g.cp, j=jj, sold=float(g.strike), n_held=len(held), chance=1 / len(held), **{f'hit_{a}': float(b == g.strike) for a, b in cand.items()}))
                kk = (g.cp, int(g.strike)); pos[kk] = pos.get(kk, 0) + g.sg * g.lots
                if g.sg > 0: first_buy.setdefault((g.cp, float(g.strike)), g.ts); last_buy[(g.cp, float(g.strike))] = g.ts
            k_ = m; continue
        if q.module == 'num' and q.role in ('open_long', 'close_long'):
            s0, l0 = gap(q.cp); BW.append(dict(cid=i, cp=q.cp, tod=q.tod, j=j, role=q.role, lots=q.lots, strike=q.strike, otm_steps=(q.strike - c[j - 1]) / st * (1 if q.cp == 'CE' else -1), S_before=s0, L_before=l0))
        if q.module == 'v_' and q.role == 'close_long':
            ke = lumpe.get((q.cp, int(q.strike)), []); e = sum(p_ * n_ for p_, n_ in ke) / max(sum(n_ for _, n_ in ke), 1) if ke else np.nan
            LP.append(dict(cid=i, cp=q.cp, tod=q.tod, j=j, lots=q.lots, strike=q.strike, px=q.px_avg, entry=e, ratio=q.px_avg / e if e == e and e > 0 else np.nan, otm_steps=(q.strike - c[j - 1]) / st * (1 if q.cp == 'CE' else -1)))
        if q.module == 'num' and q.role in ('open_short', 'cover_short'): last_body[q.cp] = q.ts
        kk = (q.cp, int(q.strike)); pos[kk] = pos.get(kk, 0) + q.sg * q.lots
        if q.module == 'v_': posv[kk] = posv.get(kk, 0) + q.sg * q.lots
        if q.sg > 0: first_buy.setdefault((q.cp, float(q.strike)), q.ts); last_buy[(q.cp, float(q.strike))] = q.ts
        k_ += 1
W = pd.DataFrame(WV); BYd = pd.DataFrame(BY); L = pd.DataFrame(RL); B = pd.DataFrame(BW); LPd = pd.DataFrame(LP)
for nm, df in (('waves', W), ('buys', BYd), ('release', L), ('bodylong', B), ('lump', LPd)): df.to_csv(f'{OUT}/bl_d0h_{nm}.csv', index=False)
# H1
R['H1'] = {kd: dict(waves=int(len(g)), equals_gap=float((g.lots_signed == g.gap).mean()), equals_gap_excl_v=float((g.lots_signed == g.gap_excl_v).mean()), sign_right=float((np.sign(g.lots_signed) == np.sign(g.gap)).mean()), lots=int(g.lots_signed.abs().sum())) for kd, g in W.groupby('kind')}
R['H1']['by_hour_equals_gap'] = W.assign(h=(W.ts // 3600).astype(int)).groupby('h').apply(lambda g: float((g.lots_signed == g.gap).mean())).round(3).to_dict()
# H2 wing strike: premium nearest X% of the ATM premium; X refit out-of-fold
XS_ = [0.005, 0.01, 0.015, 0.02, 0.025, 0.03, 0.04, 0.05, 0.075, 0.10]
def hit(df, x):
    ex = []; p1 = []
    for q in df.itertuples():
        r = CY.iloc[q.cid]; op = OPT[(r.und, r.expiry)]; pr = op[(q.cp, 'close')][:, q.j - 1]; K = op['K']; otm = (K - q.spot) * (1 if q.cp == 'CE' else -1) > 0; ok = otm & np.isfinite(pr)
        if not ok.any() or not (q.atm_px == q.atm_px): ex.append(np.nan); p1.append(np.nan); continue
        kk = K[ok][np.argmin(np.abs(pr[ok] - x * q.atm_px))]; ex.append(float(kk == q.strike)); p1.append(float(abs(kk - q.strike) <= ref.STEP[r.und] + 1e-6))
    return np.nanmean(ex), np.nanmean(p1)
h2 = []
for x in XS_: e, p = hit(BYd, x); h2.append(dict(X=x, exact=e, within1=p))
H2 = pd.DataFrame(h2); oof = []
for h in (0, 1):
    tr = BYd[BYd.cid % 2 != h]; te = BYd[BYd.cid % 2 == h]; bx = max(XS_, key=lambda x: hit(tr, x)[0]); e, p = hit(te, bx); oof.append(dict(half=h, X=bx, exact=e, within1=p, n=len(te)))
H2 = pd.concat([H2, pd.DataFrame(oof).assign(X=lambda d: d.X.astype(str) + ' (OOF half ' + d.half.astype(str) + ')')[['X', 'exact', 'within1']]], ignore_index=True); H2.to_csv(f'{OUT}/bl_d0h_h2.csv', index=False)
R['H2'] = dict(buys=int(len(BYd)), d1_rule_2p5=dict(zip(['exact', 'within1'], hit(BYd, 0.025))), oof=oof, chance_exact=0.1, chance_within1=0.3)
# H3, H4, H5
R['H3'] = dict(n=int(len(L)), chance=float(L.chance.mean()), **{c_[4:]: float(L[c_].mean()) for c_ in L.columns if c_.startswith('hit_')})
wb = W[(W.kind == 'buy') & (W.dt_body < 600)]; R['H4_dt_body_q_buy'] = wb.dt_body.quantile([.1, .25, .5, .75, .9]).tolist(); ws = W[(W.kind == 'sell') & (W.dt_body < 600)]; R['H4_dt_body_q_sell'] = ws.dt_body.quantile([.1, .25, .5, .75, .9]).tolist()
hs = O[(O.dayno == 1) & (O.module == 'h_') & O.role.isin(['open_short', 'cover_short'])]; R['H5'] = dict(by_role=hs.groupby('role').lots.sum().to_dict(), cycles=int(hs.groupby(['und', 'expiry']).ngroups), hours=hs.assign(h=(hs.tod // 3600).astype(int)).groupby(['role', 'h']).lots.sum().astype(int).to_dict())
R['H5']['hours'] = {f'{a}_{b}': v for (a, b), v in R['H5']['hours'].items()}
# H6 lump salvage
R['H6'] = dict(lots=int(LPd.lots.sum()), cycles=int(LPd.cid.nunique()), orders=int(len(LPd)), ratio_q=LPd.ratio.quantile([.1, .25, .5, .75, .9]).round(3).tolist(), hour=LPd.assign(h=(LPd.tod // 3600).astype(int)).groupby('h').lots.sum().to_dict(),
             first_sale_q=LPd.groupby('cid').tod.min().quantile([.1, .5, .9]).tolist(), orders_per_cycle_q=LPd.groupby('cid').size().quantile([.25, .5, .75]).tolist(), otm_steps_q=LPd.otm_steps.quantile([.1, .5, .9]).round(2).tolist(),
             share_ratio_ge1=float((LPd.ratio >= 1).mean()))
# H7 body-stream longs
B['window'] = np.where(B.tod < 33300 + 180, '09:15-09:17', np.where(B.tod >= 54540, '15:09+', 'other'))
R['H7'] = {f'{w}_{ro}': dict(lots=int(g.lots.sum()), orders=int(len(g)), otm_steps_med=float(g.otm_steps.median()), cycles=int(g.cid.nunique())) for (w, ro), g in B.groupby(['window', 'role'])}
rec('d0h1', R); print({k: R[k] for k in ('H1', 'H2', 'H3', 'H4_dt_body_q_buy', 'H4_dt_body_q_sell')}); print(R['H5']); print(R['H6']); print(R['H7']); print(H2.round(3).to_string(index=False))
