"""Leg attribution on the HOLD_SETTLE baseline (base slippage/costs). Per-leg net is rebuilt from trades+settlement with the same cost functions and cross-checked to the reported cycle net."""
import json, math
from common import *
d = cycles('HOLD', 'HOLD_SETTLE'); intr = lambda cp, K, S: max(S - K, 0.0) if cp == 'CE' else max(K - S, 0.0)
rows = []; chk = []
for r in d.itertuples():
    c = Cy.load(r.und, str(r.expiry)[:10]); px = A.Px(c); lot = c['lot_d1'] if 'lot_d1' in c else r.lot; res = {}
    E1 = scen.epoch(c['d1'], '15:29'); E0o = scen.epoch(c['d0'], '09:15')
    for lid in ('SCE', 'SPE', 'WCE', 'WPE'):
        lg = c['legs'][lid]; trs = [t for t in r.trades if t[1] == lid]
        if not trs: continue
        t = trs[0]; q = t[3]; side = t[2]; ref, exe = t[4], t[5]; cp = lg['cp']; k = lg['strike']
        sv = [x for x in r.settle if x[0] == lid]; sval = sv[0][2] if sv else 0.0
        cost = sum(A.order_costs(r.und, c['d1'], tt[2], tt[3] * tt[5]) for tt in trs) + (A.stt_exercise(str(r.d0)[:10]) * sval * q if (side > 0 and sval > 0) else 0.0)
        gross = r.leg_pnl[lid]; net_px = -side * q * exe + side * q * sval; net_leg = net_px - cost
        # path of leg MTM (entry exec -> marks); positive = good for the position
        m = []
        for tt, cl in zip(px.start[lid], px.close[lid]):
            if tt + 60 >= t[0]: m.append((tt + 60, side * q * (cl - exe)))
        mt = np.array([v for _, v in m]); ts = np.array([x for x, _ in m])
        mtm_d1 = [v for x, v in m if x <= E1 + 60]; mtm_d1 = mtm_d1[-1] if mtm_d1 else np.nan
        pre_open = [v for x, v in m if x <= E0o + 60]; pre_open = pre_open[-1] if pre_open else np.nan
        res[lid] = dict(side=side, qty=q, strike=k, entry_ref=ref, entry_exec=exe, premium_cash=-side * q * exe, settle_value_pts=sval, gross=gross, net=net_leg, costs=cost, slip=(gross - net_px), mae=float(mt.min()) if len(mt) else np.nan, mfe=float(mt.max()) if len(mt) else np.nan,
                        mtm_d1_close=mtm_d1, mtm_d0_open=pre_open, substituted=lg['substituted'], entry_minute=lg['hm'], dist_from_K=abs(k - r.K), traded_vol=lg['volume'])
    tot = sum(v['net'] for v in res.values()); chk.append(abs(tot - r.net))
    row = dict(und=r.und, expiry=str(r.expiry)[:10], split=r.split, subset=r.subset, K=r.K, W=c['W'], close=r.official_close, net=r.net, gross=r.gross, move_pts=r.official_close - r.K, spot_d1_close=float(c['spot_d1'].close.iloc[-1]) if hasattr(c['spot_d1'], 'close') else np.nan)
    for lid, v in res.items():
        for kk, vv in v.items(): row[f'{lid}_{kk}'] = vv
    rows.append(row)
