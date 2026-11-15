# R1 implementation report — intra-second fill-order convention

**Scope.** R1 only. No Medium/Low defect work and no M3 was started. Evidence tables: `reports/R1_TIE_ORDER_CONVENTION.md`. Every number below comes from committed result files or from test runs in this session.

## RESULT

* **Implemented and disclosed.** `SOURCE_ROW_ORDER_CONVENTION` is the primary convention; five sensitivity-only policies exist; the convention is stamped in the four delivered manifests; the delivered historical outputs are unchanged.
* **The evidence changed after the independent review, and your approval was given on a document that said the opposite.** NIFTY trade ids are *not* non-monotone (that claim was an artefact of pooling across IST days; withdrawn). Per instrument and IST day, NIFTY trade ids have 0 inversions in 18,305 cross-second comparisons and SENSEX nanosecond ids 0 in 19,811. File order contradicts them inside 172 same-instrument-second groups (151 NIFTY, 21 SENSEX). In only two NIFTY same-side groups does that change an opening/closing allocation.
* **One owner decision is re-presented (section 9 below).** Nothing was changed to resolve it.

## 1. What was implemented

| Item | State |
|---|---|
| Primary convention `SOURCE_ROW_ORDER_CONVENTION` (engine token `src`, alias `source_row`) | implemented; `verified_intra_second_chronology = false` in metadata |
| Sensitivity-only policies `sells_first`, `buys_first` (Python and C++), `trade_id`, `order_no`, `sensex_trade_id_time` (Python only; the CLI refuses them with `--engine cpp`) | implemented; policy-labelled keys (`Fill.tie_key = (policy, ...)`), a key of one policy cannot replay under another |
| `sensex_trade_id_time` | validated as a SENSEX-only sensitivity policy (epoch = round-half-up(ns/1e9) for 21,516 of 21,517 fills; exceptional row 8079 falls back to the epoch); **not** NIFTY, **not** the primary |
| Convention id on `LineageSet`, run manifests, four delivered manifests | stamped (`tie_order_convention`); builders assert `require_primary(ls.tie, ...)` |
| Six populations reported separately | production pipeline over the full ledger, equal to the independent references |

## 2. Updated dispositions of D-A01, B-01, C-01

All three: **REMEDIATED BY POLICY AND DISCLOSURE; primary-convention choice re-presented to the owner.** Not closed.

| Defect | Disposition text (current) |
|---|---|
| D-A01 | Convention approved, sensitivities published, metadata stamped, six populations separated; evidence partly contradicts the primary convention (sec. 9); the ambiguity cannot be removed from whole-second source data. Pending your decision and the final M2 gate. |
| B-01 | Closing-batch membership changes by 1-2 batches at every threshold (0 for `sensex_trade_id_time`); C1 = C2. Cause is the replay tie order, distinct from the approved parent-ordering tie-break. |
| C-01 | Items only in one: 2 / 4 / 2 / 2 / 0 (sells_first / buys_first / trade_id / order_no / sensex); W1 links changed 1 / 1 / 6 / 6 / 0; no evidence class changed. |

Three earlier dispositions were also corrected as overstated (C-02, D-A08, E-D03: now OPEN, work reserved for the remediation phase).

## 3. Files and commits changed

14 R1 commits on `claude/friendly-galileo-r3zezw` (`58437ea4` baseline … `a44edfe4` latest). Categories (the exact affected-file plan, presented before the metadata was applied, is `reports/m2f_audit/r1/affected_files_plan.md`):

* **Code:** `python/pe/tie_policy.py` (new), `schema.py`, `replay.py`, `lineage_set.py`, `provenance.py`, `cli.py`, `generators/historical.py`.
* **Tests:** `tests/test_tie_order_policy.py`, `tests/test_tie_order_metadata.py` (new).
* **Tools:** `r1_tie_sensitivity.py`, `r1_stamp_convention.py`, `r1_report.py`, `r1_addenda.py`; guards added to `m2c_closing_batches.py`, `m2d_wing_body.py`, `m2e_build.py`.
* **Docs (appended addenda, earlier text unchanged):** M2-B, M2-B reconciliation, M2-C, M2-D, M2-F reports, lineage rules, evidence registry (R1 entry corrected), implementation plan; new `R1_TIE_ORDER_CONVENTION.md` and this report.
* **Audit artefacts:** `reports/m2f_audit/r1/` and `r1_review/`; `dispositions.json`, `consolidated.json`, `M2F_DEFECT_REGISTER.md` regenerated (97 claims, 49 defects unchanged in count).
* **Data files changed:** four manifests only (one key appended).

