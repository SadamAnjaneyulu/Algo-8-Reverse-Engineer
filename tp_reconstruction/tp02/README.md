# TP-02 · Exit-mechanism attribution

Report: [`../TP02_REPORT.md`](../TP02_REPORT.md) · Phase 0 and pre-registration: [`../TP02_PHASE0_AUDIT.md`](../TP02_PHASE0_AUDIT.md), [`config.yaml`](config.yaml)

| Folder | Content |
|---|---|
| `scripts/` | `build_exit_timelines.py` → `classify_mechanisms.py` → `analyze_mechanisms.py` → `analyze_extra.py` → `test_hypotheses.py` → `make_figures.py` → `write_report.py`; `run_tp02.py` runs them in order (about 15 minutes) |
| `data/` | `exit_event_timelines.parquet` (event windows, three times kept apart), `exit_event_mechanisms.parquet` (flags, stop class, mechanism, confidence, populations), `profitable_nonstop_candidates.parquet` (Pop 3 / 4), `mechanism_reconciliation.csv` (agreement with TP-01), `exposure_panel_tp02.parquet` |
| `analysis/` | mechanism, clock, expiry, replacement, basket, stop-cycle, wing, convention and cycle tables, hypothesis tests with Holm, curves, figures |
| `tests/` | 31+ tests (timeline, classification, populations, replacement sequences, reconciliation, inference engine) |

```bash
export ALGO8_MARKET_DIR=/path/to/data/breeze/normalized      # raw Breeze 1-minute bars
python3 tp_reconstruction/tp02/scripts/run_tp02.py
python3 -m pytest tp_reconstruction/tp02/tests -q
```

Read-only inputs: TP-01 outputs (`tp_reconstruction/data`), the raw trade file, raw Breeze bars. No Stage 2 / alpha file is used. Everything is in-sample and descriptive.
