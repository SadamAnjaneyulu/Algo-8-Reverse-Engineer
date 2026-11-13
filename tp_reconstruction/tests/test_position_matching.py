import numpy as np, pandas as pd, pytest
from conftest import mk, mk_ledger, T0, DAY, real, tc
import matching as mt, reconstruct_positions as rp


@pytest.mark.parametrize('m', ['FIFO', 'LIFO', 'AVG'])
def test_simple_short_round_trip(m):
    o = mt.run_matching(mk([(T0, 'S', 65, 50), (T0 + 600, 'B', 65, 30)]), m); c = o['closures'].iloc[0]
    assert (c.direction, c.qty, c.entry_px, c.exit_px) == (-1, 65, 50, 30) and c.pnl_pts == 20 and c.pnl == 1300 and len(o['remaining']) == 0


@pytest.mark.parametrize('m', ['FIFO', 'LIFO', 'AVG'])
def test_simple_long_round_trip(m):
    c = mt.run_matching(mk([(T0, 'B', 65, 10), (T0 + 60, 'S', 65, 14)]), m)['closures'].iloc[0]
    assert (c.direction, c.pnl_pts, c.pnl) == (1, 4, 260)


@pytest.mark.parametrize('m', ['FIFO', 'LIFO', 'AVG'])
def test_multiple_opens_then_one_close_reconciles(m):
    o = mt.run_matching(mk([(T0, 'S', 65, 50), (T0 + 1, 'S', 65, 60), (T0 + 2, 'S', 130, 40), (T0 + 100, 'B', 260, 30)]), m)
    assert o['closures'].qty.sum() == 260 and len(o['remaining']) == 0 and o['episodes'].opened_units.sum() == 260
    assert abs(o['closures'].pnl.sum() - (65 * 50 + 65 * 60 + 130 * 40 - 260 * 30)) < 1e-9


def test_role_is_decided_by_inventory_not_by_side():
    o = mt.run_matching(mk([(T0, 'B', 65, 10), (T0 + 1, 'B', 65, 11), (T0 + 2, 'S', 65, 12), (T0 + 3, 'S', 130, 9)]), 'FIFO')['roles']
    assert o.close_qty.tolist() == [0, 0, 65, 65] and o.open_qty.tolist() == [65, 65, 0, 65] and o.is_reversal.tolist() == [False, False, False, True]


@pytest.mark.parametrize('m', ['FIFO', 'LIFO', 'AVG'])
def test_contracts_are_isolated(m):
    f = mk([(T0, 'S', 65, 50, 'A'), (T0 + 1, 'B', 65, 30, 'B'), (T0 + 2, 'B', 65, 20, 'A')], 'A')
    o = mt.run_matching(f, m); assert len(o['closures']) == 1 and o['closures'].contract_id.iloc[0] == 'A' and o['remaining'].contract_id.tolist() == ['B'] and o['remaining'].direction.iloc[0] == 1


@pytest.mark.parametrize('m', ['FIFO', 'LIFO', 'AVG'])
def test_unclosed_position_is_reported_as_remaining(m):
    o = mt.run_matching(mk([(T0, 'S', 130, 50), (T0 + 5, 'B', 65, 40)]), m)
    assert o['remaining'].qty.sum() == 65 and o['closures'].qty.sum() == 65 and o['episodes'].remaining_units.iloc[0] == 65


def test_flat_contract_never_produces_an_unmatched_close():
    """a sell into a flat contract OPENS a short; closed quantity can never exceed what was opened"""
    o = mt.run_matching(mk([(T0, 'S', 65, 50), (T0 + 9, 'S', 65, 55)]), 'FIFO'); assert len(o['closures']) == 0 and o['roles'].close_qty.sum() == 0 and o['remaining'].qty.sum() == 130


def test_carried_inventory_across_sessions_and_unclosed_status():
    L = mk_ledger([(T0, 'S', 130, 50), (T0 + 10, 'S', 65, 52), (T0 + DAY, 'B', 65, 30)], expiry='2026-07-07')       # opened 7 Jul, closed 8 Jul (after expiry date for the test of status below)
    L['expiry'] = pd.Timestamp('2026-07-08')
    B = rp.build(L); c = B['pieces'][(B['pieces'].method == 'FIFO') & (B['pieces'].row_type == 'CLOSED')]
    assert c.session_relation.tolist() == ['CARRIED'] and c.qty.sum() == 65
    r = B['remaining'][B['remaining'].method == 'FIFO']; assert r.qty.sum() == 130 and set(r.status) == {'EXPIRED_UNCLOSED'}


def test_same_session_and_open_at_end_status():
    L = mk_ledger([(T0, 'S', 65, 50), (T0 + 600, 'B', 65, 30), (T0 + 700, 'S', 65, 20)]); L['expiry'] = pd.Timestamp('2026-12-31')
    B = rp.build(L); c = B['pieces'][(B['pieces'].method == 'FIFO') & (B['pieces'].row_type == 'CLOSED')]
    assert c.session_relation.tolist() == ['SAME_SESSION']; assert set(B['remaining'].status) == {'OPEN_AT_END_OF_DATA'}


def test_reconciliation_identity_on_a_mixed_scenario():
    L = mk_ledger([(T0, 'S', 130, 50), (T0 + 1, 'B', 65, 45), (T0 + 2, 'B', 130, 40), (T0 + 3, 'S', 65, 41), (T0 + 4, 'B', 65, 30)])
    B = rp.build(L); S = rp.reconcile(L, B)
    assert (S.unexplained_fill_units == 0).all() and (S.unexplained_open_minus_close_minus_remaining == 0).all() and (S.cells_not_reconciling == 0).all() and (S.cash_identity_difference.abs() < 1e-9).all()


@real
def test_real_data_quantities_reconcile_for_all_methods():
    import os
    S = pd.read_csv(os.path.join(tc.DATA, 'reconciliation_summary.csv'))
    assert (S.unexplained_fill_units == 0).all() and (S.cells_not_reconciling == 0).all() and (S.unmatched_closed_units == 0).all() and (S.cash_identity_difference.abs() < 1e-3).all()
    assert S.closed_units.nunique() == 1 and S.remaining_units.nunique() == 1 and S.opened_units.nunique() == 1
