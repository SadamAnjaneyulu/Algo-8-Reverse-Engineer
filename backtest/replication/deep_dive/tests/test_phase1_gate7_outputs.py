"""Regression tests for Gate 7 outputs."""
import json, os
OD = os.path.join(os.path.dirname(__file__), '..', 'outputs', 'phase1', '7'); T = lambda: json.load(open(os.path.join(OD, 'tests.json')))
def test_all_robustness_tests_pass_and_are_pinned():
    t = T(); assert all(t[k]['passed'] for k in ('R1', 'R2', 'R3', 'R4', 'R5', 'R6'))
    assert abs(t['R1']['loco_keys_F1_60s'] - 0.4279) < 1e-3 and t['R1']['cycles'] == 30
def test_loco_folds_exclude_their_test_cycle_and_constants_are_stable():
    import pandas as pd
    P = pd.read_pickle(os.path.join(OD, 'loco_params.pkl')); assert len(P) == 30 and all(set(p['train']).isdisjoint(p['test']) and len(p['train']) == 29 for p in P.values())
    assert all(v == 1.0 for v in T()['R2']['modal_share'].values())
def test_causality_perturbation_covers_both_engines():
    d = T()['R5']['tests']; assert len(d) == 18 and {x['engine'] for x in d} == {'D0', 'D1'} and all(x['identical'] and x['events'] > 0 for x in d)
def test_no_independent_data_is_declared():
    t = T(); assert t['R8']['independent_validation'] == 'none exists' and not any(x['independent'] for x in t['R8']['datasets'] if x['independent'] is not None)
def test_timing_agreement_is_specific():
    s = T()['R4']['f1_by_shift_s']; assert s['-120'] < s['0'] and s['120'] < s['0'] and s['-60'] < s['0']
