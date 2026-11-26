# Phase 1 final loop: decision record (Investigations A-D and population reconciliation)

*2026-11-25. Plans (criteria fixed before each result, with the honest-ordering notes they contain): `PHASE1_LOOP2_A_PLAN.md`, `_B_PLAN.md`, `_C_PLAN.md` (+ Addenda 1-2), `_D_PLAN.md`. Outputs: `outputs/phase1/9/`. Evidence label for everything here: **historical reproduction on development cycles; no independent validation exists**. Everything is uncommitted. The OMS was not started. Baselines (B0/B1, frozen D-1 and D0 configurations) were not modified by any experiment; the only source edits are default-off switches (below) and they are covered by the full regression.*

## 0. Population reconciliation (D0): done, reconciles exactly
D0 log **29,959 orders in 33 cycles** = evaluated **26,430 orders in 30 cycles** + excluded **3,529 orders in 3 cycles** (NIFTY 2026-06-23: 1,846; 2026-08-11: 797; 2026-09-15: 886). Reason, verified: these three cycles have **no D-1 cycle record** (zero D-1 orders and no market-data cache), so a D0 replay has no carried book or option chain; they are excluded, not replaced. Two D-1 cycle-table rows (NIFTY 2026-09-01, 2026-09-29) have **no D0 log** and are in the 32-cycle D-1 evaluation but not in any D0 or integrated number. **Every D0 and integrated metric therefore covers 30 of the 33 D0-log cycles (88.2% of D0 orders)**; the integrated cycle count is 30, D-1 alone 32. The word "OOF" names the interleaved-halves split over those 30 cycles. Files: `population_reconciliation.csv/json`.

## 1. Investigation A: option-premium-triggered solo ladder: **REJECTED at the decision level (data-limited)**
* Test (preregistered, cell level, 21,938 cycle-minute-right cells, 637 real solo sells, 381 missed by B1): premium-extreme indicator P vs the engine's spot-extreme indicator S. F1: S 0.437, **P 0.460**, union 0.421.
* PA1 (F1 gain >= 0.03 with the interval above 0): gain 0.023, interval lower bound -0.0016: **fail**. PA2 (covers >= 40% of the B1-missed solo sells at lift >= 3): 75%, lift 10.8: pass. PA3 (precision >= 0.8 x S): pass. Union rule: gain -0.016 (negative): fail. **P_supported = False, U_supported = False.**
* Stop rule applied: **no engine variant was built.** What is true: P is a slightly better single indicator than S and covers more missed solo sells (S alone covers 55% of them at the cell level, P 75%), but the gain is within noise and the indicators are highly correlated; the cell-level classification is not the order-level problem (counts and timing remain tick-driven).
* Post hoc (not tested further): S AND P gives F1 0.495 (precision 0.418, recall 0.608): a precision/recall trade of the same kind as the archived V01, which failed the recall and lot criteria; the stop rule forbids an engine variant without a preregistration.
* **Classification (D1-05): Unresolved / data-limited; H6 rejected.**

