# Phase 1, Gate 5c: D0 opening, carry, clearance and stop. Result

*Evidence: **historical reproduction, development cycles, mode T**. Not independent. Code executed, results observed (`outputs/phase1/5c/*`). Plan with criteria fixed before the variants ran: `PHASE1_GATE5C_PLAN.md` (+ Addendum 1, a labelled pre-run amendment of K1 after the baseline showed the events convention caps clearance-window recall). Nothing committed.*

## Headline (RESULT)
* **X1 (era clearance clock: pre-auction cycles clear at minute 363, post-auction 359): accepted as a CANDIDATE correction.** All preregistered criteria pass. OOF keys F1 0.420 -> 0.422; legacy lot-level 0.410 -> 0.414; clearance-window buy-back F1 (`one_lot`) 0.204 -> 0.322, (`events`) 0.098 -> 0.153; improves in 7 of 8 pre-auction cycles with a clearance; post-auction orders identical.
* **X3 (opening-long clock at 09:16): REJECTED and archived.** Opening-window body-long recall 0.344 vs baseline 0.342 (needed >= 0.442); improves in 8 of 29 cycles. The decoded count rule (rho 0.92 with the 09:16 sells) does not become order-level agreement because the strike (unresolved) and the engine's own 09:16 sells (often absent) limit it.
* **X2 (cycle stop): diagnostic only, no change.** On the real book the rule (cumulative MTM, D-1 + D0, minute-close marks, L = 1.20 lakh) reproduces **11 of 11 stops (stop minute or the minute before), 0 false alarms in 19 cycles, 0 misses** (re-executed from the stored real-book MTM paths: `outputs/phase1/5c/stop_real_book_check.csv`; lowest non-stop cycle -1.172 lakh, shallowest stop cycle -1.29 lakh). The engine/real stop disagreement (both stop in 8 of 11; engine-only 3, real-only 3 of 30) is therefore **inherited from book divergence after D0 decisions, not a rule error**.

## Variants (OOF 30 cycles, `events`, 60 s keys; class F1)
| Class | D0-B (V0) | X1 | X3 |
|---|---:|---:|---:|
| body_buyback | 0.330 | 0.333 | 0.329 |
| body_long | 0.340 | 0.355 | 0.356 |
| body_sell | 0.520 | 0.520 | 0.520 |
| stop | 0.163 | 0.163 | 0.163 |
| wing_buy | 0.574 | 0.574 | 0.575 |
| wing_sell | 0.351 | 0.356 | 0.353 |

## Acceptance
**X1 (363):**
| Criterion | Result |
|---|---|
| C1 overall keys F1 >= base - 0.003 | PASS |
| C2 legacy lot-level F1 >= 0.4103 - 0.005 | PASS |
| C3 every class F1 >= base - 0.02 | PASS |
| C4 no cycle falls by > 0.05 | PASS |
| C5 forward A and B not lower by > 0.003 | PASS |
| K1 one_lot clearance-window F1 >= base + 0.10 and events window F1 not lower | PASS |
| K2 clearance-window F1 improves in a majority of pre-auction cycles with a clearance | PASS |
| K3 post-auction cycles identical | PASS |

**X1 sensitivity 364 (labelled, not selectable):** also passes every criterion (`one_lot` clearance-window F1 0.327); the data cannot separate 363 from 364.
**X3:**
| Criterion | Result |
|---|---|
| C1 overall keys F1 >= base - 0.003 | PASS |
| C2 legacy lot-level F1 >= 0.4103 - 0.005 | PASS |
| C3 every class F1 >= base - 0.02 | PASS |
| C4 no cycle falls by > 0.05 | PASS |
| C5 forward A and B not lower by > 0.003 | PASS |
| O1 opening-window body-long recall >= base + 0.10 and precision >= base - 0.05 | FAIL |
| O2 opening-long F1 improves in a majority of cycles with real opening longs | FAIL |

## Important limits
* **C5 is vacuous for X1:** the forward A/B sets contain no pre-auction cycle, so X1 changes nothing there (forward deltas 0.000). The evidence for X1 is the 8 pre-auction OOF cycles with a clearance: in-sample for the era boundary and for the clock constant (a median of the same cycles), a decoded register value. **Not independent evidence.**
* X1 changes only pre-auction cycles. The post-auction regime has 10 cycles, all consistent with minute 359 (8 of 10 exactly); the regime after 7 Dec 2026 has no D0 log (unobservable; recorded as an open limit).
* The stop is marked on the close of the minute it stops in (up to 60 s of look-ahead in real time); a completed-bar implementation fires one minute later (prev-close variant: 4/11 hits, F1 0.53). Any live use must act at the next minute. Timing of the stop is a data limit (ticks would be needed).
* Clearance spread: real pre-auction clearance spans several minutes (60% in the first); the engine clears in one minute. The remaining difference is execution/timing, not a strategy rule.

## Unresolved after 5c (evidence-limited; no new mechanism, not re-fitted)
Opening solo sells (485 lots in the first three minutes, count not predictable), body-stream long strikes and intraday longs, buy-back burst membership (sets not predictable: `D0_BURST_LONG.md`), 15:30+ residual orders (138 real, 0 simulated), real-vs-engine stop staging.

## Gate 5c status: **CONDITIONAL** (one candidate correction accepted, one rejected, stop rule confirmed on real state; remaining D0 decision-level gaps are the documented data limits).

## Addendum (Phase 1 final loop, 2026-11-25): X1 demoted, stop constant corrected
* X1 (pre-auction clearance at 15:18) is **not a production default**: it stays an experimental in-sample candidate in the historical-reproduction configuration only. Production/forward: clearance 359 everywhere. Staggered (CH2) and LOCO fixed-clock (CH1) alternatives were rejected under preregistered criteria (CH2 a near-miss); state dependence not supported.
* The D0 cycle-stop constant is corrected from 1.20 to 1.25 lakh (X2's "0 false alarms" covered the D0 stage only). `PHASE1_LOOP2_RESULT.md` sections 2-3.
