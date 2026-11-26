#!/usr/bin/env bash
# Parity test: run the C++ backtest on the shipped sample and compare with the Python reference ledger (tolerance 1e-3 rupees).
set -e
BUILD=${1:-build}; HERE="$(cd "$(dirname "$0")/.." && pwd)"
"$BUILD/algo8_backtest" --cycles "$HERE/data/sample/cycles.csv" --data "$HERE/data/sample" --waves "$HERE/data/frozen_d0_waves.csv" --stop 200000 --out "$BUILD/parity_out" --threads 2 > /dev/null
python3 "$HERE/tests/compare_ledgers.py" "$HERE/data/sample/expected_ledger_S200.csv" "$BUILD/parity_out/ledger.csv" 1e-3
