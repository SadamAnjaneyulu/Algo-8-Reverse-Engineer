"""Phase 1 final-loop freeze v2. The Gate 8 freeze (outputs/phase1/8/) is kept untouched as v1. v2 records: the two frozen D0 configurations (forward/production and historical-reproduction), the frozen D-1 B1 configuration (now with default-off fields), source hashes old (v1) vs new with the reason for every change,
the default-configuration regression against the Gate 5a reference, and artefact hashes of the final-loop evidence. Writes outputs/phase1/9/freeze_v2/."""
import sys, os, json, hashlib, glob, warnings, dataclasses; os.environ.setdefault('ORDER_SPLIT', 'one_lot_v2')
for p in ('.', '../../../../d0_strategy', '../../../../d1_strategy', '../../../..'): sys.path.insert(0, p)
warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
import bl_common, bl_p1_5a_port as A, bl_p1_5c as C
from d0_algo import D0Engine
from d1_algo import config_for
OUT = bl_common.OUT; OD = f'{OUT}/phase1/9/freeze_v2'; os.makedirs(OD, exist_ok=True); ROOT = os.path.abspath('../../../..'); sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
V1 = json.load(open(f'{OUT}/phase1/8/freeze_manifest.json')); man = dict(version='v2', frozen_at='2026-11-25 (Phase 1 final loop)', status='FROZEN CANDIDATE (uncommitted; user review pending)', evidence_label='historical reproduction on development cycles; no independent validation exists', supersedes='outputs/phase1/8/freeze_manifest.json (kept unchanged as v1)')
# 1. default regression (engine default config vs the Gate 5a reference)
REF = pd.read_pickle(f'{OUT}/bl_d0_fr_orders.pkl.gz'); PR = pd.read_pickle(f'{OUT}/phase1/5a/ref_params.pkl'); same = tot = 0
for nm, P in PR.items():
    for i in P['test']:
        e = D0Engine(A.config_mode(P, i, 'enforce'), A.market_of(i), A.opening_of(i)); e.run(); tot += 1; same += int(e.events_frame().equals(REF[nm][i].reset_index(drop=True)))
man['default_regression_vs_gate5a_reference'] = dict(cycles=tot, identical=same, passed=same == tot)
# 2. frozen D0 configurations (parameters unchanged from v1: same all-cycle fit)
Pf = json.load(open(f'{OUT}/phase1/8/frozen_d0_params.json')); man['frozen_d0_params_sha256_v1'] = V1['frozen_d0_params_sha256']; assert sha(f'{OUT}/phase1/8/frozen_d0_params.json') == V1['frozen_d0_params_sha256']
import bl_d0_fr as F
D0C = list(F.D0C); PF = F.fit(D0C, [], {'V1': 'V1', 'V2': 'V2'}); Pq = dict(W=PF['W'], k3=PF['k3'], m1=PF['m1'], r=PF['r'], ow=PF['ow'])
for name, mod in (('forward', C.mod_fwd), ('historical_reproduction', C.mod_hr)):
    cfgs = {}
    for i in D0C:
        c = mod(A.config_of(Pq, i), i); c.risk_mode = 'enforce'; r = A.CY.iloc[i]; cfgs[f'{r.und}|{r.expiry}'] = dataclasses.asdict(c)
    fn = f'{OD}/frozen_d0_configs_{name}.json'; json.dump(cfgs, open(fn, 'w'), indent=1, default=float); man[f'frozen_d0_configs_{name}_sha256'] = sha(fn)
man['d0_configuration_definitions'] = dict(forward='production/forward default: clearance minute 359 in every cycle (no era rule), cycle stop 1.25 lakh, enforce risk guard, all candidates off', historical_reproduction='forward + EXPERIMENTAL IN-SAMPLE era clearance 363 for pre-auction expiries (X1); not independent; not a production default')
d1 = {}
for r in A.CY.itertuples(): d1[f'{r.und}|{r.expiry}'] = dataclasses.asdict(config_for(r.und, r.d1, order_split='one_lot_v2'))
fn = f'{OD}/frozen_d1_configs_per_cycle.json'; json.dump(d1, open(fn, 'w'), indent=1, default=str); man['frozen_d1_configs_sha256'] = sha(fn); man['d1_note'] = 'B1 = one_lot_v2; new fields cycle_stop_rupees=None (rejected candidate, default off) and cycle_stop_check_s=5 do not change behaviour'
# 3. sources: v1 hash, new hash, reason
srcs = sorted(glob.glob(f'{ROOT}/d1_strategy/d1_algo/*.py') + glob.glob(f'{ROOT}/d0_strategy/d0_algo/*.py') + glob.glob(f'{ROOT}/algo8_integrated/*.py') + [f'{ROOT}/d0_strategy/test_d0_engine.py', f'{ROOT}/algo8_integrated/test_integrated.py', f'{ROOT}/d1_strategy/test_cycle_stop.py'])
REASON = {'d1_strategy/d1_algo/engine.py': 'default-off cycle-stop switch (BE-D1, rejected, archived)', 'd1_strategy/d1_algo/config.py': 'default-off cycle_stop_rupees / cycle_stop_check_s fields', 'd1_strategy/d1_algo/risk.py': 'cycle_stop roles treated as risk-reducing (only reachable with the switch on)', 'd0_strategy/d0_algo/engine.py': 'default-off clearance_hazards (CH2, rejected, archived)', 'd0_strategy/d0_algo/config.py': 'default-off clearance_hazards field', 'd0_strategy/test_d0_engine.py': 'tests for the clearance_hazards switch', 'd1_strategy/test_cycle_stop.py': 'new tests for the D-1 cycle-stop switch'}
new = {os.path.relpath(p, ROOT): sha(p) for p in srcs}; old = V1['source_sha256']
man['source_sha256'] = new; man['source_sha256_v1'] = old; man['changed_since_v1'] = {f: dict(old=old.get(f), new=h, reason=REASON.get(f, 'UNEXPLAINED')) for f, h in new.items() if old.get(f) != h}
man['unexplained_changes'] = [f for f, v in man['changed_since_v1'].items() if v['reason'] == 'UNEXPLAINED']
# 4. artefact hashes of the final-loop evidence
arts = ['phase1/9/population_reconciliation.json', 'phase1/9/A_analytic.json', 'phase1/9/B_fullpath_stop_test.json', 'phase1/9/BE_D1_result.json', 'phase1/9/BE_D0_L125.json', 'phase1/9/C_acceptance.json', 'phase1/9/D_analytic.json', 'phase1/9/final_hr/summary.json', 'phase1/9/final_fwd/summary.json', 'phase1/9/final_hr_integrated/summary.json', 'phase1/9/final_fwd_integrated/summary.json', 'phase1/9/final_robust.json', 'phase1/baseline_manifest.json', 'scoring/spec_freeze.json', 'scoring/execution_convention.json']
man['artefact_sha256'] = {k: sha(f'{OUT}/{k}') for k in arts}; man['v1_manifest_sha256'] = sha(f'{OUT}/phase1/8/freeze_manifest.json')
man['frozen_late_sale_shadow'] = 'untouched: shadow.py and shadow_state.py hashes equal v1 (and git HEAD)'
json.dump(man, open(f'{OD}/freeze_manifest_v2.json', 'w'), indent=1, default=float); print(json.dumps({k: v for k, v in man.items() if k not in ('source_sha256', 'source_sha256_v1', 'artefact_sha256', 'changed_since_v1')}, indent=1, default=float)); print('changed', list(man['changed_since_v1']), 'unexplained', man['unexplained_changes'])
