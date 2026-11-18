# Simulator Defect Remediation (Phase 1)

**Result:** all five defects from the D0 independent review were investigated; **A, C, D and E are fixed or audited with regression tests; B cannot be fixed from the ledger and is represented as an explicit unknown with bounds.** Historical code and outputs were preserved (the legacy `d0_sim.py` v1.1, `compare_events.py`, `build_events.py` are untouched); corrected logic lives in `lot_lifecycle/src/`. **Every re-evaluation below uses cycles that were already inspected, so all numbers are labelled CONTAMINATED-DEVELOPMENT and are not validation evidence.** Code executed: `run_remediation.py`; tests: `tests/test_remediation.py` (6), `tests/test_lots_adversarial.py` (12).

| Defect | Finding | Fix / status | Regression test (fails on legacy) |
|---|---|---|---|
| **A** passive lump/stop lots kept after a stop | **CONFIRMED OBSERVATION** (code): `d0_sim.py` closed only body and wings at a stop; the ledger shows the stop module closing lump lots. | `d0_sim_v2.py`: every passive lot (lump, stop-module, manual, body-long, wing-short) is closed at the stop (`STOP_LIQUIDATION_PASSIVE`); at the 15:14 flatten passive lots are **not** touched (the ledger shows they are salvaged at various later times: UNKNOWN). | `test_defect_a…`: SENSEX 2026-09-24: legacy gross +₹22 k, v2 −₹173 k (live −₹153 k); no passive lot remains; legacy−v2 > ₹100 k. |
| **B** replacement sales get no wings | The ledger gives a wing for ≈ 41 % of replacement-labelled sales (0.47 per lot; earlier phase) and replacement labels are themselves coincidence-prone (Replacement report). **No rule is supported.** | Not invented. `replacement_wings='none'` (default) and `'one_per_lot'` give the two bounds; effect on D0 P&L is ≤ ₹0.07 L (discovery-label) and ₹0.003 L (holdout-label), i.e. immaterial to conclusions. | `test_defect_b…` (explicit parameter, default unchanged). Status: **UNKNOWN** (kept as a documented bound). |
| **C** fixed-bin matching | **CONFIRMED**: bins `j//2`, `j//10` split events 2 s apart (unit test: 0 matches legacy vs 1 with a window). | `matching.py`: optimal one-to-one assignment (Hungarian) per (cycle, right[, strike]) with |dt| ≤ tolerance, unit-lot level, unmatched preserved; tolerances 0/30/60/120/180/300 s reported. | `test_defect_c…`: no double matching, monotone in tolerance, never above the smaller side, bin-edge case. |
| **D** 09:15 look-ahead | **CONFIRMED** in the legacy event table (1,311 orders). | `features.py::prev_bar`: at D0 minute 0 the last D-1 bar; at D-1 minute 0 NaN. The new carried-lot panel uses bar `j−1` of a D-1+D0 concatenated array (so minute 0 of D0 reads the last D-1 bar by construction). The legacy event table is **not** re-generated (it is part of the freeze); statistics from it are flagged. | `test_defect_d…`: perturbing the 09:15 bar leaves the decision unchanged; prev-bar mapping at j = 0, 1 and 374. |
| **E** start-book | Audited independently: the opening book from the **lot engine** (different code, exact per-fill prices) equals `d0_sim.start_book` v1.1 in **30/30** cycles (body shorts, wings, cash to ₹0.001) | v1.1 stands. Not independent evidence (the corrected code was validated on already-seen cycles). | `test_defect_e…` reads `outputs/opening_book_audit.csv` (30 rows). |

## Effect of the fixes on the D0 replay (variant V1, all cycles previously inspected)

| Split label | Cycles | D0 P&L increment, legacy v1.1 | **v2 (A fixed)** | Live | Stop cycles sim (v2) / live |
|---|---:|---:|---:|---:|---|
| discovery-label (< 2026-09-23) | 22 | ₹6.15 L | **₹6.65 L** | ₹5.31 L | 6 / 7 |
| holdout-label (≥ 2026-09-23) | 8 | +₹0.08 L | **−₹1.53 L** | +₹1.90 L | 4 / 4 |

The corrected simulation **loses money on the later block** where the legacy one appeared break-even — the earlier "P&L is wrong, event agreement is fine" caveat was right. D0 P&L from any rule simulator remains sensitive to fill assumptions (one-minute latency earlier moved it by ₹1.3 L) and is **not** used as evidence.

## Scheduled-sale matching sensitivity (holdout-label cycles, 405 simulated vs 542 / 682 actual lots; `scheduled_matching_sensitivity.csv`)

| Tolerance (any strike) | Actual = class SCHEDULED_SALE: precision / recall | Actual = window-only scheduled: precision / recall |
|---|---|---|
| 0 s | 0.26 / 0.20 | 0.32 / 0.19 |
| 30 s | 0.64 / 0.48 | 0.74 / 0.44 |
| 60 s | 0.68 / 0.51 | 0.78 / 0.47 |
| 120 s | 0.73 / 0.55 | 0.83 / 0.49 |
| 300 s | 0.74 / 0.55 | 0.83 / 0.49 |
| legacy 2-min bin | 0.69 / 0.52 | 0.80 / 0.47 |

The recall never exceeds ≈ 0.55 and crosses 0.50 only for one of the two actual-sale definitions and tolerance ≥ 60 s. **Verdict (HYPOTHESIS, not robust):** the scheduled-sale *timing* is reproduced; the *quantity* is not (simulated lots 405 vs actual 542–682). The earlier "fail" and the reviewer's "pass" are both convention artefacts.

## Not fixed (documented)
The legacy event table's minute-0 features and REPLACEMENT_SALE labels stay as published; new analysis does not use them. Replacement wings remain UNKNOWN. There is **no C++ implementation** of any of this logic; parity applies only to the unchanged engine (see `VALIDATION_AND_LIMITATIONS.md`).
