"""P6b: bracket the configured stop level. Instantaneous MTM at every order timestamp:
traded contracts marked at the order's recovered quote L, others at the same-minute candle close (ffill).
Upper bound on threshold = most negative MTM observed WITHOUT a trigger; lower bound = least negative MTM AT a trigger."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from load import load_tagged
C = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_cache')
d = load_tagged().sort_values(['t', 'row'])
d['L'] = np.where(d.side == 'Buy', d.px_order / 1.15, d.px_order / 0.85)
v = d.tp == 'v_'; d.loc[v, 'L'] = np.where(d.side == 'Buy', d.px_order / 1.03, d.px_order / 0.85)[v]
o = pd.read_pickle(os.path.join(C, 'opt_candles.pkl'))
o['key'] = o.cp + o.strike.astype(int).astype(str)
d['key'] = d.cp + d.strike.astype(int).astype(str)
stops = d[d.tp == 's_'].groupby(['und', 'expiry']).t.min()
rows = []
for (u, e), c in d.groupby(['und', 'expiry']):
    lot = c.lot.iloc[0]; trig = stops.get((u, e), pd.NaT)
    oc = o[(o.und == u) & (o.expiry == e) & o.ts.dt.normalize().isin(sorted(c.date.unique()))]
    close = oc.pivot_table(index='ts', columns='key', values='c', aggfunc='last').sort_index().ffill()
    pos = {}; cash = 0.0; best = []
    last_quote = {}
    for r in c.itertuples():
        if pd.notna(trig) and r.t >= trig: break
        # evaluate MTM just BEFORE this order's fill, using this order's quote for its contract
        m = r.t.floor('min')
        row = close.loc[:m].iloc[-1] if (close.index <= m).any() else None
        last_quote[r.key] = (r.t, r.L)
        val = 0.0
        for k, p in pos.items():
            if abs(p) < 1e-9: continue
            q = last_quote.get(k)
            px = q[1] if (q and (r.t - q[0]).total_seconds() <= 20) else (row[k] if row is not None and k in row and pd.notna(row[k]) else (q[1] if q else 0))
            val += p * lot * px
        best.append((r.t, cash + val))
        pos[r.key] = pos.get(r.key, 0.0) + r.sl; cash += r.cash
    b = pd.DataFrame(best, columns=['t', 'mtm'])
    if len(b): rows.append(dict(und=u, expiry=e.date(), stop=pd.notna(trig), min_mtm_without_trigger=round(b.mtm.min()), at=b.loc[b.mtm.idxmin(), 't'].strftime('%m-%d %H:%M:%S')))
r = pd.DataFrame(rows).sort_values('min_mtm_without_trigger')
pd.set_option('display.width', 200)
print(r.head(15).to_string(index=False))
print('\nUPPER bound for the threshold (deepest instantaneous MTM seen without any trigger):', r.min_mtm_without_trigger.min())
