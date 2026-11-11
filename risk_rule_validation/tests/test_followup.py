"""python -m pytest risk_rule_validation/tests/test_followup.py -q   (run the follow-up scripts first)"""
import os
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); F = os.path.join(os.path.dirname(HERE), 'followup', 'results')

def test_order_numbers_monotone_inside_blocks():
    V = pd.read_csv(os.path.join(F, 'order_number_stream_validation.csv'))
    assert V.fill_time_inversions.sum() / V.adjacent_pairs.sum() < 0.01
    assert V.minute_inversions.sum() / V.adjacent_pairs.sum() < 0.005

def test_every_post_stop_short_open_is_classified_and_reversed():
    P = pd.read_csv(os.path.join(F, 'post_stop_short_fills_classified.csv'))
    assert P.classification.notna().all() and len(P) == 60
    assert set(P.basis) <= {'order number (same block as an s_ order)', 'order-entry minute (fallback)'}
    S = pd.read_csv(os.path.join(F, 'stop_event_summary.csv'))
    assert len(S) == 12 and (S.open_short_lots_end_of_session.abs() < 1e-9).all()

def test_patch_is_one_function():
    d = open(os.path.join(F, 'pr3_rerun_patch.diff')).read()
    changed = [l for l in d.splitlines() if (l.startswith('+') or l.startswith('-')) and not l.startswith(('+++', '---'))]
    assert all(('minute_index' in l) or l[1:].startswith('    ') for l in changed) and len(changed) < 15

def test_rerun_ledger_matches_session_aware_ledger_except_no_D0_cycle():
    C = pd.read_csv(os.path.join(F, 'pr3_rerun_vs_rr_ledger_check.csv'))
    bad = C[~C.agree]
    assert set(map(str, bad.expiry)) <= {'2026-09-29'}

def test_stop_level_robust_to_quote_variants():
    S = pd.read_csv(os.path.join(F, 'stop_mtm_sensitivity_summary.csv'))
    s = S[S.subset.str.startswith('10') & S.variant.str.match(r'V[134] ')]
    assert len(s) == 3 and (s['median'].between(-1.45e5, -1.37e5)).all() and (s.sd < 7000).all()
