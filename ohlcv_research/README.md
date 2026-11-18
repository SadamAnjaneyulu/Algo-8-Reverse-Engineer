# OHLCV indicator discovery and alpha research

Separate research package (branch `research/algo8-ohlcv-indicator-alpha`). It reads the clean ledger and the Breeze OHLCV files and writes
only inside this folder. `alpha_freeze/`, the stop models and earlier findings are not modified.

**Track A** (does Algo 8 use OHLCV-derived conditions?) and **Track B** (independent alpha) are kept separate throughout.

| Phase | Deliverable | Status |
|---|---|---|
| 0 | [`data_manifest.md`](data_manifest.md), [`data_audit.py`](data_audit.py) | Done — awaiting review |
| 1 | [`OHLCV_FEATURE_CATALOG.md`](OHLCV_FEATURE_CATALOG.md), [`features.py`](features.py), [`tests/`](tests/) | Done — awaiting review |
| 2 design | [`OPPORTUNITY_PANEL_DESIGN.md`](OPPORTUNITY_PANEL_DESIGN.md) | Proposed — not run |
| 2 | `ALGO8_INDICATOR_TRIGGER_FINDINGS.md` | Not started (blocked on review) |
| 3 | `ALPHA_HYPOTHESIS_REGISTER.md` | Not started |
| 4 | `ALPHA_SCREENING_RESULTS.csv` | Not started |
| 5 | `ALPHA_BACKTEST_RESULTS.csv` | Not started |
| 6 | `RESEARCH_DECISION_REPORT.md` | Not started |

Run (market files are on branch `data/local-breeze-fetch`):

```bash
export ALGO8_MARKET_DIR=/path/to/data/breeze/normalized
```

```bash
python3 ohlcv_research/data_audit.py
```

```bash
python3 ohlcv_research/build_features.py
```

```bash
python -m pytest ohlcv_research/tests -q
```
