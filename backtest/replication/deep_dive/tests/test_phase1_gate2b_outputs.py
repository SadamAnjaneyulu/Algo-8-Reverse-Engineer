"""Regression contract of the saved Gate 2B outputs: no rule supported, S1 baseline value, attribution, and the support rule applied as registered."""
import os, json
HERE = os.path.dirname(os.path.abspath(__file__)); O = f'{HERE}/../outputs/phase1'
def test_no_strike_rule_meets_the_preregistered_support_rule():
    r = json.load(open(f'{O}/2B_strike_eval.json')); v = r['vs_S1_on_orders_with_last_sale']
    for k, x in v.items(): assert not (x['diff_exact_vs_S1'] >= 0.05 and x['ci95'][0] > 0 and x['cycles_ge_S1'] >= 20), k
    s = json.load(open(f'{O}/2B_strike_eval_S8_S9.json')); assert s['S8']['supported'] is False and s['S9']['supported'] is False
    s1 = [t for t in r['rules'] if t['rule'] == 'S1'][0]; assert abs(s1['exact_own'] - 0.5013) < 5e-4 and r['orders'] == 1140 and r['S5_LOCO']['modal_share'] == 1.0
def test_context_attribution_is_recorded():
    a = json.load(open(f'{O}/2B_strike_attribution.json')); assert a['n'] == 403 and a['rule_on_real_context_exact_vs_real'] > a['sim_strike_exact_vs_real'] + 0.2
