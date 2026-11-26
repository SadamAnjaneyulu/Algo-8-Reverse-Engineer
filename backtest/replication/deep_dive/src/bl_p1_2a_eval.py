"""Apply the preregistered acceptance criteria A1-A9 of reports/PHASE1_GATE2A_PLAN.md to every variant run in outputs/phase1/2A. Criteria and baseline values are fixed in the plan; nothing here is tuned."""
import sys, os, json, glob; sys.path.insert(0, '.'); sys.path.insert(0, '../..'); sys.path.insert(0, '../../..')
import numpy as np, pandas as pd, bl_common, bl_p1_eval as E
OUT = bl_common.OUT; D = f'{OUT}/phase1/2A'; B1 = f'{OUT}/scoring/d1_F_v2_onelot'
BASE = dict(F1=0.7586, strict_F1=0.5954, recall=0.7325, precision=0.7866, real_lots=4671, b1_lots=4091, sched_matched=2086, sched_exact=0.669, l1=0.508, cls=dict(wing_buy=0.822, wing_sell=0.497, body_buyback=0.573, opening_wings=0.854, lump=0.328))
def evaluate(d):
    m = E.body_metrics(d); cf = E.class_f1(d); l1 = E.state_l1(d); pc = E.per_cycle_body(d); pc0 = E.per_cycle_body(f'{D}/V00'); better = int((pc.set_index('cyc').F1 > pc0.set_index('cyc').F1 + 1e-12).sum())
    A = {}
    A['A1'] = m['F1'] >= BASE['F1'] + 0.02; A['A2'] = m['strict_F1'] >= BASE['strict_F1'] + 0.01; A['A3'] = (m['recall'] >= BASE['recall'] + 0.02) and (m['precision'] >= BASE['precision'] - 0.01)
    A['A4'] = abs(m['sim_lots'] - BASE['real_lots']) < abs(BASE['b1_lots'] - BASE['real_lots']); A['A5'] = (m['scheduled_matched'] >= 2076) and ((m['scheduled_exact_second_share'] or 0) >= 0.659)
    A['A6'] = all(cf.get(k, 0) >= v - 0.02 for k, v in BASE['cls'].items()); A['A7'] = l1 <= BASE['l1'] + 0.02; A['A8'] = better >= 20
    return dict(metrics=m, class_f1=cf, state_l1=l1, cycles_improved=better, criteria=A, passes_A1_A8=all(A.values()))
if __name__ == '__main__':
    ids = sorted(os.path.basename(p) for p in glob.glob(f'{D}/V*') if os.path.exists(f'{p}/run_record.json')); R = {v: evaluate(f'{D}/{v}') for v in ids}; rows = []
    for v, r in R.items():
        m = r['metrics']; rows.append(dict(id=v, F1=round(m['F1'], 4), strict_F1=round(m['strict_F1'], 4), recall=round(m['recall'], 4), precision=round(m['precision'], 4), sim_lots=m['sim_lots'], extras=m['extras'], missing=m['missing'], sched=f"{m['scheduled_matched']}/{m['scheduled_sim']}", L1=round(r['state_l1'], 3), cyc_better=r['cycles_improved'], **{k: ('PASS' if x else 'fail') for k, x in r['criteria'].items()}))
    T = pd.DataFrame(rows); pd.set_option('display.width', 300); print(T.to_string(index=False))
    # A9: leave-one-cycle-out selection among all variants (best pooled body-sell F1 on the other cycles, keys, 60 s)
    pcs = {v: E.per_cycle_body(f'{D}/{v}').set_index('cyc') for v in ids}; cyc = list(pcs[ids[0]].index); chosen = []; tp_r = tp_s = nr = ns = 0
    for c in cyc:
        others = [x for x in cyc if x != c]; score = {v: E.pooled_f1(pcs[v].loc[others].reset_index()) for v in ids}; best = max(score, key=score.get); chosen.append(best); row = pcs[best].loc[c]; tp_r += row.tp_real; tp_s += row.tp_sim; nr += row.real; ns += row.sim
    loco_f1 = E._f1(tp_s / max(ns, 1), tp_r / nr); modal = pd.Series(chosen).value_counts(); A9 = dict(chosen_counts=modal.to_dict(), modal_share=float(modal.iloc[0] / len(chosen)), loco_pooled_F1=float(loco_f1), passes=bool(modal.iloc[0] / len(chosen) >= 0.8 and loco_f1 >= BASE['F1'] + 0.01))
    print('A9 (leave-one-cycle-out):', json.dumps(A9)); json.dump(dict(variants=R, A9=A9, baseline_values=BASE), open(f'{D}/evaluation.json', 'w'), indent=1, default=float); T.to_csv(f'{D}/evaluation_table.csv', index=False)
