"""Gate 7: true leave-one-cycle-out refit of the D0 fitted parts (research-layer `fit`), resumable. Each fold: train = the other D0 cycles, vmap as OOF/forward A (same version). Writes outputs/phase1/7/loco_params.pkl (dict cid -> params + seconds)."""
import sys, os, time, warnings; sys.path.insert(0, '.'); sys.path.insert(0, '../../../../d0_strategy'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
import bl_d0_fr as F, bl_common
OUT = bl_common.OUT; OD = f'{OUT}/phase1/7'; os.makedirs(OD, exist_ok=True); PK = f'{OD}/loco_params.pkl'
if __name__ == '__main__':
    done = pd.read_pickle(PK) if os.path.exists(PK) else {}; D0C = list(F.D0C); print('cycles', len(D0C), 'done', len(done), flush=True)
    for i in D0C:
        if i in done: continue
        t0 = time.time(); tr = [c for c in D0C if c != i]; P = F.fit(tr, [i], {'V1': 'V1', 'V2': 'V2'}); P['train'] = tr; P['test'] = [i]; P['seconds'] = time.time() - t0; done[i] = P; pd.to_pickle(done, PK); print(i, round(P['seconds']), 's', P['k3'], P['m1'], P['r'], P['ow'], flush=True)
