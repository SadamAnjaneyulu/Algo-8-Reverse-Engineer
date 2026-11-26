# Phase 1, Gate 2A: solo-sell trigger. Result

*2026-11-25. Plan: `PHASE1_GATE2A_PLAN.md` (with Addendum 1), written before any run. Experiments `P1-2A-0` (analytic T1-T3) and `P1-2A-V00` to `V08` (9 engine runs of 32 cycles, `outputs/phase1/2A/`). Evidence label: historical reproduction on the 32 development cycles. Baseline B1 preserved and re-verified (V00 through the modified engine reproduces B1 exactly, 9,035 identical orders). Nothing committed.*

## Gate report
| Field | Content |
|---|---|
| Gate | 2A: solo-sell trigger |
| Status | **FAIL: the preregistered correction is REJECTED** (no variant passes A1-A9). Gate 2 stays IN PROGRESS (2B, 2C, 2D open) |
| Baseline | B1 body sells: F1 0.7586 (recall 0.7325, precision 0.7866); strict F1 0.5954; 873 extra, 1,179 missing; 4,091 lots vs real 4,671; legacy lot-level F1 0.6878 |
| Latest result | best variant V01: body F1 **0.7699**, strict F1 **0.6149**, recall 0.7169, precision **0.8314**, extras **639**, missing 1,248, lots 3,789, legacy lot-level F1 **0.6978** |
| Root causes | not identified as a rule; see below |
| Corrections | none accepted. Switches `ladder_lots_mode`, `ladder_book_condition` exist in the engine, default off, tested |
| Regression | none: defaults reproduce B1; scheduled straddles 2,086 of 2,112 matched in every variant |
| Evidence | `outputs/phase1/2A/{T1_T3_analytic.json, V00..V08, evaluation.json, evaluation_table.csv}`, `src/bl_p1_2a_*.py`, `d1_strategy/test_ladder_candidates.py` |
| Remaining | 2B, 2C, 2D; the solo count and timing residual (below) |
| Next action | Gate 2B (solo strike reference) |

## Preregistered criteria, per variant (B1 values from the plan)
| ID | Change | F1 | strict F1 | recall | precision | lots | extras | A1 | A2 | A3 | A4 | A5 | A6 | A7 | A8 |
|---|---|--:|--:|--:|--:|--:|--:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| V00 | baseline | 0.7586 | 0.5954 | 0.733 | 0.787 | 4,091 | 873 | | | | | | | | |
| **V01** | book condition (H4) | **0.7699** | **0.6149** | 0.717 | **0.831** | 3,789 | **639** | fail | PASS | fail | fail | PASS | PASS | PASS | PASS |
| V02 | gate 15 min (H3) | 0.6987 | 0.5382 | 0.748 | 0.656 | 5,008 | 1,723 | fail | fail | fail | PASS | PASS | fail | fail | fail |
| V03 | gate 5 min (H3) | 0.6730 | 0.5165 | 0.751 | 0.609 | 5,420 | 2,117 | fail | fail | fail | fail | PASS | fail | fail | fail |
| V04 | steps mode (H1) | 0.7348 | 0.5710 | 0.742 | 0.728 | 4,475 | 1,217 | fail | fail | fail | PASS | PASS | PASS | fail | fail |
| V05 | steps, step 0.1 | 0.6591 | 0.4815 | 0.804 | 0.559 | 6,345 | 2,801 | fail | fail | fail | fail | PASS | fail | fail | fail |
| V06 | steps, step 0.05 | 0.5166 | 0.3632 | 0.845 | 0.372 | 10,042 | 6,305 | fail | fail | fail | fail | PASS | fail | fail | fail |
| V07 | step 0.1 (H2) | 0.7340 | 0.5442 | 0.790 | 0.686 | 5,071 | 1,594 | fail | fail | fail | PASS | PASS | fail | fail | fail |
| V08 | step 0.05 (H2) | 0.6602 | 0.4694 | 0.831 | 0.548 | 6,713 | 3,037 | fail | fail | fail | fail | PASS | fail | fail | fail |
A9 (leave-one-cycle-out over all variants): V01 is the choice in 32 of 32 folds, pooled held-out F1 0.7699 (passes A9 alone). **V01 fails A1, A3 and A4, so it is rejected under the rule "fail any criterion = rejected"; the criteria were not relaxed.** The combination V09 is empty: only V01 passed the directional check, so there is nothing to combine. Guard rejections (the 40-per-minute cap) occurred in V02, V03, V05-V08 (2 to 903 orders), another sign those variants over-fire.

## What each hypothesis now stands at (evidence)
| Hyp. | Verdict | Basis |
|---|---|---|
| H1 k lots = k rungs | **Contradicted** | T2: group size vs rungs crossed, Spearman -0.03 (p 0.50, n 541); V04 worse on every body measure and on legacy lot F1 (0.6702) |
| H2 finer ladder step | **Contradicted at the order level** | V07/V08: recall rises (0.79 / 0.83) but precision collapses (0.69 / 0.55); extras 1,594 / 3,037; legacy lot F1 0.674 / 0.612 |
| H3 shorter gate window | **Contradicted at the order level** | T3 said shorter windows cover more real solo-sell minutes (88% at 5 min vs 71% at 60), but V02/V03 add far more false orders than true ones |
| H4 book-state condition | **Partially supported** | V01 removes 302 solo orders, 228 of them false (75%, against 56% false in the baseline ladder): precision +4.5 points, extras -27%, strict F1 +0.02, legacy lot F1 +0.010 (0.6878 to 0.6978), wing buy and lump F1 up; but it also removes 74 true orders (recall -1.6 points) and the simulated lots fall further below the real total |
| H5 tick-level tracker | **Not testable**; consistent with everything above | no spot-only, order-level parameterisation of the ladder reproduces the real count and spacing |
| H6 premium-based trigger | untested | needs its own preregistration |
| H7 hidden input / reference rule | untestable | |

## Classification after Gate 2A (updates the register for D1-05)
Solo-sell **trigger: Partial.** Side and fresh-extreme dependence, and a book-state gate (H4, partially supported), are identified; **spacing, count and timing are not reproducible from one-minute bars and look tick-driven (H5): Unresolved, data-limited**, pending tick or one-second data. Per the stop rule, **no further grid search on these cycles without a new mechanism** (H6 would be a separate preregistered experiment).

## What this changes
* Nothing enters the baseline. V01 stays an archived near-miss and a documented partial finding (the strongest single piece of evidence this gate produced: a book-state condition separates real from false solo fires better than chance, not well enough to meet the preregistered bar).
* An honest reading of the solo-sell reconstruction: with minute bars the simulator cannot match the real solo sells much better than F1 about 0.76 (order level) without over-firing; the remaining gap is mostly the tick path.

## Limits
Same development cycles; ten runs counted (nine variants plus T1-T3); criteria fixed in advance (arbitrary but registered); the replay fixes an intrabar path by convention; module labels of real orders are inferred.

## Addendum (Phase 1 final loop, 2026-11-25): H6 tested and rejected
H6 (premium-triggered ladder) was tested at the decision level under `PHASE1_LOOP2_A_PLAN.md`: premium-extreme indicator F1 0.460 vs spot 0.437 (+0.023, interval lower bound -0.002): **PA1 fails**; union worse; no engine variant (stop rule). Solo trigger stays Unresolved / data-limited. See `PHASE1_LOOP2_RESULT.md` section 1.
