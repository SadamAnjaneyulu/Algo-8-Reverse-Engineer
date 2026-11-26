"""Regression tests for the Phase 1 final-loop outputs (Investigations A-D, population reconciliation). Verdicts are the preregistered ones."""
import json, os
import pandas as pd
OD = os.path.join(os.path.dirname(__file__), '..', 'outputs', 'phase1', '9'); J = lambda n: json.load(open(os.path.join(OD, n)))
def test_d0_population_reconciles_exactly():
    p = J('population_reconciliation.json'); assert p['reconciles'] and p['d0_log_orders'] == 29959 == p['d0_evaluated_orders'] + p['d0_excluded_orders'] and p['d0_evaluated_orders'] == 26430 and p['d0_excluded_orders'] == 3529
    assert p['d0_log_cycles'] == 33 and p['d0_evaluated_cycles'] == 30 and {(x['und'], x['expiry']) for x in p['d0_excluded']} == {('NIFTY', '2026-06-23'), ('NIFTY', '2026-08-11'), ('NIFTY', '2026-09-15')}
    assert {(x['und'], x['expiry']) for x in p['d1_cycles_without_d0_log']} == {('NIFTY', '2026-09-01'), ('NIFTY', '2026-09-29')} and p['d1_real_orders_32_cycles'] == 9915
def test_investigation_a_rejected_at_decision_level():
    a = J('A_analytic.json'); assert not a['P_supported'] and not a['U_supported'] and not a['criteria']['PA1']['passed'] and a['criteria']['PA2']['passed'] and a['criteria']['PA3']['passed'] and a['cells'] == 21938
    assert a['pooled']['P']['F1'] - a['pooled']['S']['F1'] < 0.03
def test_investigation_b_constant_interval_and_engine_candidate():
    b = J('B_fullpath_stop_test.json'); assert b['BX0']['false_alarms'] == 2 and not b['BX0']['supported'] and b['BX1']['supported'] and b['BX1']['hits'] == 11 and b['BX1']['false_alarms'] == 0 and b['BX1_candidate_valid']
    assert 1.21 < b['interval_lakh'][0] < 1.22 and 1.28 < b['interval_lakh'][1] < 1.30 and b['extra_d1_only_cycles']['NIFTY|2026-09-01']['cross_1_25'] == 331
    r = J('BE_D1_result.json'); assert r['stop_cycles']['NIFTY|2026-09-01']['stop_minute'] == 331 and r['stop_cycles']['NIFTY|2026-09-01']['real_stop_minute'] == 331
    assert len(r['engine_stop_cycles']) - 1 > 2 and r['cand']['sched_matched'] < 2076 and r['cycles_without_stop_identical_to_B1']['identical'] == r['cycles_without_stop_identical_to_B1']['total']
    assert abs(r['base']['keys'] - 0.7392) < 5e-4 and abs(r['base']['strict'] - 0.4722) < 5e-4 and r['base']['sched_matched'] == 2086 and abs(r['base']['legacy'] - 0.6878) < 5e-4         # the B1 re-run through this runner equals B1
    g = J('BE_D0_acceptance_generic.json'); assert g['passed']; assert J('BE_D0_stop_agreement.json')['125000.0']['hits'] == 8
def test_real_d1_has_exactly_one_stop_cycle_and_it_is_the_cycle_stop():
    x = pd.read_csv(os.path.join(OD, 'B_real_book_mtm.csv')); s = x[x.real_stop_j.notna()]; assert list(s.cyc) == ['NIFTY|2026-09-01'] and int(s.real_stop_j.iloc[0]) == 331 and s.min_before_stop_lakh.iloc[0] < -1.29
def test_investigation_c_candidates_rejected_and_structure_facts():
    c = J('C_acceptance.json'); assert not c['CH1']['adopted'] and not c['CH2']['adopted'] and not c['CH3']['supported'] and not c['CH2']['CA1']['passed'] and c['CH2']['CA1']['legs']['le_0_85_X1'] and not c['CH2']['CA1']['legs']['le_0_5_V0']
    x = pd.read_csv(os.path.join(OD, 'C_real_clearance_cycles.csv')); late = x[x.orders_after_1530 > 0]; assert list(late.cyc) == ['SENSEX|2026-08-13'] and int(late.orders_after_1530.iloc[0]) == 138
    m = pd.read_csv(os.path.join(OD, 'C_clearance_measures.csv')); pre = m[m.era == 'before']; post = m[m.era == 'after']; assert (pre.m90 >= 363).all() and (pre.m90 == 364).sum() == 7 and (post.m90 == 359).sum() == 9
def test_investigation_d_timestamp_audit_and_causal_analogue():
    d = J('D_analytic.json'); assert d['DT0']['before_candle_completion'] == 7 and d['DT0']['at_or_after'] == 1 and not d['DT0']['t_dec_available_for_body_orders'] and d['DT1']['reproduces_G1b']
    assert d['DT2']['success'] and d['DT2']['burst_hit'] == 6 and not d['DT3']['373']['success'] and d['DT4']['starts_in_last_120s'] == 7
def test_new_switches_are_default_off():
    import sys; R = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..')); sys.path.insert(0, f'{R}/d1_strategy'); sys.path.insert(0, f'{R}/d0_strategy')
    from d1_algo import D1Config; from d0_algo import D0Config
    assert D1Config().cycle_stop_rupees is None and D0Config().clearance_hazards is None and D0Config().cycle_stop_rupees == 1.2e5 and D0Config().clearance_minute == 359 and D0Config().opening_long_clock is False
