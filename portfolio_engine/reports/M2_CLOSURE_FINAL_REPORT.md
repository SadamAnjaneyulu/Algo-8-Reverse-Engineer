# M2 closure — final report and acceptance decision

Date: 2026-11-16 · Branch `engineering/position-lifecycle-basket-reconstruction` · Baseline convention `SOURCE_ROW_ORDER_CONVENTION`; sensitivity scenario `PER_CONTRACT_ID_SEQUENCE`. Neither is claimed to be verified exchange chronology.

# DECISION: **M2 — CONDITIONAL PASS** (proposed; M3 does not start until the owner approves it)

**Why not FAIL.** No Critical or High defect is open. Every headline quantity re-derived from the raw ledger by the audit tracks, by the closure work and by a fresh-context reviewer (own code, no project imports) was reproduced exactly. The delivered historical outputs are reproduced byte for byte from the current code.
**Why not an unconditional PASS.** (1) The root ambiguity cannot be removed: whole-second timestamps make the same-instrument intra-second order unobservable, so episode identity, reversal counts, FIFO/LIFO attribution, 1 closing batch per view, 6 W1/W2 links and opening body units remain **ordering-dependent** and must be reported under both scenarios. (2) Four Medium defects are **deferred with reasons** (they need approvals not given: replacing delivered figures or changing delivered manifests) and two Low defects are OPEN. (3) The independent review was done by the same model family as the authors.
**Conditions (standing, to be honoured by M3):**
* C1. Every downstream result is produced under **both** scenarios and labelled ordering-stable or ordering-dependent.
* C2. **No portfolio-level event-path interpretation inside a second** (intra-second exposure, peak inside a second, same-second risk decision) is authorized for either scenario; only per-instrument transitions and second-end **inventory, cash and gross opened/closed units** may be used (realized P&L, per-module attribution and reversal counts at second end still depend on same-instrument order).
* C3. The deferred items (D-01, D-04, E-D02, E-D03) and the two open Lows (C-06, E-D11) stay disclosed; closing them needs the owner's approval to regenerate delivered figures / manifests.

# 1. What was done (in the owner's order)

