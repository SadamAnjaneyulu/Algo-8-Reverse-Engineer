# R1 — affected-file plan (presented BEFORE the convention metadata is applied)

Approved policy: `SOURCE_ROW_ORDER_CONVENTION` is the primary deterministic fill-order convention (not verified intra-second chronology). Baseline hashes of every tracked file: `baseline_sha256_before_R1.json` (HEAD `562d7eb6`, 666 files).

## A. Convention metadata: files that WILL change (metadata only)
| # | File | Change | Data values affected |
|---|---|---|---|
| 1 | `portfolio_engine/reports/m2c_data/manifest.json` | add key `tie_order_convention` | none |
| 2 | `portfolio_engine/reports/m2d_data/manifest.json` | add key `tie_order_convention` | none |
| 3 | `portfolio_engine/reports/m2e_data/NIFTY_2026-06-30/manifest.json` | add key `tie_order_convention` | none |
| 4 | `portfolio_engine/reports/m2e_data/SENSEX_2026-07-16/manifest.json` | add key `tie_order_convention` | none |
| 5 | `portfolio_engine/tools/m2c_closing_batches.py`, `m2d_wing_body.py`, `m2e_build.py` | assert the primary convention before writing and stamp the same key on future regeneration | none (they are not re-run) |

Existing metadata (all four manifests): no tie-order field; the convention was implicit (`'src'` passed to `LineageSet`).
Proposed metadata (identical in all four):
```json
"tie_order_convention": {"id": "SOURCE_ROW_ORDER_CONVENTION", "engine_policy": "src",
                         "verified_intra_second_chronology": false,
                         "statement": "same-instrument fills inside one second are processed in source-file row order; a deterministic convention, not verified execution chronology",
                         "sensitivity": "reports/R1_TIE_ORDER_CONVENTION.md"}
```
Run manifests written by `pe.provenance.manifest()` already carry `config.tie_order`; they additionally gain a top-level `tie_order_convention` string (code change in `provenance.py`, already in the engine commit; `run_id` is unchanged because it hashes the config, not this field).

## B. Files that must NOT change (verified by hash after the stamping)
Every `*.tsv.gz`, `*.tsv`, `*.csv`, `*.png`, `m2c_summary.json`, `m2d_summary.json`, `m2e_summary.json`, `coverage.json`, `case_studies.json`, `figure_manifest.json`, `case_figure_manifest.json`, all M1/M2-B fixtures and reports, the raw csv, `tp_reconstruction/`. No figure or dataset is regenerated. The stamping tool (`tools/r1_stamp_convention.py`) refuses to write unless a no-op JSON round-trip of each manifest is byte-identical, and prints before/after sha256 for every changed file.

## C. Disclosure addenda (appended sections; earlier text untouched) — separate commit
`reports/M2B_REPORT.md`, `reports/M2B_RECONCILIATION_REPORT.md`, `docs/POSITION_LINEAGE_RULES.md`, `reports/M2C_CLOSING_BATCH_REPORT.md`, `reports/M2D_WING_BODY_REPORT.md`, `docs/EVIDENCE_REGISTRY.md`, `IMPLEMENTATION_PLAN.md`, `reports/M2F_FINAL_AUDIT_REPORT.md`, `reports/M2F_METHODOLOGY_LIMITATIONS.md`; new canonical document `reports/R1_TIE_ORDER_CONVENTION.md`; D-A01 / B-01 / C-01 amendments (`reports/m2f_audit/r1/amendments.json`, rendered in `M2F_DEFECT_REGISTER.md`, which keeps the original text). M2-E reports are generated from their tools and are NOT edited; the affected M2-E outputs (episode identities, reversal counts, case records) are listed in the R1 document and the evidence registry instead.

## D. Code already added (engine commit, no delivered output changes)
`python/pe/tie_policy.py` (new), `schema.py` (`Fill.tie_key`, `KEYED_TIE_ORDERS`), `replay.py` (keyed orders; `source_row` alias normalised to the legacy token `src`, so dump bytes are unchanged), `lineage_set.py` (`convention`), `provenance.py`, `generators/historical.py` (`attach_tie_keys`). The C++ core and its `TIE_ORDERS` are unchanged; the three keyed policies are Python-only sensitivity policies.
