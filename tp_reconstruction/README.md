# TP-01 · Profitable position reconstruction and exit classification

Report: [`TP01_REPORT.md`](TP01_REPORT.md) · Phase 0 audit: [`PHASE0_AUDIT.md`](PHASE0_AUDIT.md) · configuration fixed before classification: [`config.yaml`](config.yaml)

| Folder | Content |
|---|---|
| `scripts/` | `build_event_ledger.py` → `reconstruct_positions.py` → `classify_exits.py` → `crosscheck_stage1.py` → `analyze_exits.py` → `make_figures.py` → `write_report.py` (`run_all.py` runs them in order); `matching.py` is the engine |
| `data/` | fill-event ledger, reconstructed position ledger (pieces, 3 conventions), position episodes, fill roles, exit events, consensus table, reconciliation summary |
| `analysis/` | matching sensitivity, profitability, exit patterns, expiry / underlying summaries, decay / hazard / context tables, figures |
| `tests/` | 70 tests (synthetic scenarios + real-data invariants) |

```bash
python3 tp_reconstruction/scripts/run_all.py          # needs ALGO8_MARKET_DIR for the market-context part
python3 -m pytest tp_reconstruction/tests -q
```

Inputs: `Trades_GKOHNP140.csv` (read-only) and the raw Breeze bars. No PR #3 / PR #5 output and no Stage 2 file is an input.
Gross P&L only (the raw file has no charge fields). Everything is in-sample and descriptive; the take-profit rule is not recovered.