| Step | Result | Evidence |
|---|---|---|
| 1. Reconcile the 167/139/29 inventory | The figures were wrong: 139 + 29 = 168, and 11 figure files had been copied, not generated. Reconciled over **170 paths** (168 delivered + 2 scenario-only sidecars): baseline 167 IDENTICAL / 2 NEW / 1 EXCLUDED; hybrid 134 IDENTICAL / **33 DIFFERENT** / 2 NEW / 1 EXCLUDED; every path once, hashes and machine-computed reasons | `reports/r1c_dual_scenario/file_inventory.json`, `N2_PROVENANCE_AND_RECONCILIATION.md`, `tools/r1c_inventory.py` |
| 2. N1 cross-instrument ordering | Keyed policies sorted keys of different instruments together. Measured (hybrid, old vs local): 8,196 of 41,421 stream positions and 2,532 intermediate aggregate gross states differed (max 7,150 units); per-instrument sequences and second-end inventory were unaffected. **Fixed**: orders are local to (instrument, second); designs A/B/C compared; usage rule C; 9 of 9 mutants killed by assertion. Severity Medium | `docs/ORDERING_SEMANTICS.md`, `replay.py _local_keyed_order`, `reports/m2f_audit/n1/`, `mutation_results_N1.json` |
| 3. N2 scratch provenance | The scratch run is documented; the repo-native `--scenario/--out-root` mechanism reproduces it exactly (155 shared files, 0 differences); the baseline scenario reproduces **every generated delivered file** (slow test) | `pe/scenario.py`, `tools/r1c_scenario_run.py`, `tests/test_scenario.py` |
| 4. Documentation | Plan, README, architecture design, defect register (original M2-F dispositions restored verbatim for the six overwritten defects, with dated, commit-referenced amendments and a closure line), M2-F report and limitations addenda, R1 / R1-C reports, evidence registry; originals preserved (test against `562d7eb6`) | `reports/m2f_audit/disposition_history.json`, `tests/test_m2f_disposition_history.py` |
| 5. Decision A (case wording) | Corrected wording in generator, docstring, case report, forensics report, review record; D-1 concentration computed and disclosed (17 of 17 on D-1; 16 at 09:xx, 1 at 11:xx IST; none on D0; D0 eligibility counts); the 17 case records and all datasets byte-identical; upstream price-scrambling test (whole pipeline) + static lint; 8 of 8 mutants killed | `tests/test_decision_a.py`, `mutation_results_DA.json` |
| 6. Decision B (reversals) | Per-fill zero-crossing (primary) and parent-level same-second net sign flip (diagnostic), never merged. Baseline **23 / 26**, hybrid **21 / 22**; NIFTY cycle 1 / 1, SENSEX cycle 0 / 1; SENSEX wording per the approved sentence; 10 of 10 mutants killed | `python/pe/reversals.py`, `reports/r1c_dual_scenario/reversal_measures.json`, `tests/test_decision_b.py`, `tests/test_reversals.py` |
| 7. Decision C (threshold) | Inclusive `gap <= threshold` kept; exclusive reading as a separate artifact (1,214 / 840 / 153 / 50 / 63 batches only in the exclusive view = the independent M2-F reference; net +661 / +441 / +79 / +25 / +33); below / at / above tests for 2, 5, 10, 30, 60 s and C1 / C2; invariants; provenance; 14 of 14 mutants killed (C and D) | `tests/test_decision_c.py`, `reports/r1c_dual_scenario/m2c_exclusive_threshold/` |
| 8. Decision D (interpretations) | Recorded and tested with synthetic counterexamples: C2 predecessor, stream boundary, tie-break, parent identity (column 163 vs reused column 4), EXPIRED_UNCLOSED as an inference, number-block unresolved, W-classes, tag-scope denominators that reconcile (opening 1,414,545 = 617,130 + 626,765 + 170,650; closing 1,377,065 = 500,775 + 540,250 + 336,040) | `docs/BASKET_GROUPING_METHODOLOGY.md`, `tests/test_decision_d.py` |
| 9-10. Medium / Low registers | All 49 defects have a closure disposition beside the original M2-F disposition (below) | `reports/m2f_audit/closure_dispositions.json`, `M2F_DEFECT_REGISTER.md`, `tests/test_m2f_closure_register.py` |
| 11-13. Regression and mutation | Full Python suite and C++ (below); mutation results (below) | |
| 14. Fresh-context audit | 8 findings (1 Medium, 7 Low), no Critical / High; all fixed or dispositioned | `reports/m2f_audit/closure_review/` |

# 2. Defect register after closure

| Severity | FIXED | ACCEPTED WITH EVIDENCE / RATIONALE | DEFERRED WITH REASON | OPEN |
|---|---:|---:|---:|---:|
| High (1) | 0 | 1 (D-A01) | 0 | 0 |
| Medium (19) | 12 | 3 (B-01, C-01, D-03) | 4 (D-01, D-04, E-D02, E-D03) | 0 |
| Low (29) | 4 | 8 | 15 | 2 (C-06, E-D11) |

# 3. Test and mutation evidence (all executed in this session)