## 2. Investigation B: D-1 session stop
* **Session scope is not separable from cycle scope in D-1** (the loss since the D-1 open is the same window); the D0-only scope was rejected earlier (F1 <= 0.27). Recorded as an ambiguity, not asserted.
* **The real D-1 log holds exactly one stop**: NIFTY 2026-09-01, `s_` module, 14:46, 30 orders liquidating the whole book (the cycle stop firing in D-1).
* **Measurement defect found and corrected.** The earlier claim "constant 1.20 lakh, no false alarm in the 19 non-stop cycles" tested the D0 stage only. On the **full D-1 + D0 real-book path** (30 cycles) the constant 1.20 lakh gives **2 false alarms** (NIFTY 2026-10-06 min -1.2177, SENSEX 2026-10-08 min -1.2173, both D-1 sessions) with 11 of 11 stops hit. The data-supported interval for minute-close marks is **(1.2177, 1.2902] lakh**. **BX1 (1.25 lakh, interval midpoint): all 11 D0 stops hit and the D-1 stop hit (first crossing at the real stop minute 331), 0 false alarms in 32 D-1 + 30 D0 sessions: supported** (in-sample interval estimate from 12 stops; the midpoint is a choice).
* **BE-D0 (promote 1.25 in the D0 engine): accepted.** OOF keys F1 0.422 vs 0.422; legacy 0.415; all generic criteria pass; the engine stop agreement is unchanged (8 hits / 3 false). The engine default stays 1.20 (it is the Gate 5a regression anchor); the constant lives in the frozen configurations.
* **BE-D1 (a stop in the D-1 engine; new default-off switch): REJECTED.** The stop fires in NIFTY 2026-09-01 at **minute 331, exactly the real stop minute**, liquidating 146 lots in 23 orders and preventing 40 later simulated orders (B1 sends 40 more orders after it, 30 of them from 15:15 where the real log has 0). **But it stops 4 sessions that never stopped (limit 2)**: the simulated book's mark-to-market differs from the real one (the real book never reached -1.25 there). Keys F1 0.734 vs 0.739; strict 0.468 vs 0.472; scheduled straddles matched 2046 (< 2,076). The 27 sessions without a stop are identical to B1. Rejected under the preregistered criteria; archived (`BE_D1_result.json`); the switch stays in the engine, default off, with 4 unit tests.
* **Classification (D1-15):** rule **Confirmed on the real book** in D-1 and D0 (12 of 12 stops, 0 false alarms, minute-close marks, cumulative D-1 + D0, constant in (1.218, 1.290] lakh; frozen at 1.25); **free-running D-1 stop: rejected (book divergence)**; timing from completed bars still unrecoverable.

## 3. Investigation C: D0 clearance spread
* Real structure (`C_real_clearance_cycles.csv`, `C_clearance_measures.csv`): **post-auction: 90% of the clearance lots are done at 15:14 (minute 359) in 9 of 10 clearing cycles (m50 also 359 in 8 of 10); the exception, SENSEX 2026-08-13, clears at 15:33 and alone holds all 138 real orders from 15:30** (the "15:30+ block" is one cycle). **Pre-auction: a gradual flow from 15:00 and a final sweep with 90% done at minute 364 in 7 of 8 cycles (363 in one); m50 is unstable (350-362).** Stopped cycles excluded; SENSEX 2026-09-10 holds no shorts at 15:09.
* CH3 (state dependence): no |rho| >= 0.5 with q < 0.05 in either era (n = 8 and 10): **not supported**.
* Engine runs (mode T, leave-one-cycle-out constants): pre-auction clearance timing error (minutes per lot) V0 **4.44**, X1 4.21, CH1 4.22, **CH2 3.04**.
* **CH1 (fixed sweep clock, LOCO 364): rejected** (no better than X1; CA1 and CA5 fail). **CH2 (staggered hazards): rejected under the preregistered rule** (CA1 requires <= 0.5 x V0; it reaches 0.68 x V0 and 0.72 x X1; CA2-CA5 pass). CH2 is the best-evidence clearance candidate (clearance-window `one_lot` F1 0.362 vs X1 0.322; OOF keys F1 0.4234) and is recorded as a **near-miss for a future independent test**, not adopted.
* **X1 (363 pre-auction) is not promoted.** It stays an **experimental, in-sample, historical-regime candidate** (8 cycles; forward sets have none). **Production/forward default: clearance at 359 for every cycle** (post-auction, the only regime a future expiry can be in, is 9 of 10 at 359). X1 appears only in the historical-reproduction configuration, labelled.
* The 15:30+ tail is one anomalous cycle; the engine session is not extended (ends 15:29). **Classification (D0-06): post-auction clock Decoded (9/10); pre-auction sweep Decoded (364); spread/flow Partial; SENSEX 2026-08-13 15:33 clearance Unresolved (isolated).**

