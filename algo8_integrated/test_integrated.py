"""Unit tests of the D-1 -> D0 handoff and the integrated runner (Gate 6). Synthetic data only; the real-data identity check is in backtest/replication/deep_dive/tests/test_phase1_gate6_outputs.py."""
import inspect, os, sys, numpy as np, pytest
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..')); sys.path.insert(0, os.path.join(HERE, '..', 'd1_strategy')); sys.path.insert(0, os.path.join(HERE, '..', 'd0_strategy'))
from d1_algo.book import Book
from d1_algo.models import Lot, Fill
from algo8_integrated import d1_state_to_d0_opening, HandoffError, run_integrated_cycle
def fill(side, px, lots): return Fill('t', 0.0, 'CE', 24000.0, lots, side, px, 'x')
def test_handoff_maps_shorts_wings_lump_and_cash_exactly():
    b = Book(); b.add_short('CE', 24000.0, Lot(0.0, 3, 10.0, 'x'), 2); b.add_short('PE', 23900.0, Lot(0.0, 5, 12.5, 'x')); b.add_wing('CE', 24500.0, 4); b.lump[('PE', 23000.0)] = 6
    op = d1_state_to_d0_opening(b, [fill('SELL', 10.0, 2), fill('SELL', 12.5, 1), fill('BUY', 1.0, 4), fill('BUY', 0.5, 6)], 65.0, chain=np.arange(22000.0, 26001.0, 50.0))
    assert sorted(op.lots) == [['CE', 24000.0, 10.0], ['CE', 24000.0, 10.0], ['PE', 23900.0, 12.5]] and op.longs == {('h_', 'CE', 24500): 4, ('v_', 'PE', 23000): 6} and op.oshort == {}
    assert op.cash == pytest.approx((10 * 2 + 12.5 - 4 * 1.0 - 6 * 0.5) * 65.0)
def test_handoff_refuses_contracts_outside_the_d0_chain_and_does_not_repair():
    b = Book(); b.add_short('CE', 30000.0, Lot(0.0, 1, 5.0, 'x'))
    with pytest.raises(HandoffError): d1_state_to_d0_opening(b, [], 65.0, chain=np.arange(22000.0, 26001.0, 50.0))
def test_empty_book_gives_empty_opening_with_zero_cash():
    op = d1_state_to_d0_opening(Book(), [], 65.0, chain=np.arange(22000.0, 26001.0, 50.0)); assert op.lots == [] and op.longs == {} and op.cash == 0.0
def test_integrated_runner_has_no_real_order_input_and_hands_off_only_d1_state():
    names = list(inspect.signature(run_integrated_cycle).parameters); assert names == ['d1_cfg', 'd1_feed', 'd0_cfg', 'd0_market', 'unit']
    src = inspect.getsource(sys.modules['algo8_integrated.runner']); assert not any(tok in src for tok in ('read_csv', 'read_pickle', 'load_orders', 'REAL', 'real_orders', 'px_avg', 'dayno'))
    # the opening state of D0 is produced by the handoff function from the D-1 engine state only
    assert 'd1_state_to_d0_opening(e1.book, broker.all_fills' in src
