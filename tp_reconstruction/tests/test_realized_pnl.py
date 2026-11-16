import numpy as np, pandas as pd, pytest
from conftest import mk, T0, real, tc
import matching as mt


def test_short_and_long_pnl_formulas():
    s = mt.run_matching(mk([(T0, 'S', 130, 50), (T0 + 1, 'B', 130, 42.5)]), 'FIFO')['closures'].iloc[0]
    l = mt.run_matching(mk([(T0, 'B', 130, 50), (T0 + 1, 'S', 130, 42.5)]), 'FIFO')['closures'].iloc[0]
    assert s.pnl_pts == 7.5 and s.pnl == 975 and l.pnl_pts == -7.5 and l.pnl == -975


def test_quantity_is_units_so_no_lot_multiplier_is_applied():
    c = mt.run_matching(mk([(T0, 'S', 65, 10), (T0 + 1, 'B', 65, 9)]), 'FIFO')['closures'].iloc[0]
    assert c.pnl == 65.0            # 1 point x 65 units, not x 65 again


def test_cash_identity_closed_plus_remaining_equals_cash_flow():
    f = mk([(T0, 'S', 195, 50), (T0 + 1, 'B', 65, 45), (T0 + 2, 'S', 65, 52), (T0 + 3, 'B', 130, 30)])
    cash = -(f.sgn * f.qty_units * f.px_fill).sum()
    for m in ['FIFO', 'LIFO', 'AVG']:
        o = mt.run_matching(f, m); bv = -(o['remaining'].direction * o['remaining'].qty * o['remaining'].entry_px).sum() if len(o['remaining']) else 0
        assert abs(o['closures'].pnl.sum() + bv - cash) < 1e-9


@pytest.mark.parametrize('pts,label', [(0.0, 'BREAKEVEN'), (0.025, 'BREAKEVEN'), (-0.025, 'BREAKEVEN'), (0.0251, 'PROFIT'), (-0.0251, 'LOSS'), (0.05, 'PROFIT'), (-0.05, 'LOSS')])
def test_breakeven_tolerance_is_half_a_tick_and_fixed_in_the_config(pts, label):
    assert tc.TOL == 0.025 == tc.TICK / 2
    assert mt.classify(np.array([pts]), tc.TOL)[0] == label


def test_average_cost_pnl_uses_the_pool_average():
    c = mt.run_matching(mk([(T0, 'S', 65, 40), (T0 + 1, 'S', 65, 60), (T0 + 2, 'B', 65, 45)]), 'AVG')['closures'].iloc[0]
    assert c.entry_px == 50 and c.pnl_pts == 5 and c.pnl == 325


def test_pnl_in_rupees_equals_points_times_units_for_every_piece():
    c = mt.run_matching(mk([(T0, 'S', 130, 40), (T0 + 1, 'S', 65, 60), (T0 + 2, 'B', 195, 45)]), 'FIFO')['closures']
    assert (c.pnl == c.pnl_pts * c.qty).all()


@real
def test_net_pnl_is_not_reported_because_no_charges_exist():
    import os
    E = pd.read_parquet(os.path.join(tc.DATA, 'exit_events.parquet')); assert E.net_pnl_rupees.isna().all() and tc.CFG['charges']['available'] is False
