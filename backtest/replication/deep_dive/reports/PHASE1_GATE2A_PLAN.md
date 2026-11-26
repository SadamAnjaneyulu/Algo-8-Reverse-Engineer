# Phase 1, Gate 2A: solo-sell trigger. Preregistration

*Written 2026-11-25 **before** any Gate 2A test or candidate run. Experiment IDs `P1-2A-*`. Baseline B1 = accepted `one_lot_v2` F run (`outputs/scoring/d1_F_v2_onelot`); B0 = original `freeze_v1` run, kept. All candidate runs go to new directories under `outputs/phase1/2A/`. Nothing is committed. Evidence: historical reproduction on the 32 development cycles (no independent data exists).*

## 1. Problem
Body sells: of 4,408 real orders, **1,179 have no simulated sell of the same type within 60 s** (M1 727, M4 305, M3 123, M2 24) and **873 simulated body sells are extra** (730 are solo-ladder; X4 359 with no real sell within 300 s). Inferred module of the misses: solo 675, pair 486, scheduled clock 18. Matched ladder-solo orders have the exact strike only 25.6% of the time (that is 2B). Real body sells total 4,671 lots; the simulator's 4,091.

## 2. Evidence already in the repository (not re-run)
* Solo lots are **dripped over about 5 s** (median gap 0.5 s); the count looks set by the tick path (`D1_LOTS.md`). Depth-based sizing was tested and **rejected out-of-fold** (`D1_LOTS.md`); "one lot per 0.2-step rung" rejected (rho 0.06). **Not reopened here.**
* Spot-only machines plateau at decision-level F1 about 0.49 (`BODY_SOLO_DECODE.md`); fresh-extreme windows of 5-60 minutes all help ("no sharp N"); the register says solo sells fire while **the own side is in profit and the other side losing** (book ratio AUC 0.26 / 0.75) **but the engine has no such condition**.
* New evidence (body-sell ledger): the engine's "new 60-minute extreme" holds at only **8%** of unmatched real solo sells; 27.8% of real body sells share a second with another same-type sell.
* A correction of my own earlier statement: "consecutive real sells are 0.15 of the engine's trigger apart" **mixes same-second pairs (spacing 0)** with distinct-second pairs. T1 below separates them.

## 3. Competing hypotheses (all kept until tested)
| ID | Hypothesis | Testable here? |
|---|---|---|
| H1 | Same spot ladder; when a move crosses k rungs the system sends **k single-lot orders** (lots = steps crossed, as decoded for D0) | partly (variant) |
| H2 | The ladder is **finer** than 0.2 strike steps (D0 uses 0.05) | yes (variant) |
| H3 | Fresh-extreme **gate window** shorter than 60 minutes (5-30) | yes (variant, T3) |
| H4 | A **book-state condition** (own side in profit, other side losing) gates the ladder; its absence causes the extras (X4) | yes (variant) |
| H5 | A **tick-level tracker** sells one lot per new extreme print inside the minute; the count and timing are set by the tick path | **no** (needs ticks); the finer-step variants emulate it only crudely |
| H6 | The trigger variable is the **option premium**, not spot | not in this experiment (separate preregistration if H1-H4 fail) |
| H7 | Hidden or discretionary input; reference-reset rule different from the engine's | not testable |

## 4. Analytical tests on the existing ledger (run first; no engine change)
* **T1 (H1 vs H2):** for consecutive same-type real solo-labelled sells in **different seconds** within 60 s, the distribution of |spot change| / (0.2 strike steps), using the minute-close spot (convention-free) and the replay spot (intrabar convention, labelled). H2 predicts a median well below 1; H1 predicts about 1 or above.
* **T2 (H1):** for same-second groups of size k >= 2, the relation between k and the number of 0.2-step rungs crossed since the previous group (Spearman). H1 predicts a clearly positive relation.
* **T3 (H3):** for minutes containing a real solo sell, the share in which the minute's low (CE) or high (PE) makes a new N-minute extreme, N = 5, 15, 30, 60, against the base rate over all minutes of the same cycles.
Their purpose is to prune the variants below; a variant whose hypothesis is clearly contradicted is still run once (to keep the record complete) but cannot enter a combination.

## 5. Candidate variants (enumerated now; counted for selection bias: **9 single-factor variants plus at most 1 combination = 10**)
Switches are added to `D1Config` with defaults equal to the baseline (verified by test against the B0 snapshot). Everything else is unchanged.
| ID | Change | Hypothesis |
|---|---|---|
| V01 | book condition on (own-side premium ratio <= 1 if the side has lots; other side >= 1 if it has lots; no lots, no constraint; no fitted constant) | H4 |
| V02 / V03 | gate window 15 / 5 minutes | H3 |
| V04 | lots mode `steps` (k single-lot orders at the same second, k = rungs crossed, step 0.2) | H1 |
| V05 / V06 | `steps` with step 0.1 / 0.05 | H1 + H2 |
| V07 / V08 | one lot per trigger with step 0.1 / 0.05 | H2 |
| V09 | combination of the single-factor variants that each pass the directional check (body-sell F1 keys +0.005 with A5-A7 intact), tested **once** | joint |
Constants (step, gate window) are selected **leave-one-cycle-out**: for each held-out cycle, the variant with the best pooled body-sell F1 (keys, 60 s) on the other 31 cycles is evaluated on the held-out cycle.

