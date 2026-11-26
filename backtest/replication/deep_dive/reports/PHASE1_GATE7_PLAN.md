# Phase 1, Gate 7: robustness and independence review. Preregistration

*Written 2026-11-25 **before** any Gate 7 computation was scored (the true leave-one-cycle-out refit of the D0 fitted parts, `outputs/phase1/7/loco_params.pkl`, was computed first because it is a pure fit with no scoring; its parameter values were seen before this plan was written and are listed in the result). Evaluated objects: frozen D-1 B1; D0-C (Gate 5a + X1); integrated mode F (Gate 6). Existing data only. Evidence label: historical reproduction. Nothing committed.*

## 1. Aim
Decide what the evidence supports about robustness, and state plainly what is **not** independent. No new rule, no re-tuning, no change to any component.

## 2. Tests and criteria (fixed now)
| # | Test | Criterion |
|---|---|---|
| R1 | **True leave-one-cycle-out for D0:** the fitted parts (`fit`) are refit on the other 29 D0 cycles for each held-out cycle; D0-C is run on the held-out cycle (mode T, X1 on, `events`); pooled keys F1 (60 s) | LOCO pooled F1 >= half-split OOF (0.4217) - 0.03 |
| R2 | **Parameter stability across the 30 LOCO folds** (stop theta, take-profit, ladder step/gate/multiplier, counter ratio r, opening wings ow) | each parameter takes its modal value (ow: within +/-2 of the median) in >= 75% of folds |
| R3 | **Regimes:** keys F1 by era (pre/post auction), underlying, D-1 version (V1/V2), cycles with/without a real stop (OOF, D0-C, mode T; and D-1 B1) | no subgroup with >= 5 cycles below 0.7 x the pooled F1 (otherwise reported as regime-dependent) |
| R4 | **Timing sensitivity:** shift every simulated D0 order by -120, -60, +60, +120 s and rescore | F1 at +60 s (the causal one-minute-delayed variant) >= 0.80 x unshifted; F1 at +/-120 s below the unshifted value (the agreement is timing-specific, not a bag-of-orders artefact) |
| R5 | **Causality perturbation (D0 engine):** replace every bar after minute m (m = 100, 200, 300) by garbage on 4 cycles; the events with j <= m must be identical | all identical (0 differences) |
| R6 | **Train/test hygiene:** in every stored split (OOF, forward A, forward B) and in LOCO, the test cycles are disjoint from the training cycles; D-1 B1 constants documented as fitted on all 32 cycles | disjoint in all splits; D-1 flagged in-sample |
| R7 | **Selection accounting:** number of variants/rules tested per gate (from the registers), reported; no deflation claimed | report |
| R8 | **Independence statement:** list every dataset and whether it is independent of the fitting | report; **independent validation: none exists** |
Verdict rule: Gate 7 can be at most **CONDITIONAL**, because no cycle is independent of the development of the rules (stated in advance). It is CONDITIONAL if R1-R6 hold; FAIL if R5 or R6 fails (leakage), or R1 fails by more than 0.06; otherwise CONDITIONAL with the failing tests named.

## 3. Limits stated in advance
All 32 cycles are development cycles for D-1; D0 fitted constants are out-of-fold but the structure and many rules were chosen looking at all cycles; LOCO folds share structure decided with the held-out cycle visible; placebo and shift tests cannot detect overfitting of structure; the three D0 cycles without D-1 data are outside.
