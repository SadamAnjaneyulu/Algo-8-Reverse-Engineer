# M2-F — Test coverage and mutation results

Compiled from `reports/m2f_audit/track_*/mutations.json` and Track E's `TEST_COVERAGE.md` (appended verbatim below). A mutation counts as **killed** only if an assertion failed for the mutated behaviour; crashes and internal-guard failures are flagged in the track records and are NOT design-quality kills.

## 1. Suite status (Track E, clean scratch tree, [REPRO])

* 274 passed, 0 skipped, 0 warnings in 212.9 s (236 fast in 90.7 s, 38 slow). C++ `pe_core_tests` 24/24; fresh Release build warning-free under -Wall -Wextra -Wpedantic.
* Statement coverage of `pe/` 91 %, branch 85.5 % (understated for C++-dependent tests: stale CMake cache in the traced copy). `pe.cli` 0 %; `provenance.py` 55 %; `cases.record` lines 96-123 never executed in the original suite; no test runs any stage script.
* After this audit three regression test functions were added (`tests/test_m2f_regressions.py`, 4 collected cases incl. parametrization); they were run once and pass. They have NOT been re-run against the mutants they target.

## 2. Mutation results by track

| Track | Layer | Mutation records | Existing tests killed | Existing tests survived | Auditor's own independent check missed |
|---|---|---:|---:|---:|---:|
| A | Accounting / lineage (Python+C++) | 26 | 25 | 1 | 0 |
| B | Closing batches | 28 | 27 | 1 | 3 |
| C | Wing/body | 29 | 28 | 1 | 0 |
| D | Forensics / visualization | 21 (+1 control) | 14 | 7 | 1 |
| E | System / infrastructure | 19 | 14 | 5 | 1 |
| **Total** | | **123** | **108** | **15** | **5** |

Survivors are kept visible below. "Independent" in the last column of the track records means the detector does not run through the mutated code path.

## 3. Surviving mutants

### 3a. Survived the EXISTING test suites

