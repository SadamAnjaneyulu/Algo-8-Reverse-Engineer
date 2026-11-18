"""Lot lineage: FIFO pairs (same role books and routing as build_events.py) with opening-order class and closing-order class, for P&L attribution (D0_PNL_ATTRIBUTION). Residual lots are settled at the Yahoo official close."""
from collections import deque, defaultdict
from d0common import *
E_ = pd.read_csv(f'{RES}/d0_events.csv', parse_dates=['t']); S_ = pd.read_csv(f'{RES}/cycle_status.csv')
ROUTE = {('num', 'Sell'): (['body'], 'body'), ('num', 'Buy'): (['body'], 'body'), ('h_', 'Buy'): (['wing'], 'wing'), ('h_', 'Sell'): (['wing', 'lump'], 'wing'), ('v_', 'Buy'): (['lump'], 'lump'), ('v_', 'Sell'): (['lump', 'wing'], 'lump'), ('s_', 'Buy'): (['body', 'lump', 'wing'], 'stop'), ('s_', 'Sell'): (['wing', 'lump', 'body'], 'stop'), ('m_', 'Buy'): (['body', 'lump', 'wing'], 'stop'), ('m_', 'Sell'): (['wing', 'lump', 'body'], 'stop')}
rows = []
for (u, e), g in E_.sort_values(['t', 'sec']).groupby(['und', 'expiry']):
    lot = LOT[u]; books = defaultdict(deque); sg = lambda s: 1 if s == 'Buy' else -1; S0 = YAHOO[u].close.get(pd.Timestamp(e), np.nan)
    for r in g.itertuples():
        closes, openrole = ROUTE[(r.module, r.side)]; q = r.lots; s = sg(r.side)
        for rl in closes:
            L = books[(r.cp, r.strike, rl)]
            while q > 1e-9 and L and L[0][0] != s:
                o = L[0]; t = min(q, o[1]); pnl = (o[2] - r.px if o[0] < 0 else r.px - o[2]) * t * lot
                rows.append(dict(und=u, expiry=e, split=r.split, role=rl, open_class=o[3], open_day=o[4], close_class=r.event_class, close_day=r.day, lots=t, pnl=pnl, open_px=o[2], close_px=r.px, hold_min=(r.t - o[5]).total_seconds() / 60, open_tag=o[6], close_tag=r.tag)); o[1] -= t; q -= t
                if o[1] <= 1e-9: L.popleft()
        if q > 1e-9: books[(r.cp, r.strike, openrole)].append([s, q, r.px, r.event_class, r.day, r.t, r.tag])
    for (cp, k, rl), L in books.items():
        for o in L:
            v = (max(S0 - k, 0) if cp == 'CE' else max(k - S0, 0)); rows.append(dict(und=u, expiry=e, split=g.split.iloc[0], role=rl, open_class=o[3], open_day=o[4], close_class='SETTLEMENT', close_day='D0', lots=o[1], pnl=(o[2] - v if o[0] < 0 else v - o[2]) * o[1] * lot, open_px=o[2], close_px=v, hold_min=np.nan, open_tag=o[6], close_tag=''))
Lg = pd.DataFrame(rows); Lg.to_csv(f'{RES}/lot_lineage.csv', index=False)
LP = pd.read_csv(f'{RRES}/live_cycle_pnl.csv'); LP['expiry'] = LP.expiry.str[:10]; g = Lg.groupby(['und', 'expiry']).pnl.sum().rename('lineage').reset_index().merge(LP[['und', 'expiry', 'gross']], on=['und', 'expiry']); print('max |lineage - live gross| per cycle:', (g.lineage - g.gross).abs().max().round(2), ' total', g.lineage.sum().round(0), g.gross.sum().round(0))
