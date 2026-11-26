"""Execution convention 'one_lot_v2' (D1Config.order_split): a granularity change for the identified roles only. Software validation: quantity, timing, strikes, sizing and the decisions themselves must not change."""
import pandas as pd, pytest
from d1_algo import D1Config, config_for
from d1_algo.engine import ONE_LOT_ROLES, ORDER_SPLIT_CONVENTIONS
from test_d1_algo import make, run, OPEN
def scenario(split, **kw):
    """three straddle waves in the same minute (3 lots per right at one strike), then a spike that stops all of them at once: a multi-lot stop buy-back and the 3-lot opening wings"""
    state = {"spike_from": OPEN + 60 + 300 + 70}
    def price(right, k, spot, t):
        base = 50.0
        return base * 1.7 if t >= state["spike_from"] else base
    eng, feed = make(lambda t: 24000.0, price, timetable=[300, 301, 302], lump_minute=10 ** 6, order_split=split, **kw); run(eng, feed, OPEN, OPEN + 60 + 300 + 200); return eng
def frame(eng): return eng.orders_frame()
KEY = ["ts", "right", "strike", "side", "role"]
def test_default_convention_is_the_baseline_and_unknown_values_raise():
    assert D1Config().order_split == "freeze_v1" and config_for("NIFTY", "2026-10-01").order_split == "freeze_v1" and set(ORDER_SPLIT_CONVENTIONS) == {"freeze_v1", "one_lot_v2"}
    with pytest.raises(ValueError): scenario("three_lot_v9")
def test_only_the_identified_roles_are_in_the_split_set():
    assert ONE_LOT_ROLES == {"opening_wing_buy", "stop_buyback"}                      # wing-controller buys / sells, lump and straddles are not split
def test_baseline_emits_multi_lot_orders_for_these_roles_and_v2_emits_single_lots():
    a, b = frame(scenario("freeze_v1")), frame(scenario("one_lot_v2"))
    ow1, ow2 = a[a.role == "opening_wing_buy"], b[b.role == "opening_wing_buy"]; st1, st2 = a[a.role == "stop_buyback"], b[b.role == "stop_buyback"]
    assert len(ow1) == 2 and ow1.lots.tolist() == [3, 3] and len(ow2) == 6 and (ow2.lots == 1).all()                    # 3 lots per right: one 3-lot order vs three 1-lot orders
    assert len(st1) == 2 and st1.lots.tolist() == [3, 3] and len(st2) == 6 and (st2.lots == 1).all()
def test_total_quantity_timing_strikes_and_every_other_role_are_unchanged():
    e1, e2 = scenario("freeze_v1"), scenario("one_lot_v2"); a, b = frame(e1), frame(e2)
    assert a.groupby("role").lots.sum().to_dict() == b.groupby("role").lots.sum().to_dict()                                   # total quantity per role
    g1 = a.groupby(KEY).lots.sum().reset_index(); g2 = b.groupby(KEY).lots.sum().reset_index(); pd.testing.assert_frame_equal(g1, g2)  # same second, strike, side, role, same lots: the decisions are untouched
    other = ~a.role.isin(ONE_LOT_ROLES); other2 = ~b.role.isin(ONE_LOT_ROLES); pd.testing.assert_frame_equal(a[other].reset_index(drop=True), b[other2].reset_index(drop=True))     # every other order is identical, row by row
    assert len(e1.rejected) == len(e2.rejected) == 0 and e1.book.short_count("CE", False) == e2.book.short_count("CE", False) and e1.book.wing_count("PE") == e2.book.wing_count("PE")   # same exposure, nothing blocked by the guard
def test_v2_orders_pass_the_risk_guard_and_fill_individually():
    e = scenario("one_lot_v2"); assert len(e.fills) == len(e.orders) and all(f.lots == 1 for f in e.fills if f.role in ONE_LOT_ROLES)
def test_rate_limit_counts_one_slot_per_decision_so_the_split_never_blocks_a_baseline_order():
    for split, children in (("freeze_v1", 1), ("one_lot_v2", 3)):                                          # one 3-lot buy-back decision in a minute with a limit of 1 order
        eng, feed = make(lambda t: 24000.0, lambda r, k, s, t: 50.0, timetable=[], lump_minute=10 ** 6, order_split=split, max_orders_per_minute=1); run(eng, feed, OPEN, OPEN + 200)     # run past the opening-wing minute
        n0, r0 = len(eng.orders), len(eng.rejected)
        assert eng._submit("CE", 24000.0, 3, "BUY", "stop_buyback") and len(eng.rejected) == r0 and len(eng.orders) - n0 == children and sum(o.lots for o in eng.orders[n0:]) == 3
        assert not eng._submit("PE", 24000.0, 1, "BUY", "stop_buyback") and len(eng.rejected) == r0 + 1      # the NEXT decision in the same minute is refused: the limit still binds decisions
