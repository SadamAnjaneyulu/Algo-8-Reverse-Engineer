# Validation and Limitations (Phase 6)

**Result:** nothing in this milestone is validated on independent data. **All 35 cycles have been inspected repeatedly** (the D0 discovery/holdout of the previous phase, the earlier TEST boundary, pooled descriptive tables, this lot analysis and an independent review that was shown results). Chronological blocks are *labels*, not holdouts. After the independent review, code defects found **after seeing evaluation results** were fixed, the affected pre-review outputs were preserved (`outputs/v1_pre_review/`) and all re-evaluations are **CONTAMINATED-DEVELOPMENT**. Two hypotheses fail (H2, H6); no rule is proposed for the engine. Evidence classes: CONFIRMED OBSERVATION · STRONGLY SUPPORTED · HYPOTHESIS · UNKNOWN · REJECTED.

## 1. Evidence status of the data
| Data | Status |
|---|---|
| 35 live cycles (23 Jun–22 Oct 2026) | **Previously inspected research data**; no untouched holdout; no newly acquired data |
| 30 complete cycles (D-1 + D0 logs) | all lot-level carried analyses; 5 cycles partial (3 no D-1, 2 no D0) |
| Earlier 2023–26 Breeze dataset | not used here (no ledger exists for it) |

## 2. Methodology followed — and what was not pre-registered
Hypotheses H1–H7 and replacement thresholds were written into scripts before the *reported* runs, but **the files were first committed after evaluation, so no pre-registration can be demonstrated**. H1, H3, H6 thresholds come from earlier project literature; H2, H4, H5, H7 and the replacement excess/delay thresholds are author-chosen round numbers; none were tuned, but sensitivity grids are reported where a count flips (`replacement_threshold_grid.csv`). Splits are by cycle in chronological order (22 dev / 8 later, boundary 2026-09-23) — **never by lot or minute**. Bootstrap CIs resample cycles. No multiplicity correction was applied (7 hypotheses × variants × blocks; 32 replacement cells).

## 3. Rule-by-rule status
| Question | Status | Why |
|---|---|---|
| Entry fills, prices, quantities of every lot | **CONFIRMED OBSERVATION** | ledger, exact |
| Cycle and class P&L totals | **CONFIRMED OBSERVATION** | reconciled to ₹0.000 (cash conservation only) |
| Lot ownership (which fill closes which lot) | **UNKNOWN** | no allocation id; 89 % of body shorts ambiguous (30 cycles) |
| Reading of a body buy with no recorded short | **UNKNOWN** (D1) | closes an unrecorded short *or* opens a long; both implemented |
| Expiry-day EOD body sells close wing longs | HYPOTHESIS | routing inferred from tags/timing (1,104 lots) |
| Deep-OTM carried lots are left to expire | **STRONGLY SUPPORTED** | 76 % settled at > 6 steps vs ≤ 1 % within 3 steps (FIFO set; ≈ same under other conventions) |
| Buy-backs occur in bursts (≤ 2 min after another) | HYPOTHESIS | lift 2.1–2.5, recall 0.64–0.67, both blocks |
| Price ≥ 1.55× cheapest entry raises buy-back hazard | HYPOTHESIS | lift 2.4–2.7 [CI 1.6–3.9] but precision ≤ 7 % |
| Last-hour clearance | HYPOTHESIS | lift 2.6–2.9 |
| Clock-B minute raises hazard | HYPOTHESIS | lift 1.6, recall 0.10 |
| ITM migration | HYPOTHESIS (unstable) | lift 1.4 → 2.4 |
| Decay take-profit (price ≤ 0.5× entry) | **REJECTED** as trigger | lift 0.87 / 0.69 (< 1 in both blocks) |
| ≤ ₹1 contracts are bought back (salvage) | **REJECTED** | lift 0.11 / 0.04 (they are held) |
| Same-contract replacement | not supported as a general pattern | 1.9× at 0–30 s only; headline same-right ratio 1.25 [0.91, 1.56] |
| Cross-right sale after a buy-back | HYPOTHESIS | 2.8× at 0–30 s unscheduled (exploratory) |
| Scheduled D0 sale timing | HYPOTHESIS (not robust) | recall 0.19–0.55 across tolerances/definitions |
| Replacement wings | UNKNOWN | bounds only |
| Stop liquidates all passive lots | UNKNOWN (assumption, defect A) | two bounds; sign of later-block D0 P&L depends on it |

## 4. What failed validation
H2 and H6; same-contract replacement as a general pattern; the first-draft replacement counts and the 4.8× cross-right ratio (biased null); the first-draft ambiguity (83 %), carried-P&L range (±2.3 %), anomalous-lot description and ₹36.5 k "price" attribution (all corrected here); the earlier D0 rule set (previous phase) stays failed; the legacy simulator's P&L (defect A). Summary: **no tested rule explains the buy-backs; only timing structure and the deep-OTM expiry behaviour are supported.**

## 5. Python/C++ parity
No lot-engine, matching, opening-book, carried-lot or replacement logic exists in C++ and none was ported (no rule is validated). Parity holds for the **unchanged engine**: all stored diagnostic engine runs carry `parity=True` (400 runs had been generated without the C++ check, which made the existing parity test fail; re-run with the check, results unchanged) and the existing backtest test suite passes.

## 6. Limitations
Second-resolution fills and minute-resolution market data; the within-second order is the file order; no bid/ask, depth, IV or exchange settlement; ledger gaps (5 cycles); settlement by Yahoo close (up to 89 points from the 15:29 spot bar in 13 early cycles); the lot engine's role routing and EOD cross-role closes are assumptions supported by tags and timing; unit lots are indivisible, so "partial close" exists only at order/contract level; the panel omits buy-backs of contracts with no recorded inventory (237 of 3,991 buy-back contract-minutes, 43 % of those in minutes 0–5); untraded minutes in 1-minute option bars are stale; all effects are for one four-month window of one account.

## 7. Reproducibility
`run_all.sh` regenerates every output from the ledger and the pinned dataset; large raw data is not committed; `outputs/` holds derived tables (compressed). Tests: `python -m pytest backtest/replication/lot_lifecycle/tests`.
