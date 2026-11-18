| id | change | existing tests | Track D checks |
|---|---|---|---|
| m00 | CONTROL: no change, manifests refreshed | control: passes (expected) | control: passes (expected) |
| m01 | V3 entry-minute cohort CSV: body units +65 in one (session, minute) row (wrong per-minute aggregation) | killed | killed |
| m02 | V1 CSV: one FILL row duplicated | killed | killed |
| m03 | V2 CSV: REVERSED event row dropped | killed | killed |
| m04 | V3 CSV: one body item labelled WING_LONG_BY_TAG (role label swap) | SURVIVED | killed |
| m05 | V4_C1 CSV: duration_s +1 for one batch | SURVIVED | killed |
| m06 | V5_W1 CSV: wing units no-candidate (unmatched) set to 0, total unchanged | SURVIVED | killed |
| m07 | V6 CSV: full-ledger scope number wing_items_with_candidate_full_ledger_W1 +1 | killed | killed |
| m08 | V1 CSV: D-1/D0 labels swapped (SENSEX) | SURVIVED | killed |
| m09 | V1 CSV: short_CE sign flipped on 5 rows | killed | killed |
| m10 | fills.tsv: exec_price_paise replaced by raw order running-average column (col 18) for all NIFTY fills | killed | killed |
| m11 | m2e_charts footer drops the execution-price/marks/unit annotation; V1 re-rendered (PNG only) | SURVIVED | SURVIVED |
| m12 | case_studies.json CT6 record: opening_parents[0] replaced by a closing parent | SURVIVED | killed |
| m13 | lifecycle_events.tsv (SENSEX): one event quantity +65 | killed | killed |
| m14 | episodes.tsv (NIFTY): n_parents +1 on one episode | killed | killed |
| m15 | coverage.json (SENSEX): fills.opening_units +65 | killed | killed |
| m16 | session_carry.tsv (NIFTY): D-1 short_CE +65 | killed | killed |
| m17 | V5_W1_S60 CSV: 5 links moved to the adjacent dt_s histogram bin | SURVIVED | killed |
| m18 | m2c_closing_batches_C1.tsv slice (NIFTY): total_closing_qty +65 for one batch | killed | killed |
| m19 | opening_items.tsv (NIFTY): avg_exec_price_paise written in rupees (/100) | killed | killed |
| m20 | cases/CT5_REVERSAL.csv: REVERSED event dropped | killed | killed |
| m21 | V2 CSV (SENSEX): inventory_after sign flipped on one ADDED event | killed | killed |
