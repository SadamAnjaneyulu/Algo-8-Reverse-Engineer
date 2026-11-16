# Implementation plan

| Milestone | Scope | Exit criterion | Status |
|---|---|---|---|
| M0 | audit, architecture, plan, dependency audit, component inventory, schemas, risk register | documents exist and match the repo | **complete** (historical status "this commit" at the time of M0) |
| M1 | shared schemas, Python + C++ event model and replay, deterministic ordering, snapshots, accounting invariants, mode isolation, synthetic fixtures, real-data replay, parity, reconciliation to TP-01 | all tests executed; parity dumps identical; TP-01 totals/episodes/roles reproduced | **complete** (`reports/M1_REPORT.md`; historical status "in progress → report") |
| M2 | Position manager (lifecycle query), Basket manager, membership provenance, grouping conventions | basket/portfolio totals reconcile to positions | **executed as M2-A..M2-F; M2-F CONDITIONAL PASS; closure in progress; NOT YET ACCEPTED** (see "Status as of 2026-11-16"). Historical status was "planned". The scope cell is the original plan; what was executed is the M2 breakdown below (position lineage, closing batches and wing/body as analytical views, forensics, audit); no behavioural basket manager exists |
| M3 | plugin interfaces + registry + no-op/default/synthetic plugins; generators framework | plugins cannot mutate state (tested); fill-order conventions configurable and every research result produced under both scenarios (Option C) | planned; **not started** |
| M4 | basket cut (full/partial/side/position/wing-aware) and re-entry; execution states; reconciliation after every fill | synthetic 195/195 scenario + historical basket replay | planned; not started |
| M5 | 27 required charts with data export and mode stamps | charts from real or explicitly synthetic data | planned; not started |
| M6 | one historical cycle end to end | parity + reconciliation + charts | planned; not started |

Rules kept in every milestone: stage only listed files; no `git add .`; never write to `tp_reconstruction/`, `Trades_GKOHNP140.csv` or other research outputs; do not touch PRs #8–#12; no TP-03 experiment; `stage2_alpha_research/` untouched; draft PR only after M1 tests pass and only on this branch.

### Status as of 2026-11-16 (authoritative; older status text elsewhere is kept as history)
* **Implemented and tested:** M1 (shared model, deterministic replay, accounting invariants, Python/C++ parity); M2-B (position lineage, FIFO/LIFO/AVG attribution, episodes, lifecycle), M2-C (closing-batch views C1/C2), M2-D (wing/body associations W1/W1_S60/W2/W3), M2-E (historical forensics, two frozen cycles), M2-F (independent audit: **CONDITIONAL PASS**), R1 (fill-order policies and disclosure), R1-C (Option C: baseline and `PER_CONTRACT_ID_SEQUENCE` scenarios).
* **Awaiting acceptance:** M2 as a whole. The final M2 acceptance decision (exactly one of PASS / CONDITIONAL PASS / FAIL) has **not** been issued; closure items are listed in "M2 closing sequence" below.
* **Not started:** M3, M4, M5, M6. No behavioural basket manager, cut or re-entry policy, plugin interface or chart suite (beyond the M2 figures) exists.
* **Decisions in force:** `SOURCE_ROW_ORDER_CONVENTION` is the historical baseline; `PER_CONTRACT_ID_SEQUENCE` is a separate sensitivity scenario; neither is verified exchange chronology; delivered M2-B..M2-E outputs are not replaced; downstream research evaluates both.

## Directory structure
```
portfolio_engine/
  ARCHITECTURE_DESIGN.md  IMPLEMENTATION_PLAN.md  README.md
  docs/        SCHEMAS.md  EVIDENCE_REGISTRY.md  DEPENDENCY_AUDIT.md  REUSABLE_COMPONENTS.md  RISK_LIMITATION_REGISTER.md
  python/pe/   schema.py events.py ledger.py snapshot.py invariants.py replay.py provenance.py tsvio.py cli.py generators/
  cpp/         CMakeLists.txt include/pe/*.hpp src/pe_replay.cpp tests/
  fixtures/    synthetic event files (generated, seeded, committed)
  tests/       python tests incl. parity and TP-01 reconciliation
  tools/       build + parity scripts
  runs/        (git-ignored) outputs by execution mode
```


## Milestone 2 breakdown
| Step | Scope | Gate |
|---|---|---|
| M2-A | ontology, lineage rules, grouping methodology, schema additions, branch reconciliation, decisions to approve | **review before any code** (this commit) |
| M2-B | OA/CP/CA/slice/lifecycle in Python + C++, FIFO/LIFO/AVG, reversal handling, position query, I1–I7, I10–I11, parity | accounting tests + byte parity |
| M2-C | Model A (both languages), Models B and C (Python), reconciliation I8/I9 | partition tests |
| M2-D | wing/body methods W1–W5, unmatched/ambiguous quantification | uncertainty retained |
| M2-E | forensics on one NIFTY and one SENSEX cycle, six chart families with saved data | charts reproduce from CSV |
| M2-F | independent adversarial audit, regression counterexamples, final reports | PASS / PARTIAL |
Not in M2: cut/re-entry policies, alpha, new dependencies.
*Result vocabulary: the table's M2-F gate "PASS / PARTIAL" was superseded by the audit brief's three-way decision; M2-F issued CONDITIONAL PASS.*


### M2 status (chronological log; the latest state is "Status as of 2026-11-16" above and "M2 closing sequence" below)
M2-A approved (D1–D7). Demonstration cycles frozen: NIFTY 2026-06-30, SENSEX 2026-07-16. **M2-B complete and independently reviewed (`reports/M2B_REPORT.md`): PASS.** M2-C (Models A/B/C) awaits authorization; the number-block semantics need a decision first. *[History: superseded by the later entries; M2-C was executed.]*

