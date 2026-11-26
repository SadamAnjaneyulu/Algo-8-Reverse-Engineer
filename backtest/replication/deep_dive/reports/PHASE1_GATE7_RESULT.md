# Phase 1, Gate 7: robustness and independence review. Result

*Evaluated: frozen D-1 B1, D0-C (Gate 5a + X1), integrated mode F (Gate 6). Plan and criteria fixed before scoring: `PHASE1_GATE7_PLAN.md` (the LOCO parameter fit, a pure fit, was computed before the plan was written; its values appear in R2). Code executed, results observed (`outputs/phase1/7/tests.json`). Nothing committed.*

## Headline (RESULT)
**Gate 7: CONDITIONAL.** R1-R6 all hold: the D0 result survives a true leave-one-cycle-out refit (keys F1 0.428 vs 0.422 half-split), the fitted constants do not move (identical in all 30 folds), no future bar leaks into any decision (18 of 18 perturbation tests), and agreement is timing-specific. **But no data in this repository is independent of the development of the rules**, so no independent-validation claim is possible. The strongest honest statement is: *a stable, causal, in-sample reconstruction with modest order-level agreement.*

## R1: true leave-one-cycle-out (D0-C, mode T)
LOCO pooled keys F1 (60 s) **0.428** (CI 0.391-0.462), legacy lot-level 0.424, shift placebo 0.240; half-split OOF was 0.422 / 0.414. Criterion (>= OOF - 0.03): **PASS**. LOCO is slightly *higher* than the half-split because each fold trains on 29 cycles instead of 15. (The structure of every rule was chosen with all cycles visible: LOCO tests constants, not structure.)

## R2: parameter stability (30 LOCO folds)
Stop theta 1.4, take-profit 0.1, ladder (step 0.05, gate 60 min, multi-lot), counter ratio 0.25, opening wings 20 lots: **each identical in 30 of 30 folds**. In the half-split runs two splits chose other values (ladder step 0.1, counter ratio 0.5, opening wings 13): the choices sit near flat optima, so small training sets move them. **PASS** (the criterion needs 75% modal share).

## R3: regimes (macro-mean of per-cycle keys F1; D0-C mode T OOF and D-1 B1)
| D0 subgroup | Cycles | Macro F1 | Ratio to all |
|---|---:|---:|---:|
| era = after | 19 | 0.379 | 0.98 |
| era = before | 11 | 0.397 | 1.03 |
| und = NIFTY | 13 | 0.392 | 1.02 |
| und = SENSEX | 17 | 0.381 | 0.99 |
| version = V1 | 20 | 0.395 | 1.02 |
| version = V2 | 10 | 0.367 | 0.95 |
| stop = False | 19 | 0.441 | 1.14 |
| stop = True | 11 | 0.290 | 0.75 |

| D-1 subgroup | Cycles | Macro F1 | Ratio to all |
|---|---:|---:|---:|
| era = after | 21 | 0.733 | 0.99 |
| era = before | 11 | 0.763 | 1.03 |
| und = NIFTY | 15 | 0.749 | 1.01 |
| und = SENSEX | 17 | 0.738 | 0.99 |
| version = V1 | 21 | 0.755 | 1.02 |
| version = V2 | 11 | 0.720 | 0.97 |
| stop = False | 31 | 0.743 | 1.00 |
| stop = True | 1 | 0.742 | 1.00 |

No subgroup of >= 5 cycles falls below 0.7 of the pooled value: **PASS**. **The weak regime is D0 stop cycles** (11 cycles, macro F1 0.290, ratio 0.75, close to the 0.7 line): when the real system stops early, the engine's order stream diverges. Era (pre/post auction), underlying and version are balanced. D-1 has one stop cycle only (no regime inference).

## R4: timing sensitivity (D0-C OOF events, keys F1 at 60 s after shifting simulated times)
| Shift | -120 s | -60 s | 0 | +60 s | +120 s |
|---|---:|---:|---:|---:|---:|
| F1 | 0.237 | 0.299 | 0.422 | 0.435 | 0.317 |
**PASS.** Agreement is timing-specific (falls both ways), and **a one-minute causal delay does not hurt (+60 s = 0.435, ratio 1.03)**: the engine stamps decisions at the start of the minute whose bar it reads; a live version acting on the completed bar loses no agreement. (Within the stamped minute the engine uses that minute's own high, low or close: an in-minute information convention, stated.)

## R5: causality perturbation
Every bar after minute m (m = 100, 200, 300) replaced by garbage on 4 D0 cycles and 2 D-1 cycles: events (D0) and orders (D-1) up to minute m **identical in 18 of 18 tests**: no future bar reaches any decision. **PASS.**

## R6: train/test hygiene
Train and test cycles are disjoint in OOF half 0/1, forward A, forward B and all 30 LOCO folds. D-1 B1 constants are fitted on all 32 cycles (**in-sample by construction**). **PASS.**

## R7: selection accounting (Phase 1 only; counted, not deflated)
2A solo trigger 10, 2B strike rule 10, 2C 15:00+ block 2, 2D delayed breakout sizing 4, 3A buy-back stop (K1-K6) 6, 3B/3C wings and lump 10, 5C D0 (X1, X3; +1 labelled sensitivity) 3; **about 45 ideas tested on the same cycles in Phase 1**, plus the earlier D-1/D0 research chunks (not countable). A best-of-many selection effect is therefore certain; the placebo and LOCO tests do not remove it.

## R8: independence statement
| Dataset | Independent of rule development? |
|---|---|
| 32 D-1 cycles (Jun-Oct 2026) | **No** (all rules and constants) |
| 30 D0 cycles (same expiries) | **No** (structure chosen on all; constants out-of-fold) |
| forward A / forward B splits | **No** (pseudo-forward: same cycles, structure visible) |
| post-22-Oct exports, tick/second data, decision logs | **Not available** |
**Independent validation: none exists.** Needed to close it: post-freeze expiries with order logs (or live paper trading with the frozen configuration), scored once with the frozen spec.

## Gate 7 status: **CONDITIONAL** (all robustness tests pass; independence is not achievable with existing data).

## Addendum (Phase 1 final loop, 2026-11-25)
R1, R4, R5, R6 were repeated for the final configurations (true LOCO HR 0.428 / forward 0.427; timing-specific; causality 18/18 including the D-1 engine with the stop switch ON). Independent validation: still none. `PHASE1_LOOP2_RESULT.md` section 7.7.
