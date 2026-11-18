"""Which live body sales earn the D0 money? Classify every body sale (D-1 and D0) as SCHEDULED (first 3 min of a 15-min slot) / REPLACEMENT (same cycle+right buy-back in the same or previous minute) / OTHER, then FIFO-attribute gross P&L to the opening sale's class. Association only; no causal claim."""
from collections import deque
from common import *
E = pd.read_csv(f'{RES}/live_decision_events.csv'); LOT = {'NIFTY': 65, 'SENSEX': 20}
B = E[E.tp == 'num'].copy(); B['side'] = np.where(B.side == 'Buy', 1, -1); B['dayn'] = np.where(B.day == 'D-1', 0, 1); B['off'] = (B.minute - 1) % 15
# buy-back minutes per cycle/day/right
bb = B[B.side == 1].groupby(['und', 'expiry', 'dayn', 'cp']).minute.apply(lambda x: np.array(sorted(set(x)))).to_dict()
def cls(r):
    if r.side != -1: return 'n/a'
    a = bb.get((r.und, r.expiry, r.dayn, r.cp), np.array([])); rep = bool(len(a) and ((a == r.minute) | (a == r.minute - 1)).any())
    if rep: return 'REPLACEMENT'
    return 'SCHEDULED' if r.off < 3 else 'OTHER'
B['cls'] = [cls(r) for r in B.itertuples()]
print(B[B.side == -1].groupby(['day', 'cls']).lots.sum().unstack().round(0))
# FIFO with class on opening sale
out = []
for (u, e), g in B.groupby(['und', 'expiry']):
    books = {}; S0 = YAHOO[u].close.get(pd.Timestamp(e), np.nan)
    for r in g.sort_values('row').itertuples():
        k = (r.cp, r.strike); bk = books.setdefault(k, deque()); q = r.lots
        while q > 1e-9:
            if bk and bk[0][0] != r.side:
                o = bk[0]; m = min(q, o[2]); pnl = (o[1] - r.px if o[0] < 0 else r.px - o[1]) * m * LOT[u]; out.append(dict(und=u, expiry=e, cls=o[3], open_day=o[4], close_day=r.dayn, pnl=pnl, lots=m, open_side=o[0])); o[2] -= m; q -= m
                if o[2] <= 1e-9: bk.popleft()
            else: bk.append([r.side, r.px, q, r.cls, r.dayn]); q = 0
    for (cp, K), bk in books.items():
        for o in bk:
            v = max(S0 - K, 0) if cp == 'CE' else max(K - S0, 0); out.append(dict(und=u, expiry=e, cls=o[3], open_day=o[4], close_day=2, pnl=(o[1] - v if o[0] < 0 else v - o[1]) * o[2] * LOT[u], lots=o[2], open_side=o[0]))
P = pd.DataFrame(out); P = P[P.open_side == -1]; P['open'] = P.open_day.map({0: 'D-1', 1: 'D0'})
T = P.groupby(['open', 'cls']).agg(lots=('lots', 'sum'), gross_pnl=('pnl', 'sum')).assign(pnl_per_lot=lambda x: x.gross_pnl / x.lots); T.to_csv(f'{RES}/d0_sales_by_class.csv'); print(T.round(0))
# per-cycle contribution of D0 replacement sales and their correlation with cycle outcome
pc = P[(P.open == 'D0')].groupby(['und', 'expiry', 'cls']).pnl.sum().unstack().fillna(0); LP = pd.read_csv(f'{RES}/live_cycle_pnl.csv', parse_dates=['expiry']).set_index(['und', 'expiry']); pc = pc.join(LP[['gross', 'stop_cycle']], how='left'); print(pc.groupby('stop_cycle').mean().round(0)); pc.to_csv(f'{RES}/d0_sales_by_cycle.csv')