L = pd.DataFrame(rows); L.to_csv(f'{RES}/leg_attribution_cycles.csv', index=False)
print('max |sum(leg nets) - cycle net| =', max(chk))
legs = ('SCE', 'SPE', 'WCE', 'WPE'); out = []
for p in ('IS', 'OOS', 'OOS_exposed', 'OOS_clean'):
    for u in ('COMBINED', 'NIFTY', 'SENSEX'):
        m = L[L.split.eq('IS') if p == 'IS' else (L.split.eq('OOS') if p == 'OOS' else (L.subset.eq('OOS_EXPOSED') if p == 'OOS_exposed' else L.subset.isin(['OOS_CLEAN_BEFORE', 'OOS_CLEAN_AFTER'])))]
        if u != 'COMBINED': m = m[m.und == u]
        for lg in legs:
            g = m[f'{lg}_gross']; n = m[f'{lg}_net']
            out.append(dict(part=p, scope=u, leg=lg, cycles=int(g.notna().sum()), premium_cash_flow=m[f'{lg}_premium_cash'].sum(), gross_pnl=g.sum(), net_pnl=n.sum(), costs=m[f'{lg}_costs'].sum(), slippage=m[f'{lg}_slip'].sum(), mean_net=n.mean(), pct_cycles_positive=(n > 0).mean(), mean_MAE=m[f'{lg}_mae'].mean(), mean_MFE=m[f'{lg}_mfe'].mean(),
                            mean_MTM_at_D1_close=m[f'{lg}_mtm_d1_close'].mean(), substituted_share=m[f'{lg}_substituted'].mean(), mean_distance_from_K=m[f'{lg}_dist_from_K'].mean()))
O = pd.DataFrame(out); O.to_csv(f'{RES}/leg_attribution_summary.csv', index=False)
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30); print(O[O.scope == 'COMBINED'].round(0).to_string(index=False))
# wing diagnostics: did the wing ever finish ITM, payoff vs cost, wings in worst cycles
W = []
for r in L.itertuples():
    for lg, cp in (('WCE', 'CE'), ('WPE', 'PE')):
        pv = getattr(r, f'{lg}_settle_value_pts'); 
        if pv == pv: W.append(dict(und=r.und, split=r.split, subset=r.subset, leg=lg, dist=getattr(r, f'{lg}_dist_from_K'), subst=getattr(r, f'{lg}_substituted'), cost_cash=-getattr(r, f'{lg}_premium_cash'), settle_pts=pv, itm=pv > 0, gross=getattr(r, f'{lg}_gross'), net=getattr(r, f'{lg}_net')))
W = pd.DataFrame(W); W.to_csv(f'{RES}/wing_cycles.csv', index=False)
ws = W.groupby(['und', 'leg']).agg(n=('net', 'size'), mean_dist=('dist', 'mean'), substituted=('subst', 'mean'), prem_paid=('cost_cash', 'sum'), itm_rate=('itm', 'mean'), gross_pnl=('gross', 'sum'), net_pnl=('net', 'sum')).reset_index(); ws.to_csv(f'{RES}/wing_summary.csv', index=False); print(ws.round(2).to_string(index=False))
# worst-10 cycles: what the wings did
wk = L.sort_values('net').head(10)[['und', 'expiry', 'subset', 'net', 'move_pts', 'W', 'SCE_gross', 'SPE_gross', 'WCE_gross', 'WPE_gross', 'WCE_dist_from_K', 'WPE_dist_from_K', 'WCE_substituted', 'WPE_substituted']]; wk.to_csv(f'{RES}/worst10_leg_view.csv', index=False); print(wk.round(0).to_string(index=False))
# nominal-wing counterfactual: how often is a wing at the *rulebook* distance actually reached by the move? (|move| > W)
L['abs_move'] = L.move_pts.abs(); L['move_exceeds_W'] = L.abs_move > L.W; print('share of cycles with |close-K| > rulebook W:', L.groupby('und').move_exceeds_W.mean().round(3).to_dict())
# wing-substituted cycles vs not: effect on worst cycle (tail)
L['any_subst'] = L.WCE_substituted.fillna(False).astype(bool) | L.WPE_substituted.fillna(False).astype(bool)
print(L.groupby(['und', 'any_subst']).net.agg(['count', 'mean', 'min', 'sum']).round(0))
L[['und', 'expiry', 'any_subst', 'move_exceeds_W', 'abs_move']].to_csv(f'{RES}/wing_reach.csv', index=False)
