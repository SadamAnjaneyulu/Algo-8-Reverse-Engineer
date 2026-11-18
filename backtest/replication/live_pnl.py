"""Realised P&L of the REAL Algo 8 ledger per cycle (und, expiry): fill cash flows + cash settlement of lots still open at expiry. Gross, and net of the SAME cost model used in our backtest (assumed brokerage 20/order etc.). Diagnostic/benchmark only."""
import math
from common import *
from bt import account as A
d = live_ledger(); d['expiry'] = pd.to_datetime(d.expiry); d['cash'] = -d.sgn * d.qty_fill * d.px_fill
rows = []; open_rows = []
for (u, e), g in d.groupby(['und', 'expiry']):
    cash = g.cash.sum(); sett = 0.0; S = YAHOO[u].close.get(e, np.nan)
    pos = g.groupby(['cp', 'strike']).apply(lambda x: (x.sgn * x.qty_fill).sum())
    for (cp, k), q in pos.items():
        if abs(q) > 1e-9: sett += q * intr(cp, k, S); open_rows.append(dict(und=u, expiry=e, cp=cp, strike=k, open_qty=q))
    # costs: per order id, value-weighted
    o = g.assign(v=g.qty_fill * g.px_fill).groupby('oid').agg(side=('sgn', 'first'), v=('v', 'sum'), day=('date', 'first'))
    brok = 20.0 * len(o); full = 0.0
    for r in o.itertuples(): full += A.order_costs(u, str(r.day.date()), int(r.side), r.v)
    ex = sum(A.stt_exercise(str(e.date())) * max(intr(cp, k, S), 0) * q for (cp, k), q in pos.items() if q > 0 and intr(cp, k, S) > 0)
    first = g.date.min(); days = g.date.nunique()
    rows.append(dict(und=u, expiry=e, first_day=first, days_traded=days, fills=len(g), orders=len(o), gross=cash + sett, settle_part=sett, brokerage_20=brok, cost_model_total=full + ex, net_cost_model=cash + sett - full - ex, stop_cycle=bool((g.tp == 's_').any()), lots_sold=float(g[(g.sgn < 0) & (g.tp == 'num')].lots.sum()), peak_day_orders=g.groupby('date').oid.nunique().max()))
P = pd.DataFrame(rows).sort_values('expiry'); P['wk'] = P.expiry.dt.strftime('%G-W%V'); P.to_csv(f'{RES}/live_cycle_pnl.csv', index=False); pd.DataFrame(open_rows).to_csv(f'{RES}/live_open_at_expiry.csv', index=False)
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30)
print(P[['und', 'expiry', 'days_traded', 'fills', 'orders', 'gross', 'brokerage_20', 'cost_model_total', 'net_cost_model', 'stop_cycle']].round(0).to_string(index=False))
full = P[P.days_traded >= 2]
def sh(w, k=52): return w.mean() / w.std(ddof=1) * math.sqrt(k)
for lab, x in (('ALL cycles', P), ('D-1+D0 cycles only', full)):
    for col in ('gross', 'net_cost_model'):
        w = x.groupby('wk')[col].sum(); print(f'{lab:22s} {col:15s} cycles={len(x)} weeks={len(w)} total={x[col].sum():,.0f} mean_wk={w.mean():,.0f} sd_wk={w.std(ddof=1):,.0f} Sharpe(wk,sqrt52,cap2Cr)={sh(w):.2f}  ret%={100*x[col].sum()/CAP:.2f}')
print('orders per cycle (median):', P.orders.median(), ' backtest baseline orders/cycle: 4')
