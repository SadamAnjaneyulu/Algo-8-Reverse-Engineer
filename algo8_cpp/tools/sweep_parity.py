#!/usr/bin/env python3
"""Full parity sweep: C++ vs the Python reference on every cycle and stop level (NONE, 125000, 200000).
Exports sessions in chunks (disk friendly), runs algo8_backtest, compares with backtest/recon_bt/results/runs.pkl.   Usage: sweep_parity.py BUILD_DIR [CHUNK=20]"""
import sys, os, pickle, shutil, subprocess, tempfile, json
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); R = os.path.abspath(os.path.join(HERE, '..', '..')); sys.path.insert(0, R); sys.path.insert(0, f'{R}/backtest'); sys.path.insert(0, HERE)
from export_sessions import write_session
from backtest.recon_bt.engine_run import load_session
build = sys.argv[1]; chunk = int(sys.argv[2]) if len(sys.argv) > 2 else 20
runs = pickle.load(open(f'{R}/backtest/recon_bt/results/runs.pkl', 'rb')); C = pd.read_csv(f'{R}/backtest/recon_bt/results/cycles275.csv'); LV = {'NONE': 0, 'S125': 125000, 'S200': 200000}
rows = []; worst = {k: 0.0 for k in ('gross', 'slippage', 'costs', 'net', 'min_path', 'max_path')}; mism = 0
for i0 in range(0, len(C), chunk):
    part = C.iloc[i0:i0 + chunk]; d = tempfile.mkdtemp(prefix='a8sweep_', dir='/tmp')
    try:
        for r in part.itertuples():
            for day in (r.d1, r.d0): sp, o = load_session(r.und, r.expiry, day); write_session(f'{d}/{r.und}_{r.expiry}_{day}.a8s', sp, o)
        part[['und', 'expiry', 'd1', 'd0']].assign(lot=part.lot1).to_csv(f'{d}/cycles.csv', index=False)
        for name, L in LV.items():
            subprocess.run([f'{build}/algo8_backtest', '--cycles', f'{d}/cycles.csv', '--data', d, '--waves', f'{R}/algo8_cpp/data/frozen_d0_waves.csv', '--stop', str(L), '--out', f'{d}/out_{name}', '--threads', '4'], check=True, stdout=subprocess.DEVNULL)
            led = pd.read_csv(f'{d}/out_{name}/ledger.csv')
            for r in led.itertuples():
                p = runs[(name, r.und, r.expiry)]
                for col, pv in (('gross', p['gross']), ('slippage', p['slippage']), ('costs', p['costs']), ('net', p['net']), ('min_path', p['min_path']), ('max_path', p['max_path'])): worst[col] = max(worst[col], abs(pv - getattr(r, col)))
                flags = (int(p['n_orders']) == r.n_orders, int(p['n_fills']) == r.n_fills, bool(p['d1_stopped']) == bool(r.d1_stopped), bool(p['d0_stopped']) == bool(r.d0_stopped), (p['stop_minute'] if p['stop_minute'] is not None else -1) == r.stop_minute)
                if not all(flags): mism += 1; print('MISMATCH', name, r.und, r.expiry, flags)
                rows.append((name, r.und, r.expiry))
    finally: shutil.rmtree(d, ignore_errors=True)
    print(f'chunk {i0}-{i0 + len(part)} done', flush=True)
res = dict(runs_compared=len(rows), cycles=len(C), levels=list(LV), worst_abs_difference=worst, count_or_flag_mismatches=mism, parity_ok=bool(mism == 0 and max(worst.values()) < 1e-3))
json.dump(res, open(f'{R}/algo8_cpp/docs/parity_sweep.json', 'w'), indent=1); print(res)
