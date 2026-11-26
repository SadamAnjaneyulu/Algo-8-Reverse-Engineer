"""Run all 275 cycles at the three preregistered stop levels (NONE, S125 = 1.25 lakh, S200 = 2.0 lakh). Resumable; writes results/runs.pkl (list of cycle rows incl. equity paths)."""
import sys, os, time, pickle
R = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
for p in (R, f'{R}/backtest'): sys.path.insert(0, p)
from multiprocessing import Pool
import pandas as pd
from recon_bt.engine_run import run_cycle
LEVELS = {'NONE': None, 'S125': 125000.0, 'S200': 200000.0}; OUT = f'{R}/backtest/recon_bt/results/runs.pkl'
if __name__ == '__main__':
    C = pd.read_csv(f'{R}/backtest/recon_bt/results/cycles275.csv'); done = pickle.load(open(OUT, 'rb')) if os.path.exists(OUT) else {}
    tasks = [(name, dict(und=r.und, expiry=r.expiry, d1=r.d1, d0=r.d0, lot=int(r.lot1), L=L)) for name, L in LEVELS.items() for r in C.itertuples() if (name, r.und, r.expiry) not in done]
    print('tasks', len(tasks), flush=True); t0 = time.time()
    def key(n, t): return (n, t['und'], t['expiry'])
    with Pool(4) as p:
        for n, (name, t) in enumerate(tasks):
            pass
        it = p.imap_unordered(run_cycle, [t for _, t in tasks], chunksize=1); idx = {(t['und'], t['expiry'], t['L']): name for name, t in tasks}
        for k, r in enumerate(it):
            name = idx[(r['und'], r['expiry'], r['L'])]; done[(name, r['und'], r['expiry'])] = r
            if k % 25 == 0 or k == len(tasks) - 1: pickle.dump(done, open(OUT, 'wb')); print(k + 1, '/', len(tasks), round(time.time() - t0), 's', flush=True)
    pickle.dump(done, open(OUT, 'wb')); print('done', len(done))
