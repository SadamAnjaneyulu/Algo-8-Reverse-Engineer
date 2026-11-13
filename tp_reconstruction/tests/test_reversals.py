import numpy as np, pandas as pd, pytest
from conftest import mk, T0, real, tc
import matching as mt


@pytest.mark.parametrize('m', ['FIFO', 'LIFO', 'AVG'])
def test_long_to_short_reversal_splits_the_fill(m):
    o = mt.run_matching(mk([(T0, 'B', 65, 10), (T0 + 1, 'S', 195, 14), (T0 + 2, 'B', 130, 9)]), m)
    R = o['roles']; assert R.close_qty.tolist() == [0, 65, 130] and R.open_qty.tolist() == [65, 130, 0] and R.is_reversal.tolist() == [False, True, False]
    E = o['episodes'].sort_values('open_epoch'); assert len(E) == 2 and E.direction.tolist() == [1, -1] and E.ended_by.tolist() == ['reversal', 'flat'] and E.started_by_reversal.tolist() == [False, True]
    c = o['closures']; assert c.qty.tolist() == [65, 130] and c.entry_px.tolist() == [10, 14] and c.pnl.tolist() == [260, 650]


@pytest.mark.parametrize('m', ['FIFO', 'LIFO', 'AVG'])
def test_short_to_long_reversal_and_quantity_reconciliation(m):
    o = mt.run_matching(mk([(T0, 'S', 65, 50), (T0 + 1, 'B', 130, 40)]), m)
    assert o['roles'].is_reversal.tolist() == [False, True] and o['remaining'].direction.tolist() == [1] and o['remaining'].qty.tolist() == [65] and o['remaining'].entry_px.tolist() == [40]
    assert o['roles'].open_qty.sum() == o['closures'].qty.sum() + o['remaining'].qty.sum()


def test_reversal_opens_at_the_reversing_fill_price_and_average_cost_restarts():
    o = mt.run_matching(mk([(T0, 'S', 65, 50), (T0 + 1, 'B', 195, 40), (T0 + 2, 'S', 65, 45)]), 'AVG')
    c = o['closures']; assert c.entry_px.tolist() == [50, 40] and c.pnl.tolist() == [650, 325]


@real
def test_real_data_reversals_reconcile():
    import os
    S = pd.read_csv(os.path.join(tc.DATA, 'reconciliation_summary.csv')); assert (S.reversal_fills == 23).all() and (S.reversal_units_reopened > 0).all() and (S.unexplained_fill_units == 0).all()
