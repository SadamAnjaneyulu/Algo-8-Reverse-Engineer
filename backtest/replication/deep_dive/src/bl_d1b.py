"""D-1 study, parts C (lifecycle) and D (ending logic). Outputs outputs/bl_d1_C_*.csv, bl_d1_D_*.csv"""
import sys; sys.path.insert(0, '.')
from bl_common import *
O = load_orders(); cyc = pd.read_csv(ref.CYCLES); D1 = O[O.dayno == 0]; ch = Chain()
OK = set((u, e) for u, e, h in zip(cyc.und, cyc.expiry, cyc.has_d1) if h)       # cycles with a D-1 log
# ---------------- C: strike-position table (contract level, all modules), D-1 only
rows = []
for (u, e, cp, k), g in D1[D1.expiry.isin([e for (uu, e) in OK])].groupby(['und', 'expiry', 'cp', 'strike']):
    if (u, e) not in OK: continue
    g = g.sort_values(['te', 'row']); net = g.sl.cumsum(); sold = g[(g.side == 'Sell')]; cov = g[(g.side == 'Buy')]
    if net.min() >= 0: continue                                  # never short on D-1
    first_short = g.te[net < 0].iloc[0] % 100000; flat_after = (net >= 0) & (net.shift(1) < 0)
    t_flat = g.te[flat_after].iloc[-1] % 100000 if (net.iloc[-1] >= 0 and flat_after.any()) else np.nan
    rows.append((u, e, cp, k, g.lots[g.side == 'Sell'].sum(), len(sold), cov.lots.sum(), -net.min(), net.iloc[-1], first_short, t_flat, g[g.module == 'num'].lots.sum()))
