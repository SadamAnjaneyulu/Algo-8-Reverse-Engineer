#!/usr/bin/env bash
# Reproduces the D0 reconstruction. Discovery steps first; the holdout steps need results/FREEZE.json (written by freeze.py after the rule set is fixed).
set -euo pipefail; cd "$(dirname "$0")"
python3 build_events.py; python3 build_lineage.py; python3 build_snapshots.py; python3 build_final_snapshot.py     # Phase A (all cycles; no rule fitting)
python3 b_replacement.py; python3 c_clockb_discovery.py; python3 c_offschedule_discovery.py                         # Phases B, C (discovery only)
python3 fit_discovery.py                                                                                           # discovery-only parameter fit -> rules_d0_v1.json
# python3 freeze.py   # already executed and committed (40642216); re-running would change the timestamp
for v in NULL V0 V1; do python3 run_replay.py $v DISCOVERY; python3 compare_events.py results/replay_orders_DISCOVERY_$v.csv DISCOVERY discovery_$v; done
for v in NULL V0 V1; do python3 run_replay.py $v HOLDOUT; python3 compare_events.py results/replay_orders_HOLDOUT_$v.csv HOLDOUT holdout_$v; done
python3 latency_sensitivity.py; python3 mismatch_report.py; python3 build_lineage_lifo.py; python3 pnl_attribution.py; python3 figures.py
