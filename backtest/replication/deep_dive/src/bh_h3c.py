"""H3c: order-level level control with contract-level S and L (all modules). For every h_ order (decision stamp T):
S = short lots, L = long lots, per right over all strikes, from net position per contract after all events strictly before T (body fills at their fill second; stamped modules at their decision stamp; earlier body fills in the same second as floor(T) included).
gap_before = S - L; the order's signed lots sw (+ Buy / - Sell). Output outputs/bh_h3c_wing_orders.csv. Cycles with unknown carry-in flagged complete=False and excluded from headline."""
import sys; sys.path.insert(0, '.')
from bh_common import *
X = fills_x(); O = order_table(X); O['te'] = np.where(O.module.isin(['h_', 's_', 'v_', 'm_']), O.tt_dec, O.tt_first); O['sl'] = np.where(O.side == 'Buy', O.lots, -O.lots)
rows = []
for (u, e, cp), o in O.groupby(['und', 'expiry', 'cp']):
    o = o.sort_values(['te', 'row']); comp = bool(o.complete.iloc[0]); keys = {k: i for i, k in enumerate(sorted(o.strike.unique()))}; net = np.zeros(len(keys)); te = o.te.values; idx = o.strike.map(keys).values; sl = o.sl.values; mod = o.module.values; tags = o.tag.values; dn = o.dayno.values; lots = o.lots.values; ll = o.lim_lots.values; sd = o.side.values
    n = len(o); i = 0
    while i < n:
        # events with the same floor-second are applied after evaluating wing orders stamped inside that second only if they are body fills at second > floor? keep simple: strict time order using te (body fill second as t, stamped modules float)
        if mod[i] == 'h_':
            S = -net[net < 0].sum(); Lg = net[net > 0].sum(); rows.append((tags[i], u, e, cp, dn[i], te[i], sd[i], lots[i], ll[i], sl[i], S, Lg, comp))
        net[idx[i]] += sl[i]; i += 1
G = pd.DataFrame(rows, columns=['tag', 'und', 'expiry', 'cp', 'dayno', 'tt_dec', 'side', 'lots', 'lim_lots', 'sw', 'S', 'L_before', 'complete']); G['gap_before'] = G.S - G.L_before; G['gap_after'] = G.S - (G.L_before + G.sw)
G.to_csv(f'{OUT}/bh_h3c_wing_orders.csv', index=False)
c = G[G.complete]; print('wing orders', len(G), 'complete-carry', len(c), 'cycles', c.groupby(['und', 'expiry']).ngroups)
print('sign(sw)==sign(gap_before)', (np.sign(c.sw) == np.sign(c.gap_before)).mean().round(3), '| gap_after==0', (c.gap_after == 0).mean().round(3), '| sw==gap_before (exact catch-up)', (c.sw == c.gap_before).mean().round(3), '| |gap_after|<|gap_before|', (c.gap_after.abs() < c.gap_before.abs()).mean().round(3))
print(c.groupby(['dayno', 'side']).apply(lambda g: pd.Series(dict(n=len(g), sign_ok=(np.sign(g.sw) == np.sign(g.gap_before)).mean(), gap0_after=(g.gap_after == 0).mean(), exact=(g.sw == g.gap_before).mean(), med_gap=g.gap_before.median()))).round(3))
