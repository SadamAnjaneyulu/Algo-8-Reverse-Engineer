"""python -m pytest risk_rule_validation/tests -q   (run risk_rule_validation/run_all.py first for the result-file tests)"""
import os, sys
import numpy as np, pandas as pd, pytest
HERE = os.path.dirname(os.path.abspath(__file__)); RR = os.path.dirname(HERE); sys.path.insert(0, RR)
import rr_common as rc

def test_client_constants_are_the_stated_values():
    assert rc.CARRY_PCT == 0.04 and rc.EXPIRY_LIMIT == 200000.0 and rc.CAPITAL == 2.0e7

def test_first_cross_is_causal():
    s = np.array([0, -1, -5, -2, -9.0]); assert rc.first_cross(s, -4, 0) == 2
    s2 = s.copy(); s2[3:] = -100                      # changing the future cannot move an earlier first crossing
    assert rc.first_cross(s2, -4, 0) == 2
    assert rc.first_cross(s, -4, 3) == 4 and rc.first_cross(s, -50, 0) is None

def test_session_minute_keeps_late_D1_orders_on_D1():
    mk = rc.markets(); m = mk[('NIFTY', pd.Timestamp('2026-10-19'))]
    d1, d0 = rc.d_bounds(m); d1date = m['grid'][d1].normalize()
    late = d1date + pd.Timedelta('15:35:00')
    assert rc.session_minute(m, late, d1date) == d1                   # PR #3's minute_index would return d0 here
    assert m['day'][rc.session_minute(m, late, d1date)] == 0

@pytest.mark.parametrize('conv', rc.CONVS)
def test_ledger_lots_and_final_inventory_reconcile_to_fills(conv):
    L = rc.ledger(conv); o = rc.orders()
    assert len(L) + int(L.exit_oid.notna().sum()) == int(o.lots.sum())   # traded lots = opened lots + closures (each row: one opening, at most one closure)
    d = rc.fills(); net = d.groupby(['und', 'expiry', 'cp', 'strike']).sl.sum().round(6)
    op = L[L.exit_px.isna()].groupby(['und', 'expiry', 'cp', 'strike']).sgn.sum()
    ix = net[net != 0].index.union(op.index)
    assert np.allclose(net.reindex(ix).fillna(0).values, op.reindex(ix).fillna(0).values)

def test_carried_inventory_equals_fills_net_at_D1_close():
    P = pd.read_csv(os.path.join(rc.RES, 'phase1_inventory_by_cycle.csv')); P = P[P.has_D1]
    for c in rc.CONVS:
        assert (P[f'carried_short_lots_{c}'] == P.carried_short_lots_fills.round()).all()
        assert (P[f'carried_long_lots_{c}'] == P.carried_long_lots_fills.round()).all()

@pytest.mark.parametrize('key', [('SENSEX', '2026-07-09'), ('NIFTY', '2026-10-13'), ('NIFTY', '2026-10-19')])
def test_day_pnl_identity_and_held_path(key):
    u, e = key[0], pd.Timestamp(key[1]); B = rc.CycleBook(u, e, 'fifo')
    R, U = B.day_parts(); cum = B.cum()
    assert np.allclose((R + U)[B.d0_first:], cum[B.d0_first:] - cum[B.d1_last], atol=1e-6)
    Rc, Uc = B.day_parts(B.carried); Rn, Un = B.day_parts(B.new_d0)
    assert np.allclose(Rc + Uc + Rn + Un, R + U, atol=1e-6)             # carried + new = whole D0 book
    h = B.carried_held_day(); assert h[B.d0_first - 1] == 0             # held path starts at zero at the D-1 close

def test_end_of_export_mtm_matches_fills_based_mtm():
    P = pd.read_csv(os.path.join(rc.RES, 'phase1_inventory_by_cycle.csv'))
    assert (P.ledger_vs_fills_mtm_abs_diff_end_of_export < 1).sum() >= 31

def test_deliverables_exist_and_cover_every_cycle():
    for f in ('cycle_level_risk_reconciliation.csv', 'carry_forward_4pct_tests.csv', 'expiry_day_1pct_tests.csv', 'order_action_matching.csv'):
        assert os.path.exists(os.path.join(RR, f)), f
    T = pd.read_csv(os.path.join(RR, 'cycle_level_risk_reconciliation.csv')); assert len(T) == 35
