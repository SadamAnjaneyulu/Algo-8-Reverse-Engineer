"""Book at 15:10 on D0 (body shorts) vs what remains after the last order of the day: which lots are held to settlement? Uses previous-minute (15:09) prices."""
from collections import deque, defaultdict
from d0common import *
from data import load_cycle, NM
E_ = pd.read_csv(f'{RES}/d0_events.csv', parse_dates=['t']); S_ = pd.read_csv(f'{RES}/cycle_status.csv'); rows = []
for (u, e), g in E_.sort_values(['t', 'sec']).groupby(['und', 'expiry']):
    st = S_[(S_.und == u) & (S_.expiry == e)].iloc[0]
    if not (st.has_d0 and st.carry_in_known): continue
    c = load_cycle(u, e, st.d1, st.d0); ki = {int(k): i for i, k in enumerate(c['strikes'])}; lot = LOT[u]; step = 50 if u == 'NIFTY' else 100; ev = g.to_dict('records'); book = defaultdict(float); snap = None
    for r in ev:
        ab = (0 if r['day'] == 'D-1' else 86400) + r['sec']
        if snap is None and ab >= 86400 + 15 * 3600 + 10 * 60: snap = {k: v for k, v in book.items() if v > 1e-9}
        if r['module'] in ('num', 's_'):
            if r['side'] == 'Sell' and r['module'] == 'num' and r['open_role'] == 'body': book[(r['cp'], r['strike'])] += r['opened_lots']
            elif r['side'] == 'Buy': book[(r['cp'], r['strike'])] = max(book[(r['cp'], r['strike'])] - r['lots'], 0.0)
    if snap is None: snap = {k: v for k, v in book.items() if v > 1e-9}
    S0 = c[(1, 'spot')][15 * 60 + 9 - 555]
    for (cp, k), q in snap.items():
        i = ki.get(k); pr = np.nan if i is None else c[(1, cp, 'close')][i, 15 * 60 + 9 - 555]
        rows.append(dict(und=u, expiry=e, split=st.split, cp=cp, strike=k, lots_1510=q, lots_final=book[(cp, k)], held_frac=min(book[(cp, k)] / q, 1.0), price_1509=pr, off_steps=(k - S0) / step, spot=S0))
F = pd.DataFrame(rows); F.to_csv(f'{RES}/final_1510_snapshot.csv', index=False)
D = F[F.split == 'DISCOVERY'].copy(); D['bin'] = pd.cut(D.price_1509, [-1, 0.05, 0.25, 0.5, 1, 2, 5, 20, 1e9]); t = D.groupby('bin', observed=True).apply(lambda x: pd.Series(dict(contracts=len(x), lots=x.lots_1510.sum(), held_share=(x.held_frac * x.lots_1510).sum() / x.lots_1510.sum()))).round(3); print(t)
