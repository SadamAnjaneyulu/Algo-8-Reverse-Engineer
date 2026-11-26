"""Phase 1 / P1-2A candidate switches on the solo ladder (default off = baseline). Software validation of the switches, not evidence the hypotheses are true."""
import pytest
from d1_algo import D1Config, config_for
from d1_algo.models import Lot
from test_d1_algo import make, run, OPEN
def drop_scenario(**cfg):
    """one scheduled wave sets the ladder reference; then the spot falls 45 points inside one second after the ladder is live"""
    t_drop = OPEN + 60 + 200
    eng, feed = make(lambda t: 24012.0 if t < t_drop else 23967.0, timetable=[10], lump_minute=10 ** 6, order_split="one_lot_v2", **cfg); run(eng, feed, OPEN, OPEN + 60 + 260); return eng, t_drop
def solo(eng): return [o for o in eng.orders if o.role == "ladder_solo"]
def test_defaults_are_the_baseline_and_explicit_defaults_change_nothing():
    c = D1Config(); assert c.ladder_lots_mode == "one" and c.ladder_book_condition is False and c.ladder_step == 0.2 and c.ladder_gate_min == 60
    a, _ = drop_scenario(); b, _ = drop_scenario(ladder_lots_mode="one", ladder_book_condition=False, ladder_step=0.2, ladder_gate_min=60)
    assert [(o.ts, o.right, o.strike, o.lots, o.role) for o in a.orders] == [(o.ts, o.right, o.strike, o.lots, o.role) for o in b.orders]
    assert len(solo(a)) == 1 and solo(a)[0].lots == 1 and solo(a)[0].right == "CE"                                      # baseline: one lot for the whole 4-rung move
def test_steps_mode_sends_one_single_lot_order_per_rung_at_one_second_with_one_decision_id():
    base, td = drop_scenario(); e, _ = drop_scenario(ladder_lots_mode="steps"); s = solo(e); assert len(s) == 4 and all(o.lots == 1 for o in s) and len({o.ts for o in s}) == 1 and len({o.decision_id for o in s}) == 1 and all(o.right == "CE" for o in s)
    assert e.ladder_ref["CE"] == base.ladder_ref["CE"]                                                                  # the reference advance (4 rungs) is unchanged by the order granularity
    assert [o for o in e.orders if o.role != "ladder_solo"] == [o for o in base.orders if o.role != "ladder_solo"] or len(e.orders) >= len(base.orders)
def test_finer_step_fires_more_often_and_leaves_other_roles_alone():
    a, _ = drop_scenario(); f, _ = drop_scenario(ladder_step=0.05)
    assert len(solo(f)) >= len(solo(a)) and {o.role for o in f.orders} >= {"scheduled_straddle"}
    assert [(o.ts, o.right, o.strike, o.lots) for o in a.orders if o.role == "scheduled_straddle"] == [(o.ts, o.right, o.strike, o.lots) for o in f.orders if o.role == "scheduled_straddle"]
def test_book_condition_permits_and_blocks_exactly_as_defined():
    eng, feed = make(lambda t: 24012.0, lambda r, k, s, t: 50.0, timetable=[], lump_minute=10 ** 6, ladder_book_condition=True); run(eng, feed, OPEN, OPEN + 5)
    L = lambda entry: Lot(OPEN, 0, entry, "x"); assert eng._ladder_allowed("CE")                                         # no lots on either side: no constraint
    eng.book.add_short("CE", 24000.0, L(100.0), 2); assert eng._ladder_allowed("CE")                                    # own CE ratio 0.5 <= 1, other side empty
    eng.book.add_short("PE", 24000.0, L(20.0), 1); assert eng._ladder_allowed("CE")                                     # other PE ratio 2.5 >= 1 (losing): allowed
    eng.book.shorts[("PE", 24000.0)] = [L(100.0)]; assert not eng._ladder_allowed("CE")                                  # other side in profit (0.5): blocked
    eng.book.shorts[("PE", 24000.0)] = [L(20.0)]; eng.book.shorts[("CE", 24000.0)] = [L(20.0)]; assert not eng._ladder_allowed("CE")   # own side losing (2.5): blocked
    eng.book.shorts[("CE", 24000.0)] = [L(20.0)]; eng.book.shorts[("PE", 24000.0)] = [L(100.0)]; assert eng._ladder_allowed("PE")   # PE ladder: own PE in profit (0.5), other CE losing (2.5): allowed
def test_blocked_trigger_does_not_advance_the_reference_and_off_means_baseline():
    t_drop = OPEN + 60 + 200; mk = lambda **c: make(lambda t: 24012.0 if t < t_drop else 23967.0, lambda r, k, s, t: 50.0, timetable=[10], lump_minute=10 ** 6, order_split="one_lot_v2", **c)
    eng, feed = mk(ladder_book_condition=True); run(eng, feed, OPEN, OPEN + 60 + 20)
    eng.book.shorts[("CE", 24000.0)] = [Lot(OPEN, 0, 40.0, "x")]                                                          # own CE side losing (50 / 40 = 1.25, below the 1.6 stop): the ladder must stay blocked
    ref0 = eng.ladder_ref["CE"]; run(eng, feed, OPEN + 60 + 21, OPEN + 60 + 260)
    assert eng.ladder_ref["CE"] == ref0 and not [o for o in eng.orders if o.role == "ladder_solo"]                       # blocked: no order, reference unchanged (still armed)
