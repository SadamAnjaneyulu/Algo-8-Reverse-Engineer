"""H4: order pricing. (a) limit cushion by module/side/day (lim vs first fill price, fills >= 10 rupees where tick rounding is < 0.5 %), (b) IOC partial fills and whether the controller retries the shortfall,
(c) hedge price dependence on body price (log-log slope on simple orders). Outputs outputs/bh_h4_cushion.csv, bh_h4_partial.csv"""
import sys; sys.path.insert(0, '.')
from bh_common import *
O = order_table(); rows = []
for (m, s, d), g in O[O.px_first >= 10].groupby(['module', 'side', 'dayno']):
    if len(g) < 30: continue
    k = (g.lim_px / g.px_first - 1) if s == 'Buy' else (1 - g.lim_px / g.px_first)
    rows.append(dict(module=m, side=s, day=['D-1', 'D0'][d], n=len(g), cushion_median=k.median(), q25=k.quantile(.25), q75=k.quantile(.75), validity='/'.join(sorted(g.validity.unique()))))
C = pd.DataFrame(rows).round(4); C.to_csv(f'{OUT}/bh_h4_cushion.csv', index=False); print(C.to_string(index=False))
# small-price hedges: cushion with tick effect (fills 1-10)
for s in ('Buy', 'Sell'):
    g = O[(O.module == 'h_') & (O.side == s) & (O.px_first >= 2) & (O.px_first < 10)]; k = (g.lim_px / g.px_first - 1) if s == 'Buy' else (1 - g.lim_px / g.px_first); print('h_', s, 'fill 2-10', len(g), 'cushion median', k.median().round(4), 'IQR', k.quantile([.25, .75]).round(4).tolist())
# (b) IOC partials
G = pd.read_csv(f'{OUT}/bh_h3c_wing_orders.csv', dtype={'tag': str}); G['short'] = G.lim_lots - G.lots
P = G[G.short > 0].copy(); print('h_ orders with unfilled quantity', len(P), 'of', len(G), '= %.2f%%' % (100 * len(P) / len(G)), ' lots unfilled total', P.short.sum(), 'of ordered', G.lim_lots.sum())
nxt = []
Gs = G.sort_values(['und', 'expiry', 'cp', 'tt_dec'])
for (u, e, cp), g in Gs.groupby(['und', 'expiry', 'cp']):
    g = g.reset_index(drop=True)
    for i in np.where(g.short.values > 0)[0]:
        j = i + 1
        if j < len(g) and g.tt_dec[j] - g.tt_dec[i] <= 30:
            nxt.append((g.tag[i], g.short[i], g.sw[i], g.sw[j], g.gap_after[i], g.tt_dec[j] - g.tt_dec[i], g.side[i] == g.side[j]))
        else: nxt.append((g.tag[i], g.short[i], g.sw[i], np.nan, g.gap_after[i], np.nan, False))
N = pd.DataFrame(nxt, columns=['tag', 'short', 'sw', 'sw_next', 'gap_after', 'dt_next', 'same_side']); N.to_csv(f'{OUT}/bh_h4_partial.csv', index=False)
has = N.dt_next.notna(); print('partial orders followed by another wing order within 30 s:', has.mean().round(3), ' of which same side', N[has].same_side.mean().round(3), ' next signed lots == remaining gap:', (N[has].sw_next == N[has].gap_after).mean().round(3), 'median delay', N.dt_next.median())
# (c) log-log slope on simple orders
S = pd.read_csv(f'{OUT}/bh_h2_simple_tested.csv', dtype={'tag': str})
for (u, d), g in S.groupby(['und', 'dayno']):
    x = np.log(g.b_ref); y = np.log(g.w_ref); b = np.polyfit(x, y, 1); print('log(wing ref) ~ log(body ref):', u, ['D-1', 'D0'][d], 'n', len(g), 'slope', b[0].round(3), 'corr', np.corrcoef(x, y)[0, 1].round(3))
