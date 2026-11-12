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


# ---------------- final dependency audit ----------------
R = os.path.dirname(HERE); FA = os.path.join(R, 'final_audit', 'results')

def test_pr5_control_reproduces_committed_and_conclusions_hold():
    S = pd.read_csv(os.path.join(FA, 'pr5_file_summary.csv'))
    assert len(S) == 35 and S.control_reproduces_committed.all()
    same = set(S[S.status == 'identical'].file)
    for f in ('allocation_T1_closure_granularity.csv', 'allocation_T2_contract_choice.csv', 'allocation_T4_wing_coupling.csv', 'replacement_association_null.csv',
              'replacement_ownership_pairs.csv.gz', 'state_transition_metrics.csv', 'position_lifecycle_ledger.csv.gz'):
        assert f in same, f
    V = pd.read_csv(os.path.join(FA, 'pr5_rerun_outputs', 'stop_ref_verdict.csv'))
    assert len(V) == 18 and (V.cells_meeting_80_80 == 0).all() and (V.verdict == 'UNKNOWN retained').all()

def test_stop_timelines_complete_and_inventory_consistent():
    T = pd.read_csv(os.path.join(R, 'stop_controller_order_timelines.csv')); I = pd.read_csv(os.path.join(R, 'stop_inventory_transitions.csv'))
    assert T.groupby(['und', 'expiry']).ngroups == 12 and len(T) == len(I)
    assert np.allclose(T[['short_open_lots', 'short_close_lots', 'long_open_lots', 'long_close_lots']].sum(axis=1), T.fill_lots)   # roles add up to every fill
    last = I.sort_values('event_seq').groupby(['und', 'expiry']).tail(1)
    assert (last.short_lots_total.abs() < 1e-9).all() and (last.long_lots_total.abs() < 1e-9).all()                                # every stop session ends flat
    assert T.submission_evidence.notna().all()

def test_number_comparisons_only_inside_a_block():
    T = pd.read_csv(os.path.join(R, 'stop_controller_order_timelines.csv'))
    byno = T[T.submission_evidence.str.contains('order number')]
    sblocks = set(map(tuple, T[T.module == 's_'][['expiry', 'app_key', 'number_block']].astype(str).values))
    assert all(tuple(x) in sblocks for x in byno[['expiry', 'app_key', 'number_block']].astype(str).values)

def test_dependency_register_has_status_for_every_component():
    D = pd.read_csv(os.path.join(R, 'dependency_impact_register.csv'))
    assert len(D) >= 25 and D.stage2_status.notna().all()
    assert D[D.register_ids.str.contains('ML-07', na=False)].stage2_status.str.contains('PROVISIONAL').all()
