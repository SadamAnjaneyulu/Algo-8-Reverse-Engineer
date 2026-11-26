# Phase 1, Gate 5d: D0 full-system validation. Result

*Evaluated object: **D0-C = Gate 5a engine + accepted candidate X1** (era clearance clock). **Mode T** (teacher-forced start from the real carried D-1 book): the D0 decision rules run free from there, the real D0 orders are never an input. Evidence: **historical reproduction on development cycles; not independent**. Standards fixed before the run: `PHASE1_GATE5D_STANDARDS.md` (set knowing the 5b/5c values: public yardsticks, several expected to fail). Code executed, results observed (`outputs/phase1/5d/`). Nothing committed. Free-running (mode F) is Gate 6.*

## Headline (RESULT)
**Gate 5d: CONDITIONAL.** 7 of 13 standards pass (D6, D7, D8, D10, D11, D12, D13); **6 fail: D1 order-level F1 0.422 (<0.55), D2 strict F1 0.143 (<0.35), D3 legacy lot-level 0.414 (<0.55), D4 only 67% of cycles at F1 >= 0.35, D5 four classes below 0.40, D9 book distance 0.737 (>0.45).** The engine **beats chance clearly** (placebo 0.238 vs 0.422), is stable on later cycles (forward A 0.472, forward B 0.392), obeys the risk envelope, reproduces on rerun, and reconstructs the stop and clearance mechanics; it **does not reproduce D0 order-by-order**. The failures are decision-level limits documented since the D0 chunks (burst/other buy-back membership, solo/opening sells, long strikes and intraday longs, stop timing) plus the execution layer (aggregated events vs many single-lot real orders); none is attributable to a component that a further preregistered test could still fix on these data.

## Standards
| # | Standard | Value | Threshold | Verdict |
|---|---|---|---|---|
| D1 | pooled keys F1 (OOF, events, 60 s) | 0.422 | 0.55 | **FAIL** |
| D2 | pooled strict F1 | 0.143 | 0.35 | **FAIL** |
| D3 | legacy lot-level OOF F1 | 0.414 | 0.55 | **FAIL** |
| D4 | share of cycles with keys F1 >= 0.35 | 0.667 | 0.8 | **FAIL** |
| D5 | every class with >=100 real orders F1 >= 0.40 | see class table | 0.4 | **FAIL** |
| D6 | placebo / actual | 0.563 | 0.6 | **PASS** |
| D7 | stop cycles hit / false stops | see below | >=8 hits, <=3 false | **PASS** |
| D8 | risk controls (enforce): refused orders, peak short lots per right, peak sell decisions per minute | see below | 0 refused; <=306; <=90 | **PASS** |
| D9 | median normalised book distance at matched events | 0.737 | 0.45 | **FAIL** |
| D10 | forward keys F1 minus OOF | see below | -0.05 | **PASS** |
| D11 | median simulated / real clearance lots | 0.800 | 0.8-1.2 | **PASS** |
| D12 | rerun identical (engine twice per cycle), default config reproduces Gate 5a reference 49/49, suites pass | see below | all | **PASS** |
| D13 | classes with >5% unmatched have a classification or data-limit statement (see result report section on root causes) | see below | statement present | **PASS** |

D5 below 0.40: body_buyback 0.333, body_long 0.355, stop 0.163, wing_sell 0.356. D7: hits 8/11, engine-only NIFTY|2026-08-04, SENSEX|2026-09-17, SENSEX|2026-10-22, real-only NIFTY|2026-09-22, NIFTY|2026-10-13, SENSEX|2026-07-16 (passes at the threshold exactly). **D11 passes at its lower bound (median 0.80, n = 15)**: the engine clears about 80% of the real clearance lot count in the clearance minute, i.e. real clearance volume is somewhat larger than the engine's book (carry divergence and spread over later minutes).

## Full replay (OOF 30 cycles, `events`, mode T)
Orders: real 26,430, simulated 17,906; matched 60 s: 9,349 (exact second 952, within 5 s +2,709, within 60 s +5,688); unmatched real 17,081, extra simulated 8,557.
| Tolerance | keys | strike within 1 | strike exact | lots exact | type |
|---|---:|---:|---:|---:|---:|
| 0 s | 0.043 | 0.035 | 0.030 | 0.029 | 0.029 |
| 5 s | 0.165 | 0.118 | 0.089 | 0.077 | 0.077 |
| 60 s | 0.422 | 0.271 | 0.176 | 0.143 | 0.140 |

Quantity at matched keys: lots exact 0.689, absolute lot error mean 1.55 (median 0, p90 5), signed bias +1.16 lots (simulated larger). Strike at matched keys: exact 0.416, within one step 0.643. Timing: median -4 s, same minute 0.744 (simulated time is minute-resolution; exact-second share descriptive only).

**Sets (teacher-forced separate from free-running: no mode F number appears here):**
| Set | Cycles | Real | Sim | keys F1 60 s | strict F1 | placebo | `one_lot` keys F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| OOF | 30 | 26,430 | 17,906 | 0.422 | 0.143 | 0.238 | 0.403 |
| forwardA | 9 | 5,159 | 3,653 | 0.472 | 0.175 | 0.212 | 0.403 |
| forwardB | 10 | 6,477 | 5,490 | 0.392 | 0.106 | 0.194 | 0.355 |

