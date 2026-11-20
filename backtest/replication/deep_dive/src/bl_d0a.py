"""D0 study, parts A (opening inventory) and B (strike selection). Independent of the D-1 scripts except for the overnight inventory table (a state, not a rule)."""
import sys; sys.path.insert(0, '.')
from bl_common import *
O = load_orders(); cyc = pd.read_csv(ref.CYCLES); ch = Chain(); KN = {(u, e): (h1, h0, k) for u, e, h1, h0, k in zip(cyc.und, cyc.expiry, cyc.has_d1, cyc.has_d0, cyc.carry_in_known)}
CR = pd.read_csv(f'{OUT}/bl_d1_D_overnight_inventory.csv')
# ---- A opening inventory
print('A. cycles: carry-in known', sum(v[2] for v in KN.values()), 'of', len(KN), '| D-1 log missing', sum(not v[0] for v in KN.values()), '| D0 log missing', sum(not v[1] for v in KN.values()))
inv = CR.groupby(['und', 'expiry', 'side']).apply(lambda g: pd.Series(dict(contracts=len(g), lots=g.net.abs().sum()))).unstack('side').fillna(0); inv.columns = ['_'.join(c) for c in inv.columns]; inv.to_csv(f'{OUT}/bl_d0_A_opening_inventory.csv')
print('opening inventory per cycle: short lots median %.0f (IQR %s), long lots median %.0f (IQR %s); short contracts median %.0f' % (inv.lots_short.median(), inv.lots_short.quantile([.25, .75]).tolist(), inv.lots_long.median(), inv.lots_long.quantile([.25, .75]).tolist(), inv.contracts_short.median()))
sh = CR[CR.side == 'short']; sp0 = {}
for (u, e), g in sh.groupby(['und', 'expiry']):
    a = ch.spot(u, e, 0, 374); b = ch.spot(u, e, 1, 0); sp0[(u, e)] = (b - a) / ref.STEP[u]
gap = pd.Series(sp0); print('D0 open gap vs D-1 close (steps): quantiles', gap.quantile([.1, .25, .5, .75, .9]).round(2).tolist())
# opening inventory relative to the D0 open spot (moneyness of carried shorts at open)
def mny(r):
    s = ch.spot(r.und, r.expiry, 1, 0); st = (r.strike - s) / ref.STEP[r.und]; return st if r.right == 'CE' else -st
