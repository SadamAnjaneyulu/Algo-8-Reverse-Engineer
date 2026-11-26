"""Acceptance evaluation of clearance candidates CH1/CH2 against reports/PHASE1_LOOP2_C_PLAN.md section 4 (fixed before the runs). Writes outputs/phase1/9/C_acceptance.json."""
import json, os, numpy as np, pandas as pd, bl_common, bl_p1_5c_eval as E
OD = f'{bl_common.OUT}/phase1/9'; R = {n: json.load(open(f'{OD}/C_{n}.json')) for n in ('V0', 'X1', 'CH1', 'CH2')}; X = pd.read_csv(f'{OD}/C_clearance_measures.csv'); T = {n: pd.DataFrame(r['timing']) for n, r in R.items()}
err = lambda n, era: T[n][T[n].era == era].set_index('i').err.dropna()
res = {}
for n in ('CH1', 'CH2'):
    c = {}; pre = {k: err(k, 'before') for k in ('V0', 'X1', n)}; post = {k: err(k, 'after') for k in ('V0', n)}
    ca1a = pre[n].mean() <= 0.85 * pre['X1'].mean(); ca1b = pre[n].mean() <= 0.5 * pre['V0'].mean(); ca1c = post[n].mean() <= post['V0'].mean() + 0.05
    c['CA1'] = dict(pre_err=dict(V0=pre['V0'].mean(), X1=pre['X1'].mean(), cand=pre[n].mean()), post_err=dict(V0=post['V0'].mean(), cand=post[n].mean()), legs=dict(le_0_85_X1=bool(ca1a), le_0_5_V0=bool(ca1b), post_not_worse=bool(ca1c)), passed=bool(ca1a and ca1b and ca1c))
    o, b = R[n]['OOF'], R['X1']['OOF']; c['CA2'] = dict(cand=o['one_lot']['win_clear_buyback_all']['F1'], X1=b['one_lot']['win_clear_buyback_all']['F1'], passed=bool(o['one_lot']['win_clear_buyback_all']['F1'] >= b['one_lot']['win_clear_buyback_all']['F1']))
    g = E.evaluate(n, R['X1'], R[n]); gen = {k: v for k, v in g['criteria'].items() if isinstance(v, list)}; c['CA3'] = dict(detail={k: [v[0], v[1], v[2]] for k, v in gen.items() if k[:2] in ('C1', 'C2', 'C3', 'C4', 'C5')}, passed=all(v[2] for k, v in gen.items() if k[:2] in ('C1', 'C2', 'C3', 'C4', 'C5')))
    clk = {era: {i: v['clock'] for i, v in R[n]['constants'].items() if int(i) in set(X[X.era == era].i)} for era in ('before', 'after')}; share = {era: max(pd.Series(d).value_counts().iloc[0] / len(d) for d in [clk[era]]) for era in clk}; c['CA4'] = dict(modal_share=share, passed=all(v >= 0.8 for v in share.values()))
    d = (pre['X1'] - pre[n]); loo = {int(i): float((d.drop(i)).mean()) for i in d.index}; d0 = (pre['V0'] - pre[n]); loo0 = {int(i): float((d0.drop(i)).mean()) for i in d0.index}; c['CA5'] = dict(min_leave_one_out_gain_vs_X1=min(loo.values()), min_leave_one_out_gain_vs_V0=min(loo0.values()), passed=bool(min(loo.values()) > 0 and min(loo0.values()) > 0))
    c['CA6'] = dict(note='not evaluated: the candidate failed an earlier criterion (rule: failing any = rejected)') if not all(c[k]['passed'] for k in ('CA1', 'CA2', 'CA3', 'CA4', 'CA5')) else dict(note='to evaluate in integrated mode F')
    c['adopted'] = bool(all(c[k]['passed'] for k in ('CA1', 'CA2', 'CA3', 'CA4', 'CA5')) and 'not evaluated' not in c['CA6']['note']); res[n] = c
res['CH3'] = json.load(open(f'{OD}/C_CH3.json')); res['x1_timing_gain_vs_V0_pre'] = dict(V0=float(err('V0', 'before').mean()), X1=float(err('X1', 'before').mean()))
json.dump(res, open(f'{OD}/C_acceptance.json', 'w'), indent=1, default=float)
for n in ('CH1', 'CH2'): print(n, {k: (v['passed'] if isinstance(v, dict) and 'passed' in v else None) for k, v in res[n].items()}, res[n]['CA1']['legs'], round(res[n]['CA1']['pre_err']['cand'], 3), 'adopted', res[n]['adopted'])
print('CH3 supported', res['CH3']['supported'])
