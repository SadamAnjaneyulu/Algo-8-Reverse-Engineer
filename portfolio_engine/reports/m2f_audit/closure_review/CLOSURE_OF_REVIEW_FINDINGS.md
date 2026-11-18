# Closure of the fresh-context review findings (2026-11-16)

Review: `REVIEW.md` / `defects.json` in this directory (reviewer: a fresh-context subagent of the same model family as the authors; no Critical or High finding; every headline number re-derived from the raw CSV by the reviewer's own code was reproduced). Each finding was fixed or dispositioned before the relevant item was closed.

| ID | Severity | Finding | Disposition | Evidence |
|---|---|---|---|---|
| CR-01 | Medium | "second-end state identical under any ordering" over-broad: only inventory, cash and gross opened/closed units are invariant; realized P&L, per-module units and reversal counts are not | **FIXED**: docs narrowed with the measured counts; flag renamed `SECOND_END_INVENTORY_CASH_INVARIANT`; manifest `ordering_semantics` text extended; counterexample test (LIFO realized -65,000 vs +65,000 paise, inventory and cash equal) | `docs/ORDERING_SEMANTICS.md`; `python/pe/forensics.py`; `python/pe/scenario.py`; `tests/test_scenario.py::test_second_end_invariance_is_limited_to_inventory_and_cash_not_realized_pnl` |
| CR-02 | Low | "no cross-instrument order is observable" untested for SENSEX (ns agrees with file order for 87 % of cross-instrument adjacent pairs) | **FIXED (wording)**: weakened to "the project uses no cross-instrument order"; the 87 % observation and that no result depends on it are recorded | `docs/ORDERING_SEMANTICS.md` |
| CR-03 | Low | inclusive rule on whole seconds links pairs whose ns gap exceeds g; exclusive counts show one direction | **FIXED (documented)**: both directions and the net change (+661 / +441 / +79 / +25 / +33) stated | `docs/BASKET_GROUPING_METHODOLOGY.md` (Decision C notes) |
| CR-04 | Low | C2 membership depends on the tie-break among equal-first-second parents | **FIXED (cross-referenced)** | `docs/ORDERING_SEMANTICS.md` review notes; limitations section 7 |
| CR-05 | Low | 3 of 26 baseline parent-level flips are produced by other parents' fills | **FIXED (documented)**: caveat in the module docstring that defines the measure | `python/pe/reversals.py` |
| CR-06 | Low | price-scrambling test is blind to price read outside the ledger `px_fill` column | **FIXED (complementary test)**: static lint that the selection functions mention no price, P&L or raw-csv reader; kills the reviewer's mutant A form; the scrambling-test limit is stated in the D-15 disposition | `tests/test_decision_a.py::test_selection_code_reads_no_price_or_outcome_column`; `closure_dispositions.json` D-15 |
| CR-07 | Low | B-04 evidence cited a non-existent directory | **FIXED** | `reports/m2f_audit/closure_dispositions.json` B-04 |
| CR-08 | Low | "evidence-class labels verified stable" is vacuous (constants per method) | **FIXED (wording)**: labels stated as constants by construction; the measured stability is the numbers behind them (at most 0.3 %) | `reports/R1C_DUAL_SCENARIO_COMPARISON.md`; `closure_dispositions.json` C-01 |
| CR-I1 | Info | final report header never says closure completed | **FIXED**: closure addendum appended to the M2-F report (header unchanged by rule) | `reports/M2F_FINAL_AUDIT_REPORT.md` addendum |

Limits of the review (from the reviewer): kill claims checked only where re-executed; the reviewer is the same model family as the authors.