## 4. Investigation D: 15:30 candle-close bursts: **plausible but unconfirmed; the original reading is not causal**
* Timestamp audit: **7 of 8 burst starts precede the completion of the 15:00-15:30 candle (leads 4-258 s)**; only SENSEX 2026-08-12 starts at 15:30:00. The G1b condition used the close of minute 374, which exists only from 15:30:00: **it cannot be the trigger for 7 of 8 bursts.** Body orders carry no decision timestamp (`t_dec` exists only for `h_`, `s_`, `v_`, `m_`).
* DT1 reproduces G1b exactly (7/8, 12 of 29 cycles, p = 0.0033). **DT2 (causal analogue, close of minute 369, known before the earliest burst): 6/8, 10 of 29 cycles, precision 0.60, recall 0.75, p = 0.0089: passes the preregistered rule.** Sensitivity: 369 and 371 pass, **373 does not (p = 0.055, precision 0.46, 7 false-positive cycles)**; 374 passes only by using unavailable information. Burst starts are concentrated at the candle end: 7 of 8 in the last 120 s (binomial p = 0.0085).
* **Classification (G1b): temporal association + late-day range-extension state; plausible but unconfirmed; excluded from the baseline; no engine change, no session extension.** What cannot be established: the decision rule and decision time of body orders; the candle close at the time of the bursts; anything from 8 post-observation events.

## 5. Corrections and engine changes (all default off)
`d1_algo`: `cycle_stop_rupees`/`cycle_stop_check_s` and roles `cycle_stop_buyback/sell` (BE-D1, rejected, archived); `d0_algo`: `clearance_hazards` (CH2, rejected, archived); `d0_algo`: peak-short monitor (earlier). Defaults replay B1 and the Gate 5a reference unchanged (tests below). No real-order input exists in any of them.

## 6. Selection accounting for this loop
A: 2 binary rules (+1 post hoc observation, untested); B: 2 constants + 1 engine variant; C: CH1, CH2, CH3 (+ X1, X1s364 comparators); D: DT1-DT4. About 11 new tests on the same development cycles (Phase 1 total now about 56). Counted, not deflated.

## 7. Final combined validation (best defensible configuration)

**Configurations validated.** D-1: **B1** (frozen, `one_lot_v2`; both D-1 candidates of this loop rejected). D0: two frozen configurations that differ in one setting only: **forward/production** (clearance 359 in every cycle, stop 1.25 lakh) and **historical-reproduction** (forward + the experimental in-sample pre-auction clearance 363). Integrated: B1 + each D0 configuration. Same scorer (spec v1.1), same populations as before. **Scoring unit: orders, one-to-one matching; keys = side/type/right/class match within the tolerance; strict = strike and lots also exact; the lot-level F1 is the legacy bridge (a different unit: lots matched +/-1 minute) and is never mixed with the order-level numbers.**

### 7.1 D-1 (B1; mode F = mode T for D-1; 32 cycles; 9,915 real vs 9,035 simulated orders; tolerance 60 s unless stated)
| Metric | Value |
|---|---|
| keys F1 at 0 s / 5 s / 60 s | 0.213 / 0.498 / **0.739** (recall 0.706, precision 0.775) |
| strict F1 (strike and lots exact), 60 s | **0.472** (precision 0.495, recall 0.451) |
| legacy lot-level F1 (lots, +/-1 min) | **0.6878** |
| shift placebo keys F1 (+15 min) | 0.326 |
| per-cycle keys F1 | median 0.742, min 0.661, max 0.820; all 32 >= 0.60 |
| portfolio state | median normalised contract-level book distance at matched events 0.508 (Gate 4, Q9) |
| risk | 0 refused orders, peak 130 short lots per right (limit 400) |

B1 classes (keys F1 60 s): body_buyback 0.573, body_sell 0.759, lump 0.328, opening_wings 0.854, wing_buy 0.822, wing_sell 0.497.

