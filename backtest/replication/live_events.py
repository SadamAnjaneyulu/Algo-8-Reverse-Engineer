"""Decision-event table from the real Algo 8 ledger, joined to Breeze market state at decision time (spot = previous completed minute close; option price = bar close of previous minute)."""
from common import *
from data import *
from bt import cycles as Cy
cl = Cy.cycle_list(); cl = cl[cl.subset.isin(['OOS_EXPOSED']) | (cl.d0 >= '2026-06-22')]
d = live_ledger(); d['expiry'] = pd.to_datetime(d.expiry).dt.strftime('%Y-%m-%d'); d['day'] = d.date.dt.strftime('%Y-%m-%d')
rows = []; missing = []
for (u, e), g in d.groupby(['und', 'expiry']):
    m = cl[(cl.und == u) & (cl.expiry == e)]
    if not len(m): missing.append((u, e)); continue
    m = m.iloc[0]
    try: c = load_cycle(u, e, m.d1, m.d0)
    except Exception as ex: missing.append((u, e, str(ex)[:60])); continue
    step = 50 if u == 'NIFTY' else 100; lot = 65 if u == 'NIFTY' else 20; ks = c['strikes']; ki = {int(k): i for i, k in enumerate(ks)}
    for r in g.itertuples():
        di = 0 if r.day == m.d1 else (1 if r.day == m.d0 else None)
        if di is None: continue
        mi = MI.get(r.hhmm); 
        if mi is None: continue
        pm = max(mi - 1, 0); S = c[(di, 'spot')][pm]; i = ki.get(int(r.strike)); px_prev = c[(di, r.cp, 'close')][i, pm] if i is not None else np.nan
        rows.append(dict(und=u, expiry=e, d1=m.d1, d0=m.d0, day='D-1' if di == 0 else 'D0', t=r.t, hhmm=r.hhmm, minute=mi, tp=r.tp, side=r.side, cp=r.cp, strike=int(r.strike), lots=r.lots, px=r.px_fill, oid=r.oid, spot_prev=S, off_steps=(r.strike - S) / step, px_prev_close=px_prev, row=r.row))
E_ = pd.DataFrame(rows); E_.to_csv(f'{RES}/live_decision_events.csv', index=False); print(len(E_), 'events; cycles missing:', missing)
print(E_.groupby(['day', 'tp', 'side']).agg(n=('lots', 'size'), lots=('lots', 'sum')).round(0))
