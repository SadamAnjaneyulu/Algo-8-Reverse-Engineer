# Reactive pairs: what is the "dynamic" reference, and when do they activate? — plan, written before the tests

**User's summary of what stands.** Supported: the strike is one step off the ATM toward the recent move. Not established: exact look-back (15 min specifically). Unknown: what activates a pair. Not proven: calculation frequency. User's inference: it is not a plain look-back but something dynamic such as a **live-spot comparison**. Task: (1) find what the live spot is compared with; (2) find when a reactive pair activates.

**Known (read-only).** Rule on the live-spot proxy (linear interpolation of the two bracketing minute closes at the order second) hits 90.4% with spot-15-minutes-ago as the reference; every look-back from 10 to 60 minutes fits equally; anchored references (previous block, open, extreme) fit worse; gate 10:30–15:15 with flat ≈ 2.8%/min hazard inside; weak tilt only from minute-level features.

## Locked definitions
* **Event** = D-1 reactive pair (363 with 15 min of history), time = order second. **Control** = a random second inside 10:30–15:15 of the same cycle, ≥ 5 s from any timetable wave and ≥ 60 s from any reactive pair (30 per event, fixed seed). All features computed with the live-spot proxy and only information before the second (the proxy itself uses the current minute close for interpolation — a diagnostic, flagged).
* **Direction candidates** (A): sign(live spot − X) with X ∈ {spot L minutes ago (L = 10, 15, 30, 60), SMA of minute closes over N = 5, 10, 15, 30, 60, EMA(15), strike of the last timetable pair, of the last reactive pair, of the last body sell, **lot-weighted centre of the short book** (all body short contracts), the opening ATM, day mid-range (high+low)/2}. Rule = nearest strike to live spot + step × sign (sign 0 → ATM).
* **Activation features** (B): *spot position* (signed/absolute distance in steps of live spot to the last pair / last reactive pair / last sell / book centre / opening ATM / SMA(10, 30, 60); distance to day high and low; minutes since day high/low); *ATM dynamics* (ATM changes in the last 5/15 minutes, minutes since the last ATM change, fractional position of the live spot between strikes); *event ages* (seconds since the last reactive pair / any body sell / timetable wave / buy-back / non-body-module order); *clock* (seconds since 10:30, version, underlying).

## Tests
A. Hit rate of each direction candidate (with cluster-bootstrap CI), overall and by underlying/half; the best candidate must beat "spot L minutes ago" by a margin with CI excluding 0 to be called a better description.
B. Univariate AUC of every activation feature, events vs controls (cluster bootstrap; within-cycle permutation null). Leave-one-cycle-out gradient boosting by feature block (clock → + event ages → + spot position → + ATM dynamics → all), within-cycle permutation of each block. For the leading feature: hazard curve by bin and a threshold scan (step ≥ 3× between adjacent bins).
C. Second-level inter-arrival: seconds since the previous event of each type, on a log scale, vs a shifted-time null (peaks at fixed lags = timers).

## Decision rules (fixed now)
* A **dynamic reference** is "supported" only if it beats spot-L-minutes-ago by ≥ 3 points with the paired bootstrap CI above 0 and holds in both halves and both underlyings.
* An **activation trigger** is "identified" only if a feature block raises leave-one-cycle-out AUC by ≥ 0.05 over clock + event ages with the permutation maximum below the gain **and** its leading feature shows a monotone hazard with a ≥ 3× step between adjacent bins in both chronological halves. Otherwise "not identified".
* Labels: Observed / Inferred / Unresolved / Not testable. Post-hoc searches (beyond this list) are labelled.

## Limits (known in advance)
Minute closes; the live-spot proxy is an interpolation; 363 events; many candidate features (multiple testing — the AUC table is reported whole); no tick data or source code; the algorithm's internal state (timers, random draws) is not observable.
