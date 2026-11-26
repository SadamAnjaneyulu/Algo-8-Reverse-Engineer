"""Gate 5a step 1: capture the research simulator's fitted parameter sets (per split) from the UNCHANGED reference code and prove the reference is deterministic by recomputing every saved test-cycle output. Writes outputs/phase1/5a/ref_params.pkl. The reference files are not modified."""
import sys, os, json, hashlib, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
import bl_d0_fr as F
from bl_common import OUT
RES = pd.read_pickle(f'{OUT}/bl_d0_fr_orders.pkl.gz'); PAR = json.load(open(f'{OUT}/bl_d0_fr_params.json')); VER = {i: F.CY.iloc[i].version for i in F.D0C}
vmaps = {'OOF half 0 test': {'V1': 'V1', 'V2': 'V2'}, 'OOF half 1 test': {'V1': 'V1', 'V2': 'V2'}, 'forward A (same version, later cycles)': {'V1': 'V1', 'V2': 'V2'}, 'forward B (train V1, test V2)': {'V2': 'V1', 'V1': 'V1'}}
ref = {}; chk = dict(splits={}, cycles=0, identical=0)
for nm, pr in PAR.items():
    tr, te = pr['train'], pr['test']; P = F.fit(tr, te, vmaps[nm]); ok = (P['k3'] == eval(pr['k3']) if isinstance(pr['k3'], str) else P['k3'] == pr['k3']) and list(P['m1']) == list(pr['m1']) and P['r'] == pr['r'] and P['ow'] == pr['ow']
    ref[nm] = dict(train=tr, test=te, k3=P['k3'], m1=tuple(P['m1']), r=P['r'], ow=P['ow'], W=P['W'].copy()); same = 0
    for i in te:
        a = F.sim(i, P).reset_index(drop=True); b = RES[nm][i].reset_index(drop=True); same += int(a.equals(b)); chk['cycles'] += 1
    chk['identical'] += same; chk['splits'][nm] = dict(params_match_saved_json=bool(ok), test_cycles=len(te), identical_to_saved=same, waves=int(len(P['W'])))
    print(nm, chk['splits'][nm], flush=True)
pd.to_pickle(ref, f'{OUT}/phase1/5a/ref_params.pkl'); chk['ref_params_sha256'] = hashlib.sha256(open(f'{OUT}/phase1/5a/ref_params.pkl', 'rb').read()).hexdigest(); json.dump(chk, open(f'{OUT}/phase1/5a/ref_determinism.json', 'w'), indent=1); print(chk['cycles'], chk['identical'])