M2-C (closing batches) executed for C1 and C2; number-block variant audited and left `UNRESOLVED — REVIEW REQUIRED`. Stopped for review; Models A and B, wing/body and later stages are not started.

M2-D (wing/body associations) executed and independently reviewed (`reports/M2D_WING_BODY_REPORT.md`). Stopped for review; M2-E and M3 not started.

M2-E (historical position forensics and portfolio visualization) executed for the two frozen cycles and independently reviewed in two rounds (`reports/M2E_HISTORICAL_FORENSICS_REPORT.md`; gate 10/10 PASS with disclosed limitations: historical option marks absent in this environment, expired-unclosed case UNAVAILABLE in both cycles, reversal UNAVAILABLE for SENSEX). Assembled datasets `reports/m2e_data/`, figures V1–V6 `reports/m2e_figures/`, case studies, coverage report and visualization catalog delivered; no new grouping, no change to W1/W2/W3, no accounting change. Stopped for review; M3 not started.

M2-F (final independent audit of M1/M2-A..M2-E) executed with five independent tracks; decision **CONDITIONAL PASS** (`reports/M2F_FINAL_AUDIT_REPORT.md`). No Critical defect; one High (D-A01) unresolved and blocking an unconditional PASS: the observed position layer (episode identity, reversal count, FIFO/LIFO attribution, and through them closing-batch and wing/body membership) depends on an unresolved intra-second fill-order convention (file order used). Unsupported M2-E wording on case-selection history recorded as D-02 (addendum in `reports/M2F_METHODOLOGY_LIMITATIONS.md`; earlier reports not edited). 49 defects (0 Critical / 1 High / 19 Medium / 29 Low), 97 claims classified, 123 mutants run. Decisions required from the user are listed in `M2F_METHODOLOGY_LIMITATIONS.md` section 12. M3 not started; stopped for approval.

R1 (tie-order convention) executed after the M2-F CONDITIONAL PASS: `SOURCE_ROW_ORDER_CONVENTION` approved as the primary deterministic convention (not verified chronology); sensitivity-only policies (`source_row`, `sells_first`, `buys_first`, `trade_id`, `order_no`, `sensex_trade_id_time`) added to the Python engine (C++ unchanged); convention metadata stamped into four manifests; disclosure addenda appended to M2-B/M2-C/M2-D/M2-F; five sensitivity populations reported separately (`reports/R1_TIE_ORDER_CONVENTION.md`); primary outputs verified byte-identical to the pre-R1 baseline. Remaining M2-closure items (Medium/Low defects, acceptance gate) and M3 are NOT started; stopped for review. *[Update 2026-11-16: the sensitivity report has six populations (lot attribution was added after the independent review) and R1-C added the hybrid policy `per_contract_id_sequence`, so there are six sensitivity-only policies in the Python engine; the C++ core is unchanged.]*

R1-C (decision recorded 2026-11-15): **Formal project decision (owner, 2026-11-15): OPTION C.** `SOURCE_ROW_ORDER_CONVENTION` remains the primary convention of the existing historical reconstruction; the delivered M2-B to M2-E outputs are **not** regenerated or replaced. Downstream research must evaluate **both** ordering assumptions: the baseline `SOURCE_ROW_ORDER_CONVENTION` and the sensitivity scenario `PER_CONTRACT_ID_SEQUENCE` (NIFTY numeric trade id; SENSEX embedded nanosecond trade-id time with epoch fallback for the exceptional row 8079; source-row order as the final tie-break), which is kept distinct from the individual `trade_id`, `order_no` and `sensex_trade_id_time` policies. Both result sets are preserved, and conclusions are labelled ordering-stable or ordering-dependent. **Neither ordering is claimed to be verified exchange execution chronology; the true intra-second sequence is UNRESOLVED.** Evidence and comparison: `reports/R1C_DUAL_SCENARIO_COMPARISON.md`.

### M2 closing sequence (authorized order; each step stops for owner review)
1. **R1-C record (done):** Option C recorded; hybrid scenario implemented and compared; nothing delivered regenerated.
2. Phase Two methodology decisions (case-selection wording; reversal definitions; closing-batch threshold inclusivity; other recorded choices).
3. Phase Three Medium-defect remediation (defect-by-defect ledger; C-02 engine-level W3 test, D-A08 and E-D03 reopened items).
4. Low-defect dispositions (FIXED / ACCEPTED / DEFERRED / OPEN).
5. Regression and mutation testing (a test is called mutant-killing only after the mutant was executed and failed).
6. Fresh-context final audit.
7. Final M2 acceptance decision: exactly one of PASS / CONDITIONAL PASS / FAIL.
8. **M3 starts only when the owner authorizes it.** Not started.

### M3 architecture requirements recorded by Option C (not started)
* Fill-order conventions are **configurable** (a registry such as `pe.tie_policy`), selected per run, stamped into every manifest and output; the baseline is `SOURCE_ROW_ORDER_CONVENTION`.
* **Dual-scenario research:** every research result is produced under the baseline and under `PER_CONTRACT_ID_SEQUENCE`, stored side by side, with an explicit ordering-stable / ordering-dependent label.
* Source data (the raw trade file and the TP-01 ledger) is **never modified**; ordering keys are derived at load time from the raw columns and checked against the manifest hash.
* Plugins cannot mutate state (existing M3 gate); a plugin may not choose the ordering convention silently.
