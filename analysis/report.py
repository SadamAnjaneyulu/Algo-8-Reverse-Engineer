"""Reproduce the headline tables in FINDINGS.md from the raw trade log.
Run:  python3 analysis/report.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from load import load
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40); pd.set_option('display.max_rows', 500)

d = load()
d['sl'] = d.sgn * d.lots
d['cash'] = -d.sgn * d.qty_fill * d.px_fill

# ---- 1. cycle table (cycle = underlying+expiry; D-1 = day before expiry, D0 = expiry day)
rows = []
for (u, e), g in d.groupby(['und', 'expiry']):
    net = g.groupby(['cp', 'strike']).sl.sum()
    rows.append(dict(und=u, expiry=e.date(), has_d1=(g.dte >= 1).any(), has_d0=(g.dte == 0).any(),
                     fills=len(g), orders=g.oid.nunique(), left_lots=net[net.abs() > 1e-9].abs().sum(),
                     gross_pnl=round(g.cash.sum()), last_fill=g.t.max().strftime('%m-%d %H:%M')))
cyc = pd.DataFrame(rows)
print('=== cycles ===\n', cyc.to_string(index=False))

clean = cyc[cyc.has_d1 & cyc.has_d0 & (cyc.expiry != pd.Timestamp('2026-09-29').date())].copy()
clean['stop'] = clean.gross_pnl <= -130000
print('\n=== clean D-1+D0 cycles ===')
for lab, x in [('ALL', clean), ('NIFTY', clean[clean.und == 'NIFTY']), ('SENSEX', clean[clean.und == 'SENSEX'])]:
    cum = x.sort_values('expiry').gross_pnl.cumsum()
    print(f"{lab}: n={len(x)} total={x.gross_pnl.sum():,.0f} mean={x.gross_pnl.mean():,.0f} "
          f"win%={(x.gross_pnl>0).mean()*100:.0f} stops={x.stop.sum()} worst={x.gross_pnl.min():,.0f} "
          f"maxDD={(cum-cum.cummax()).min():,.0f}")

# ---- 2. EOD (D-1) carry hedge 'lump': biggest single-strike buy after 15:00
print('\n=== D-1 end-of-day lump hedge ===')
out = []
for dt, g in d[d.dte >= 1].groupby('date'):
    late = g[(g.t.dt.time >= pd.Timestamp('15:00').time()) & (g.side == 'Buy')]
    if late.empty: continue
    b = late.groupby(['cp', 'strike']).agg(lots=('lots', 'sum'), px=('px_fill', 'mean'), t=('t', 'min')).sort_values('lots', ascending=False)
    (cp, k), r = b.index[0], b.iloc[0]
    out.append(dict(date=dt.date(), und=g.und.iloc[0], side=cp, strike=k, lots=r.lots, px=round(r.px, 2), time=r.t.strftime('%H:%M:%S')))
print(pd.DataFrame(out).to_string(index=False))