**Classes (OOF events):**
| Class | Real | Sim | Recall | Precision | F1 | unmatched real share |
|---|---:|---:|---:|---:|---:|---:|
| body_buyback | 8,350 | 9,269 | 0.319 | 0.349 | 0.333 | 0.681 |
| body_long | 1,637 | 113 | 0.244 | 0.655 | 0.355 | 0.756 |
| body_sell | 7,905 | 3,974 | 0.396 | 0.756 | 0.520 | 0.604 |
| not_modelled | 164 | 0 | 0.652 | n/a | n/a | 0.348 |
| stop | 387 | 260 | 0.093 | 0.650 | 0.163 | 0.907 |
| wing_buy | 4,515 | 2,384 | 0.470 | 0.739 | 0.574 | 0.530 |
| wing_sell | 3,472 | 1,906 | 0.256 | 0.581 | 0.356 | 0.744 |

**30-minute blocks (OOF events):**
| Block | Real | Sim | F1 |
|---|---:|---:|---:|
| 09:00 | 3,712 | 1,631 | 0.418 |
| 09:30 | 1,595 | 838 | 0.412 |
| 10:00 | 1,332 | 887 | 0.506 |
| 10:30 | 1,420 | 993 | 0.508 |
| 11:00 | 1,451 | 928 | 0.478 |
| 11:30 | 1,453 | 1,076 | 0.490 |
| 12:00 | 1,111 | 999 | 0.482 |
| 12:30 | 1,999 | 1,482 | 0.540 |
| 13:00 | 1,726 | 1,572 | 0.437 |
| 13:30 | 1,578 | 1,736 | 0.436 |
| 14:00 | 2,220 | 1,535 | 0.361 |
| 14:30 | 3,247 | 1,890 | 0.362 |
| 15:00 | 3,448 | 2,339 | 0.301 |
| 15:30 | 138 | 0 | 0.000 |

**Per cycle:** median 0.411, range 0.123-0.550. Worst: NIFTY|2026-10-13 (0.123), SENSEX|2026-07-16 (0.191), SENSEX|2026-10-15 (0.198), SENSEX|2026-09-10 (0.204), SENSEX|2026-08-20 (0.254). Best: SENSEX|2026-10-22 (0.522), NIFTY|2026-08-25 (0.534), NIFTY|2026-09-08 (0.550). The worst cycles are mostly stop cycles or cycles where the real stop fired at the open and the engine did not (NIFTY 2026-10-13: real stop at minute 3, engine none; 255 real vs 1,124 simulated orders).

## Risk controls, determinism, state
Enforce mode, 49 split-cycle runs: refused orders 0, violations 0; peak short lots per right 279 (limit 306; observed real envelope 278); peak sell decisions per minute 19 (limit 90). Deterministic on rerun and position reconciliation: 49/49. Median normalised book distance at matched events 0.737 (it grows with divergence; at the first order it is zero by construction in mode T). **Opening state check:** engine mark-to-market at the open equals the real-book mark in 29 of 30 cycles (max difference Rs 88,214 in SENSEX 2026-08-20, a stop-at-open cycle) (`opening_mtm_check.json`).

## Sensitivities
| Sensitivity | Result |
|---|---|
| order convention | `one_lot` keys F1 0.403 vs `events` 0.422: the splitting convention moves F1 by 0.02; it is not the main cause |
| X1 on/off | off (5b, corrected): 0.4198 / legacy 0.4103; on: 0.422 / 0.414; 364 instead of 363: same verdict (5c) |
| lot level vs order level | legacy lot-level 0.414 ~ order-level 0.422: the gap is decisions, not order splitting |

## Root causes of unmatched orders (D13)
| Class (unmatched share) | Classification | Label |
|---|---|---|
| body_buyback (0.68) | which lots are bought back (burst/other membership) not predictable on unseen cycles; one event vs many real orders; 15:00+ clearance spread | Unresolved, data-limited (`D0_BURST_LONG.md`, 5c) |
| body_long (0.76) | strikes unresolved; intraday longs and opening count: X3 rejected; engine models only wing-style opening longs and clearance sells | Unresolved, data-limited (5c X3) |
| body_sell (0.60) | solo/opening sells: counts not predictable (485 opening solo lots); stop-at-open cycles | Unresolved, data-limited (Gates 2A-2D, `D0_OPEN_ROLL.md`) |
| stop (0.91) | the rule is confirmed on the real book (11/11, 0 false alarms), but completed bars cannot time it and real stops are staged over several minutes; 3 engine-only and 3 real-only stop cycles are inherited from book divergence after D0 decisions | Confirmed rule; timing data-limited (5c X2) |
| wing_buy (0.53) / wing_sell (0.74) | hedge controller quantity confirmed; strike and timing differences, clearance spread, post-clearance orders | Partial (Gates 3b/3c) |
| not_modelled (0.35) | real orders the engine does not model (0.6% of the real orders, 164) | Not modelled (stated) |

## Limits
Dev cycles only (in-sample structure, out-of-fold fitted constants, 3 D0 cycles without D-1 logs excluded: 3,529 orders); mode T only; minute-resolution simulated times; X1 evidence is the 8 pre-auction cycles (forward sets are all post-auction); stop marked on the minute close; the post-7-Dec-2026 regime has no log.

## Gate 5d status: **CONDITIONAL**

## Addendum (Phase 1 final loop, 2026-11-25): population statement
Every D0 number in this report covers **30 of the 33 D0-log cycles (26,430 of 29,959 orders, 88.2%)**; the 3 excluded NIFTY cycles (3,529 orders) have no D-1 record. Reconciled exactly in `outputs/phase1/9/population_reconciliation.json`. 'OOF' names the interleaved-halves split over those 30 cycles. Re-run with the final configurations: `PHASE1_LOOP2_RESULT.md` section 7.