sh = sh.assign(otm_steps_at_d0_open=sh.apply(mny, axis=1)); print('carried shorts at the D0 open: share ITM %.3f ; |steps from spot| quantiles %s' % ((sh.otm_steps_at_d0_open < 0).mean(), sh.otm_steps_at_d0_open.abs().quantile([.25, .5, .75, .9]).round(1).tolist()))
# unrecorded carry-in: D0 body buys that are not covers of recorded shorts (role open_long) by cycle completeness
b0 = O[(O.module == 'num') & (O.dayno == 1)]; ol = b0[b0.role == 'open_long'].assign(known=lambda d: [KN[(u, e)][2] for u, e in zip(d.und, d.expiry)]); print('D0 body Buys with no recorded short (open_long): known-carry cycles %d lots (%d cycles), unknown-carry-in cycles %d lots (%d cycles)' % (ol[ol.known].lots.sum(), ol[ol.known].groupby(['und', 'expiry']).ngroups, ol[~ol.known].lots.sum(), ol[~ol.known].groupby(['und', 'expiry']).ngroups))
print('   timing of those Buys: minute-of-D0 quantiles (known / unknown):', ((ol[ol.known].tod - ref.OPEN_SEC) / 60).quantile([.5, .9]).round(1).tolist(), ((ol[~ol.known].tod - ref.OPEN_SEC) / 60).quantile([.5, .9]).round(1).tolist())
# ---- B strike selection on D0
S = b0[b0.role == 'open_short'].copy(); S['hit_prev'] = S.strike == S.atm_prev; S['hit_cur'] = S.strike == S.atm_cur; S['pm1'] = (S.strike - S.atm_prev).abs() <= S.step * 1.0001; S['hour'] = (S.tod // 3600).astype(int)
S['mins'] = (S.tod - ref.OPEN_SEC) / 60
# strike status: carried (short at D0 open), opened earlier on D0, or new
carried = set((u, e, c, k) for u, e, c, k in zip(sh.und, sh.expiry, sh.right, sh.strike)); ST = []
for r in S.itertuples():
    nb = r.net_after - r.sl
    ST.append('carried_strike' if (r.und, r.expiry, r.cp, r.strike) in carried and nb < 0 else ('existing_short_strike' if nb < 0 else 'new_strike'))
S['status'] = ST; t = S.groupby('cls').agg(orders=('tag', 'size'), lots=('lots', 'sum'), exact_prev=('hit_prev', 'mean'), exact_cur=('hit_cur', 'mean'), within1=('pm1', 'mean')).round(3); t['share_lots'] = (t.lots / t.lots.sum()).round(3); t.to_csv(f'{OUT}/bl_d0_B_class.csv'); print(t.to_string())
print('D0 sells by strike status (lots share):', (S.groupby('status').lots.sum() / S.lots.sum()).round(3).to_dict(), '| by status hit_prev', S.groupby('status').hit_prev.mean().round(3).to_dict())
S['off'] = ((S.strike - S.atm_prev) / S.step).round(); S['itm'] = np.where(S.cp == 'CE', -S.off, S.off); print('D0 offset (steps; + = ITM side) distribution by class:'); print(S.groupby('cls').itm.value_counts(normalize=True).unstack(0).loc[-3:3].round(3).to_string())
# causal reference test on D0 scheduled-minute orders and boundary test
sm = S[S.cls == 'slot_minute']; d = sm[sm.atm_prev != sm.atm_cur]; print('D0 slot_minute with atm_prev != atm_cur: n', len(d), '| K==atm_prev %.3f K==atm_cur %.3f' % ((d.strike == d.atm_prev).mean(), (d.strike == d.atm_cur).mean()))
sm = sm.assign(u=(sm.spot_prev - sm.atm_prev).abs() / sm.step); print('D0 slot_minute hit by distance of spot_prev from strike:', sm.groupby(pd.cut(sm.u, [0, .2, .4, .5])).hit_prev.agg(['size', 'mean']).round(3).to_dict('index'))
print('D0 hit_prev by time since open (minutes): ', S.groupby(pd.cut(S.mins, [-1, 5, 15, 30, 60, 120, 240, 400])).hit_prev.agg(['size', 'mean']).round(3).to_dict('index'))
print('D0 hit_prev by hour (all sells):', S.groupby('hour').hit_prev.mean().round(3).to_dict(), '| by und', S.groupby('und').hit_prev.mean().round(3).to_dict())
sh.to_csv(f'{OUT}/bl_d0_A_carried_shorts.csv', index=False)

sm_ = S[S.cls == 'slot_minute']; d_ = sm_[sm_.atm_prev != sm_.atm_cur]; sm2 = sm_.assign(u=(sm_.spot_prev - sm_.atm_prev).abs() / sm_.step)
rec('d0a', dict(known=sum(v[2] for v in KN.values()), n_cycles=len(KN), d1_missing=sum(not v[0] for v in KN.values()), d0_missing=sum(not v[1] for v in KN.values()), inv_short_lots_med=inv.lots_short.median(), inv_short_lots_q=inv.lots_short.quantile([.25, .75]), inv_long_lots_med=inv.lots_long.median(), inv_long_lots_q=inv.lots_long.quantile([.25, .75]), inv_short_contracts_med=inv.contracts_short.median(), inv_n=len(inv), gap_q=gap.quantile([.1, .25, .5, .75, .9]),
  open_itm_share=(sh.otm_steps_at_d0_open < 0).mean(), open_abs_q=sh.otm_steps_at_d0_open.abs().quantile([.25, .5, .75, .9]), ol_known_lots=ol[ol.known].lots.sum(), ol_known_cyc=ol[ol.known].groupby(['und', 'expiry']).ngroups, ol_unknown_lots=ol[~ol.known].lots.sum(), ol_unknown_cyc=ol[~ol.known].groupby(['und', 'expiry']).ngroups,
  status_share=(S.groupby('status').lots.sum() / S.lots.sum()), status_hit=S.groupby('status').hit_prev.mean(), causal_n=len(d_), causal_prev=(d_.strike == d_.atm_prev).mean(), causal_cur=(d_.strike == d_.atm_cur).mean(), bound={str(k): float(v) for k, v in sm2.groupby(pd.cut(sm2.u, [0, .2, .4, .5])).hit_prev.mean().items()},
  hit_hour=S.groupby('hour').hit_prev.mean(), hit_und=S.groupby('und').hit_prev.mean(), hit_mins={str(k): float(v) for k, v in S.groupby(pd.cut(S.mins, [-1, 5, 15, 30, 60, 120, 240, 400])).hit_prev.mean().items()}, n_sells=len(S), lots_sells=S.lots.sum(), itm_dist=S.groupby('cls').itm.value_counts(normalize=True).unstack(0).loc[-3:3].round(3).fillna(0).to_dict()))
