"""D0 study, part D: ending logic. State of every contract at 15:13:59 IST and after the last event, the orders in 15:14-15:35 by module/role, residual positions, pre/post observed break (D0 date <= / >= 2026-08-24)."""
import sys; sys.path.insert(0, '.')
from bl_common import *
O = load_orders(); cyc = pd.read_csv(ref.CYCLES); ch = Chain(); T0 = 15 * 3600 + 14 * 60; CUT = '2026-08-24'   # observed break: no flatten in any measurable cycle with D0 <= 2026-08-13, flatten in every measurable cycle with D0 >= 2026-08-25 (the earlier reported cut-over 2026-08-03 does not match the data)
d0date = {(u, e): d for u, e, d in zip(cyc.und, cyc.expiry, cyc.d0)}; known = {(u, e): (h0, k) for u, e, h0, k in zip(cyc.und, cyc.expiry, cyc.has_d0, cyc.carry_in_known)}
D0 = O[O.dayno == 1].copy(); D0['post'] = [d0date[(u, e)] >= CUT for u, e in zip(D0.und, D0.expiry)]
hm = lambda t: '%02d:%02d' % (t // 3600, (t % 3600) // 60)
# orders from 15:00 by minute and module/role (lots)
x = D0[D0.tod >= 15 * 3600]; x = x.assign(mm=x.tod // 60 * 60); tb = x.groupby(['mm', 'module', 'cls']).lots.sum().unstack(['module', 'cls'], fill_value=0); tb.index = [hm(i) for i in tb.index]; tb.to_csv(f'{OUT}/bl_d0_D_last_minutes.csv')
tot = D0[D0.tod >= 15 * 3600].groupby('post').size(); print('orders from 15:00 (post cutover / pre):', tot.to_dict())
rows = []; res = []
for (u, e), g in D0.groupby(['und', 'expiry']):
    if not known[(u, e)][0]: continue
    g = g.sort_values(['te', 'row']); post = bool(g.post.iloc[0]); ck = known[(u, e)][1]
    for cp in ('CE', 'PE'):
        h = g[g.cp == cp]; net_before = h[h.tod < T0].groupby('strike').sl.sum(); net_end = h.groupby('strike').sl.sum()
        # carry-in from D-1 is included only when the cycle's D-1 events are added: use all events of the cycle (D-1 + D0)
        a = O[(O.und == u) & (O.expiry == e) & (O.cp == cp)]; nb = a[(a.dayno == 0) | (a.tod < T0)].groupby('strike').sl.sum(); ne = a.groupby('strike').sl.sum()
        S_b = -nb[nb < 0].sum(); L_b = nb[nb > 0].sum(); S_e = -ne[ne < 0].sum(); L_e = ne[ne > 0].sum()
        win = h[(h.tod >= T0) & (h.tod < T0 + 600)]; c14 = h[(h.tod >= T0) & (h.tod < T0 + 120)]
        rows.append((u, e, cp, post, ck, S_b, L_b, S_e, L_e, win.lots.sum(), c14.lots.sum(), (c14[c14.module == 'num'].lots.sum()), c14[c14.module == 'h_'].lots.sum(), c14[c14.module == 's_'].lots.sum()))
F = pd.DataFrame(rows, columns=['und', 'expiry', 'right', 'post_cutover', 'carry_known', 'S_1513', 'L_1513', 'S_end', 'L_end', 'lots_1514_1524', 'lots_1514_1515', 'body_1514_1515', 'hedge_1514_1515', 'stop_1514_1515']); F.to_csv(f'{OUT}/bl_d0_D_flatten.csv', index=False)
for post in (False, True):
    f = F[(F.post_cutover == post) & F.carry_known]
    print('cutover', 'post' if post else 'pre', ': cycle-rights', len(f), '| open at 15:13 S %d L %d | closed share of S by end %.3f, of L by end %.3f | cycle-rights flat at end %.3f | flat at end with S=L=0 only %.3f | cycle-rights with lots traded in 15:14-15:15: %.3f' % (f.S_1513.sum(), f.L_1513.sum(), 1 - f.S_end.sum() / max(f.S_1513.sum(), 1), 1 - f.L_end.sum() / max(f.L_1513.sum(), 1), ((f.S_end == 0) & (f.L_end == 0)).mean(), ((f.S_end == 0) & (f.L_end == 0)).mean(), (f.lots_1514_1515 > 0).mean()))
f = F[F.carry_known]; print('closing in 15:14-15:15 (lots) by module: body %d hedge %d stop %d ; total lots at 15:13: S %d L %d' % (f.body_1514_1515.sum(), f.hedge_1514_1515.sum(), f.stop_1514_1515.sum(), f.S_1513.sum(), f.L_1513.sum()))
# of what is open at 15:13: how much is closed during 15:14-15:15 vs later vs residual (contract-lots)
cl = []
for (u, e), a in O.groupby(['und', 'expiry']):
    if not known[(u, e)][0] or not known[(u, e)][1]: continue
    for cp in ('CE', 'PE'):
        h = a[a.cp == cp]; nb = h[(h.dayno == 0) | (h.tod < T0)].groupby('strike').sl.sum(); n1 = h[(h.dayno == 0) | (h.tod < T0 + 120)].groupby('strike').sl.sum(); ne = h.groupby('strike').sl.sum(); post = d0date[(u, e)] >= CUT
        for side, sel in (('short', nb < 0), ('long', nb > 0)):
            k = nb[sel].index; b = nb[sel].abs().sum(); c1 = (nb[sel].abs() - n1.reindex(k).fillna(0).clip(upper=0).abs() if side == 'short' else 0)
            ab = nb[sel].abs(); a1 = n1.reindex(k).fillna(0).abs() if True else None; ae = ne.reindex(k).fillna(0).abs()
            same = (np.sign(n1.reindex(k).fillna(0)) == np.sign(nb[sel])); a1 = np.where(same, n1.reindex(k).fillna(0).abs(), 0); same_e = (np.sign(ne.reindex(k).fillna(0)) == np.sign(nb[sel])); ae = np.where(same_e, ne.reindex(k).fillna(0).abs(), 0)
            cl.append((u, e, cp, post, side, ab.sum(), (ab.values - np.minimum(ab.values, a1)).sum(), (np.minimum(ab.values, a1) - np.minimum(ab.values, ae)).sum(), np.minimum(ab.values, ae).sum()))
CL = pd.DataFrame(cl, columns=['und', 'expiry', 'right', 'post', 'side', 'open_1513', 'closed_1514_1515', 'closed_after_1516', 'residual_end'])
g = CL.groupby(['post', 'side'])[['open_1513', 'closed_1514_1515', 'closed_after_1516', 'residual_end']].sum(); g['share_closed_1514_1515'] = (g.closed_1514_1515 / g.open_1513).round(3); g['share_residual'] = (g.residual_end / g.open_1513).round(3); g.to_csv(f'{OUT}/bl_d0_D_close_shares.csv'); print(g.to_string())
CL.to_csv(f'{OUT}/bl_d0_D_close_by_cycle.csv', index=False)
# residual contracts at end: moneyness vs D0 close spot and last price, strike, side
res = []
for (u, e, cp), a in O.groupby(['und', 'expiry', 'cp']):
    if not known[(u, e)][0] or not known[(u, e)][1]: continue
    ne = a.groupby('strike').sl.sum(); sp = ch.spot(u, e, 1, 374)
    for k, v in ne[ne != 0].items(): res.append((u, e, cp, k, v, (k - sp) / ref.STEP[u] * (-1 if cp == 'CE' else 1), ch.px(u, e, 1, cp, k, 374, 'close'), d0date[(u, e)] >= CUT))
RS = pd.DataFrame(res, columns=['und', 'expiry', 'right', 'strike', 'net', 'otm_steps_at_close', 'last_px', 'post']); RS['side'] = np.where(RS.net < 0, 'short', 'long'); RS.to_csv(f'{OUT}/bl_d0_D_residual.csv', index=False)
print('residual contracts at the end of D0 (known cycles):', len(RS), RS.groupby(['post', 'side']).agg(n=('net', 'size'), lots=('net', lambda s: s.abs().sum())).to_dict('index')); print('residual long wings: median |OTM steps| %.1f, last price quantiles %s ; residual shorts: OTM steps quantiles %s' % (RS[RS.side == 'long'].otm_steps_at_close.abs().median(), RS[RS.side == 'long'].last_px.quantile([.25, .5, .75]).round(2).tolist(), RS[RS.side == 'short'].otm_steps_at_close.quantile([.1, .5, .9]).round(1).tolist()))
last = D0.groupby(['und', 'expiry']).tod.max(); print('last D0 order per cycle (IST) quantiles', [hm(v) for v in last.quantile([0, .25, .5, .75, 1]).values])

Dn = O[(O.dayno == 1) & (O.module == 'num') & (O.tod >= 14 * 3600 + 30 * 60)].copy(); Dn['post'] = [d0date[(u, e)] >= CUT for u, e in zip(Dn.und, Dn.expiry)]; Dn['close'] = Dn.cls.isin(['cover_short', 'close_long']); mins = {}
for p in (False, True):
    x = Dn[(Dn.post == p) & Dn.close]; t = x.groupby(x.tod // 60 * 60).lots.sum(); t.index = [hm(i) for i in t.index]; mins['post' if p else 'pre'] = t
pd.DataFrame(mins).fillna(0).astype(int).to_csv(f'{OUT}/bl_d0_D_close_minutes_pre_post.csv')
rec('d0c', dict(n_pre=len([1 for v in d0date.values() if v < CUT]), n_post=len([1 for v in d0date.values() if v >= CUT]), body_total_pre=mins['pre'].sum(), body_total_post=mins['post'].sum(), post_1514=mins['post'].get('15:14', 0), pre_1514_1515=mins['pre'].reindex(['15:14', '15:15']).sum(), post_1514_1515=mins['post'].reindex(['15:14', '15:15']).sum(), pre_top=mins['pre'].sort_values(ascending=False).head(8), post_top=mins['post'].sort_values(ascending=False).head(8), last_order_q=[hm(v) for v in last.quantile([0, .25, .5, .75, 1]).values]))

# per-cycle evidence for the break
Dc = O[(O.dayno == 1) & (O.module == 'num') & (O.cls.isin(['cover_short', 'close_long'])) & (O.tod >= 14 * 3600 + 30 * 60)]
pc = Dc.groupby(['und', 'expiry']).apply(lambda x: pd.Series(dict(closing_lots_after_1430=x.lots.sum(), lots_in_1514_minute=x[(x.tod >= T0) & (x.tod < T0 + 60)].lots.sum()))).reset_index(); pc['share_1514'] = pc.lots_in_1514_minute / pc.closing_lots_after_1430; pc['d0'] = [d0date[(u, e)] for u, e in zip(pc.und, pc.expiry)]; pc = pc.sort_values('d0'); pc.to_csv(f'{OUT}/bl_d0_D_flatten_by_cycle.csv', index=False)
pre_ = pc[pc.d0 <= '2026-08-20']; post_ = pc[pc.d0 >= '2026-08-25']
rec('d0c_break', dict(cut=CUT, measurable_pre=len(pre_), max_share_pre=pre_.share_1514.max(), last_pre_date=pre_.d0.max(), measurable_post=len(post_), min_share_post=post_.share_1514.min(), first_post_date=post_.d0.min(), no_close_cycles=len(d0date) - len(pc)))
