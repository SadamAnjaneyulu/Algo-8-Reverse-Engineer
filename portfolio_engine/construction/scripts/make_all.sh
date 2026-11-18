#!/usr/bin/env bash
# Regenerates the scenarios, example outputs and plots (needs matplotlib).
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHONPATH=python python3 -m pc.cli generate scenarios
python3 tools/make_examples.py examples_output
python3 tools/make_plots.py plots_output