## 4. Full test results (executed this session)

| Suite | Result |
|---|---|
| Python, full | **316 passed** (`pytest tests`, 455 s) |
| Tie-order policy and metadata tests, including 5 slow real-ledger tests | 38 passed (217 s) |
| C++ (`ctest`) | 100 % passed |

Before R1 the suite had 278 tests. The new test comparing the production sensitivity JSON with the independent references reads two committed JSON files; it does not re-run either pipeline (the slow real-ledger tests do).

## 5. Mutation results

Kill = an assertion failure only (not an import or collection error), checked on a scratch mirror of the repository.

| Harness | Mutants | Killed | Survived |
|---|---:|---:|---:|
| Policy and engine (`mutation_harness_R1.py`) | 29 | 29 | 0 |
| Metadata and preservation (`mutation_harness_R1_metadata.py`) | 12 | 12 | 0 |

Both include an unmutated baseline control (passes). No test is described as mutant-killing unless the mutant was executed and failed. The reviewer's own harness found 11 of 18 mutants surviving the first test set; the tests added in `46c54985` target each of those, and the results above are after that fix.

## 6. Independent review (fresh-context reviewer, own implementation from the raw CSV)

| Id | Sev. | Finding | Disposition |
|---|---|---|---|
| R1R-01 | High | "NIFTY ids not time-monotone" rests on a pooled-across-days metric | **FIXED**: claim withdrawn; I independently confirmed 0/18,305 |
| R1R-02 | Med | Primary convention contradicted by time-consistent ids in 172 groups; report presented the evidence as neutral | **FIXED** in the document, registry, amendments; decision re-presented |
| R1R-03 | Med | "114 parents non-decreasing" vacuous | **FIXED**: replaced by per-contract monotonicity |
| R1R-04 | Med | "No group shares a parent" false (4 of 21) | **FIXED**, numbers now generated from result files |
| R1R-05 | Med | SENSEX policy "changes nothing" omits lot attribution | **FIXED**: Population 6 added; lot-sequence counts equal the reviewer's exactly (FIFO 666 / 598 / 84, LIFO 662 / 593 / 80); the lot-set count is also shown because the two definitions differ |
| R1R-06 | Med | Episode counts by ordinal id only | **FIXED**: content-based column added (buys_first 12 by id, 7 by content) |
| R1R-07 | Med | Row 8079: eight other time columns side with the id time | **DISCLOSED, UNRESOLVED**: truth UNKNOWN; policy uses the epoch. A variant trusting the id time was not run (not requested) |
| R1R-08 | Low | `tie_key` carried no policy label | **FIXED** |
| R1R-09 | Low | Alias handling inconsistent; CLI passed unnormalised token to C++ | **FIXED** |
| R1R-10 | Med | 11 of 18 mutants survived; one tautological test | **FIXED**; 29/29 and 12/12 killed |
| R1R-11 | Low | Preservation test covered 399 of 666 baseline files | **FIXED**: inverse rule (every baseline file not allowed to change must be byte-identical) |
| R1R-12 | Low | Sensitivity JSON `generated_at_head` predates code | **PARTLY**: regenerated; it records `46c54985`, but the tool was edited in the working tree before the run and committed afterwards in `a44edfe4` |
| R1R-13 | Low | Over-claiming wording | **FIXED** (also "stop fill" removed: whether the interleaved fill is a stop is not established) |
| R1R-14 | Low | Reviewer's harness briefly modified two files through a symlink | **DISCLOSED**; files restored; I re-hashed all 666 baseline files |

**Is the SENSEX timestamp evidence strong enough?** Strong enough to justify a sensitivity-only policy: the id time is consistent with the epoch (rounded copy), per-contract-per-day monotone (0/19,811), and the suffix is monotone in it (0/20,157). It is **not** strong enough to call it execution chronology: the clock is unidentified, and one fill (row 8079) is inconsistent by 56.6 s. This second-hand review judgement is mine as well as the reviewer's; no external documentation of the fields was available.

## 7. Preservation of primary historical outputs

