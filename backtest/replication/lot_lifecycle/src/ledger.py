"""Fill-level ledger loader. One row per FILL with the exact per-fill price (raw column 137, verified as the exchange tick price; the repo's px_fill is a running order average).
Within-second order = file order (row), documented DAT-17. Key of a fill = (date, tradeid, row): trade ids repeat across dates/orders (22 coincidental repeats)."""
import os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); LL = os.path.dirname(HERE); REPL = os.path.dirname(LL); BT = os.path.dirname(REPL); ROOT = os.path.dirname(BT)
for p in (os.path.join(ROOT, 'analysis'), BT, REPL, os.path.join(REPL, 'd0_reconstruction')): sys.path.insert(0, p)
OUT = os.path.join(LL, 'outputs'); REP = os.path.join(LL, 'reports'); FIG = os.path.join(REP, 'figures'); FIX = os.path.join(LL, 'fixtures')
for p in (OUT, REP, FIG, FIX): os.makedirs(p, exist_ok=True)
LOT = {'NIFTY': 65, 'SENSEX': 20}


def load_fills():
    import load as L
    d = L.load_tagged(); d = d.sort_values(['t', 'row']).reset_index(drop=True)
    d['expiry'] = pd.to_datetime(d.expiry).dt.strftime('%Y-%m-%d'); d['day'] = d.date.dt.strftime('%Y-%m-%d'); d['sec'] = d.t.dt.hour * 3600 + d.t.dt.minute * 60 + d.t.dt.second
    d['module'] = d.tp; d['px'] = d.px137.astype(float); d['n_lots'] = (d.qty_fill / d.und.map(LOT)).round().astype(int); d['sgn'] = np.where(d.side == 'Buy', 1, -1)
    assert (abs(d.n_lots * d.und.map(LOT) - d.qty_fill) < 1e-9).all()
    return d[['row', 'tag', 'tradeid', 'module', 'und', 'expiry', 'day', 'sec', 't', 'cp', 'strike', 'side', 'sgn', 'qty_fill', 'n_lots', 'px', 'px_fill', 'validity']]


def cycle_table(fills):
    from bt import cycles as Cy
    cl = Cy.cycle_list(); rows = []
    for (u, e), g in fills.groupby(['und', 'expiry']):
        m = cl[(cl.und == u) & (cl.expiry == e)].iloc[0]; days = set(g.day)
        rows.append(dict(und=u, expiry=e, d1=m.d1, d0=m.d0, has_d1=m.d1 in days, has_d0=m.d0 in days, carry_in_known=(m.d1 in days) and (m.d0 in days)))
    return pd.DataFrame(rows)
