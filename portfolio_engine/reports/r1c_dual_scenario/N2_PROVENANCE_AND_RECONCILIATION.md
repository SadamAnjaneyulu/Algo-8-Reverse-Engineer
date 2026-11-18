# N2 — provenance of the hybrid M2-D / M2-E evidence, and the reconciled file inventory

**Status:** reproduced from committed code. Generated 2026-11-16 from `reports/r1c_dual_scenario/file_inventory.json` by `tools/r1c_inventory.py`.

## 1. The earlier 167 / 139 / 29 figures were wrong; the reconciled inventory

| Quantity | Earlier report | Reconciled |
|---|---|---|
| Delivered files in the universe | "167" | **168** (167 generated + the hand-written `review_dispositions.json`; the 168th was the case-study Markdown) |
| Baseline control run | "167 identical" | 167 IDENTICAL, 0 DIFFERENT, 0 MISSING, 2 NEW (the two scenario-only `inventory_series_intra_second_flags.tsv`), 1 EXCLUDED_WITH_REASON = **170** |
| Hybrid run | "139 identical + 29 different" | 134 IDENTICAL, **33 DIFFERENT**, 0 MISSING, 2 NEW, 1 EXCLUDED_WITH_REASON = **170** |

Why the earlier numbers were wrong: 139 + 29 = 168, not 167, and the scratch mirror **copied** the 11 `m2c_figures` / `m2d_figures` files from the repository instead of generating them, so they were counted as identical without being reproduced. Regenerated from an **empty** out root, 4 of those 11 differ under the hybrid (3 M2-D figure CSVs and the M2-D overview PNG).
The tool asserts `IDENTICAL + DIFFERENT + MISSING + NEW + EXCLUDED = TOTAL_UNIVERSE` for both comparisons; every path appears once with one class, hashes and a machine-computed reason.

## 2. What the hybrid changes (by category, 33 different files)
| Category | Different / identical |
|---|---|
| figure_png | 1 / 41 |
| m2c_closing_batch_data | 6 / 0 |
| m2c_figure_csv | 0 / 3 |
| m2d_figure_csv | 3 / 0 |
| m2d_wing_body_data | 5 / 1 |
| m2e_cycle_table | 6 / 32 |
| m2e_figure_csv | 4 / 49 |
| manifest | 6 / 2 |
| markdown_report | 0 / 1 |
| summary_json | 2 / 5 |

Reasons computed per file: {'table': 22, 'json': 8, 'png': 1, 'row order only': 2}. M2-E: `fills.tsv` differs in row order only; `inventory_series.tsv` and `lifecycle_events.tsv` differ at the reordered intra-second rows; episodes, opening items, session carry, TP-03 windows, coverage and **all case studies** are identical; all M2-E figure PNGs are byte-identical (their data CSVs differ only at the reordered intra-second rows); the single different PNG is `m2d_figures/m2d_overview.png`.

## 3. N2: exact reproduction path and patch provenance
* **Earlier scratch run** (`reports/m2f_audit/p1_scratch/`): `make_mirror.py` patched a copy of the repository (`forensics.Cycle` tie order, three hard-wired source-row sorts, builder guards, a per-instrument slot permutation in `order_events`); the first two attempts failed because (1) the global keyed sort mixed instruments and (2) `forensics.py` sorted by source row in three places (fills table, inventory series, reconciliation). The third attempt succeeded.
* **Now repo-native:** `pe.scenario` and `--scenario` / `--out-root` on every builder; `forensics.Cycle` takes a scenario; `order_events` is local to (instrument, second) (`docs/ORDERING_SEMANTICS.md`).
* **Equivalence check:** the successful scratch hybrid outputs and the repo-native hybrid outputs were compared file by file: 155 shared generated files, **0 differences** (the scratch run also contained the copied hand-written record).
* **Reproduce:**
```bash
python3 portfolio_engine/tools/r1c_scenario_run.py --scenario=baseline --out-root=/tmp/baseline_out
python3 portfolio_engine/tools/r1c_scenario_run.py --scenario=per_contract_id_sequence --out-root=/tmp/hybrid_out
python3 portfolio_engine/tools/r1c_inventory.py --control=/tmp/baseline_out --scenario=/tmp/hybrid_out
```
* Test: `tests/test_scenario.py::test_baseline_scenario_reproduces_every_generated_delivered_output_byte_for_byte` (slow).

**Classification:** the hybrid M2-D / M2-E results are now `REPRODUCED_RESULT_WITH_LIMITED_INDEPENDENT_VERIFICATION`: reproduced from committed code by two paths (patched scratch and repo-native) that share the same engine and loader; the hybrid ordering itself is independently re-derived from the raw CSV only for the accounting and reversal measures (`reports/m2f_audit/r1/independent_per_contract_id_sequence.py`, `tests/test_decision_b.py`).
