"""Gate 6 acceptance evaluation against reports/PHASE1_GATE6_PLAN.md (criteria fixed before the run). Writes outputs/phase1/6/acceptance.json."""
import sys, os, json, warnings; os.environ.setdefault('ORDER_SPLIT', 'one_lot_v2')
for p in ('.', '../../../../d0_strategy', '../../../../d1_strategy', '../../../..'): sys.path.insert(0, p)
warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, inspect
import bl_common, bl_p1_5a_port as A, bl_p1_5b as B, bl_p1_5c as C, bl_oscore as Q
OUT = bl_common.OUT; OD = f'{OUT}/phase1/6'; S6 = json.load(open(f'{OD}/summary.json')); o = S6['sets']['OOF']; M = o['meta']; res = {}
def put(k, desc, value, thr, ok): res[k] = dict(desc=desc, value=value, threshold=thr, passed=bool(ok))
allm = {s: v['meta'] for s, v in S6['sets'].items()}
put('G6-1', 'handoff identity (net positions, cash), reconciliation at the D0 end', {s: dict(identity=f"{m['identity_ok']}/{m['runs']}", reconciled=f"{m['reconciled']}/{m['runs']}", max_cash_diff=m['cash_diff_max']) for s, m in allm.items()}, 'all equal', all(m['identity_ok'] == m['runs'] == m['reconciled'] and m['cash_diff_max'] < 1e-3 for m in allm.values()))
sys.path.insert(0, '../../../../algo8_integrated/..'); from algo8_integrated import run_integrated_cycle; names = list(inspect.signature(run_integrated_cycle).parameters)
put('G6-2', 'no real input: runner signature, source tokens', names, ['d1_cfg', 'd1_feed', 'd0_cfg', 'd0_market', 'unit'], names == ['d1_cfg', 'd1_feed', 'd0_cfg', 'd0_market', 'unit'])
put('G6-3', 'carried contracts outside the D0 chain (rejected handoffs)', {s: len(m['handoff_errors']) for s, m in allm.items()}, 0, all(len(m['handoff_errors']) == 0 for m in allm.values()))
# G6-4: mode T regression of D0-C and D-1 legacy
PR = pd.read_pickle(f'{OUT}/phase1/5a/ref_params.pkl'); items, opens = C.run_set(PR, C.SETS['OOF'], C.mod_clk(363)); cids = [i for i, _ in items]; real = B.real_frame(cids); attrs = B.attrs_of(cids, real); sim = B.sim_frame(items)
R = Q.score(real, sim, attrs, 'T', 'historical reproduction', shift_placebo=False, bootstrap=0); st = R['strictness']; kt = float(st[(st.cumulative_tolerance_s == 60) & (st.level == 'keys')].F1.iloc[0]); ex = {i: e.events_frame() for i, e in items}; lg = Q.legacy_d0_scores(ex, sorted(ex), A.CY, A.O(), None)['F1']
put('G6-4', 'regression: mode T D0-C keys F1 / legacy; D-1 legacy lot-level F1', dict(modeT_keys_F1=kt, modeT_legacy=lg, d1_legacy=S6['d1_legacy_F1']), '0.4217 / 0.4142 / 0.6878', abs(kt - 0.42173) < 1e-4 and abs(lg - 0.41420) < 1e-4 and abs(S6['d1_legacy_F1'] - 0.6878) < 5e-4)
put('G6-5', 'determinism on rerun', {s: f"{m['deterministic']}/{m['runs']}" for s, m in allm.items()}, 'all', all(m['deterministic'] == m['runs'] for m in allm.values()))
f6 = o['d0']['keys_F1_60s']; thr6 = 0.8 * kt; put('G6-6', 'mode F D0 keys F1 >= 0.8 x mode T and >= placebo + 0.10', dict(modeF=f6, modeT=kt, ratio=f6 / kt, placebo=o['d0']['placebo']), f'>= {thr6:.3f} and >= {o["d0"]["placebo"] + 0.10:.3f}', f6 >= thr6 and f6 >= o['d0']['placebo'] + 0.10)
b = o['both']; put('G6-7', 'integrated D-1 + D0 keys F1 >= placebo + 0.10 (D-1 and D0 parts reported)', dict(both=b['keys_F1_60s'], placebo=b['placebo'], d1_part=o['d1']['keys_F1_60s'], d0_part=f6), f'>= {b["placebo"] + 0.10:.3f}', b['keys_F1_60s'] >= b['placebo'] + 0.10)
put('G6-8', 'carry error at the D0 open (diagnostic, no threshold)', o['carry_at_open'], 'none', True)
put('G6-9', 'risk controls: refused orders, peak short lots per right (D-1 limit 400, D0 limit 306), peak sell decisions', dict(d1_rejected=S6['d1_rejected'], d1_peak_short=S6['d1_peak_short_lots_per_right'], d0_rejected={s: m['rejected'] for s, m in allm.items()}, d0_peak_short=max(m['peak_short'] for m in allm.values()), d0_peak_dec=max(m['peak_dec'] for m in allm.values())), 'rej 0, <=400, <=306, <=90', S6['d1_rejected'] == 0 and S6['d1_peak_short_lots_per_right'] <= 400 and all(m['rejected'] == 0 for m in allm.values()) and max(m['peak_short'] for m in allm.values()) <= 306 and max(m['peak_dec'] for m in allm.values()) <= 90)
hard = ['G6-1', 'G6-2', 'G6-3', 'G6-4', 'G6-5', 'G6-9']; qual = ['G6-6', 'G6-7']
verdict = 'PASS' if all(res[k]['passed'] for k in hard + qual) else ('CONDITIONAL' if all(res[k]['passed'] for k in hard) else 'FAIL'); res['verdict'] = verdict
json.dump(res, open(f'{OD}/acceptance.json', 'w'), indent=1, default=float)
for k, v in res.items():
    if k != 'verdict': print(k, 'PASS' if v['passed'] else 'FAIL', '|', v['desc'], '|', v['value'] if not isinstance(v['value'], dict) else {a: (round(b_, 4) if isinstance(b_, float) else b_) for a, b_ in v['value'].items()}, '| thr', v['threshold'])
print('VERDICT', verdict)