### 7.2 D0, forward/production configuration (mode T = start from the real carried book; population 30 of 33 D0-log cycles = 26,430 of 29,959 orders; the 3 excluded NIFTY cycles (3,529 orders) have no D-1 record; tolerance 60 s)
| Metric | OOF halves (30 cycles) | LOCO (30) | Forward A (9 cycles) | Forward B (10 cycles) |
|---|---:|---:|---:|---:|
| keys F1, `events` | **0.420** (CI 0.382-0.455) | 0.427 (CI 0.391-0.461) | 0.471 | 0.392 |
| keys recall / precision | 0.352 / 0.521 | n/a | n/a | n/a |
| strict F1 | 0.142 | 0.145 | 0.175 | 0.106 |
| legacy lot-level F1 | 0.411 | 0.421 | 0.452 | 0.390 |
| shift placebo keys F1 | 0.238 | 0.240 | 0.212 | 0.194 |
| `one_lot` convention keys F1 (sensitivity) | 0.398 | n/a | 0.403 | 0.355 |

Per-cycle keys F1 (OOF): median 0.409, IQR 0.305-0.485, min 0.123, max 0.550; 19 of 30 cycles >= 0.35. Orders: real 26,430, simulated 17,826, matched (60 s) 9,296, unmatched real 17,134, extra simulated 8,530. Median normalised book distance at matched events 0.733. D0 standards: 7 of 13 pass (D6, D7, D8, D10, D11, D12, D13); D1-D5, D9 fail (unchanged).

| Class (OOF) | Real | Sim | Recall | Precision | F1 |
|---|---:|---:|---:|---:|---:|
| body_buyback | 8,350 | 9,213 | 0.315 | 0.347 | 0.330 |
| body_long | 1,637 | 113 | 0.243 | 0.575 | 0.341 |
| body_sell | 7,905 | 3,963 | 0.396 | 0.757 | 0.520 |
| not_modelled | 164 | 0 | 0.652 | n/a | n/a |
| stop | 387 | 260 | 0.093 | 0.646 | 0.163 |
| wing_buy | 4,515 | 2,377 | 0.469 | 0.739 | 0.574 |
| wing_sell | 3,472 | 1,900 | 0.252 | 0.583 | 0.352 |

### 7.3 D0, historical-reproduction configuration (mode T = start from the real carried book; population 30 of 33 D0-log cycles = 26,430 of 29,959 orders; the 3 excluded NIFTY cycles (3,529 orders) have no D-1 record; tolerance 60 s)
| Metric | OOF halves (30 cycles) | LOCO (30) | Forward A (9 cycles) | Forward B (10 cycles) |
|---|---:|---:|---:|---:|
| keys F1, `events` | **0.422** (CI 0.384-0.457) | 0.428 (CI 0.391-0.463) | 0.471 | 0.392 |
| keys recall / precision | 0.354 / 0.522 | n/a | n/a | n/a |
| strict F1 | 0.143 | 0.145 | 0.175 | 0.106 |
| legacy lot-level F1 | 0.415 | 0.424 | 0.452 | 0.390 |
| shift placebo keys F1 | 0.238 | 0.240 | 0.212 | 0.194 |
| `one_lot` convention keys F1 (sensitivity) | 0.403 | n/a | 0.403 | 0.355 |

Per-cycle keys F1 (OOF): median 0.411, IQR 0.305-0.492, min 0.123, max 0.550; 20 of 30 cycles >= 0.35. Orders: real 26,430, simulated 17,916, matched (60 s) 9,358, unmatched real 17,072, extra simulated 8,558. Median normalised book distance at matched events 0.737. D0 standards: 7 of 13 pass (D6, D7, D8, D10, D11, D12, D13); D1-D5, D9 fail (unchanged).

| Class (OOF) | Real | Sim | Recall | Precision | F1 |
|---|---:|---:|---:|---:|---:|
| body_buyback | 8,350 | 9,275 | 0.320 | 0.349 | 0.334 |
| body_long | 1,637 | 113 | 0.245 | 0.655 | 0.357 |
| body_sell | 7,905 | 3,975 | 0.396 | 0.756 | 0.520 |
| not_modelled | 164 | 0 | 0.652 | n/a | n/a |
| stop | 387 | 260 | 0.093 | 0.646 | 0.163 |
| wing_buy | 4,515 | 2,385 | 0.470 | 0.739 | 0.574 |
| wing_sell | 3,472 | 1,908 | 0.257 | 0.582 | 0.356 |

