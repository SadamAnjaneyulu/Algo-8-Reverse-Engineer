"""TP-03 Phase 1: POST-HOC diagnostic for E5 (outside the registered family, not a decision-time reference).
Asks one question: is the traded strike closer to the ATM of the bar that contains the first fill (a fresher price than the last COMPLETED bar R1/R2)?  Uses the index bar that is still forming at the order time, i.e. information that is not available at the registered snapshot: it can explain the selector, it cannot be used as a state feature."""
import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tp03_common as tc, entry_common as ec
tc.assert_frozen(); A = tc.ANALYSIS; D = ec.Data(); P = pd.read_csv(os.path.join(A, 'p1_e5_strike_orders.csv'), parse_dates=['E', 'first_fill', 'date', 'expiry'])
step = P.und.map(ec.STEP)
def bar(r, field, t): return float(D.idx[r.und][field].get(t, np.nan))
P['R5_close_of_fill_minute'] = [bar(r, 'close', r.first_fill.floor('min')) for r in P.itertuples()]; P['R6_open_of_fill_minute'] = [bar(r, 'open', r.first_fill.floor('min')) for r in P.itertuples()]
P['R7_open_of_entry_minute'] = [bar(r, 'open', r.E.floor('min')) for r in P.itertuples()]
rows = []
for name in ('R1_close', 'R2_close', 'R7_open_of_entry_minute', 'R6_open_of_fill_minute', 'R5_close_of_fill_minute'):
    S = P[name]; K = step * np.floor(S / step + 0.5); m = np.isfinite(K); o = ((P.strike - K) / step)[m]
    for lab, sub in (('all', slice(None)), ('WINDOW_ACTION', P.event_class[m] == 'WINDOW_ACTION'), ('OFF_WINDOW_ACTION', P.event_class[m] == 'OFF_WINDOW_ACTION'), ('INITIAL_ENTRY', P.event_class[m] == 'INITIAL_ENTRY')):
        x = o[sub] if not isinstance(sub, slice) else o; rows.append(dict(reference=name, subset=lab, orders=len(x), exact=float((x == 0).mean()), within1=float((x.abs() <= 1).mean())))
R = pd.DataFrame(rows); R.to_csv(os.path.join(A, 'p1_e5_diagnostic_posthoc.csv'), index=False); print(R.to_string())