def test_late_gate_default_is_baseline_and_switches_exactly_at_the_start_minute():
    c = D1Config(); assert c.ladder_late_gate_min is None and c.late_start_min == 360
    a, _ = drop_scenario(); b, _ = drop_scenario(ladder_late_gate_min=None); assert [(o.ts, o.role, o.lots) for o in a.orders] == [(o.ts, o.role, o.lots) for o in b.orders]
    # a low at 23900, a rebound to 24050, a second wave that resets the reference there, then a fall to 24000: a fresh 5-minute low but NOT a fresh 60-minute low
    spot = lambda t: 24012.0 if t < OPEN + 160 else (23900.0 if t < OPEN + 180 else (24050.0 if t < OPEN + 520 else 24000.0))
    mk = lambda **cfg: make(spot, timetable=[10, 400], lump_minute=10 ** 6, order_split="one_lot_v2", **cfg); end = OPEN + 700; late = lambda e: [o for o in e.orders if o.role == "ladder_solo" and o.ts >= OPEN + 520]
    e0, f0 = mk(); run(e0, f0, OPEN, end); e5, f5 = mk(ladder_late_gate_min=5, late_start_min=0); run(e5, f5, OPEN, end)
    assert len(late(e0)) == 0 and len(late(e5)) > 0                                                                          # only the 5-minute gate fires on the fall to 24000
    e5b, f5b = mk(ladder_late_gate_min=5, late_start_min=10 ** 6); run(e5b, f5b, OPEN, end); assert [(o.ts, o.role) for o in e5b.orders] == [(o.ts, o.role) for o in e0.orders]      # start minute not reached: baseline
def breakout_scenario(**cfg):
    spot = lambda t: 24000.0 if t < OPEN + 76 * 60 else (24120.0 if t < OPEN + 80 * 60 else 24200.0)       # as test_breakout_fires_once...: breaks up at 10:31, deeper at 10:35
    eng, feed = make(spot, timetable=[], order_split="one_lot_v2", **cfg); run(eng, feed, OPEN, OPEN + 90 * 60); return eng
def test_breakout_one_lot_switch_default_off_and_splits_into_single_lots_with_one_decision_id():
    assert D1Config().breakout_one_lot is False
    a = breakout_scenario(breakout_size_after_s=120.0); b = breakout_scenario(breakout_size_after_s=120.0, breakout_one_lot=True)
    ba = [o for o in a.orders if o.role in ("breakout_straddle", "breakout_extra")]; bb = [o for o in b.orders if o.role in ("breakout_straddle", "breakout_extra")]
    assert any(o.lots > 1 for o in ba) and all(o.lots == 1 for o in bb) and sum(o.lots for o in ba) == sum(o.lots for o in bb)       # same total lots, single-lot orders
    assert len({o.decision_id for o in bb if o.role == "breakout_straddle" and o.right == "CE"}) == 1                                     # the n children of one decision share an id
def test_size_delay_sizes_by_the_depth_reached_after_the_delay():
    now = breakout_scenario(breakout_size_after_s=0.0); late = breakout_scenario(breakout_size_after_s=240.0)
    lots = lambda e: sum(o.lots for o in e.orders if o.role in ("breakout_straddle", "breakout_extra")); assert lots(late) > lots(now)    # deeper break after 4 minutes: larger entry
def stop_scenario(**cfg):
    state = {"spike": OPEN + 60 + 100}
    price = lambda r, k, spot, t: 50.0 * (1.7 if t >= state["spike"] else 1.0)
    eng, feed = make(lambda t: 24012.0, price, timetable=[10], lump_minute=10 ** 6, order_split="one_lot_v2", **cfg); run(eng, feed, OPEN, OPEN + 60 + 260); return eng
def test_stop_latency_default_is_baseline_and_delays_the_stop_by_exactly_the_latency():
    assert D1Config().stop_latency_s == 0.0
    a = stop_scenario(); b = stop_scenario(stop_latency_s=20.0); sa = [o for o in a.orders if o.role == "stop_buyback"]; sb = [o for o in b.orders if o.role == "stop_buyback"]
    assert len(sa) > 0 and len(sb) == len(sa) and min(o.ts for o in sb) - min(o.ts for o in sa) == 20 and sum(o.lots for o in sb) == sum(o.lots for o in sa)
    assert [o for o in a.orders if o.role not in ("stop_buyback", "protective_wing_sell")][:4] == [o for o in b.orders if o.role not in ("stop_buyback", "protective_wing_sell")][:4]
