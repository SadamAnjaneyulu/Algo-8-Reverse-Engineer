"""Gate 8 freeze: frozen D-1 (B1), D0 (D0-C) and integrated configurations with hashes, default-configuration regression against the Gate 5a reference, source and output hashes.
Nothing is overwritten: writes outputs/phase1/8/ only. The frozen D0 parameters are fitted on ALL 30 D0 cycles (in-sample by construction; no score from them is evidence)."""
import sys, os, json, hashlib, glob, warnings, dataclasses; os.environ.setdefault('ORDER_SPLIT', 'one_lot_v2')
for p in ('.', '../../../../d0_strategy', '../../../../d1_strategy', '../../../..'): sys.path.insert(0, p)
warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
import bl_common, bl_d0_fr as F, bl_p1_5a_port as A, bl_p1_5b as B, bl_p1_5c as C, bl_oscore as Q
from d0_algo import D0Engine
from d1_algo import config_for
OUT = bl_common.OUT; OD = f'{OUT}/phase1/8'; os.makedirs(OD, exist_ok=True); ROOT = os.path.abspath('../../../..'); sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest(); sj = lambda o: hashlib.sha256(json.dumps(o, sort_keys=True, default=str).encode()).hexdigest()
man = dict(frozen_at='2026-11-25', status='FROZEN CANDIDATE for Phase 1 closure (uncommitted; user review pending)', evidence_label='historical reproduction on development cycles; no independent validation exists')
# ---- 1. default-configuration regression vs the Gate 5a reference (the engine, not the stored JSON)
REF = pd.read_pickle(f'{OUT}/bl_d0_fr_orders.pkl.gz'); PR = pd.read_pickle(f'{OUT}/phase1/5a/ref_params.pkl'); same = tot = 0
for nm, P in PR.items():
    for i in P['test']:
        e = D0Engine(A.config_mode(P, i, 'enforce'), A.market_of(i), A.opening_of(i)); e.run(); tot += 1; same += int(e.events_frame().equals(REF[nm][i].reset_index(drop=True)))
man['default_regression_vs_gate5a_reference'] = dict(cycles=tot, identical=same, passed=same == tot)
# ---- 2. frozen D0 parameters (all-cycle fit) and frozen configs
D0C = list(F.D0C); PF = F.fit(D0C, [], {'V1': 'V1', 'V2': 'V2'}); W = PF['W']
frozen_d0 = dict(fit_cycles=D0C, theta=PF['k3']['theta'], take_profit=PF['k3'].get('tp'), ladder=dict(step=PF['m1'][0], gate_min=PF['m1'][1], multi_lot=bool(PF['m1'][2])), counter_ratio=PF['r'], opening_wings_lots=PF['ow'], waves=W.assign(version=W.version.astype(str)).to_dict('records'),
    era_clearance=dict(boundary_expiry='2026-08-03', pre_auction_minute=363, post_auction_minute=359), cycle_stop_rupees=1.2e5, risk=dict(mode='enforce', max_short_lots_per_right=306, max_sell_decisions_per_minute=90), switches_default='all rules on; Gate 5c candidate X3 (opening_long_clock) OFF (rejected)')
json.dump(frozen_d0, open(f'{OD}/frozen_d0_params.json', 'w'), indent=1, default=float); man['frozen_d0_params_sha256'] = sha(f'{OD}/frozen_d0_params.json')
Pf = dict(W=W, k3=PF['k3'], m1=PF['m1'], r=PF['r'], ow=PF['ow']); cfgs = {}
for i in D0C:
    c = C.mod_clk(363)(A.config_of(Pf, i), i); c.risk_mode = 'enforce'; r = A.CY.iloc[i]; cfgs[f'{r.und}|{r.expiry}'] = dataclasses.asdict(c)
json.dump(cfgs, open(f'{OD}/frozen_d0_configs_per_cycle.json', 'w'), indent=1, default=float); man['frozen_d0_configs_sha256'] = sha(f'{OD}/frozen_d0_configs_per_cycle.json')
# in-sample sanity run (labelled; NOT evidence)
items = []
for i in D0C:
    c = C.mod_clk(363)(A.config_of(Pf, i), i); c.risk_mode = 'enforce'; e = D0Engine(c, A.market_of(i), A.opening_of(i)); e.run(); items.append((i, e))
real = B.real_frame(D0C); attrs = B.attrs_of(D0C, real); R = Q.score(real, B.sim_frame(items), attrs, 'T', 'historical reproduction', shift_placebo=False, bootstrap=0); st = R['strictness']
man['frozen_d0_in_sample_check'] = dict(keys_F1_60s=float(st[(st.cumulative_tolerance_s == 60) & (st.level == 'keys')].F1.iloc[0]), label='in-sample all-cycle fit; not independent; shown only to prove the frozen file runs')
# ---- 3. frozen D-1 B1 configs
d1 = {}
for r in bl_common.ref.__dict__.get('CY', A.CY).itertuples():
    cfg = config_for(r.und, r.d1, order_split='one_lot_v2'); d1[f'{r.und}|{r.expiry}'] = dataclasses.asdict(cfg)
json.dump(d1, open(f'{OD}/frozen_d1_configs_per_cycle.json', 'w'), indent=1, default=str); man['frozen_d1_configs_sha256'] = sha(f'{OD}/frozen_d1_configs_per_cycle.json'); man['d1_order_split'] = 'one_lot_v2 (accepted execution convention; B1)'
# ---- 4. source and artefact hashes
srcs = sorted(glob.glob(f'{ROOT}/d1_strategy/d1_algo/*.py') + glob.glob(f'{ROOT}/d0_strategy/d0_algo/*.py') + glob.glob(f'{ROOT}/algo8_integrated/*.py') + [f'{ROOT}/d0_strategy/test_d0_engine.py', f'{ROOT}/algo8_integrated/test_integrated.py'])
man['source_sha256'] = {os.path.relpath(p, ROOT): sha(p) for p in srcs}
man['artefact_sha256'] = {k: sha(f'{OUT}/{k}') for k in ('phase1/baseline_manifest.json', 'phase1/5d/summary.json', 'phase1/5d/standards.json', 'phase1/6/summary.json', 'phase1/6/acceptance.json', 'phase1/7/tests.json', 'phase1/5c/acceptance.json', 'scoring/spec_freeze.json', 'scoring/execution_convention.json')}
man['frozen_scoring_spec'] = 'spec v1.1 (outputs/scoring/spec_freeze.json); one_lot_v2 execution convention'; man['frozen_late_sale_shadow'] = 'untouched: d1_strategy/d1_algo/shadow.py and shadow_state.py identical to git HEAD'
json.dump(man, open(f'{OD}/freeze_manifest.json', 'w'), indent=1, default=float)
print(json.dumps({k: v for k, v in man.items() if k not in ('source_sha256', 'artefact_sha256')}, indent=1, default=float)[:2500])
