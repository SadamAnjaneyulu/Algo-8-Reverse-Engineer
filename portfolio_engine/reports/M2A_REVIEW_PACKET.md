# M2-A review packet — conceptual model and schema review (no implementation yet)

## 1. Branch gate (executed)
| Check | Result |
|---|---|
| Local vs remote engineering branch | both `621e11e8…`; no new remote commits |
| TP-03 Phase 1 head | `502bfbed…` verified; TP-02 base `a5feffaf…` verified |
| Ancestry | both branches diverge from `a5feffaf` (merge-base); engineering = 1 commit, TP-03 = 5 commits |
| Overlap | **none** (engineering touches only `portfolio_engine/`; TP-03 only `tp_reconstruction/tp03/` and two `TP03_*` reports); `git merge-tree` clean |
| Safety reference | local branch `safety/eng-m1-621e11e8` at `621e11e8` |
| Reconciliation | new branch `engineering/position-lifecycle-basket-reconstruction` = engineering head + **merge commit** `afad6361` of TP-03 `502bfbed` (no rebase, no force-push, no history rewrite) |
| Regression after merge | `pe_core_tests` 15/15; `pytest portfolio_engine/tests` 41 passed; `parity.py --real-full` 126/126 identical, 8/8 invalid rejected; TP-03 tests 30 passed |
| Old artifacts | `reports/parity_report.json` was rewritten by the rerun (timings) and **restored** with `git checkout`; nothing under `tp_reconstruction/` modified |

## 2. Ground truth the M2-B implementation must reproduce (from existing TP-01 data, not M2 results)
OpeningAllocations 23,684 (23,661 open-only fills + 23 reversal fills) · ClosingPortions 17,760 (= TP-02 `exit_event_timelines` rows) · episodes 2,667 (2,563 flat, 23 reversal, 81 expired-unclosed) · parents 39,874 (23,057 opening-only, 16,791 closing-only, 26 mixed) · opened 1,414,545 / closed 1,377,065 / remaining 37,480 · open/close quantity per fill identical under FIFO, LIFO, AVG (verified) · no parent spans two dates · 520 of 1,674 contracts have openings on more than one date (carry).

## 3. Findings that change or qualify the brief
1. **The closing-batch definition is not a TP-02 output.** 10 s primary / 2, 5, 30, 60 s sensitivities and the number-block variant are registered in the **TP-03 Phase 0 config** and were never executed (TP-03 Phase 2 was not run). TP-02 used ±5 s basket and ±10 s wing windows per closing. Model C is therefore built fresh from the registered text.
2. **"Gap" is undefined in that registered text.** Proposal: first-fill to first-fill chaining (sensitivity: previous last fill to next first fill).
3. **No opening-cluster gap is registered** (searched TP-03 audit and config). Proposal: window attribution primary; gap sensitivities {2, 5, 10, 30, 60} s, fixed now, never selected.
4. A **ClosingPortion** entity is needed (closing quantity is convention-independent, its allocation is not); it is added to the brief's list.
5. M1's `events.tsv` has no order-entry minute, app key or order number; these live in a new `parents.tsv` (additive).
6. `h_` parents use a second app key in ≈ 7.8 % of fills, so order-number-block wing matching is `NOT_APPLICABLE` for those.
7. 26 parents are `MIXED` (open and close); they join Model B (opening part) and Model C (closing part) separately.

## 4. Decisions requested (nothing below is implemented until approved)
| # | Decision | Recommendation |
|---|---|---|
| D1 | Opening-cluster gap sensitivity set | {2, 5, 10, 30, 60} s, window attribution primary |
| D2 | Closing-batch gap measure | first-fill chaining primary; last-to-first as sensitivity; plus registered number-block variant |
| D3 | Add convention token to inferred IDs (`INF:KIND@CONV:…`) | yes, for uniqueness across views |
| D4 | Add `ClosingPortion`, `parents.tsv` and the v1.1 files (additive schema) | yes |
| D5 | Python/C++ boundary | core + allocation + Model A in both; Models B, C and wing/body Python-only |
| D6 | Opening-level wing↔body pairing window (W1) | same order-entry minute + right (TP-03 E6 convention), ±60 s sensitivity |
| D7 | Which two cycles for the demonstration | smallest-risk choice: one NIFTY and one SENSEX cycle with both D-1 and D0 sessions and a cycle stop; I propose to choose them by data completeness only, before any grouping output is viewed |

## 5. Not changed
Accounting semantics, M1 schemas and parity artifacts, any file under `tp_reconstruction/`, PRs #8–#12, `stage2_alpha_research/`.
