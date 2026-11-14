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
