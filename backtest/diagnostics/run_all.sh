#!/usr/bin/env bash
# Reproduces every diagnostic table/figure. Read-only with respect to backtest/results and backtest/reports.
# Prerequisites: backtest/cache (per-cycle pickles) and backtest/results/engine/* (original engine runs) must exist.
set -euo pipefail
cd "$(dirname "$0")"
python3 sharpe_audit.py
python3 distribution.py
python3 settlement_check.py
python3 settlement_sensitivity.py
python3 leg_attribution.py
python3 regimes.py
python3 mechanism.py
python3 run_plugin_engine.py        # writes ONLY results/engine/HOLD_SETTLE_DXOOS (diagnostic, not selection)
python3 plugin_effect.py
python3 cost_analysis.py
python3 entry_outliers.py
python3 contamination.py
python3 charts.py
