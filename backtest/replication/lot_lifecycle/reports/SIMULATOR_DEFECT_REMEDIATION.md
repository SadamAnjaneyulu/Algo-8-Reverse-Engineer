# Simulator Defect Remediation (Phase 1)

**Result:** the five defects from the D0 independent review were investigated. **C and D are fixed (new code) with regression tests; E is audited (not independent evidence); A is handled as an explicit ASSUMPTION with two bounds, not as a settled fix; B cannot be fixed from the ledger and is a bounded unknown.** Historical code and outputs are preserved (legacy `d0_sim.py` v1.1, `compare_events.py`, `build_events.py` untouched); corrected logic lives in `lot_lifecycle/src/`. **Every re-evaluation below uses cycles that were already inspected, so all numbers are CONTAMINATED-DEVELOPMENT and are not validation evidence.** After the independent review the evaluation was **re-run** (v1 outputs preserved in `outputs/v1_pre_review/`); the review-driven changes were made after seeing evaluation results and are recorded in `INDEPENDENT_REVIEW.md`. Code executed: `run_remediation.py`; tests: `tests/test_remediation.py` (6), `tests/test_review_defects.py` (10), `tests/test_lots_adversarial.py` (12).

| Defect | Finding | Fix / status | Regression test (fails on legacy) |
|---|---|---|---|
| **A** passive lump/stop lots kept after a stop | **CONFIRMED** (code): `d0_sim.py` closed only body and wings at a stop; the ledger shows the stop module closing lump lots. | `d0_sim_v2.py`: `passive_at_stop='close_all'` closes every passive lot at the stop (`STOP_LIQUIDATION_PASSIVE`) — **an assumption** (the ledger shows the stop module closing some, not that it closes all, passive lots); `'keep'` is the other bound. At the 15:14 flatten passive lots are not touched. | `test_defect_a…` (SENSEX 2026-09-24: legacy +₹22 k vs v2 −₹173 k); `test_d8…` (both bounds). |
| **B** replacement sales get no wings | The ledger gives a wing for ≈ 41 % of replacement-labelled sales; replacement labels are themselves coincidence-prone. **No rule is supported.** | `replacement_wings='none'` (default) and `'one_per_lot'` bound it; effect ≤ ₹0.07 L (discovery-label) and ≈ ₹0.003 L (holdout-label). **UNKNOWN.** | `test_defect_b…` |
| **C** fixed-bin matching | **CONFIRMED**: bins `j//2`, `j//10` split events 2 s apart. | `matching.py`: optimal one-to-one assignment per (cycle, right[, strike]) with |dt| ≤ tolerance, unit-lot level, integer-lot and NaN-strike assertions; tolerances 0–300 s reported. | `test_defect_c…` |
| **D** 09:15 look-ahead | **CONFIRMED** in the legacy event table (1,311 orders). | `features.py::prev_bar` and the carried-lot panel (`panel.py::panel_cycle`, bar `j−1`; D0 minute 0 reads the last D-1 bar). The legacy event table is **not** regenerated (it is part of the freeze). | `test_defect_d…` (unit) and `test_d4…` (**perturbing the D0 09:15 bar leaves the panel at j = 0 unchanged; the same perturbation changes j = 1**, so the test is not vacuous). |
| **E** start-book | The opening book from the lot engine (different code, exact per-fill prices) vs `d0_sim.start_book` v1.1: **30/30 equal** after the engine changes (`audit_opening_book.py`, rerun). Review noted the legacy start book carries phantom longs from excess body buys; the lot-engine book is built from the primary reading. | v1.1 stands; not independent evidence. | `test_defect_e…`; `test_d7…` (the simulator no longer mutates the start book — `deepcopy`). |

## Effect on the D0 replay (all cycles previously inspected; sum of D0 increments)

| Variant (30 cycles) | discovery-label (22) | holdout-label (8) | Stop cycles (discovery / holdout) |
|---|---:|---:|---|
| Live (ledger) | ₹5.31 L | +₹1.90 L | 7 / 4 |
| V0 (no price stop) | ₹15.38 L | −₹4.75 L | 7 / 6 |
| V1, passive lots closed at stop (assumption) | ₹6.65 L | −₹1.53 L | 6 / 4 |
| V1, passive lots kept (other bound) | ₹6.15 L | +₹0.08 L | 6 / 4 |
| V1 + one replacement wing per lot, passive closed / kept | ₹6.58 L / ₹6.08 L | −₹1.53 L / +₹0.08 L | 6 / 4 |

The sign of the later block depends on the passive-lot assumption (−₹1.53 L vs +₹0.08 L), almost entirely from **one cycle, SENSEX 2026-09-24 (−₹1.95 L swing)**; the other nine affected cycles move by ≤ ₹22 k each. The corrected simulation is therefore **not** evidence that the legacy replay was "break-even"; it also does not reproduce live (+₹1.90 L) under either bound. D0 P&L from any rule simulator stays sensitive to fill assumptions and is not used as evidence.

## Scheduled-sale matching sensitivity (holdout-label cycles, 405 simulated vs 542 / 682 actual lots; `scheduled_matching_sensitivity.csv`)

| Tolerance (any strike) | Actual = class SCHEDULED_SALE: precision / recall | Actual = window-only scheduled: precision / recall |
|---|---|---|
| 0 s | 0.26 / 0.20 | 0.32 / 0.19 |
| 30 s | 0.64 / 0.48 | 0.74 / 0.44 |
| 60 s | 0.68 / 0.51 | 0.78 / 0.47 |
| 120 s | 0.73 / 0.55 | 0.83 / 0.49 |
| 300 s | 0.74 / 0.55 | 0.83 / 0.49 |
| legacy 2-min bin | 0.69 / 0.52 | 0.80 / 0.47 |

Recall never exceeds ≈ 0.55. **Verdict (HYPOTHESIS, not robust):** scheduled-sale *timing* is partly reproduced; the *quantity* is not (405 simulated vs 542–682 actual lots). The earlier "fail" and the reviewer's "pass" are both convention artefacts.

## Not fixed (documented)
Legacy event-table minute-0 features and REPLACEMENT_SALE labels stay as published; new analysis does not use them. Replacement wings remain UNKNOWN. There is **no C++ implementation** of any of this logic (see `VALIDATION_AND_LIMITATIONS.md`).
