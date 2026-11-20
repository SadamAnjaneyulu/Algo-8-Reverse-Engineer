"""H3 (quantity / level control): does the hedge module hold wing lots W equal to body short lots S per (cycle, right)?
State: S = open body short lots (signed body fills, summed over strikes); W = wing lots (h_ buys - h_ sells), per right. Cycles with unknown carry-in excluded (complete = True).
Per wing order at its decision stamp: gap_before = S(stamp) - W(before), where S includes body fills with fill second <= floor(stamp). Outputs outputs/bh_h3_wing_orders.csv"""
import sys; sys.path.insert(0, '.')
from bh_common import *
O = order_table(); B = O[(O.module == 'num')]; W = O[O.module == 'h_']
rows = []
for (u, e, cp), w in W.groupby(['und', 'expiry', 'cp']):
    b = B[(B.und == u) & (B.expiry == e) & (B.cp == cp)].sort_values(['tt_first', 'row'])
    comp = bool(b.complete.iloc[0]) if len(b) else False
    bt = b.tt_first.values; bd = np.where(b.side == 'Sell', b.lots, -b.lots); cs = np.cumsum(bd)
    w = w.sort_values('tt_dec'); Wlev = 0
    for r in w.itertuples():
        k = np.searchsorted(bt, np.floor(r.tt_dec), side='right'); S = cs[k - 1] if k > 0 else 0
        sw = r.lots if r.side == 'Buy' else -r.lots
        rows.append((r.tag, u, e, cp, r.dayno, r.tt_dec, r.side, r.lots, r.lim_lots, sw, S, Wlev, S - Wlev, comp)); Wlev += sw
G = pd.DataFrame(rows, columns=['tag', 'und', 'expiry', 'cp', 'dayno', 'tt_dec', 'side', 'lots', 'lim_lots', 'sw', 'S', 'W_before', 'gap_before', 'complete'])
G['W_after'] = G.W_before + G.sw; G['gap_after'] = G.S - G.W_after; G.to_csv(f'{OUT}/bh_h3_wing_orders.csv', index=False)
c = G[G.complete]
print('wing orders', len(G), 'in complete-carry cycles', len(c), 'cycles', c.groupby(['und', 'expiry']).ngroups)
print('wing order lots dist', G.lots.value_counts().head(6).to_dict(), 'ordered-lots dist', G.lim_lots.value_counts().head(6).to_dict())
print('sign(wing) == sign(gap_before):', (np.sign(c.sw) == np.sign(c.gap_before)).mean().round(3), ' gap_before==0:', (c.gap_before == 0).mean().round(3))
print('|gap_after| < |gap_before|:', (c.gap_after.abs() < c.gap_before.abs()).mean().round(3), ' gap_after==0:', (c.gap_after == 0).mean().round(3))
print(c.groupby(['dayno', 'side']).apply(lambda g: pd.Series(dict(n=len(g), sign_ok=(np.sign(g.sw) == np.sign(g.gap_before)).mean(), gap0_after=(g.gap_after == 0).mean(), med_gap_before=g.gap_before.median()))).round(3))
