"""Rebuild every TP-01 output from the raw file in order. python3 tp_reconstruction/scripts/run_all.py
Needs ALGO8_MARKET_DIR (raw Breeze bars) for analyze_exits.py and the Stage 1 caches for crosscheck_stage1.py (skipped if absent)."""
import os, sys, subprocess
H = os.path.dirname(os.path.abspath(__file__))
for s in ('build_event_ledger', 'reconstruct_positions', 'classify_exits', 'crosscheck_stage1', 'analyze_exits', 'make_figures', 'write_report'):
    print('==', s, flush=True); subprocess.run([sys.executable, os.path.join(H, s + '.py')], check=True, stdout=subprocess.DEVNULL)
print('done')
