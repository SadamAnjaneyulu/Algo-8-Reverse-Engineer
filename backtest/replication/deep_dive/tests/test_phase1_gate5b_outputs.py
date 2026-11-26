"""Regression tests for Gate 5b output files (D0 order-level reconstruction)."""
import json, os
import pandas as pd

OUT = os.path.join(os.path.dirname(__file__), '..', 'outputs', 'phase1', '5b')


def _j(n):
    return json.load(open(os.path.join(OUT, n)))


def test_coverage_reconciles():
    c = _j('coverage.json')
    assert c['d0_orders_in_log'] == 29959 and c['replayable_orders'] == 26430
    assert sum(x['orders'] for x in c['not_replayable']) == 29959 - 26430
    assert c['replayable_cycles'] + len(c['not_replayable']) == c['d0_cycles_in_log']


def test_ledger_reconciles_with_summary():
    s, L = _j('summary.json'), _j('ledger_summary.json')
    o = s['OOF_events']
    assert o['real_orders'] == L['real_orders'] == 26430
    assert o['sim_orders'] == L['sim_orders']
    assert L['matched'] + L['missing_real'] == L['real_orders']
    assert L['matched'] + L['extra_sim'] == L['sim_orders']
    miss = sum(sum(v.values()) for v in L['missing_by_class_category'].values())
    extra = sum(sum(v.values()) for v in L['extra_by_class_category'].values())
    assert miss == L['missing_real'] and extra == L['extra_sim']
    assert sum(sum(v.values()) for v in L['missing_by_class_window'].values()) == L['missing_real']
    assert sum(sum(v.values()) for v in L['extra_by_class_window'].values()) == L['extra_sim']


def test_headline_values_pinned_and_above_placebo():
    o = _j('summary.json')['OOF_events']
    assert abs(o['keys_F1_60s'] - 0.41979) < 1e-4
    assert o['keys_F1_60s'] > o['placebo_keys_F1_60s'] + 0.10
    assert o['per_cycle_F1']['n'] == 30


def test_one_lot_convention_is_sensitivity_only():
    s = _j('summary.json')
    assert s['OOF_one_lot']['sim_orders'] > s['OOF_events']['sim_orders']
    assert s['OOF_one_lot']['real_orders'] == s['OOF_events']['real_orders']


def test_clearance_profile_eras():
    d = pd.read_csv(os.path.join(OUT, 'real_clearance_profile.csv'))
    a, b = d[d.era == 'after'], d[d.era == 'before']
    assert len(a) == 10 and len(b) == 8
    assert (a.j0 == 359).sum() >= 7          # post-auction: single wave at 15:14
    assert b.j0.median() > 360                # pre-auction: later
    assert b.c0.median() < a.c0.median()      # and more spread


def test_first_run_is_archived_and_correction_is_flagged():
    arch = os.path.join(OUT, '..', '5b_first_run_per_lot_stop_parts', 'summary.json')
    assert os.path.exists(arch)
    first, now = json.load(open(arch))['OOF_events'], _j('summary.json')['OOF_events']
    assert first['sim_orders'] > now['sim_orders']          # per-lot stop parts inflated simulated orders
    assert abs(first['keys_F1_60s'] - 0.4176) < 1e-3
