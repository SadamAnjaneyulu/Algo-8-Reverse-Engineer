"""Buy-back third pass, step 4: event triggers for reactive / solo lot exits. For each reactive lot (break side from the pair strike vs ATM at sale: +1 = up-break, -1 = down-break) and each solo lot:
leg role (CE/PE vs break side), spot path after the sale; at its buy-back (if any): spot move since sale (steps), whether the spot re-entered the broken two-candle channel ('failed breakout'), whether it made a new extreme beyond the break ('continuation'), a new opposite two-candle break, minutes held, ratio.
Compares with lots of the same type held through the same minutes without a buy-back (per-minute hazard given each event). Outputs bl_bt_react.csv, bl_summary_bt4.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
import bl_ohlc
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); OH = bl_ohlc.load(); SD = pd.read_pickle(f'{OUT}/bl_sd_orders.pkl.gz'); X = pd.read_pickle(f'{OUT}/bl_bt_lot.pkl.gz'); R = {}
X = X[X.typ.isin(['reactive', 'solo'])].copy()
# lot info: entry minute and break side
first = X.groupby('lid').agg(cid=('cid', 'first'), cp=('cp', 'first'), strike=('strike', 'first'), typ=('typ', 'first'), j0=('j', 'min'), held0=('held', 'min')).reset_index(); first['je'] = first.j0 - first.held0
side = {}
for f in first.itertuples():
    r = CY.iloc[f.cid]; c = OH[(r.und, r.expiry)].close.values; st = ref.STEP[r.und]; atm = round(c[max(f.je - 1, 0)] / st) * st
    side[f.lid] = int(np.sign(f.strike - atm)) if f.typ == 'reactive' else (-1 if f.cp == 'CE' else 1)      # solo: CE sold on a down move (side -1), PE on an up move (+1)
X['side'] = X.lid.map(side); X = X[X.side != 0]
# market state per (cid, j)
feat = {}
for i, r in enumerate(CY.itertuples()):
    o = OH[(r.und, r.expiry)]; h, l, c = o.high.values, o.low.values, o.close.values; st = ref.STEP[r.und]
    for j in range(2, 375):
        b0 = ((33300 + 60 * j) // 1800) * 1800; a = max(int(np.ceil((b0 - 3600 - 33300) / 60)), 0); e = max(int(np.ceil((b0 - 33300) / 60)), 1)
        feat[(i, j)] = (c[j - 1], h[a:e].max() if e > a else np.nan, l[a:e].min() if e > a else np.nan, h[j], l[j], st)
rows = []
for x in X.itertuples():
    cprev, H2, L2, hj, lj, st = feat[(x.cid, x.j)]; je = x.j - x.held; cent = feat.get((x.cid, max(je, 2)))[0]
    mv = x.side * (cprev - cent) / st                                  # + = market continued in the break direction since the sale
    inside = (L2 <= cprev <= H2) if H2 == H2 else False
    rows.append((x.lid, x.j, x.y, x.typ, x.cp, x.side, x.held, x.ratio_h, mv, int(inside), int(x.side > 0 and hj > H2 or x.side < 0 and lj < L2), int(x.side > 0 and lj < L2 or x.side < 0 and hj > H2), int((x.cp == 'CE') == (x.side > 0))))
P = pd.DataFrame(rows, columns=['lid', 'j', 'y', 'typ', 'cp', 'side', 'held', 'ratio_h', 'move_since_sale', 'inside_channel', 'cont_break', 'opp_break', 'leg_with_move'])
P.to_pickle(f'{OUT}/bl_bt_react.pkl.gz')
for t, g in P.groupby('typ'):
    g = g[g.ratio_h > 1]; print(t, 'in-loss lot-minutes', len(g), 'buy-backs', int(g.y.sum()))
    for v in ('leg_with_move', 'inside_channel', 'cont_break', 'opp_break'):
        print('   ', v, g.groupby(v).y.agg(['mean', 'sum', 'size']).assign(mean=lambda d: (d['mean'] * 100).round(2)).to_dict('index'))
    print('    hazard % by move since sale (steps, + = continued in break direction):', g.groupby(pd.cut(g.move_since_sale, [-9, -2, -1, -0.5, 0, 0.5, 1, 2, 9])).y.mean().mul(100).round(2).to_dict())
    print('    hazard % by held minutes:', g.groupby(pd.cut(g.held, [0, 5, 10, 20, 30, 60, 400])).y.mean().mul(100).round(2).to_dict())