### 7.4 Integrated D-1 + D0 (forward/production D0; mode F: free-running, no real order or position enters any decision; 30 cycles; tolerance 60 s)
| Set | Cycles | D-1 part | D0 part | Combined | Combined placebo | strict combined | Carry distance at D0 open (median) | Engine stops (real: 11 in the OOF set) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| OOF | 30 | 0.739 | 0.395 | **0.497** | 0.256 | 0.228 | 0.790 | 13 |
| forwardA | 9 | 0.725 | 0.474 | **0.569** | 0.258 | 0.299 | 0.786 | 5 |
| forwardB | 10 | 0.715 | 0.272 | **0.443** | 0.205 | 0.232 | 0.886 | 7 |

Handoff identity (positions and cash) 49/49, reconciliation and determinism the same; 0 refused orders; peak short lots per right D0 229 (limit 306), D-1 130 (limit 400). Combined per-cycle keys F1 (OOF): median 0.528, min 0.301, max 0.708. Carry distance at the D0 open: IQR 0.624-0.985, simulated/real short-lot ratio 0.95. **A pass of the integration checks is not evidence of fidelity to the original strategy.**

### 7.5 Integrated D-1 + D0 (historical-reproduction D0; mode F: free-running, no real order or position enters any decision; 30 cycles; tolerance 60 s)
| Set | Cycles | D-1 part | D0 part | Combined | Combined placebo | strict combined | Carry distance at D0 open (median) | Engine stops (real: 11 in the OOF set) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| OOF | 30 | 0.739 | 0.397 | **0.498** | 0.255 | 0.228 | 0.790 | 13 |
| forwardA | 9 | 0.725 | 0.474 | **0.569** | 0.258 | 0.299 | 0.786 | 5 |
| forwardB | 10 | 0.715 | 0.272 | **0.443** | 0.205 | 0.232 | 0.886 | 7 |

Handoff identity (positions and cash) 49/49, reconciliation and determinism the same; 0 refused orders; peak short lots per right D0 229 (limit 306), D-1 130 (limit 400). Combined per-cycle keys F1 (OOF): median 0.531, min 0.301, max 0.708. Carry distance at the D0 open: IQR 0.624-0.985, simulated/real short-lot ratio 0.95. **A pass of the integration checks is not evidence of fidelity to the original strategy.**

### 7.6 Before / after (OOF, 60 s keys F1; same populations)
| Metric | Phase 1 closure (D0-C: X1, stop 1.20) | Final: historical-reproduction (X1, stop 1.25) | Final: forward/production (359, stop 1.25) |
|---|---:|---:|---:|
| D-1 (B1) keys F1 | 0.739 | 0.739 (unchanged) | 0.739 (unchanged) |
| D0 mode T keys F1 | 0.422 | 0.422 | 0.420 |
| D0 mode T legacy lot-level | 0.414 | 0.415 | 0.411 |
| D0 mode T strict F1 | 0.143 | 0.143 | 0.142 |
| D0 true LOCO keys F1 | 0.428 | 0.428 | 0.427 |
| Integrated mode F, D0 part | 0.397 | 0.397 | 0.395 |
| Integrated mode F, combined | 0.498 | 0.498 | 0.497 |

**The four investigations and the corrections moved no headline keys F1 by more than 0.002 (legacy lot-level by at most 0.004).** The stop constant (1.25) is a correction of a measured contradiction; the X1 clearance setting adds +0.002 in-sample; everything else was rejected or classified.

### 7.7 Robustness and integrity of the final configurations
True LOCO: HR 0.428, forward 0.427 (half-split OOF 0.422 / 0.420). Timing (HR, shift of the simulated times): -120 s 0.238, -60 s 0.300, 0 0.422, +60 s 0.436, +120 s 0.318. Causality: future bars replaced by garbage after minute m = 100/200/300 on 4 D0 cycles (final HR configuration) and 2 D-1 cycles **with the stop switch ON**: events up to minute m identical in 18 of 18 tests. Train/test disjoint in all splits and LOCO folds.
