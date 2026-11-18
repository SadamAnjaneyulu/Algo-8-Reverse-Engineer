"""Book snapshots at every D0 Clock-B tick (minute mm%15==14, 09:29..14:59) for cycles with a known carry-in book. Snapshot = state BEFORE the first order with seconds >= tick-minute start. Features use prices of the previous completed minute (tick minute - 1)."""
from collections import deque, defaultdict
from d0common import *
from data import load_cycle, NM
E_ = pd.read_csv(f'{RES}/d0_events.csv', parse_dates=['t']); S_ = pd.read_csv(f'{RES}/cycle_status.csv'); rows = []; ctr = []
for (u, e), g in E_.sort_values(['t', 'sec']).groupby(['und', 'expiry']):
    st = S_[(S_.und == u) & (S_.expiry == e)].iloc[0]
    if not (st.has_d0 and st.carry_in_known): continue
    c = load_cycle(u, e, st.d1, st.d0); ki = {int(k): i for i, k in enumerate(c['strikes'])}; lot = LOT[u]; step = 50 if u == 'NIFTY' else 100
    px = {}
    for r in ('CE', 'PE'):
        a = c[(1, r, 'close')].copy(); prev = c[(0, r, 'close')][:, -1].copy()
        for j in range(NM):
            m = np.isnan(a[:, j]); a[m, j] = (a[m, j - 1] if j > 0 else prev[m])
        px[r] = a
    body = defaultdict(deque); wing = defaultdict(float); ticks = [(h * 60 + m) for h in range(9, 15) for m in range(60) if m % 15 == 14 and 9 * 60 + 29 <= h * 60 + m <= 14 * 60 + 59]
    ev = g.to_dict('records'); [x.__setitem__('abs', (0 if x['day'] == 'D-1' else 86400) + x['sec']) for x in ev]; p = 0; last_act_spot = None; first = True
    def snap(tmin):
        j = tmin - 555; pm = max(j - 1, 0); S = c[(1, 'spot')][pm]; items = []
        for (cp, k), L in body.items():
            q = sum(x[0] for x in L)
            if q < 1e-9: continue
            i = ki.get(k); pr = px[cp][i, pm] if i is not None else np.nan; avg = sum(x[0] * x[1] for x in L) / q; cheap = min(x[1] for x in L)
            items.append(dict(cp=cp, strike=k, lots=q, price=pr, avg_entry=avg, cheapest=cheap, off_steps=(k - S) / step, ratio_cheapest=pr / cheap, ratio_avg=pr / avg, upnl=(avg - pr) * q * lot))
        return S, items
    for tm in ticks:
        tsec = tm * 60; tabs = 86400 + tsec
        while p < len(ev) and ev[p]['abs'] < tabs:       # apply all orders before the tick minute (any day; D-1 included)
            r = ev[p]; p += 1
            if r['module'] == 'num':
                if r['side'] == 'Sell' and r['opened_lots'] > 0 and r['open_role'] == 'body': body[(r['cp'], r['strike'])].append([r['opened_lots'], r['px']])
                elif r['side'] == 'Buy':
                    q = r['lots']; L = body[(r['cp'], r['strike'])]
                    while q > 1e-9 and L: t = min(q, L[0][0]); L[0][0] -= t; q -= t; (L.popleft() if L[0][0] <= 1e-9 else None)
                elif r['side'] == 'Sell' and r['closed_lots'] > 0:
                    pass
            elif r['module'] == 's_' and r['side'] == 'Buy':
                q = r['lots']; L = body[(r['cp'], r['strike'])]
                while q > 1e-9 and L: t = min(q, L[0][0]); L[0][0] -= t; q -= t; (L.popleft() if L[0][0] <= 1e-9 else None)
            elif r['module'] == 'h_': wing[r['cp']] += r['lots'] if r['side'] == 'Buy' else -r['lots']
        S, items = snap(tm)
        if not items: continue
        acts = [x for x in ev if x['day'] == 'D0' and x['module'] == 'num' and x['side'] == 'Buy' and x['closed_lots'] > 0 and tsec <= x['sec'] < tsec + 120]
        bought = defaultdict(float)
        for x in acts: bought[(x['cp'], x['strike'])] += x['lots']
        nsh = sum(i['lots'] for i in items); spot_prev = S
        for it in items: rows.append(dict(und=u, expiry=e, split=st.split, tick_min=tm, tick_hhmm=f'{tm // 60:02d}:{tm % 60:02d}', spot=S, **it, bought_lots=bought.get((it['cp'], it['strike']), 0.0), tick_acted=len(acts) > 0, tick_bought_lots=sum(bought.values()), tick_n_orders=len(acts), book_short_CE=sum(i['lots'] for i in items if i['cp'] == 'CE'), book_short_PE=sum(i['lots'] for i in items if i['cp'] == 'PE'), wing_long_CE=wing['CE'], wing_long_PE=wing['PE'], n_contracts=len(items)))
S2 = pd.DataFrame(rows); S2.to_csv(f'{RES}/clockb_snapshots.csv', index=False); print(len(S2), S2.groupby('split').apply(lambda x: x[['und', 'expiry', 'tick_min']].drop_duplicates().shape[0]).to_dict(), 'acted tick share (all):', S2.drop_duplicates(['und', 'expiry', 'tick_min']).tick_acted.mean().round(3))