## 6. Affected population and expected behaviour
Population: all D-1 solo orders (real solo-labelled 1,140; simulated ladder 1,292) in the 32 cycles. Expected if a hypothesis is right: M1 supply misses and X4/X1 extras fall together; simulated body-sell lots move toward 4,671; the scheduled straddles and breakout orders are unchanged.

## 7. Acceptance criteria (all must hold; fixed now; B1 values from `bl_p1_eval.py`)
B1 body sells: F1 (keys, 60 s) **0.7586** (recall 0.7325, precision 0.7866); strict F1 (strike and lots exact, 60 s) **0.5954**; simulated lots 4,091 vs real 4,671; extras 873; scheduled 2,086 of 2,112 matched, exact-second share 0.669; median normalised book L1 at matched events 0.508; class F1: wing buy 0.822, wing sell 0.497, buy-back 0.573, opening wings 0.854, lump 0.328.
| # | Criterion |
|---|---|
| A1 | body-sell F1 (keys, 60 s) >= B1 + 0.02 |
| A2 | body-sell **strict** F1 >= B1 + 0.01 (no acceptance on a permissive timing score alone) |
| A3 | recall >= B1 + 0.02 **and** precision >= B1 - 0.01 |
| A4 | simulated body-sell lots closer to the real 4,671 than B1's 4,091 |
| A5 | scheduled straddles: matched >= 2,076 and exact-second share >= 0.659 (no material regression) |
| A6 | each other class F1 >= B1 - 0.02 |
| A7 | median normalised book L1 at matched events <= B1 + 0.02 |
| A8 | body-sell F1 improves in at least 20 of 32 cycles |
| A9 | leave-one-cycle-out: the selected constants agree in at least 80% of folds **and** the pooled held-out body-sell F1 >= B1 + 0.01 |
A candidate that fails any criterion is **rejected and archived**; criteria are not relaxed after the results. Rejected variants stay in the record.

## 8. Regression tests (before any run)
(1) The live engine at default configuration replays identically to the B0 snapshot (`tests/test_phase1_baseline.py`). (2) Unit tests for each new switch: default off changes nothing; `steps` emits k single-lot orders at one second with one decision id and the same ladder-reference advance; the book condition permits and blocks exactly as defined. (3) Full 32-cycle replay of every variant; scorer, legacy bridge and class tables as for B1.

## 9. Stop rule
If no variant or combination passes A1-A9, Gate 2A's solo-trigger correction is **rejected**; the residual is classified: trigger spacing and count **Partial; count and timing data-limited (tick-level tracker, H5) and Unresolved**; no further grid search on these cycles without new evidence (a mechanism that is not a re-parameterisation, for example H6 as a separately preregistered experiment). If a variant passes, it is frozen as a candidate (not yet baseline), then the full regression and the other gates apply.

## 10. Limits stated in advance
Same development cycles throughout (historical reproduction, in-sample); the minute-bar replay fixes an intrabar path by convention; solo counts depend on a tick path that the data do not contain; module labels of real orders are inferred; ten variants on the same data raise selection risk, counted here.

## Addendum 1 (after T1-T3 and the switch implementation; before any variant run)
* **T1-T3 results (`outputs/phase1/2A/T1_T3_analytic.json`).** T1: distinct-second consecutive solo sells within 60 s (n = 353) are a median 0.12 of the trigger apart on the replay path (intrabar convention), but the 86 pairs in different minutes are a median 1.20 triggers apart on completed-minute closes; **inconclusive** for H1 versus H2 (within a minute the spot path between two sells is not in the data). **T2: Spearman between same-second group size and rungs crossed since the previous group = -0.03 (p = 0.50, n = 541): H1 (k lots = k rungs) is contradicted**; V04-V06 are therefore run once for the record and **cannot enter the combination V09**. T3: the share of real solo-sell minutes that contain a new N-minute extreme is 87.6% (N=5; base rate 25%), 83.0% (15; 14%), 78.4% (30; 9.8%), 71.4% (60; 6.8%): the engine's 60-minute gate excludes 29% of the minutes in which the real system sold; shorter windows cover more of them at lower lift. H3 and H4 are untouched by T1-T3; H2 survives (V07-V08).
* **Definition fixed before running (V01):** the book condition is evaluated at the moment the ladder would fire, using the current premium; a **blocked trigger does not advance the ladder reference** (it stays armed). The alternative (advance anyway) is not run.
* Switches added to `D1Config` (`ladder_lots_mode`, `ladder_book_condition`; defaults baseline) with tests in `d1_strategy/test_ladder_candidates.py` (5), mutation-checked.
