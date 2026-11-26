# Reactive pairs — is there a per-minute tracker (state machine)? Pre-registered plan

*Written before the tests below were run. Investigation only; in-sample (D-1 of 32 cycles with reactive pairs). No engine/simulator change, no new alpha.*

## Why a new approach
The previous study judged a candidate trigger by "of the minutes where the condition is true, how many contain a pair" (19% for a range breakout). That treats the condition as stateless. The user's point: if a tracker updates every minute and **keeps state** (resets when it fires), most condition-true minutes are *not supposed* to fire, so precision per condition-minute is the wrong yardstick. The right test is to **simulate the tracker forward through each day, let it reset on its own fires, and compare its fire times with the actual pair times**.

## Deliverable 1 — time-aligned example
One NIFTY and one SENSEX D-1 cycle, **chosen by a rule fixed now**: among cycles with ≥ 8 reactive pairs, the one whose reactive-pair count is closest to the median over all cycles (ties: earliest expiry). Panels over 09:15–15:30: spot (minute closes) with the trailing 60-minute high/low band and every reactive pair at its exact second (strike side, strike offset to ATM); scheduled timetable pairs and body buy-backs as context; range position; minutes since the last reactive pair; and the fire times of the best simulated tracker. A table of every pair of that cycle accompanies it.

## Block T1 — timing structure
Second-of-minute distribution of reactive pairs vs scheduled pairs (timer-driven) vs uniform (chi-square); a per-minute tracker with fixed latency would concentrate at particular seconds. Number of reactive pairs per cycle vs breakout minutes per cycle (a quota/budget would decouple them); dispersion of counts vs Poisson.

## Block T2 — forward-simulated trackers (state resets on fire)
Minute panel 10:30–15:15 (minutes 75–360). Two information variants: **bar** (tracker evaluated at the start of minute j with closes through j−1: causal) and **intra** (the current minute's close is used: look-ahead proxy for a tick-level tracker). Machines (grid fixed now):
* **M0 stateless range edge**: fire iff close beyond the previous N closes, N ∈ {30, 45, 60, 90}.
* **M1 range edge + refractory**: as M0 and at least K minutes since the machine's own last fire (K = 1, 2, 3, 5, 8, 12, 16, 20, 25, 30, 40, 50, 60); optional variant: refractory only for the same side.
* **M2 reference-move (grid) tracker**: reference R set at 10:30 and reset to the spot at each fire; fire when |spot − R| ≥ θ steps (θ = 0.5, 1, 1.5, 2, 3, 4, 5, 6, 8); variant where R also resets at every scheduled timetable pair (exogenous times).
* **M3 swing (zig-zag) tracker**: after a reset, track the running low and high; fire when spot − running low ≥ θ (up-swing) or running high − spot ≥ θ (down-swing), then reset; θ as in M2.
* **M4 range edge + swing**: fire iff M0 (N = 60) and M3 would fire.
Scoring: predicted fire minutes vs actual pair minutes, greedy one-to-one matching with tolerance 0 and ±1 minute; precision, recall, F1; side agreement of matched pairs. **Parameters are chosen on alternating cycle halves** (fit on even cycles, score on odd, and vice versa) with the ±1-minute F1 as the objective. **Null:** the machine's fire times shifted by a random offset per cycle (circular within the window, 1,000 draws); a machine "reproduces" the pairs only if its out-of-fold F1 exceeds the 99th percentile of the null **and** precision and recall are both ≥ 0.4 at tolerance ±1. Otherwise: not reproduced.

## Evidence rules
Observed / Inferred / Unresolved / Not testable. The machine grids above are the whole search (≈ 100 configurations); the count is reported. No parameter or machine is added after seeing results without a "post-hoc" label.

## Not testable (stated in advance)
Tick-level timing within the minute; true intraday high/low; any state variable not recoverable from minute closes, the order ledger and option minute data.