def test_the_limit_still_applies_to_decisions_under_v2():
    e = scenario("one_lot_v2", max_orders_per_minute=3); assert len(e.rejected) > 0 and all(w == "too many orders this minute" for _, w in e.rejected)      # not disabled: decisions beyond the limit are still refused

def quiet(split, **kw):
    eng, feed = make(lambda t: 24000.0, lambda r, k, s, t: 50.0, timetable=[], lump_minute=10 ** 6, order_split=split, **kw); run(eng, feed, OPEN, OPEN + 200); return eng        # past the opening-wing minute
def test_child_orders_share_a_decision_id_and_independent_decisions_never_do():
    e = quiet("one_lot_v2"); n0 = len(e.orders); e._submit("CE", 24000.0, 3, "BUY", "stop_buyback"); e._submit("PE", 24000.0, 2, "BUY", "stop_buyback"); e._submit("CE", 24000.0, 1, "BUY", "stop_buyback")
    ids = [o.decision_id for o in e.orders[n0:]]; assert ids[:3] == [ids[0]] * 3 and ids[3:5] == [ids[3]] * 2 and len({ids[0], ids[3], ids[5]}) == 3 and all(ids) and e.orders_frame().decision_id.notna().all()
    assert len({o.tag for o in e.orders}) == len(e.orders)                                                                                         # tags (idempotency keys) stay unique per child
def test_the_cap_is_enforced_on_independent_decisions_in_both_conventions():
    for split in ("freeze_v1", "one_lot_v2"):
        e = quiet(split, max_orders_per_minute=3); n0, r0 = len(e.orders), len(e.rejected); ok = [e._submit("CE", 24000.0, 1, "BUY", "stop_buyback") for _ in range(5)]
        assert ok == [True, True, True, False, False] and len(e.orders) - n0 == 3 and len(e.rejected) - r0 == 2 and all(w == "too many orders this minute" for _, w in e.rejected[r0:])      # 3 independent decisions fit, the 4th and 5th are refused
def test_three_children_of_one_decision_take_one_slot_but_three_independent_decisions_take_three():
    e = quiet("one_lot_v2", max_orders_per_minute=3); n0 = len(e.orders)
    assert e._submit("CE", 24000.0, 3, "BUY", "stop_buyback") and len(e.orders) - n0 == 3 and e._submit("PE", 24000.0, 1, "BUY", "stop_buyback") and e._submit("CE", 24000.0, 1, "BUY", "stop_buyback")      # 1 + 1 + 1 slots
    assert not e._submit("PE", 24000.0, 1, "BUY", "stop_buyback")                                                                                  # the fourth decision of the minute is refused
    f = quiet("one_lot_v2", max_orders_per_minute=3); m0 = len(f.orders); assert all(f._submit(r, 24000.0, 1, "BUY", "stop_buyback") for r in ("CE", "PE", "CE")) and len(f.orders) - m0 == 3 and not f._submit("PE", 24000.0, 1, "BUY", "stop_buyback")
def test_freeze_v1_still_counts_every_child_order():
    e = quiet("freeze_v1", max_orders_per_minute=2, freeze_lots=1); n0 = len(e.orders); assert e._submit("CE", 24000.0, 3, "BUY", "stop_buyback") and len(e.orders) - n0 == 2 and len(e.rejected) > 0     # baseline: each freeze-quantity child takes a slot, the third is refused
    g = quiet("one_lot_v2", max_orders_per_minute=2, freeze_lots=1); m0 = len(g.orders); r0 = len(g.rejected); assert g._submit("CE", 24000.0, 3, "BUY", "stop_buyback") and len(g.orders) - m0 == 3 and len(g.rejected) == r0   # the same decision under v2: one slot, all three sent
def test_splitting_does_not_bypass_the_other_risk_controls():
    from d1_algo.risk import RiskGuard; from d1_algo.models import OrderRequest
    cfg = config_for("NIFTY", "2026-07-01", order_split="one_lot_v2"); g = RiskGuard(cfg); mk = lambda **k: OrderRequest("t", 1.0, "CE", 24000.0, k.pop("lots", 1), k.pop("side", "SELL"), k.pop("limit", 5.0), k.pop("role", "ladder_solo"), "DAY", "num", "d1")
    assert g.check(mk(), 0, 1)[0]                                                                                                                  # first child of decision d1 passes and takes its slot
    assert g.check(mk(lots=0), 0, 1) == (False, "non-positive quantity")                                                                           # later child with the SAME decision id is still validated: quantity
    assert g.check(mk(limit=float("nan")), 0, 1) == (False, "no valid limit price")                                                                # price
    assert g.check(mk(), cfg.max_short_lots_per_right, 1) == (False, "short lot limit")                                                            # position limit
    g.halt("test"); assert g.check(mk(), 0, 1)[1].startswith("halted")                                                                             # kill switch / loss halt
    assert g.check(mk(role="stop_buyback", side="BUY"), 0, 1)[0]                                                                                   # reducing orders are not blocked by halt in the baseline either (unchanged semantics)
