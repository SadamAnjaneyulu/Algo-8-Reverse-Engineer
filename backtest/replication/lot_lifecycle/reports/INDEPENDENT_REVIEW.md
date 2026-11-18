# Independent Review (Phase 8) — findings, responses, contamination record

**Process.** An adversarial reviewer (a separate model instance; its report is model output, not a user decision) re-implemented the lot accounting, the opening book, the matching and the panel features and was shown the first results. It found nine defects (D1–D9) and several minor errors. In line with the brief — *do not silently fix defects discovered after seeing evaluation results; record them, preserve the affected output, correct the implementation, label later evaluation as contaminated* — the pre-review outputs are preserved in `outputs/v1_pre_review/` (with `DO_NOT_CITE.txt`; the pre-review engine is `lots_v1.py`, the pre-review replacement script `replacement_v1.py`), the corrected code is in `src/`, and **every number in the reports is now post-review and CONTAMINATED-DEVELOPMENT** (all cycles were already inspected). The reviewer's conclusions were verified by running code, not accepted on authority.

## Findings and responses
| ID | Finding | Response | Regression test |
|---|---|---|---|
| D1 | A body Buy with no recorded short was silently opened as a *long* (primary) or treated as an unrecorded short — the ledger cannot decide. | Reclassified as an **unresolved interpretation**: parameter `excess_body_buy='long'|'unrecorded_short'`, both datasets built (33,172 / 34,110 lots), flags and report ranges. | `test_d1…` (both readings on a fixture) |
| D2 | Stop-module lots (role `stop`) were not netted: `s_`/`m_` orders opened new lots while old stop lots were open. | `ROUTE` for `s_`/`m_` includes `stop`; opens by closing-side orders are flagged `OPENED_BY_CLOSING_SIDE_ORDER`. Stop lots opened: 515 short / 154 long (was 641 / 657). | `test_d2…` |
| D3 | Expiry-day end-of-day body sells created spurious body shorts instead of closing wing longs of the same contract. | Cross-role EOD wing close (flag `CROSS_ROLE_EOD_WING_CLOSE`, 1,104 lots) — an **inference**, reported as HYPOTHESIS. | `test_d3…` |
| D4 | P&L reconciliation: (a) the ₹36.5 k difference to the earlier gross was blamed on running-average prices; (b) the identity was presented as validation although it is tautological for cash conservation. | (a) Only −₹2.5 k is in the 30 complete cycles; −₹33.7 k is one partial cycle (NIFTY 2026-06-23) and **unattributed**. (b) Identity relabelled as bookkeeping. | `test_lot_reconciliation_outputs` (existing) |
| D5 | Replacement null biased (arbitrary shifts, draws dropped when leaving the session), many-to-one pairing, threshold cliff, "STRONG count stable" claim. | `replacement.py` rewritten: circular 15-min-multiple shifts, one-to-one assignment, 200 draws, cycle-bootstrap CI, threshold grid. Headline results changed (0 strongly supported; 4.8× → 2.8×). | `test_d5…` |
| D6 | `entry_order_lots` described as order size but filled with fill size. | Both fields: `entry_order_lots` (order) and `entry_fill_lots` (fill). | `test_d6…` |
| D7 | The simulator mutated the caller's start book (state leaking between variants). | `deepcopy(start)`; all variants re-run. | `test_d7…` |
| D8 | "Fix" for defect A (close all passive lots at a stop) is itself an assumption. | `passive_at_stop='close_all'|'keep'` bounds; reports state the sign of the later-block D0 P&L depends on it. | `test_d8…` |
| D9 | Carried-lot hypothesis tests: no uncertainty, row counts misreported, threshold provenance unclear, convention-dependent counts stated as fixed. | Cycle-bootstrap CIs, j ≥ 6 variant, 158,575 analysed rows, thresholds' provenance and non-pre-registration disclosed, counts by convention (258/260/263/254 settled). | `carried_hypothesis_tests.csv` (regenerated) |
| M1 | Panel/feature timing at D0 minute 0. | Perturbation test via `panel_cycle`: changing the D0 09:15 bar leaves j = 0 unchanged and changes j = 1. | `test_d4_panel…` |
| M2 | Holding time counted overnight seconds. | Market seconds (overnight excluded). | `test_holding_seconds…` |
| M3 | "~3 point" settlement difference; "153 unrecorded in 3 cycles"; "anomalous lots matched to nothing"; "83 % ambiguity"; "carried P&L ±2.3 %"; "opposite right 4.8×"; "STRONG 139 stable". | All corrected in the reports (settlement proxy up to 89 points in 13 cycles; 161 unrecorded in 5 cycles; 89 % / 87 % ambiguity; ₹4.9 L split range; 2.8×; 0–88). | `test_settlement_proxy…` |

## Not accepted / limits of the review
* The review could not remove the central limitation: without allocation ids, lot ownership remains a range.
* The reviewer's suggested reading of the body-buy ambiguity was not adopted as a finding (D1 stays unresolved).
* Contamination: because the review followed the first results, any statistic in this milestone is development evidence only; no holdout exists.

## Test status
`python -m pytest backtest/replication/lot_lifecycle/tests`: 28 passed (12 adversarial, 6 remediation, 10 review-defect regressions); `python -m pytest backtest`: 62 passed in this run.
