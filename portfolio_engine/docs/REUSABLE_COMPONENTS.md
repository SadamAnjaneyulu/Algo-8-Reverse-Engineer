# Reusable component inventory (read-only reuse; nothing is modified)

| Component | Location | Reuse in this project |
|---|---|---|
| Normalised fill ledger (41,421 rows, `src_row`, dq flags, tie groups) | `tp_reconstruction/data/fill_event_ledger.parquet`, built by `scripts/build_event_ledger.py` | **input** of the historical generator |
| Matching engine FIFO/LIFO/AVG, tie orders, role ambiguity | `tp_reconstruction/scripts/matching.py` | **oracle**: engine re-implements the documented rule; tests compare outputs; not imported by the engine |
| Fill roles (3 methods), position episodes (8,001 per method), reconstructed position ledger, reconciliation summary | `tp_reconstruction/data/*.parquet`, `reconciliation_summary.csv`, `role_ambiguity_fills.csv` | reconciliation targets |
| Source manifest + raw hash | `data/source_manifest.json`, `scripts/tp_common.py::sha256` | provenance |
| Lot / tick configuration | `tp_reconstruction/config.yaml` (`units`) | instrument table (data-verified) |
| Market bars loaders | `tp_reconstruction/scripts/market_data.py` | M5/M6 marks (needs `ALGO8_MARKET_DIR`) |
| TP-02 exit timelines, mechanisms | `tp_reconstruction/tp02/` | M4/M6 context only |
| Stage 1 / audit registers | `algo8_skeleton/`, `audit/ALGO8_MASTER_FINDINGS_REGISTER.md` | finding ids for the evidence registry (only when they exist) |
| Charting conventions | matplotlib, PNG + CSV beside each | M5 |
| Test conventions | pytest, synthetic scenarios + real-data invariants (`tp_reconstruction/tests`) | same style |
| TP-03 Phase 0 audit/config | branch `research/tp03-entry-exit-trigger-reconstruction` (not an ancestor of this branch) | read-only reference; no TP-03 experiment is run here |