| Track | Id | Change | Detected by auditor's own check? | Note |
|---|---|---|---|---|
| A | M11 | 19800-second timestamp shift in historical generator [python/pe/generators/historical.py] | True | SURVIVOR of all 127 existing tests: the shift is uniform so ordering, day assignment (max IST time 15:39+5:30 < 24:00) and all aggregates are unchanged; only a  |
| B | M22 | summarize: pairs_linked uses `<` instead of `<=` | True | EXISTING TESTS SURVIVE (25/25 pass): reporting-layer summarize() numbers (pairs_linked, the headline table) are not asserted by any non-snapshot test. Own detec |
| C | M19 | W3 weight denominators use body quantity instead of wing quantity | True | SURVIVED all 33 existing tests: no test pins the W3 weight column. Killed only by own reference |
| D | M-D-04 | V3 CSV: one body item labelled WING_LONG_BY_TAG (role label swap) | True | pytest: 89 passed in 248.48s (0:04:08); first failure: ; own failed counts {'verify_datasets': 1, 'verify_v4v5v6': 0, 'verify_cases': 0, 'verify_manifests': 0} |
| D | M-D-05 | V4_C1 CSV: duration_s +1 for one batch | True | pytest: 89 passed in 239.35s (0:03:59); first failure: ; own failed counts {'verify_datasets': 0, 'verify_v4v5v6': 1, 'verify_cases': 0, 'verify_manifests': 0} |
| D | M-D-06 | V5_W1 CSV: wing units no-candidate (unmatched) set to 0, total unchanged | True | pytest: 89 passed in 246.23s (0:04:06); first failure: ; own failed counts {'verify_datasets': 0, 'verify_v4v5v6': 1, 'verify_cases': 0, 'verify_manifests': 0} |
| D | M-D-08 | V1 CSV: D-1/D0 labels swapped (SENSEX) | True | pytest: 89 passed in 308.65s (0:05:08); first failure: ; own failed counts {'verify_datasets': 729, 'verify_v4v5v6': 0, 'verify_cases': 0, 'verify_manifests': 0 |
| D | M-D-11 | m2e_charts footer drops the execution-price/marks/unit annotation; V1 re-rendered (PNG only) | False | verify_manifests flagged the informational PNG hash (png_sha256_informational not refreshed by the harness): INCIDENTAL, no check reads the footer text, so the  |
| D | M-D-12 | case_studies.json CT6 record: opening_parents[0] replaced by a closing parent | True | pytest: 89 passed in 251.11s (0:04:11); first failure: ; own failed counts {'verify_datasets': 0, 'verify_v4v5v6': 0, 'verify_cases': 1, 'verify_manifests': 0} |
| D | M-D-17 | V5_W1_S60 CSV: 5 links moved to the adjacent dt_s histogram bin | True | pytest: 89 passed in 260.52s (0:04:20); first failure: ; own failed counts {'verify_datasets': 0, 'verify_v4v5v6': 2, 'verify_cases': 0, 'verify_manifests': 0} |
| E | E05 | manifest hash computed over the wrong bytes (trailing newline stripped) [tools/m2c_closing_batches.py] | True | SURVIVOR of the suite: no test executes the stage scripts |
| E | E07 | provenance sha wrong: git_sha() returns a constant [python/pe/provenance.py] | True | SURVIVOR: provenance.py is 55 % covered, git_sha unasserted |
| E | E08 | schema_version not checked by the Python event reader (version bump undetected) [python/pe/tsvio.py] | True | SURVIVOR: no invalid fixture for schema_version; real writer always emits v1 |
| E | E14 | m2e manifest hash over the wrong bytes (last byte dropped) [tools/m2e_build.py] | True | SURVIVOR of the suite |
| E | E17 | IST offset constant wrong (0) in the C++ core (rebuild required) [cpp/include/pe/types.hpp] | True | SURVIVOR of all 274 tests + 24 C++ checks: no fixture or real-data day crosses IST midnight in UTC terms |

### 3b. Survived the auditor's own independent check

| Track | Id | Change | Existing tests caught? | Note |
|---|---|---|---|---|
| B | M13 | wrong closing-quantity attribution at parent level: qty += min(r[8], 65) | True | Existing tests kill it (4 tests incl. members-file closing_qty). OWN IMPL detector SURVIVES: it does not compare the members-file closing_qty column; only the [ |
| B | M23 | stability: nested forced True | True | Own detector survives: on the real data nesting is always true so forcing nested=True is behaviourally equivalent there; existing synthetic test kills it. Own c |
| B | M28 | closing portions without parent id pooled (unattributable check removed) | True | Existing tests kill it; own detector has no missing-parent-id scenario (own-check gap; real data has 0 such rows). |
| D | M-D-11 | m2e_charts footer drops the execution-price/marks/unit annotation; V1 re-rendered (PNG only) | False | verify_manifests flagged the informational PNG hash (png_sha256_informational not refreshed by the harness): INCIDENTAL, no check reads the footer text, so the  |
| E | E01 | batch-id collision: sequence number dropped from CLOSING_BATCH ids [python/pe/closing_batches.py] | True | killed in 10 s by test_COUNTEREXAMPLE_mixed_parent... |

Mutations that are invisible on the real ledger and detected only by synthetic input (noted by the tracks): IST-midnight / missing-minute handling in wing/body (C: M03, M15, M24), C2-collapse and boundary-merge mutants in closing batches (B: M04, M05, M07-M09, M19), the C++ IST day boundary (E: E17), the OPEN_AT_END_OF_DATA path (A: D-A04). The real ledger has no fill after 15:39 IST, no cross-session link and no flagged duplicate, so these code paths are exercised only by synthetic tests.

## 4. Tests that are circular or weak (summary)

* Dataset-vs-recompute tests regenerate the expected value with production code (internal consistency, [REPRO]); the independent evidence is the raw-ledger re-derivation done by the audit tracks.
* Manifest hash snapshot tests kill several mutants only because the committed output changes; they cannot detect an error that was already committed.
* No test reads PNG content; presentation mutants (legend, footer text, bin shift) survive. The M2-E suite checks CSVs, not pixels.
* Markdown report tests are substring/count checks and catch only gross staleness.

---

## Appendix: Track E coverage report (verbatim)

# Track E - TEST_COVERAGE (M2-F audit; scratch execution, repo untouched)

Evidence classes: [REPRO] suite re-execution; [INV] coverage trace. Coverage = `coverage 7.17.3` (installed with `pip --target` into scratch; not into the repo), `branch=True`, `dynamic_context=test_function`, run over a scratch copy.
**Caveat (VERIFIED):** the coverage copy was made with `cp -r` and carried a CMake cache pointing at the original build directory, so the 5 `test_parity.py` and 2 `test_lineage_parity.py` tests (7, all needing the C++ build) ERRORED in the traced run (267 passed, 7 errors; 464 s under heavy machine load). The untraced run in a clean scratch copy had all 274 pass (below). Python lines reached only through those 7 tests (TSV writers `tsvio.write_*`, `historical.write`, `replay.roles_tsv`) are therefore under-reported in the table; they are exercised by the parity tests only.

## 1. Suite execution (VERIFIED, [REPRO])
| Run | Result |
|---|---|
| Full suite incl. slow, clean scratch copy WITHOUT `data_generated/` and `runs/` (clean-checkout condition), Python 3.13.18, `-p no:cacheprovider` | **274 passed, 0 failed, 0 skipped, 0 warnings, 212.9 s** (uncontended) |
| `-m "not slow"` | 236 passed, 38 deselected, 90.7 s |
| `-m slow` selection | 38 tests: test_tp01_reconciliation 13, test_lineage_real 9, test_parity 5, test_closing_batches 4, test_wing_body 3, test_lineage_parity 2, test_forensics 2 |
| C++ core checks (`pe_core_tests`, Release, g++ 13.3 `-Wall -Wextra -Wpedantic -ffp-contract=off`, fresh scratch build, 4.5 s, 0 compiler warnings) | **24/24 core checks passed** (ctest 1/1) |
Per-file counts: test_accounting 23, test_closing_batches 25, test_forensics 89, test_lineage 19, test_lineage_mutations 16, test_lineage_parity 2, test_lineage_real 9, test_lineage_reference 40, test_parity 5, test_tp01_reconciliation 13, test_wing_body 33 (= 274).
Observations: (a) the suite wrote no new file in the scratch tree other than bytecode (VERIFIED by tree diff); (b) the 'slow' marker is under-applied: 87 of 89 `test_forensics.py` tests load the real ledger (25 s fixture setup each for the two cycles) but are not marked slow, so `-m "not slow"` still takes 90 s and still requires the TP-01 parquet (defect E-D09); (c) no test is skipped by markers (0 skipped).

## 2. Line / branch coverage of `portfolio_engine/python/pe` (traced run, [INV])
Total: 1301 statements, 119 missed (91 % statements), 532 branches, 77 missing (85.5 % branches), 89.3 % combined.
| Module | Stmts | Miss | Cover | Test files that execute it | Not exercised |
|---|---:|---:|---:|---|---|
| schema.py | 30 | 0 | 100 | accounting, lineage*, closing_batches, wing_body, forensics, tp01 | - (but no test pins `IST_OFFSET_S`/`ist_day` on a pre-/post-18:30 UTC boundary; see mutations E09) |
| ledger.py | 82 | 0 | 99 | accounting, lineage, lineage_mutations, lineage_reference, lineage_real, tp01, ... | one branch exit |
| replay.py | 71 | 3 | 95 | accounting, lineage*, tp01, forensics | `roles_tsv` (only used by parity tests; ERRORed in traced run) |
| invariants.py | 25 | 0 | 97 | accounting, lineage*, tp01 | AVG tolerance branch 23->25 |
| lineage.py | 53 | 0 | 100 | lineage, lineage_mutations, lineage_reference, lineage_real, forensics | - |
| lineage_set.py | 113 | 0 | 99 | lineage*, closing_batches, wing_body, forensics | 2 branch exits |
| parents.py | 31 | 1 | 89 | lineage*, wing_body | `read_parents` non-integer branch (line 36) |
| closing_batches.py | 142 | 0 | 96 | closing_batches, forensics | `check_view` raise branches partly (tamper test covers most) |
| wing_body.py | 263 | 3 | 97 | wing_body | lines 220-221, 259 (descriptive categories) |
| forensics.py | 187 | 32 | 84 | forensics | `recompute_m2c_m2d` (179-183), `historical marks` block (227-234), `cycle_coverage` body (241-260) only run by `tools/m2e_build.py`, not by any test |
| cases.py | 82 | 26 | 63 | forensics | **`record()` (lines 96-123: the case-study record builder) is never executed by any test**; tests check selection and the committed JSON/markdown only |
| generators/historical.py | 39 | 3 | 88 | forensics, lineage_real | `write()` (parity tests only) |
| generators/synthetic*.py | 72 | 0 | 100 | many | - |
| tsvio.py | 62 | 13 | 75 | accounting (readers); parity (writers; errored in traced run) | instrument-field ValueError / bad-expiry branches (26, 30, 37) |
| provenance.py | 18 | 8 | 55 | forensics (hash helpers only) | **`manifest()`, `git_sha` failure path, `run_dir()` never executed** |
| cli.py | 30 | 30 | **0** | none | entire module (`pe.cli replay`, `--engine cpp`, run manifests) is untested (VERIFIED 0 %) |

## 3. Tools (`portfolio_engine/tools/`) - manual matrix (INSPECTED + mutation evidence)
| Tool | Exercised by tests? |
|---|---|
| m2c_closing_batches.py, m2d_wing_body.py, m2e_build.py, m2e_cases.py, m2e_catalog.py, m2e_coverage_report.py, m2e_report.py | **No test runs these scripts.** Tests re-derive the same data through `pe.*` functions and compare with the committed files; the scripts' own manifest-writing, gzip, summary and report code is only covered by my determinism reruns (this audit) and by mutations E05, E14 |
| m2e_charts.py | imported (`import m2e_charts as CH`) by test_forensics; chart code run via the tests' figure-data checks |
| parity.py / parity_lineage.py | imported by test_parity / test_lineage_parity (build + real runs) |
| m2b_reconcile.py, m2c_charts.py, m2d_charts.py, m2c_addendum.py, number_block_diagnostics.py, unit_audit.py, select_demo_cycles.py (needs external `market_data`, `ALGO8_MARKET_DIR`), make_fixtures*.py, position_query.py | no tests; select_demo_cycles.py NOT RUNNABLE here (raw bars absent): NOT VERIFIED |
C++ (`cpp/include/pe/*.hpp`, `src/pe_replay.cpp`): line coverage not measured (no gcov run); behaviour covered by `test_core.cpp` (24 checks, hand-computed scenarios) and by parity tests (C++ vs Python on fixtures + full ledger + invalid fixtures + mode contamination). INSPECTED: no C++ test for CRLF/`+5`/whitespace tokens, int64 overflow in unchecked sums, or invalid schema_version.

## 4. Test-quality assessment (INSPECTED unless stated)
* Independent expectations (hand-computed numbers): test_accounting (23), test_lineage hand scenarios, test_closing_batches / test_wing_body synthetic builders, `cpp/tests/test_core.cpp`.
* Independent re-implementation: `test_lineage_reference.py` (40 seeds, reference implemented in the test); `check_view` -> `reference_partition` (second implementation, same author, same module); `test_tp01_reconciliation.py` compares to the TP-01 stage (an earlier implementation from the same project: semi-independent; both consume the same TP-01 ledger, which is not the raw file). None of this is raw-source validation except hash binding of the ledger to `Trades_GKOHNP140.csv`.
* Self-referential / reproducibility-only: `test_*_reproduce_the_committed_manifest`, `test_datasets_reproduce_committed_files`, `test_case_selection_reproducible_and_matches_committed`, parity tests ([XLANG]) - they prove the code still produces what was committed, not that the committed numbers are right.
* Tests that cannot fail: none found by inspection of assertions; `test_replay_is_deterministic` compares two runs in one process (cannot detect hash-seed or version dependence: SUSPECTED weak, confirmed by defect E-D04 where coverage.json order varies by PYTHONHASHSEED and no test noticed).
* Tautology risk: `test_manifest_hashes_match_files` recomputes `sha256(text)` with the same helper family as the generator (`F.sha`), which validates the manifest against files but not the generator's choice of bytes (mutation E14).

## 5. Ten most safety-critical functions: which test fails if wrong, and independence
| # | Function | Failing test if wrong | Independent of the function? |
|---|---|---|---|
| 1 | `PortfolioState.apply_fill` (accounting replay) | test_accounting hand numbers (open_close_full, partial_close_conventions, reversal); test_lineage_reference (40 seeds); tp01 per-fill roles; mutations E03 | yes (hand-computed / reference / TP-01); my 1,043-case reference ([IMPL], exact Fractions) agrees |
| 2 | reversal split (`close_q=min(q,inv)`, residual opens new episode) | test_accounting.test_reversal_counts_and_pnl; test_lineage.test_reversal_100_130...; test_lineage_mutations M2/M7 | yes (hand-computed) |
| 3 | CA allocation FIFO/LIFO/AVG | test_lineage.test_ab_lots..., test_lineage_reference, M4/M5 (row-level in `check`) | mostly; `check()` re-derives from the emitted rows (semi-independent) |
| 4 | closing-batch chaining (`build_view`) | test_closing_batches boundary/tie/C2 tests; `check_view` reference_partition; E01/E06/E11 | hand-built synthetic cases yes; `reference_partition` same author/module (semi) |
| 5 | W1 / W1_S60 candidate selection | test_wing_body (entry minute, 60 s inclusive/61 excluded, session boundary, false matches) | yes (hand-built) |
| 6 | W3 queue pairing | test_W3_is_arithmetic... (exact segments and residual); `wb.check` I-W3-residual | yes for the tested scenario; one scenario only |
| 7 | episode terminal status / expired-unclosed | test_lineage M10, M11 (parametrised boundary), test_lineage.test_expired_unclosed_has_no_settlement_pnl | yes |
| 8 | IST session assignment (`ist_day`, `IST_OFFSET_S`, `forensics.ist_*`) | forensics.test_ist_helpers_not_utc pins `forensics.ist_str/ist_date` only; `schema.ist_day` is pinned indirectly through committed datasets (E16 killed) | `schema.ist_day` boundary not unit-tested (E09 result in mutations.json) |
| 9 | manifest hashing (`sha256_of_text`, `sha256`) | test_manifest_hashes_match_files; reproduce-committed-manifest tests | validates files vs manifest, not the generator scripts (E05, E14 survive the suite) |
| 10 | case selection (`pe.cases`) | test_case_selection_* incl. brute force 6-9 and mutation tests | partially independent (brute force in test); `record()` untested |
