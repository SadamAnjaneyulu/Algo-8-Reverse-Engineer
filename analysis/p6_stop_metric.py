"""P6: which P&L metric does the stop module watch?  python3 analysis/p6_stop_metric.py
Candidate metrics evaluated on minute MTM (fills + Breeze closes); at triggers we use the exact LTP-based MTM recovered from s_ orders.
Score: tightness of trigger values (CV) and separation vs the most extreme value ever reached in non-stop cycles."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from load import load_tagged
from mtm import cycle_mtm
C = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_cache')

d = load_tagged().sort_values(['t', 'row'])
d['L'] = np.where(d.side == 'Buy', d.px_order / 1.15, d.px_order / 0.85)
v = d.tp == 'v_'; d.loc[v, 'L'] = np.where(d.side == 'Buy', d.px_order / 1.03, d.px_order / 0.85)[v]
o = pd.read_pickle(os.path.join(C, 'opt_candles.pkl'))
stops = d[d.tp == 's_'].groupby(['und', 'expiry']).t.min()
BROK = 20.0  # Rs per executed order, assumption for the cost-inclusive variant

def exact_trigger_mtm(c, t0):
    pre = c[c.t < t0]; lot = c.lot.iloc[0]
    win = c[(c.t >= t0) & (c.t <= t0 + pd.Timedelta(seconds=180))]
    Ls = win.groupby(['cp', 'strike']).L.first(); last = pre.groupby(['cp', 'strike']).px_fill.last()
    pos = pre.groupby(['cp', 'strike']).sl.sum(); pos = pos[pos.abs() > 1e-9]
    return pre.cash.sum() + sum(pos[i] * lot * (Ls[i] if i in Ls.index else last.get(i, 0.0)) for i in pos.index), pre

rows = []
for (u, e), c in d.groupby(['und', 'expiry']):
    m = cycle_mtm(d, o, u, e)                         # minute series, end-of-minute
    days = sorted(c.date.unique())
    # orders submitted so far (for cost variant)
    oc = c.groupby('oid').t.min().sort_values()
    norders = pd.Series(1, index=oc.values).groupby(level=0).sum().cumsum()
    nord_m = norders.reindex(m.index, method='ffill').fillna(0) if len(norders) else m * 0
    day_of = m.index.normalize()
    prev_close = {}
    for i, dd in enumerate(days):
        prev_close[dd] = 0.0 if i == 0 else m[day_of == days[i - 1]].iloc[-1] if (day_of == days[i - 1]).any() else 0.0
    base = pd.Series([prev_close.get(x, 0.0) for x in day_of], index=m.index)
    trig = stops.get((u, e), pd.NaT)
    if pd.notna(trig):
        mt, pre = exact_trigger_mtm(c, trig)
        mm = m[m.index < trig.floor('min')]
        peak = max(mm.max() if len(mm) else 0.0, 0.0)
        tday = trig.normalize()
        dbase = prev_close.get(tday, 0.0)
        dpeak = max(mm[mm.index.normalize() == tday].max() if (mm.index.normalize() == tday).any() else dbase, dbase)
        n_ord = pre.oid.nunique()
        rows.append(dict(und=u, expiry=e.date(), stop=True, day='D0' if (e - tday).days == 0 else 'D-1',
                         cycle_mtm=mt, dd_from_cycle_peak=mt - peak, day_mtm=mt - dbase, dd_from_day_peak=mt - dpeak,
                         cycle_mtm_net_brok=mt - BROK * n_ord, cycle_peak=peak))
    else:
        peak = m.cummax().clip(lower=0)
        dpk = pd.concat([pd.concat([base[day_of == x], m[day_of == x]], axis=1).max(axis=1).cummax() for x in days if (day_of == x).any()])
        rows.append(dict(und=u, expiry=e.date(), stop=False, day='-',
                         cycle_mtm=m.min(), dd_from_cycle_peak=(m - peak).min(), day_mtm=(m - base).min(),
                         dd_from_day_peak=(m - dpk.reindex(m.index)).min(), cycle_mtm_net_brok=(m - BROK * nord_m).min(), cycle_peak=m.max()))
r = pd.DataFrame(rows)
gap = r.expiry.astype(str).isin(['2026-08-18', '2026-08-20'])
pd.set_option('display.width', 250)
print(r.round(0).to_string(index=False))
print('\n=== metric scorecard (non-gap stops vs non-stop cycles) ===')
out = []
for col in ['cycle_mtm', 'dd_from_cycle_peak', 'day_mtm', 'dd_from_day_peak', 'cycle_mtm_net_brok']:
    t = r[r.stop & ~gap][col]; n = r[~r.stop][col]
    out.append(dict(metric=col, trig_mean=round(t.mean()), trig_sd=round(t.std()), trig_cv=round(abs(t.std() / t.mean()), 3),
                    trig_least_extreme=round(t.max()), nonstop_most_extreme=round(n.min()),
                    separable=bool(n.min() > t.max()), margin=round(n.min() - t.max())))
print(pd.DataFrame(out).to_string(index=False))
r.to_pickle(os.path.join(C, 'p6_metrics.pkl'))