* Raw CSV sha256 `86e65ab6…f528` unchanged. 666 baseline files hashed at `562d7eb6`.
* **26 of 666 differ, all expected:** 4 manifests (below) and 22 code/test/tool/audit/Markdown files. No dataset (`.tsv.gz`), figure, summary JSON, CSV, fixture or `tp_reconstruction` file differs (verified by the inverse-rule test and by an independent script this session).
* Manifest hashes, before → after (first 12 hex): `m2c_data` 2fc06d9f29a8 → ad4a03549bda; `m2d_data` 01b3f8cdb99f → db21ef171933; `m2e_data/NIFTY_2026-06-30` 525076da23a5 → 9bd3a8590bba; `m2e_data/SENSEX_2026-07-16` 03224fd0e479 → b03f715a946b. Removing the new key reproduces the baseline bytes exactly (tested).
* No unrelated dataset or figure was regenerated.

## 8. Remaining uncertainty

* The true intra-second execution order is **UNKNOWN** and cannot be recovered from whole-second timestamps. Episode identity, reversal counts, allocation membership, FIFO/LIFO attribution, closing-batch and wing/body membership are conditional on the chosen convention.
* Whether NIFTY trade ids and SENSEX nanosecond ids are exchange execution chronology is **UNRESOLVED**.
* Row 8079's true time is UNKNOWN.
* Realized P&L deltas are 0 only for the five approved policies, measured by the independent reference; the stress orders (reversed, seeded random) move FIFO/LIFO realized P&L by up to 1,300 paise.
* The slow tests pin results on this ledger; they are not tests of a theory of the venue.

## 9. DECISION RE-PRESENTED (project owner; one decision)

Evidence now available that the approval was not based on: the id orders are time-consistent across seconds and disagree with file order in 172 groups, so `SOURCE_ROW_ORDER_CONVENTION` is contradicted by the best sub-second evidence in those groups, although with an accounting effect in two NIFTY groups only.

| Option | What happens | Cost |
|---|---|---|
| **A** (current state) | Keep `SOURCE_ROW_ORDER_CONVENTION` as primary; the contradicting evidence is disclosed; `trade_id` and `sensex_trade_id_time` are the best-supported sensitivities | none; numbers unchanged |
| **B** | Change the primary to a per-contract id-sequence convention (NIFTY trade id; SENSEX ns time with epoch fallback; source row last) | output-changing: 2 NIFTY instruments, 4 episodes, 4 fills' open/close split, reversal-ended episodes 23 → 21, 1 batch per view, 6 W1 links, lot attribution for about 666 FIFO closing fills; M2-B to M2-E regenerated with before/after comparison |
| **C** | Keep A now; run downstream research conditional on both conventions until the id semantics are documented externally | extra analysis; no output change |

My recommendation is **C**: it changes no historical number, does not claim certainty either way, and keeps the choice reversible. This is a recommendation, not a decision. I am stopping here as instructed: the remaining Medium/Low defect fixes, Phase Two methodology decisions and M3 have not been started.

## 10. DECISION RECORDED (2026-11-15): Option C

**Formal project decision (owner, 2026-11-15): OPTION C.** `SOURCE_ROW_ORDER_CONVENTION` remains the primary convention of the existing historical reconstruction; the delivered M2-B to M2-E outputs are **not** regenerated or replaced. Downstream research must evaluate **both** ordering assumptions: the baseline `SOURCE_ROW_ORDER_CONVENTION` and the sensitivity scenario `PER_CONTRACT_ID_SEQUENCE` (NIFTY numeric trade id; SENSEX embedded nanosecond trade-id time with epoch fallback for the exceptional row 8079; source-row order as the final tie-break), which is kept distinct from the individual `trade_id`, `order_no` and `sensex_trade_id_time` policies. Both result sets are preserved, and conclusions are labelled ordering-stable or ordering-dependent. **Neither ordering is claimed to be verified exchange execution chronology; the true intra-second sequence is UNRESOLVED.** Evidence and comparison: `reports/R1C_DUAL_SCENARIO_COMPARISON.md`.

Section 9 above is kept as written; its recommendation (C) was adopted. Deliverables of the Option C step: `reports/R1C_DUAL_SCENARIO_COMPARISON.md`, `reports/r1c_dual_scenario/dual_scenario_results.json`, the policy `per_contract_id_sequence`, and the records listed in the Option C change list.
