# Validation and Limitations (Phase 6)

**Result:** nothing in this milestone is validated on independent data. **All 35 cycles have been inspected repeatedly** (the D0 discovery/holdout of the previous phase, the earlier TEST boundary, pooled descriptive tables, and now this lot analysis). Chronological blocks are used for *labelling*, not as holdouts. Every inferred rule remains **unvalidated**; two hypotheses were REJECTED; no rule is proposed for the engine. Evidence classes: CONFIRMED OBSERVATION · STRONGLY SUPPORTED · HYPOTHESIS · UNKNOWN · REJECTED.

## 1. Evidence status of the data
| Data | Status |
|---|---|
| 35 live cycles (23 Jun–22 Oct 2026) | **Previously inspected research data**; no untouched holdout; no newly acquired data |
| 30 complete cycles (D-1 + D0 logs) | all lot-level carried analyses; 5 cycles partial (3 no D-1, 2 no D0) |
| Earlier 2023–26 Breeze dataset | not used here (no ledger exists for it) |

## 2. Methodology followed
Hypotheses H1–H7 (Phase 3) and the replacement classification thresholds were written into the scripts before evaluation; thresholds are taken from the project's earlier literature (1.55× stop band, Clock-B minute, ₹1 salvage) or are conventional (2× excess); nothing was tuned. Splits are by cycle in chronological order (22 dev / 8 later, boundary 2026-09-23) — **never by lot or minute**. Results by block are reported side by side; **the later block is not independent** (the boundary coincides with the previous TEST set, which earlier research had already scored).

## 3. Rule-by-rule status
| Question | Status | Why |
|---|---|---|
| Entry/exit fills, prices, quantities of every lot | **CONFIRMED OBSERVATION** | ledger, exact |
| Cycle and class P&L totals | **CONFIRMED OBSERVATION** | reconciled to ₹0.000 |
| Lot ownership (which fill closes which lot) | **UNKNOWN** | no allocation id; 83 % of body shorts ambiguous |
| Deep-OTM carried lots are left to expire | **STRONGLY SUPPORTED** | 76 % settled at > 6 steps vs ≤ 1 % within 3 steps |
| Buy-backs occur in bursts (≤ 2 min after another) | HYPOTHESIS | lift 2.1–2.5, recall 0.64–0.67, both blocks |
| Price ≥ 1.55× entry raises buy-back hazard | HYPOTHESIS | lift 2.4–2.7 but precision ≤ 7 % |
| Last-hour clearance | HYPOTHESIS | lift 2.6–2.9 |
| Clock-B minute raises hazard | HYPOTHESIS | lift 1.6, recall 0.10 |
| ITM migration | HYPOTHESIS (unstable) | lift 1.4 → 2.4 |
| Decay take-profit (price ≤ 0.5× entry) | **REJECTED** | lift 0.87 / 0.69 |
| ≤ ₹1 contracts are bought back (salvage) | **REJECTED** | lift 0.11 / 0.04 (they are held) |
| Same-contract replacement | **REJECTED as general pattern** | ≤ 1.6× chance, < 1 beyond 60 s |
| Cross-right sale after a buy-back | HYPOTHESIS | 4.8× chance (0–30 s) |
| Scheduled D0 sale timing | HYPOTHESIS (not robust) | recall 0.19–0.55 across tolerances/definitions |
| Replacement wings | UNKNOWN | bounds only |

## 4. What failed validation
H2 and H6 (rejected); same-contract replacement; the stability of the STRONGLY_SUPPORTED replacement count (139 vs 256); the earlier D0 rule set (previous phase) stays failed; the legacy simulator's P&L (defect A). A one-sentence summary: **no tested rule explains the buy-backs; only timing structure and the deep-OTM expiry behaviour are supported.**

## 5. Python/C++ parity
No lot-engine, matching, opening-book, carried-lot or replacement logic exists in C++ and none was ported (no rule is validated). Parity holds for the **unchanged engine**: 180 engine tests pass and **all 400 stored diagnostic engine runs now carry `parity=True`** (they had been generated without the C++ check in the diagnostics phase, which made `test_every_stored_engine_run_has_python_cpp_parity` fail; re-run with the check, results unchanged).

## 6. Limitations
Second-resolution fills and minute-resolution market data; the within-second order is the file order; no bid/ask, depth, IV, or exchange settlement; ledger gaps (5 cycles); settlement by Yahoo close; the lot engine's role routing is an assumption supported by tags; unit lots are indivisible, so "partial close" exists only at order/contract level; the carried-lot panel uses 1-minute option bars where untraded minutes are stale; all effects are for one four-month window of one account.

## 7. Reproducibility
`run_all.sh` (this directory's parent) regenerates every output from the ledger and the pinned dataset; large raw data is not committed; `outputs/` holds derived tables (compressed).
