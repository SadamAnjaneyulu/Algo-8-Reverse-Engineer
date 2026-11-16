#!/usr/bin/env bash
# TP-03 Phase 1 (entry reconstruction only): full chain, in order. Needs ALGO8_MARKET_DIR (raw 1-minute Breeze bars). Takes about 25 minutes on 4 cores.
set -euo pipefail
S="$(cd "$(dirname "$0")" && pwd)"
python3 "$S/p1_dataset.py"; python3 "$S/p1_e2_run.py"; python3 "$S/p1_descriptive.py"; python3 "$S/p1_structure_tests.py"; python3 "$S/p1_timeline_b6.py"; python3 "$S/p1_e5_diagnostic.py"; python3 "$S/p1_holm.py"
