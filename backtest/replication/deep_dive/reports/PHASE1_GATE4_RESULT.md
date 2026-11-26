# Phase 1, Gate 4: D-1 full-system validation. Result

*2026-11-25. Standards `PHASE1_GATE4_STANDARDS.md` (fixed before the report, public yardsticks, not blind targets). Object: frozen **B1** (accepted `one_lot_v2`), mode F, 32 development cycles, no engine change since Gate 0. Evidence label: **historical reproduction** (in-sample; no independent data). F and TF-E are reported separately and never mixed. Numbers from `outputs/phase1/gate4/gate4_report.json`. Nothing committed.*

## Gate report
| Field | Content |
|---|---|
| Gate | 4: D-1 full-system validation |
| Status | **CONDITIONAL** (7 of 10 standards pass; the 3 failures trace to gates already run to their stop rules and are data-limited) |
| Baseline | B1 |
| Latest result | order-level F1 (keys, 60 s) **0.739**; strict (strike and lots exact) **0.472**; legacy lot-level **0.688**; per-cycle median 0.742, minimum 0.661 (no cycle below 0.60) |
| Root causes | solo/breakout timing and count (tick path), buy-back trigger gap and upstream positions, frozen index in the late window, lump size: see Q11 table |
| Corrections | none in this gate |
| Regression | none: replay identical on rerun (Q10); the engine at defaults equals the B0 snapshot |
| Evidence | `outputs/phase1/gate4/gate4_report.json`, `src/bl_p1_gate4.py`, `tests/test_phase1_gate4_outputs.py` |
| Remaining | Q2, Q5, Q9 stay below standard (data-limited, quantified below) |

## Standards versus results
| # | Standard | Result | Verdict |
|---|---|--:|:-:|
| Q1 | pooled F1 (keys) >= 0.70 | **0.739** | PASS |
| Q2 | strict F1 >= 0.55 | **0.472** | fail |
| Q3 | legacy lot-level F1 >= 0.65 | **0.688** | PASS |
| Q4 | per-cycle F1 >= 0.60 in every cycle | min **0.661**, median 0.742, none below 0.60 (NIFTY 0.742, SENSEX 0.740); worst: SENSEX 22 Oct 0.661, NIFTY 19 Oct 0.670, SENSEX 1 Oct 0.675 | PASS |
| Q5 | every class with >= 100 real orders F1 >= 0.50 | min **0.497** (wing sell) | fail (by 0.003) |
| Q6 | placebo (+15 min) F1 <= half of actual | **0.326** vs 0.739 (ratio 0.44) | PASS |
| Q7 | >= 95% of simulated scheduled straddles matched | **98.8%** (2,086 of 2,112) | PASS |
| Q8 | risk controls | 0 rejected; max net short lots CE 130 / PE 93 (limit 400); decision cap 40 enforced (children per minute peak 45, informational) | PASS |
| Q9 | median normalised book distance <= 0.35 | **0.508** (short and long lots equal on both rights in 1% of matched events) | fail |
| Q10 | reproducible; tests pass | replay identical on rerun for B0 and B1; suites pass | PASS |
| Q11 | every class > 5% unmatched has a root-cause classification | all classified (next table) | PASS |

## By class (F, 60 s) with the root-cause classification (Q11)
| Class | Real | Recall | Precision | F1 | Unmatched | Root cause (gate) |
|---|--:|--:|--:|--:|--:|---|
| body sell | 4,408 | 0.732 | 0.787 | 0.759 | 26.7% | solo/breakout trigger timing and count, tick-path data limit (2A, 2D); strike context (2B); late window frozen index (2C) |
| wing buy | 3,146 | 0.830 | 0.815 | 0.822 | 17.0% | inherited from body sells (controller quantity Confirmed) |
| body buy-back | 1,324 | 0.490 | 0.689 | 0.573 | 51.0% | 54.5% of misses upstream positions; independent trigger gap 163; no mechanism supported (3a) |
| wing sell | 600 | 0.410 | 0.631 | 0.497 | 59.0% | inherits buy-back timing (matched buy-backs a median 18 s early); which wing Partial (3b) |
| opening wings | 186 | 0.978 | 0.758 | 0.854 | 2.2% | order granularity of F reported by the spec (precision shows unmatched single lots) |
| lump | 73 | 0.274 | 0.407 | 0.328 | 72.6% | size not explained by position (3c); clock and side Confirmed |
| not modelled | 178 | 0.382 | | | 61.8% | stop module and body-stream closes are not in the engine (D1-15, G4) |

## By time of day (F1 by 30-minute block)
Strongest 09:30-11:30 (0.76-0.87); 12:00-14:30 0.69-0.76; **15:00 block 0.369** (recall 0.317, precision 0.441); 15:30 block 0.180. The late block is the weak point: the frozen index in post-auction cycles (2C), tick-driven reactive sells, and the late rule not in the engine. Sensitivity (diagnostic input convention C1): keys F1 0.746, strict 0.479, legacy lot F1 0.699 (rows below).

## Placebo, sensitivity, diagnostics
| Row | keys F1 (60 s) | strict F1 | legacy lot F1 |
|---|--:|--:|--:|
| **B1 (official baseline)** | 0.739 | 0.472 | 0.688 |
| V01 book condition (rejected candidate) | 0.745 | 0.482 | 0.698 |
| C1 rebased futures feed (diagnostic input convention only) | 0.746 | 0.479 | 0.699 |
| +15 minute placebo | 0.326 | | |
TF-E (separate, not a score): keys F1 0.645 (first decisions) against F 0.739; see `D1_TFE_COMPARISON.md`. No row above is a different "baseline"; B1 stays the baseline.

## Reading
* **What is reproduced well:** the clock-driven structure (98.8% of scheduled straddles), the wing controller quantity, order mechanics, every cycle above 0.66 on keys F1, an actual-to-placebo ratio of 0.44, and all risk controls.
* **What is not:** the reactive decisions (timing and count), buy-back trigger gap, lump size, the late block, and the portfolio state (median book distance 0.51): the state error is the **accumulated** consequence of these (the within-epoch drift in TF-E is small: median 0, mean 0.027).
* **Conditional because** Q2, Q5, Q9 are below the standards for reasons the earlier gates classified as data-limited; Q5 misses by 0.003.

## Limits
In-sample (same cycles fitted the engine); standards written knowing B1; the strict F1 is the spec's level (strike and lots exact, tolerance 60 s); module labels inferred; the report reads saved runs.
