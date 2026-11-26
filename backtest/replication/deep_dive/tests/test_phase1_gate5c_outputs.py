"""Regression tests for Gate 5c outputs: acceptance verdicts, reproduction of the baseline, vacuity of the forward check, stop real-book evidence."""
import json, os
import pandas as pd
OUT = os.path.join(os.path.dirname(__file__), '..', 'outputs', 'phase1', '5c'); J = lambda n: json.load(open(os.path.join(OUT, n)))
def test_baseline_reproduces_5b_and_the_legacy_bridge():
    v0 = J('V0.json')['OOF']; s = json.load(open(os.path.join(OUT, '..', '5b', 'summary.json')))['OOF_events']
    assert abs(v0['keys_F1_60s'] - s['keys_F1_60s']) < 1e-9 and abs(v0['legacy_D0_OOF']['F1'] - 0.4103) < 1e-3
def test_verdicts_are_the_preregistered_ones():
    a = J('acceptance.json'); assert a['X1']['passed'] and a['X1s364']['passed'] and not a['X3']['passed']
    fails = [k for k, v in a['X3']['criteria'].items() if isinstance(v, list) and not v[2]]; assert any(k.startswith('O1') for k in fails) and any(k.startswith('O2') for k in fails)
def test_x1_changes_only_pre_auction_cycles_and_forward_sets_are_unaffected():
    v0, x1 = J('V0.json'), J('X1.json'); post = [c for c, e in v0['OOF']['era'].items() if e == 'after']; assert len(post) >= 15
    assert all(v0['OOF']['sim_orders_hash'][c] == x1['OOF']['sim_orders_hash'][c] for c in post)
    for s in ('forwardA', 'forwardB'): assert all(e == 'after' for e in v0[s]['era'].values()) and v0[s]['keys_F1_60s'] == x1[s]['keys_F1_60s']     # vacuous C5: no pre-auction cycles
def test_stop_rule_on_the_real_book_has_no_miss_and_no_false_alarm():
    d = pd.read_csv(os.path.join(OUT, 'stop_real_book_check.csv')); stops = d[d.real_stop_j.notna()]
    assert len(d) == 30 and len(stops) == 11 and bool(stops.hit.all()) and d[d.real_stop_j.isna()].cross_1_20.isna().all()
    assert d[d.real_stop_j.isna()].min_mtm_lakh.min() > -1.20 and stops.min_mtm_lakh.max() < -1.20
