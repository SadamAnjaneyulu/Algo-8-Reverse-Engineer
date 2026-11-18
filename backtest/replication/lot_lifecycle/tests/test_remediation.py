"""Regression tests for the review defects A-E (each fails on the legacy behaviour)."""
import os, copy
import numpy as np, pandas as pd, pytest
import features, matching


def test_defect_d_features_never_use_the_same_bar():
    assert features.prev_bar(1, 0) == (0, 374) and features.prev_bar(0, 0) is None and features.prev_bar(0, 5) == (0, 4) and features.prev_bar(1, 7) == (1, 6)
    spots = {0: np.arange(375, dtype=float), 1: 1000 + np.arange(375, dtype=float)}
    assert features.prev_spot(spots, 1, 0) == 374.0 and np.isnan(features.prev_spot(spots, 0, 0))
    spots2 = {0: spots[0].copy(), 1: spots[1].copy()}; spots2[1][0] = 9999.0                                      # perturb the 09:15 bar of D0: the decision at j = 0 must not change
    assert features.prev_spot(spots2, 1, 0) == features.prev_spot(spots, 1, 0)


def test_defect_c_matching_is_one_to_one_and_window_based():
    sim = pd.DataFrame(dict(und='N', expiry='e', cp='CE', strike=1, sec=[119, 119], lots=[1, 1])); act = pd.DataFrame(dict(und='N', expiry='e', cp='CE', strike=1, sec=[121], lots=[1]))
    m = matching.match(sim, act, 5); assert m['matched'] == 1 and m['sim_unmatched'] == 1 and m['act_unmatched'] == 0                  # one actual lot can match only one simulated lot
    assert matching.match_binned_legacy(sim.iloc[:1], act, 120)['matched'] == 0                                                         # legacy bins split events 2 s apart
    a = pd.DataFrame(dict(und='N', expiry='e', cp='CE', strike=1, sec=[100], lots=[3])); s = pd.DataFrame(dict(und='N', expiry='e', cp='CE', strike=1, sec=[100, 400], lots=[2, 2]))
    prev = -1
    for tol in (0, 60, 300, 1000):
        mm = matching.match(s, a, tol)['matched']; assert mm >= prev and mm <= 3; prev = mm                                           # monotone in tolerance, never above the smaller side
    assert matching.match(s, a, 0, 'same')['matched'] == 2 and matching.match(s.assign(strike=2), a, 1000, 'same')['matched'] == 0     # strike-equal mode


def _cycle(und, exp):
    from ledger import cycle_table, load_fills
    from data import load_cycle, CACHE
    if not os.path.exists(os.path.join(CACHE, f'{und}_{exp}.pkl')): pytest.skip('cache absent')
    F = load_fills(); C = pd.read_csv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'outputs', 'cycles.csv')); r = C[(C.und == und) & (C.expiry == exp)].iloc[0]
    return F, load_cycle(und, exp, r.d1, r.d0), r


def test_defect_a_passive_lots_are_closed_at_a_stop():
    import d0_sim_v2 as S2, d0_sim as S1
    from opening_book import opening_book
    F, c, r = _cycle('SENSEX', '2026-09-24'); start = opening_book(F, r.und, r.expiry, r.d1)
    v2 = S2.simulate_d0(c, r.und, None, start=start, price_stop=True); assert v2['stopped'] and not v2['passive_open_at_end'] and (v2['orders'].cls == 'STOP_LIQUIDATION_PASSIVE').any()
    ev = pd.read_csv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'd0_reconstruction', 'results', 'd0_events.csv'))
    v1 = S1.simulate_d0(c, r.und, ev[(ev.und == r.und) & (ev.expiry == r.expiry) & (ev.day == 'D-1')], price_stop=True)
    assert v1['gross'] > 0 > v2['gross'] and v1['gross'] - v2['gross'] > 100000                                                   # legacy credits ~Rs 200k of spurious settlement; live lost ~Rs 153k


def test_defect_b_replacement_wings_are_an_explicit_unknown():
    import d0_sim_v2 as S2
    from opening_book import opening_book
    F, c, r = _cycle('SENSEX', '2026-07-02'); n0 = S2.simulate_d0(c, r.und, None, start=opening_book(F, r.und, r.expiry, r.d1), price_stop=True)['orders']; n1 = S2.simulate_d0(c, r.und, None, start=opening_book(F, r.und, r.expiry, r.d1), price_stop=True, replacement_wings='one_per_lot')['orders']
    assert (n0.cls == 'HEDGE_ADD').sum() == (n0.cls == 'SCHEDULED_SALE').sum() and (n1.cls == 'HEDGE_ADD').sum() >= (n0.cls == 'HEDGE_ADD').sum()


def test_defect_e_opening_book_is_reconciled_with_the_ledger():
    import d0_sim as S1
    from ledger import load_fills
    from opening_book import opening_book
    C = pd.read_csv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'outputs', 'opening_book_audit.csv')); assert len(C) == 30 and (C.d_body.abs() < 1e-9).all() and (C.cash_diff.abs() < 1e-3).all() and ((C.lot_engine_wing - C.d0sim_v11_wing).abs() < 1e-9).all()


def test_lot_reconciliation_outputs():
    R = pd.read_csv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'outputs', 'cycle_reconciliation.csv')); assert len(R) == 35 and R.identity_residual_FIFO.abs().max() < 1e-6
