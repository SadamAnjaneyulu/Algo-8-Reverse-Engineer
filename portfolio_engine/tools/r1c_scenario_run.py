"""Run the historical output chain (M2-C, M2-D, M2-E data, case studies, figures) for ONE ordering scenario into an out root, never into the delivered directories.
  python3 portfolio_engine/tools/r1c_scenario_run.py --scenario=baseline|per_contract_id_sequence --out-root=<dir>
The out root starts EMPTY (refused otherwise) so that every file in it was produced by this chain; each tool stamps scenario_id / tie_order_convention / source_hash / generator_version / execution_mode in its manifests."""
import os, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); PE = os.path.dirname(HERE); sys.path.insert(0, os.path.join(PE, 'python'))
from pe import scenario as SC
CHAIN = ['m2c_closing_batches', 'm2d_wing_body', 'm2e_build', 'm2e_cases', 'm2e_charts', 'm2c_charts', 'm2d_charts']      # same order that reproduces the delivered files byte for byte
SCN = SC.from_argv(sys.argv, PE)
if not SCN.out_root: sys.exit('--out-root is required')
if os.path.exists(SCN.out_root) and os.listdir(SCN.out_root): sys.exit(f'out root {SCN.out_root} is not empty')
os.makedirs(SCN.out_root, exist_ok=True); log = []
for t in CHAIN:
    t0 = time.time(); p = subprocess.run([sys.executable, os.path.join(HERE, t + '.py'), f'--scenario={SCN.id}', f'--out-root={SCN.out_root}'], capture_output=True, text=True)
    log.append(f'{t} rc={p.returncode} {round(time.time() - t0)}s'); print(log[-1], flush=True)
    if p.returncode: print(p.stdout[-1500:], p.stderr[-3000:]); sys.exit(1)
open(os.path.join(SCN.out_root, 'chain.log'), 'w').write('\n'.join(log) + '\n')
