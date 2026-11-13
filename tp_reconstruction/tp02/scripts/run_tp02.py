"""Rebuild every TP-02 output in order. python3 tp_reconstruction/tp02/scripts/run_tp02.py   (needs ALGO8_MARKET_DIR; about 20 minutes)"""
import os, sys, subprocess
H = os.path.dirname(os.path.abspath(__file__))
for s in ('build_exit_timelines', 'classify_mechanisms', 'isolate_nonstop_exits', 'analyze_mechanisms', 'analyze_extra', 'test_hypotheses', 'make_figures', 'write_report'):
    print('==', s, flush=True); subprocess.run([sys.executable, os.path.join(H, s + '.py')], check=True, stdout=subprocess.DEVNULL)
print('done')
