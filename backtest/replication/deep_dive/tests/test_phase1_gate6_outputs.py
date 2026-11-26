"""Regression tests for Gate 6 outputs: handoff identity on real-cycle replays, acceptance verdict, mode F vs T relationship, no handoff error."""
import json, os
OD = os.path.join(os.path.dirname(__file__), '..', 'outputs', 'phase1', '6'); J = lambda n: json.load(open(os.path.join(OD, n)))
def test_acceptance_verdict_and_every_criterion():
    a = J('acceptance.json'); assert a['verdict'] == 'PASS' and all(v['passed'] for k, v in a.items() if k != 'verdict')
def test_handoff_identity_and_reconciliation_on_every_run():
    s = J('summary.json')['sets']; assert sum(v['meta']['runs'] for v in s.values()) == 49
    for v in s.values(): m = v['meta']; assert m['identity_ok'] == m['runs'] == m['reconciled'] == m['deterministic'] and not m['handoff_errors'] and m['rejected'] == 0 and m['cash_diff_max'] < 1e-6
def test_d1_part_equals_frozen_b1():
    s = J('summary.json'); assert abs(s['d1_legacy_F1'] - 0.6878) < 5e-4 and s['d1_rejected'] == 0
    assert abs(s['sets']['OOF']['d1']['keys_F1_60s'] - 0.739) < 0.02       # B1 keys F1 0.739 on all 32 cycles
def test_mode_f_is_a_separate_run_from_mode_t_and_is_not_mixed():
    s = J('summary.json')['sets']['OOF']; t = json.load(open(os.path.join(OD, '..', '5d', 'summary.json')))['OOF_events']
    assert s['d0']['keys_F1_60s'] != t['keys_F1_60s'] and s['d0']['keys_F1_60s'] >= 0.8 * t['keys_F1_60s']