* Python: **511 passed** in 1,047 s (`pytest tests`, including the slow real-ledger, reproduction, price-scrambling and manifest tests; run on the final tree).
* C++ core: `ctest` passed; `pe_core_tests` 24 of 24. Python / C++ parity tests are part of the Python suite (shared logic only; the hybrid and the keyed policies are Python-only by design).
* Mutation, kill = an **assertion failure** (an error, import failure or the engine's own invariant check raising is not a kill):

| Harness | Mutants | Killed | Notes |
|---|---:|---:|---|
| N1 local ordering (`mutation_harness_N1.py`) | 9 | 9 | assertion text stored per kill |
| Hybrid policy (`mutation_harness_R1C_hybrid.py`) | 12 | 12 | |
| Decision A (`..._DA.py`) | 8 | 8 | DA08 killed in an individual re-run after the section text became a testable function; the first full run had it surviving (recorded) |
| Decision B (`..._DB.py`) | 10 | 10 | one survivor of the first run (a published count) was fixed with a fast pinned test |
| Decisions C and D (`..._DCD.py`) | 14 | 14 | four early "kills" were the engine's own invariant check, not assertions; tests rewritten and re-run |
| B-04 / C-02 (subagent, **re-run by the lead**) | 21 | 21 | |
| D-A04 expiry (subagent, **re-run by the lead**) | 14 | 14 | |
| D-A02 verifier (subagent, **re-run by the lead**) | 11 | 11 | |
| D-A08 generator (subagent, **re-run by the lead**) | 10 | 7 | 3 stopped by the generator's own grid check: errors, **not counted** |
| E-D01/02/03/07/09/12 (subagent) | 22 | 22 | executed by the subagent only; not re-run by the lead |

# 4. Preservation of the delivered historical outputs

* Raw CSV sha256 `86e65ab6…` unchanged. Of 666 files hashed before R1, **43 differ**: 9 engine code files, 9 tools, 1 existing test file, 17 Markdown documents, 2 audit files, **4 manifests (one provenance key appended)**, and `review_dispositions.json` (approved wording lines only, line-diff guarded). **No dataset, figure, summary or fixture differs.**
* The delivered wording changes are confined to approved lines of four documents (Decision A and B), each checked line by line against verbatim "before" copies.
* The baseline scenario regenerates every generated delivered file byte for byte from an empty directory (the one hand-written record excluded by name).

# 5. Evidence classes

Unchanged or more conservative: W1 WEAKLY_SUPPORTED, W1_S60 / W3 UNRESOLVED, W2 arithmetic weights, protective intent NOT_TESTABLE, EXPIRED_UNCLOSED an inference, number-block UNRESOLVED. The 18 Track D classes that the audit derived mechanically from verification tags were re-read: 15 unchanged, **3 downgraded** to "reproduced with limited independent verification" (case-selection invariance, full-ledger scope numbers, V5/V6 equality with a reference that shares the written rule) (`reports/m2f_audit/closure_review/track_d_class_review.json`). The hybrid M2-D / M2-E results are REPRODUCED_RESULT_WITH_LIMITED_INDEPENDENT_VERIFICATION.

# 6. The 15 acceptance conditions of the M2-F report, re-evaluated

| # | Condition | Result |
|---|---|---|
| 1 | Accounting and position quantities reconcile to source fills | MET (both scenarios; totals identical) |
| 2 | Lineage does not double-count or omit inventory | MET |
| 3 | FIFO/LIFO/AVG differences remain analytical | MET (lot attribution of 666 / 662 closing fills depends on the order, labelled) |
| 4 | Reversal and partial-close behaviour correct | MET (two measures separated; ordering dependence disclosed, CR-05 caveat) |
| 5 | Closing-batch rules implemented as documented | MET (boundary tests for every threshold; interpretations recorded) |
| 6 | C1/C2 sensitivities and tie-order limitations correctly reported | MET (was NOT FULLY MET): exclusive and tie-order sensitivities published |
| 7 | Wing/body methods preserve ambiguity and unmatched quantities | MET |
| 8 | Evidence classes conservative | MET (3 Track D classes downgraded; CR-08 wording fixed) |
| 9 | Scope exclusions remain visible | MET (denominators reconcile) |
| 10 | Both frozen cycles reconcile to raw source | MET |
| 11 | Chart data and figures reproducible | MET (byte-identical regeneration) with the manifest-coverage gap E-D03 pinned (28 of 168 delivered files unmanifested) |
| 12 | Python/C++ consistency for shared logic | MET (XLANG only) |
| 13 | Critical and high defects resolved or explicitly block | MET: D-A01 accepted by the owner's Option C with evidence |
| 14 | Medium/low limitations documented | MET: every defect has a closure disposition |
| 15 | No unsupported claims of ownership, intent, triggers or alpha | MET (the case-selection wording was corrected) |

# 7. Remaining uncertainty

* The true intra-second order is UNKNOWN and unrecoverable from whole-second data; whether NIFTY trade ids or SENSEX embedded times are exchange chronology is UNRESOLVED (row 8079 is inconsistent by 56.6 s).
* The inclusive threshold on whole seconds links pairs whose SENSEX nanosecond gap exceeds the threshold (CR-03).
* C2 membership depends on the tie-break among equal-first-second parents (CR-04).
* The independent review and the audit tracks share a model family with the authors; the subagent mutation runs for E-D items were not re-executed by the lead.
* Not exercised on real data: the expiry `<=` boundary; the C++ replay path through the CLI.

# 8. Proposed M3 requirements (nothing started)

Configurable fill-order conventions (registry, stamped in every output); dual-scenario results side by side; source data never modified; snapshots only at second boundaries (condition C2); plugins cannot mutate state; no plugin may choose the ordering convention silently.
