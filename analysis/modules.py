"""Module decomposition + order-pricing + stop-trigger reconstruction.   python3 analysis/modules.py
Order tag (raw col 163): numeric=body short legs (DAY) | h_=wing hedges (IOC) | s_=stop-loss module | v_=overnight lump hedge | m_=manual
Marketable-limit band: Buy limit = LTP*1.15, Sell limit = LTP*0.85 (v_ Buy: ~LTP*1.03) -> LTP at decision time L = limit/1.15 or /0.85.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from load import load_tagged
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40); pd.set_option('display.max_rows', 200)

d = load_tagged().sort_values(['t', 'row'])
d['L'] = np.where(d.side == 'Buy', d.px_order / 1.15, d.px_order / 0.85)
v = d.tp == 'v_'
d.loc[v, 'L'] = np.where(d.side == 'Buy', d.px_order / 1.03, d.px_order / 0.85)[v]

print('=== 1. module decomposition (fills / lots) ===')
print(d.groupby(['tp', 'side']).agg(fills=('row', 'size'), lots=('lots', 'sum')).to_string())

print('\n=== 2. limit/fill ratio by module (first fill per order, fill>=5) ===')
o = d.groupby('oid').first().reset_index(); o['r'] = o.px_order / o.px_fill
for (tp, sd), g in o[o.px_fill >= 5].groupby(['tp', 'side']):
    if len(g) > 20: print(f'{tp:4s}{sd:5s} n={len(g):5d} median={g.r.median():.3f}')

print('\n=== 3. stop-module trigger: cycle-cumulative MTM at LTP, at the instant the first s_ order fires ===')
stops = d[d.tp == 's_'].groupby(['und', 'expiry', 'date']).t.min().reset_index().rename(columns={'t': 't_trig'})
rows = []
for r in stops.itertuples():
    c = d[(d.und == r.und) & (d.expiry == r.expiry)]; pre = c[c.t < r.t_trig]; lot = c.lot.iloc[0]
    win = c[(c.t >= r.t_trig) & (c.t <= r.t_trig + pd.Timedelta(seconds=180))]
    Ls = win.groupby(['cp', 'strike']).L.first(); last = pre.groupby(['cp', 'strike']).px_fill.last()
    pos = pre.groupby(['cp', 'strike']).sl.sum(); pos = pos[pos.abs() > 1e-9]
    mtm = pre.cash.sum() + sum(pos[i] * lot * (Ls[i] if i in Ls.index else last.get(i, 0.0)) for i in pos.index)
    last_s = c[(c.tp == 's_')].t.max()
    rows.append(dict(und=r.und, date=r.date.date(), trigger=r.t_trig.strftime('%H:%M:%S'), seconds_to_flat=int((last_s - r.t_trig).total_seconds()),
                     short_lots=-pos[pos < 0].sum(), mtm_at_trigger=round(mtm), final_cycle_pnl=round(c.cash.sum())))
t = pd.DataFrame(rows); print(t.to_string(index=False))
gapdays = {'2026-08-18', '2026-08-20'}
n = t[~t.date.astype(str).isin(gapdays)]
print(f'\nnon-gap stops (n={len(n)}): mean MTM at trigger = {n.mtm_at_trigger.mean():,.0f}  sd = {n.mtm_at_trigger.std():,.0f}  range [{n.mtm_at_trigger.min():,}, {n.mtm_at_trigger.max():,}]')
print('short lots range across these stops:', n.short_lots.min(), '-', n.short_lots.max(), '(threshold is size-independent)')
