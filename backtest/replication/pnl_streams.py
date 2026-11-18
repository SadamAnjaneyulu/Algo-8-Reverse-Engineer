"""Where does the money come from, live vs reconstruction? FIFO-pair every lot (per cycle, role, right, strike) and classify gross P&L by role x open-day x close-day. Settlement of lots still open at expiry uses the official close (Yahoo). Gross = reference prices, no slippage/costs."""
from collections import deque
from common import *
E = pd.read_csv(f'{RES}/live_decision_events.csv'); S = pd.read_csv(f'{RES}/replay_sim_events.csv'); LP = pd.read_csv(f'{RES}/live_cycle_pnl.csv', parse_dates=['expiry'])
LOT = {'NIFTY': 65, 'SENSEX': 20}
def pairs(df, unit_col):
    """df columns: und, expiry, role, cp, strike, side(+1 buy/-1 sell), lots, px, order(time key), day(0/1)"""
    out = []
    for (u, e), g in df.groupby(['und', 'expiry']):
        books = {}
        for r in g.sort_values('order').itertuples():
            k = (r.role, r.cp, r.strike); bk = books.setdefault(k, deque()); q = r.lots
            while q > 1e-9:
                if bk and bk[0][0] != r.side:
                    o = bk[0]; m = min(q, o[2]); pnl = (o[1] - r.px if o[0] < 0 else r.px - o[1]) * m * LOT[u]
                    out.append(dict(und=u, expiry=e, role=r.role, open_day=o[3], close_day=r.day, pnl=pnl, lots=m, open_side=o[0])); o[2] -= m; q -= m
                    if o[2] <= 1e-9: bk.popleft()
                else: bk.append([r.side, r.px, q, r.day]); q = 0
        for k, bk in books.items():                                 # settle the remainder
            S0 = YAHOO[u].close.get(pd.Timestamp(e), np.nan)
            for o in bk:
                role, cp, K = k; v = max(S0 - K, 0) if cp == 'CE' else max(K - S0, 0); pnl = (o[1] - v if o[0] < 0 else v - o[1]) * o[2] * LOT[u]
                out.append(dict(und=u, expiry=e, role=role, open_day=o[3], close_day=2, pnl=pnl, lots=o[2], open_side=o[0]))
    return pd.DataFrame(out)
L = E[E.tp.isin(['num', 'h_'])].copy(); L['role'] = np.where(L.tp == 'num', 'body', 'wing'); L['side'] = np.where(L.side == 'Buy', 1, -1); L['order'] = L.row; L['day'] = np.where(L.day == 'D-1', 0, 1); L['px'] = L.px
PL = pairs(L[['und', 'expiry', 'role', 'cp', 'strike', 'side', 'lots', 'px', 'order', 'day']], None)
PL['stream'] = PL.role + ': open ' + PL.open_day.map({0: 'D-1', 1: 'D0'}) + ' -> close ' + PL.close_day.map({0: 'D-1', 1: 'D0', 2: 'settle'})
rows = [PL.groupby('stream').agg(pnl=('pnl', 'sum'), lots=('lots', 'sum')).assign(source='LIVE (body+wing only; lump/stop modules excluded)')]
for v in ('R1', 'R2'):
    s = S[S.variant == v].copy(); s['lots'] = 1.0; s['order'] = s.d * 1000 + s.j; s['strike'] = s.strike; s['day'] = s.d; s['px'] = s.ref; s['cp'] = s.right; s['side'] = s.side
    P = pairs(s[['und', 'expiry', 'role', 'cp', 'strike', 'side', 'lots', 'px', 'order', 'day']], None); P['stream'] = P.role + ': open ' + P.open_day.map({0: 'D-1', 1: 'D0'}) + ' -> close ' + P.close_day.map({0: 'D-1', 1: 'D0', 2: 'settle'})
    rows.append(P.groupby('stream').agg(pnl=('pnl', 'sum'), lots=('lots', 'sum')).assign(source=v))
T = pd.concat(rows).reset_index().pivot_table(index='stream', columns='source', values=['pnl', 'lots'], aggfunc='sum').fillna(0)
T.to_csv(f'{RES}/pnl_streams_live_vs_sim.csv'); pd.set_option('display.width', 250); print((T['pnl']).round(0).to_string()); print(T['pnl'].sum().round(0)); print((T['lots']).round(0).to_string())
# live: by module incl lump/stop (all fills) for total reconciliation
print('live gross all modules (from live_cycle_pnl):', LP.gross.sum().round(0))
