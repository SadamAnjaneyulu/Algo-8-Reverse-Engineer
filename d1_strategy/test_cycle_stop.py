"""P1-9-B candidate: D-1 cycle stop (default off). Software validation of the switch, not evidence that a D-1 stop exists beyond the one real event."""
import pytest
from d1_algo import D1Config
from d1_algo.models import Lot
from test_d1_algo import make, run, OPEN
def px_fn(spike_t): return lambda r, k, s, t: 75.0 if (t >= spike_t and abs(k - 24000.0) <= 100.0) else 50.0      # near-the-money options rise 1.5x (below the 1.6x per-lot stop); far wings unchanged
def scenario(**cfg):
    spike = OPEN + 600
    eng, feed = make(lambda t: 24012.0, px_fn(spike), timetable=[10, 1140], lump_minute=10 ** 6, order_split="one_lot_v2", **cfg); run(eng, feed, OPEN, OPEN + 1500); return eng, spike
def test_default_is_off_and_explicit_none_changes_nothing():
    assert D1Config().cycle_stop_rupees is None
    a, _ = scenario(); b, _ = scenario(cycle_stop_rupees=None); assert [(o.ts, o.role, o.right, o.strike, o.lots) for o in a.orders] == [(o.ts, o.role, o.right, o.strike, o.lots) for o in b.orders] and not a.stopped
    assert not [o for o in a.orders if o.role.startswith("cycle_stop")]
def test_stop_fires_after_the_adverse_move_not_before_and_liquidates_and_halts():
    off, spike = scenario(); on, _ = scenario(cycle_stop_rupees=1.0e3)
    assert on.stopped and on.stop_time >= spike and on.stop_time <= spike + 10          # fires within one check cadence after the price jump, never before it
    stop_orders = [o for o in on.orders if o.role.startswith("cycle_stop")]; assert stop_orders and all(o.module == "s_" and o.validity == "DAY" for o in stop_orders)
    assert sum(len(v) for v in on.book.shorts.values()) == 0                              # every short lot bought back
    assert not [o for o in on.orders if o.ts > on.stop_time and not o.role.startswith("cycle_stop")]       # nothing else after the stop
    assert [o for o in off.orders if o.role == 'scheduled_straddle' and o.ts > on.stop_time]          # the baseline WOULD have sold again later, so the halt is what removes it
    assert [o for o in on.orders if o.ts < spike] == [o for o in off.orders if o.ts < spike]               # before the stop the run is identical to the baseline
def test_threshold_not_reached_means_no_stop_and_identical_orders():
    off, _ = scenario(); big, _ = scenario(cycle_stop_rupees=1.0e9); assert not big.stopped and [(o.ts, o.role, o.lots) for o in off.orders] == [(o.ts, o.role, o.lots) for o in big.orders]
def test_mtm_uses_only_simulated_cash_and_live_marks_no_future():
    eng, feed = make(lambda t: 24012.0, lambda r, k, s, t: 50.0, timetable=[], lump_minute=10 ** 6); run(eng, feed, OPEN, OPEN + 5)
    assert eng.book_mtm() == 0.0
    eng.book.add_short("CE", 24000.0, Lot(OPEN, 0, 100.0, "x"), 2); u = eng.cfg.lot_units; assert eng.book_mtm() == pytest.approx(-50.0 * 2 * u)       # shorts marked at the live price (cash not yet recorded: only the marks)
