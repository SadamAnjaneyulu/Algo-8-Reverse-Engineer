"""Regression tests for Gate 5d outputs: standards verdicts, risk, determinism, report content."""
import json, os
OD = os.path.join(os.path.dirname(__file__), '..', 'outputs', 'phase1', '5d'); J = lambda n: json.load(open(os.path.join(OD, n)))
def test_standards_verdicts_pinned():
    s = J('standards.json'); assert {k for k, v in s.items() if v['passed']} == {'D6', 'D7', 'D8', 'D10', 'D11', 'D12', 'D13'} and {k for k, v in s.items() if not v['passed']} == {'D1', 'D2', 'D3', 'D4', 'D5', 'D9'}
def test_headline_matches_5c_candidate_run_and_exceeds_placebo():
    o = J('summary.json')['OOF_events']; x1 = json.load(open(os.path.join(OD, '..', '5c', 'X1.json')))['OOF']
    assert abs(o['keys_F1_60s'] - x1['keys_F1_60s']) < 1e-9 and abs(o['legacy_lot_level']['F1'] - x1['legacy_D0_OOF']['F1']) < 1e-9 and o['placebo_keys_F1_60s'] < 0.6 * o['keys_F1_60s']
def test_risk_and_determinism():
    r = J('risk_determinism.json'); assert sum(v['runs'] for v in r.values()) == 49
    for v in r.values(): assert v['rejected'] == 0 and v['violations'] == 0 and v['max_short_lots_per_right'] <= 306 and v['max_sell_decisions_per_minute'] <= 90 and v['deterministic'] == v['reconciled'] == v['runs']
def test_ledger_reconciles():
    L = J('ledger_summary.json'); assert L['matched'] + L['missing_real'] == L['real_orders'] and L['matched'] + L['extra_sim'] == L['sim_orders']
def test_opening_state_matches_real_book_except_the_stop_at_open_cycle():
    c = J('opening_mtm_check.json'); assert c['n_equal_within_1_rupee'] == 29 and [d['cyc'] for d in c['differing']] == ['SENSEX|2026-08-20']
def test_result_report_contains_root_cause_table_for_every_class_over_5pct_unmatched():
    t = open(os.path.join(OD, '..', '..', '..', 'reports', 'PHASE1_GATE5D_RESULT.md')).read()
    for c in ('body_buyback', 'body_long', 'body_sell', 'stop', 'wing_buy', 'wing_sell', 'not_modelled'): assert c in t.split('## Root causes')[1]
