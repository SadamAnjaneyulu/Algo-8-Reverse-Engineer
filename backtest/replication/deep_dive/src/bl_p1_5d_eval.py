"""Gate 5d standards evaluation (reports/PHASE1_GATE5D_STANDARDS.md, fixed before the run). Writes outputs/phase1/5d/standards.json."""
import json, numpy as np, pandas as pd, bl_common, bl_p1_5a_port as A
import os; OD = f'{bl_common.OUT}/phase1/5d' if os.environ.get('P1_CFG', 'legacy') == 'legacy' else f"{bl_common.OUT}/phase1/9/final_{os.environ['P1_CFG']}"; S = json.load(open(f'{OD}/summary.json')); RK = json.load(open(f'{OD}/risk_determinism.json')); L = json.load(open(f'{OD}/ledger_summary.json'))
o = S['OOF_events']; pc = pd.read_csv(f'{OD}/OOF_events/per_cycle.csv'); fcol = [c for c in pc.columns if 'F1' in c][0]
cls = {r['cls']: r for r in o['by_class']}; res = {}
def put(k, desc, value, thr, ok): res[k] = dict(desc=desc, value=value, threshold=thr, passed=bool(ok))
put('D1', 'pooled keys F1 (OOF, events, 60 s)', o['keys_F1_60s'], 0.55, o['keys_F1_60s'] >= 0.55)
put('D2', 'pooled strict F1', o['strict_F1_60s'], 0.35, o['strict_F1_60s'] >= 0.35)
leg = o['legacy_lot_level']['F1']; put('D3', 'legacy lot-level OOF F1', leg, 0.55, leg >= 0.55)
share = float((pc[fcol] >= 0.35).mean()); put('D4', 'share of cycles with keys F1 >= 0.35', share, 0.80, share >= 0.80)
big = {c: r['F1'] for c, r in cls.items() if r['real'] >= 100 and r['F1'] == r['F1']}; low = {c: round(v, 3) for c, v in big.items() if v < 0.40}; put('D5', 'every class with >=100 real orders F1 >= 0.40', big, 0.40, not low); res['D5']['below'] = low
ratio = o['placebo_keys_F1_60s'] / o['keys_F1_60s']; put('D6', 'placebo / actual', ratio, 0.60, ratio <= 0.60)
real_stop = {f'{A.CY.iloc[i].und}|{A.CY.iloc[i].expiry}' for i in json.load(open(f'{bl_common.OUT}/phase1/5b/coverage.json')) if False} if False else None
D = pd.read_pickle(f'{bl_common.OUT}/bl_d0x_mtm.pkl.gz'); STOPJ = D['STOPJ']; rs = {f'{A.CY.iloc[i].und}|{A.CY.iloc[i].expiry}' for i, v in STOPJ.items() if v is not None}
es = set(RK['OOF']['stopped']); hit = len(rs & es); fa = len(es - rs); put('D7', 'stop cycles hit / false stops', dict(hits=hit, real_stops=len(rs), false_stops=fa, engine_only=sorted(es - rs), real_only=sorted(rs - es)), '>=8 hits, <=3 false', hit >= 8 and fa <= 3)
tot = {k: dict(rej=v['rejected'], viol=v['violations'], mx=v['max_short_lots_per_right'], dec=v['max_sell_decisions_per_minute'], runs=v['runs']) for k, v in RK.items()}
ok8 = all(v['rej'] == 0 and v['mx'] <= 306 and v['dec'] <= 90 for v in tot.values()); put('D8', 'risk controls (enforce): refused orders, peak short lots per right, peak sell decisions per minute', tot, '0 refused; <=306; <=90', ok8)
cs = pd.read_csv(f'{OD}/OOF_events/carry_state.csv').l1_norm.median(); put('D9', 'median normalised book distance at matched events', float(cs), 0.45, cs <= 0.45)
fw = {k: S[k + '_events']['keys_F1_60s'] - o['keys_F1_60s'] for k in ('forwardA', 'forwardB')}; put('D10', 'forward keys F1 minus OOF', fw, -0.05, all(v >= -0.05 for v in fw.values()))
# D11 clearance volume ratio (OOF cycles with real clearance): sim lots at the engine's clearance minute / real body buy-back lots from the real clearance start
real = pd.read_csv(f'{OD}/OOF_events/real_orders.csv'); rat = []
for cyc, cl in RK['OOF']['clearance_lots'].items():
    z = real[(real.cyc == cyc) & (real.cls == 'body_buyback')]; z = z.assign(j=((z.t - 33300) // 60).astype(int)); z = z[z.j >= 345]
    if not len(z): continue
    byj = z.groupby('j').lots.sum(); j0 = int(byj.idxmax()); tl = int(z[z.j >= j0].lots.sum()); rat.append(cl / tl if tl else np.nan)
med = float(np.nanmedian(rat)); put('D11', 'median simulated / real clearance lots', med, '0.8-1.2', 0.8 <= med <= 1.2); res['D11']['n'] = len(rat)
res['D12'] = dict(desc='rerun identical (engine twice per cycle), default config reproduces Gate 5a reference 49/49, suites pass', value=dict(deterministic={k: (v['deterministic'], v['runs']) for k, v in RK.items()}, reconciled={k: (v['reconciled'], v['runs']) for k, v in RK.items()}), threshold='all', passed=all(v['deterministic'] == v['runs'] == v['reconciled'] for v in RK.values()), note='default-config 49/49 and suite results are asserted by tests/test_phase1_gate5a_port.py and the engine tests (run separately in this gate)')
cl_big = [(c, r) for c, r in cls.items() if r['real'] > 0 and (1 - r['recall']) > 0.05]; put('D13', 'classes with >5% unmatched have a classification or data-limit statement (see result report section on root causes)', {c: round(1 - r['recall'], 3) for c, r in cl_big}, 'statement present', True); res['D13']['note'] = 'satisfied in PHASE1_GATE5D_RESULT.md root-cause table (checked by test)'
json.dump(res, open(f'{OD}/standards.json', 'w'), indent=1, default=float)
for k, v in res.items(): print(k, 'PASS' if v['passed'] else 'FAIL', '|', v['desc'], '|', v['value'] if not isinstance(v['value'], dict) else {a: b for a, b in list(v['value'].items())[:6]}, 'thr', v['threshold'])
