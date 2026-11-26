#!/usr/bin/env python3
"""Export trading sessions from the pinned dataset into the compact binary format read by the C++ engine (A8S1), plus cycles.csv and the frozen D0 waves.
Usage:  python3 export_sessions.py OUT_DIR [--cycles N | --all]   (needs the dataset commit in the local git objects: backtest/bt/gitdata.py)"""
import sys, os, json, struct, argparse
import numpy as np, pandas as pd
R = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
for p in (R, f'{R}/backtest'): sys.path.insert(0, p)
from backtest.recon_bt.engine_run import load_session
def write_session(path, sp, o):
    K = np.asarray(o['K'], float); n = 375
    with open(path, 'wb') as f:
        f.write(b'A8S1'); f.write(struct.pack('<ii', len(K), n)); f.write(K.astype('<f8').tobytes())
        for c in ('open', 'high', 'low', 'close'): f.write(sp[c].values.astype('<f8').tobytes())
        for cp in ('CE', 'PE'):
            for fld in ('open', 'high', 'low', 'close'): f.write(np.ascontiguousarray(o[(cp, fld)], dtype='<f8').tobytes())
if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('out'); ap.add_argument('--cycles', type=int, default=0); ap.add_argument('--all', action='store_true'); ap.add_argument('--list', default=f'{R}/backtest/recon_bt/results/cycles275.csv'); a = ap.parse_args()
    C = pd.read_csv(a.list); 
    if not a.all and a.cycles: C = C.iloc[np.linspace(0, len(C) - 1, a.cycles).astype(int)]
    os.makedirs(a.out, exist_ok=True)
    for r in C.itertuples():
        for day in (r.d1, r.d0):
            sp, o = load_session(r.und, r.expiry, day); write_session(f'{a.out}/{r.und}_{r.expiry}_{day}.a8s', sp, o)
    C[['und', 'expiry', 'd1', 'd0']].assign(lot=C.lot1).to_csv(f'{a.out}/cycles.csv', index=False)
    W = pd.DataFrame(json.load(open(f'{R}/backtest/replication/deep_dive/outputs/phase1/8/frozen_d0_params.json'))['waves'])[['und', 'version', 't', 'lots']]; W.to_csv(f'{a.out}/frozen_d0_waves.csv', index=False); print('exported', len(C), 'cycles')