P = pd.DataFrame(rows, columns=['und', 'expiry', 'right', 'strike', 'lots_sold', 'sell_orders', 'lots_bought', 'peak_short', 'net_end_D1', 'first_short_tod', 'last_flat_tod', 'body_lots']); P['carried_short'] = P.net_end_D1 < 0; P['closed_in_D1'] = P.net_end_D1 >= 0
P['hold_min'] = (P.last_flat_tod - P.first_short_tod) / 60; P.to_csv(f'{OUT}/bl_d1_C_positions.csv', index=False)
print('D-1 short strike-positions (cycle x right x strike):', len(P), 'in', P.groupby(['und', 'expiry']).ngroups, 'cycles | carried short', P.carried_short.sum(), '(%.3f)' % P.carried_short.mean(), '| closed in D-1', P.closed_in_D1.sum())
print('lots sold per position quantiles', P.lots_sold.quantile([.25, .5, .75, .9]).tolist(), '| peak short quantiles', P.peak_short.quantile([.25, .5, .75, .9]).tolist(), '| sell orders per position', P.sell_orders.quantile([.25, .5, .75]).tolist())
print('strikes per (cycle,right) with short on D-1: median %.0f IQR %s' % (P.groupby(['und', 'expiry', 'right']).size().median(), P.groupby(['und', 'expiry', 'right']).size().quantile([.25, .75]).tolist()))
print('hold minutes (closed positions, first short -> last flat): quantiles', P.hold_min.dropna().quantile([.1, .25, .5, .75, .9]).round(0).tolist())
# share of D-1 sold lots (body) carried: lots carried / lots sold (contract level)
print('lots: sold %d ; carried short at D-1 end %d (%.3f)' % (P.lots_sold.sum(), -P[P.net_end_D1 < 0].net_end_D1.sum(), -P[P.net_end_D1 < 0].net_end_D1.sum() / P.lots_sold.sum()))
# lot-level FIFO lifecycle (convention-labelled)
L = pd.read_csv('../../lot_lifecycle/outputs/lots.csv.gz', low_memory=False); L = L[(L.role == 'body') & (L.side == 'SHORT')].merge(cyc[['und', 'expiry', 'd1', 'd0']].rename(columns={'und': 'index'}), on=['index', 'expiry'], how='left')
L1 = L[(L.entry_day == L.d1)].copy(); L1['closed_day'] = np.where(L1.close_day == L1.d1, 'D-1', np.where(L1.close_day == L1.d0, 'D0', 'other')); L1['carried'] = L1.close_day != L1.d1
print('FIFO body short lots entered on D-1:', len(L1), '| closed on D-1: %.3f | carried to D0: %.3f' % ((L1.closed_day == 'D-1').mean(), (L1.closed_day == 'D0').mean()), '| close reasons D-1 closes:', L1[L1.closed_day == 'D-1'].close_reason.value_counts(normalize=True).round(3).to_dict(), '| D0 closes:', L1[L1.closed_day == 'D0'].close_reason.value_counts(normalize=True).round(3).to_dict())
hm = L1[L1.closed_day == 'D-1'].holding_seconds / 60; print('FIFO hold minutes for D-1 closes: quantiles', hm.quantile([.1, .25, .5, .75, .9]).round(1).tolist())
for conv in ('LIFO', 'LOW_ENTRY_FIRST', 'HIGH_ENTRY_FIRST'): print('  convention sensitivity: carried-to-D0 share using', conv, 'close rows missing (carried) share ->', L1['close_row_' + conv].isna().mean().round(3))
L1.groupby(['closed_day', 'close_reason']).size().to_csv(f'{OUT}/bl_d1_C_lot_close.csv')
# ---------------- D: ending logic
S = O[(O.module == 'num') & (O.role == 'open_short') & (O.dayno == 0) & O.apply(lambda r: (r.und, r.expiry) in OK, axis=1)]; Cv = O[(O.module == 'num') & (O.role == 'cover_short') & (O.dayno == 0) & O.apply(lambda r: (r.und, r.expiry) in OK, axis=1)]
def hm(t): return '%02d:%02d' % (t // 3600, (t % 3600) // 60)
b = lambda x: (x.tod // 900).astype(int) * 900
for nm, X in (('sell', S), ('cover', Cv)):
    h = X.groupby(b(X)).lots.sum(); h.index = [hm(i) for i in h.index]; print('D-1 body', nm, 'lots by 15-min bucket:', h.to_dict())
last = S.groupby(['und', 'expiry']).tod.max(); print('last body sale per cycle (IST): quantiles', [hm(x) for x in last.quantile([0, .1, .25, .5, .75, .9, 1]).values], '| share of cycles with a body sale at/after 15:00:', (last >= 15 * 3600).mean().round(3), ' after 15:15:', (last >= 15 * 3600 + 15 * 60).mean().round(3))
mn = Cv.groupby((Cv.tod // 60).astype(int) * 60).lots.sum().sort_values(ascending=False).head(8); print('top body-cover minutes on D-1:', {hm(i): int(v) for i, v in mn.items()}, ' share of D-1 cover lots in top 8 minutes: %.3f' % (mn.sum() / Cv.lots.sum()))
mn2 = S.groupby((S.tod // 60).astype(int) * 60).lots.sum().sort_values(ascending=False).head(8); print('top body-sale minutes on D-1:', {hm(i): int(v) for i, v in mn2.items()})
last_min = D1[(D1.module == 'num')].groupby(['und', 'expiry']).tod.max(); print('last body order of D-1 per cycle (IST) quantiles', [hm(x) for x in last_min.quantile([0, .25, .5, .75, 1]).values])
# carry composition: contract-level inventory at D-1 end for cycles with a D-1 log
cr = []
for (u, e, cp), g in D1[D1.apply(lambda r: (r.und, r.expiry) in OK, axis=1)].groupby(['und', 'expiry', 'cp']):
    net = g.groupby('strike').sl.sum(); sp_end = ch.spot(u, e, 0, 374); lump = g[g.module == 'v_'].groupby('strike').sl.sum()
    for k, v in net[net != 0].items():
        cr.append((u, e, cp, k, v, lump.get(k, 0), (k - sp_end) / ref.STEP[u], ch.px(u, e, 0, cp, k, 374, 'close')))
CR = pd.DataFrame(cr, columns=['und', 'expiry', 'right', 'strike', 'net', 'lump_net', 'steps_from_close_spot', 'close_px']); CR['side'] = np.where(CR.net < 0, 'short', 'long'); CR.to_csv(f'{OUT}/bl_d1_D_overnight_inventory.csv', index=False)
print('overnight inventory (contracts):', len(CR), CR.groupby('side').net.agg(['size', lambda s: s.abs().sum()]).to_dict('index'))
sh = CR[CR.side == 'short']; print('carried shorts: steps from close spot quantiles', sh.steps_from_close_spot.abs().quantile([.1, .25, .5, .75, .9]).round(1).tolist(), '| close price quantiles', sh.close_px.quantile([.1, .5, .9]).round(1).tolist())
print('carried shorts by right moneyness (CE strike below spot=ITM): ITM share', ((sh.right == 'CE') & (sh.steps_from_close_spot < 0) | (sh.right == 'PE') & (sh.steps_from_close_spot > 0)).mean().round(3))
cy = CR.groupby(['und', 'expiry', 'side']).net.apply(lambda s: s.abs().sum()).unstack(fill_value=0); print('per cycle carried lots: short median %.0f, long median %.0f; cycles with zero carried shorts %d of %d' % (cy.short.median(), cy.long.median(), int((cy.short == 0).sum()), len(cy)))

rec('d1b', dict(n_pos=len(P), n_cyc=P.groupby(['und', 'expiry']).ngroups, carried_pos=P.carried_short.sum(), closed_pos=P.closed_in_D1.sum(), lots_sold=P.lots_sold.sum(), lots_carried=-P[P.net_end_D1 < 0].net_end_D1.sum(), lots_sold_q=P.lots_sold.quantile([.25, .5, .75, .9]), peak_q=P.peak_short.quantile([.25, .5, .75, .9]), orders_q=P.sell_orders.quantile([.25, .5, .75]), strikes_med=P.groupby(['und', 'expiry', 'right']).size().median(), strikes_q=P.groupby(['und', 'expiry', 'right']).size().quantile([.25, .75]), hold_q=P.hold_min.dropna().quantile([.1, .25, .5, .75, .9]),
  partial_carried=((P.net_end_D1 < 0) & (P.lots_bought > 0)).sum(), fifo_n=len(L1), fifo_closed=(L1.closed_day == 'D-1').mean(), fifo_carried=(L1.closed_day == 'D0').mean(), reason_d1=L1[L1.closed_day == 'D-1'].close_reason.value_counts(normalize=True).to_dict(), reason_d0=L1[L1.closed_day == 'D0'].close_reason.value_counts(normalize=True).to_dict(), fifo_hold_q=(L1[L1.closed_day == 'D-1'].holding_seconds / 60).quantile([.1, .25, .5, .75, .9]),
  last_sale_q=[hm(x) for x in last.quantile([0, .1, .25, .5, .75, .9, 1]).values], share_after_1500=(last >= 15 * 3600).mean(), share_after_1515=(last >= 15 * 3600 + 15 * 60).mean(), last_order_q=[hm(x) for x in last_min.quantile([0, .25, .5, .75, 1]).values], top_cover=dict((hm(i), int(v)) for i, v in mn.items()), top_cover_share=mn.sum() / Cv.lots.sum(), top_sale=dict((hm(i), int(v)) for i, v in mn2.items()),
  sell_buckets={hm(i): int(v) for i, v in S.groupby(b(S)).lots.sum().items()}, cover_buckets={hm(i): int(v) for i, v in Cv.groupby(b(Cv)).lots.sum().items()}, n_short_contracts=len(sh), short_lots=sh.net.abs().sum(), long_contracts=int((CR.side == 'long').sum()), long_lots=CR[CR.side == 'long'].net.abs().sum(), steps_q=sh.steps_from_close_spot.abs().quantile([.1, .25, .5, .75, .9]), itm_share=((sh.right == 'CE') & (sh.steps_from_close_spot < 0) | (sh.right == 'PE') & (sh.steps_from_close_spot > 0)).mean(), close_px_q=sh.close_px.quantile([.1, .5, .9]), cy_short_med=cy.short.median(), cy_long_med=cy.long.median(), zero_short_cycles=int((cy.short == 0).sum()), n_cycles_inv=len(cy)))
