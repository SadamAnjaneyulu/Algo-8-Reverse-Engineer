"""Apply the preregistered criteria L1-L8 of reports/PHASE1_GATE2C_PLAN.md to the 2C candidates."""
import sys, os, json; sys.path.insert(0, '.'); sys.path.insert(0, '../..'); sys.path.insert(0, '../../..')
import numpy as np, pandas as pd, bl_common, bl_p1_eval as E, bl_fr_sim as S
OUT = bl_common.OUT; D = f'{OUT}/phase1/2C'; B1 = f'{OUT}/scoring/d1_F_v2_onelot'; CAS = '2026-08-03'; T0 = 33300 + 360 * 60
post = [f'{r.und}|{r.expiry}' for r in S.CY.itertuples() if r.d1 >= CAS]; pre = [f'{r.und}|{r.expiry}' for r in S.CY.itertuples() if r.d1 < CAS]
b1w = E.window_metrics(B1, T0, post); b1m = E.body_metrics(B1); b1cf = E.class_f1(B1); b1l1 = E.state_l1(B1); b1sim = pd.read_csv(f'{B1}/sim_orders.csv'); res = {'B1_window': {k: v for k, v in b1w.items() if k != 'per_cycle_F1'}}
for v in ('C1', 'C2'):
    d = f'{D}/{v}'; w = E.window_metrics(d, T0, post); m = E.body_metrics(d); cf = E.class_f1(d); l1 = E.state_l1(d); rr = json.load(open(f'{d}/run_record.json')); sim = pd.read_csv(f'{d}/sim_orders.csv')
    cols = list(b1sim.columns); same_pre = all(sim[sim.cyc == c][cols].astype(str).reset_index(drop=True).equals(b1sim[b1sim.cyc == c][cols].astype(str).reset_index(drop=True)) for c in pre)
    better = sum(w['per_cycle_F1'].get(c, 0) > b1w['per_cycle_F1'].get(c, 0) + 1e-12 for c in post)
    A = {'L1': w['F1'] >= b1w['F1'] + 0.05, 'L2': (w['recall'] >= b1w['recall'] + 0.05) and (w['precision'] >= b1w['precision'] - 0.02), 'L3': m['F1'] >= 0.7586 - 0.005 and m['strict_F1'] >= 0.5954 - 0.005, 'L4': bool(same_pre), 'L5': m['scheduled_matched'] >= 2076 and (m['scheduled_exact_second_share'] or 0) >= 0.659,
         'L6': all(cf.get(k, 0) >= b1cf[k] - 0.02 for k in ('wing_buy', 'wing_sell', 'body_buyback', 'opening_wings', 'lump')) and l1 <= b1l1 + 0.02 and rr['legacy_f1'] >= 0.6878 - 0.005, 'L7': better >= 12}
    res[v] = dict(window={k: x for k, x in w.items() if k != 'per_cycle_F1'}, overall=dict(F1=m['F1'], strict_F1=m['strict_F1'], recall=m['recall'], precision=m['precision'], extras=m['extras'], missing=m['missing'], sim_lots=m['sim_lots']), class_f1=cf, state_l1=l1, legacy_f1=rr['legacy_f1'], window_cycles_improved=better, criteria=A, passes_all=all(A.values()))
    print(v, 'window F1', round(w['F1'], 4), 'rec', round(w['recall'], 3), 'prec', round(w['precision'], 3), '| overall F1', round(m['F1'], 4), 'strict', round(m['strict_F1'], 4), 'legacy', round(rr['legacy_f1'], 4), '| cycles improved', better, '/', len(post), '| criteria', {k: ('PASS' if x else 'fail') for k, x in A.items()}, '| pre-auction identical', same_pre)
json.dump(res, open(f'{D}/evaluation.json', 'w'), indent=1, default=float)
