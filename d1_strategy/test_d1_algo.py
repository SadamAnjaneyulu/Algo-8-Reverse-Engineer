"""Tests of the live engine with a controllable fake feed. Run: python -m pytest test_d1_algo.py -q"""
import json
import os
import numpy as np
import pytest
from d1_algo import D1Config, D1Engine, PaperBroker, ReplayFeed, config_for, run_replay
from d1_algo.models import SESSION_OPEN_S, minute_index
from example_synthetic import make_day

OPEN = SESSION_OPEN_S


class FakeFeed:
    """Spot and option prices set by functions of time, so tests can script exactly what the engine sees."""
    def __init__(self, spot_fn, price_fn=None, step=50.0):
        self.t = float(OPEN); self.spot_fn = spot_fn; self.step = step; self._K = np.arange(20000.0, 28000.0 + 1, step)
        self.price_fn = price_fn or (lambda right, k, spot, t: max((spot - k) if right == "CE" else (k - spot), 0.0) + 40.0 * np.exp(-abs(k - spot) / 400.0) + 0.5)
    def now(self): return self.t
    def spot(self): return float(self.spot_fn(self.t))
    def strikes(self): return self._K
    def option_ltp(self, right, strike):
        return float(self.price_fn(right, strike, self.spot(), self.t))


def run(engine, feed, t0, t1):
    t = int(t0)
    while t <= t1:
        feed.set_time(t) if hasattr(feed, "set_time") else setattr(feed, "t", float(t)); engine.step(); t += 1


def make(spot_fn, price_fn=None, **cfg_over):
    feed = FakeFeed(spot_fn, price_fn); cfg = config_for("NIFTY", "2026-07-01", **cfg_over); eng = D1Engine(cfg, feed, PaperBroker(feed)); return eng, feed


def test_scheduled_waves_fire_at_their_seconds_at_atm_of_previous_close():
    eng, feed = make(lambda t: 24012.0)
    run(eng, feed, OPEN, OPEN + 130)
    sched = [o for o in eng.orders if o.role == "scheduled_straddle"]
    assert len(sched) == 6 and {o.right for o in sched} == {"CE", "PE"}              # waves at +1, +2, +7 s after 09:16:00, call and put each
    assert all(o.strike == 24000.0 for o in sched)                                     # ATM of the previous close (24012 -> 24000)
    assert sorted({round(o.ts - (OPEN + 60)) for o in sched}) == [1, 2, 7]
    assert all(o.lots == 1 and o.side == "SELL" for o in sched)


def test_late_waves_are_skipped_not_fired_late():
    eng, feed = make(lambda t: 24012.0)
    run(eng, feed, OPEN + 600, OPEN + 700)                                             # engine starts 9 minutes late: waves of the first minute are old
    assert not [o for o in eng.orders if o.role == "scheduled_straddle" and o.ts < OPEN + 60 + 100]


def test_every_short_gets_a_wing_a_few_seconds_later_and_counts_match():
    eng, feed = make(lambda t: 24012.0, lump_minute=10 ** 6)
    run(eng, feed, OPEN, OPEN + 400)
    for right in ("CE", "PE"):
        assert eng.book.short_count(right) == eng.book.wing_count(right)
    first_sell = min(o.ts for o in eng.orders if o.role == "scheduled_straddle"); first_wing = min(o.ts for o in eng.orders if o.role == "protective_wing_buy" or o.role == "opening_wing_buy")
    assert first_wing >= OPEN + 60                                                       # opening wings come at 09:16:00, before the first scheduled straddle
    wings = [o for o in eng.orders if o.role == "protective_wing_buy"]
    for o in wings:
        assert (o.strike > 24012.0) if o.right == "CE" else (o.strike < 24012.0)       # out of the money


def test_breakout_fires_once_per_side_per_candle_one_strike_toward_the_break():
    def spot(t):
        return 24000.0 if t < OPEN + 76 * 60 else (24120.0 if t < OPEN + 80 * 60 else 24200.0)   # flat, then breaks up at 10:31, higher at 10:35
    eng, feed = make(spot, timetable=[])
    run(eng, feed, OPEN, OPEN + 90 * 60)
    up = [o for o in eng.orders if o.role == "breakout_straddle"]
    assert {o.right for o in up} == {"CE", "PE"} and len({o.ts for o in up}) == 1      # one entry, call and put together
    assert all(o.strike == 24050.0 for o in up)                                          # ATM(24000)+one step
    assert any(o.role == "breakout_extra" and o.right == "PE" for o in eng.orders)     # favourable side of an up-break is the put
    assert all(o.ts >= OPEN + 75 * 60 for o in up)                                       # not before 10:30


def test_stop_fires_for_a_lot_from_an_earlier_minute_only():
    state = {"spike_from": None}
    def price(right, k, spot, t):
        base = 50.0
        if state["spike_from"] is not None and t >= state["spike_from"]: return base * 1.7
        return base
    eng, feed = make(lambda t: 24000.0, price, timetable=[300], lump_minute=10 ** 6)        # one wave at 09:21:00
    state["spike_from"] = OPEN + 60 + 300 + 5                                              # spike 5 seconds after the sale, same minute
    run(eng, feed, OPEN, OPEN + 60 + 300 + 50)
    assert not [o for o in eng.orders if o.role == "stop_buyback"]                         # same minute: no stop
    run(eng, feed, OPEN + 60 + 300 + 51, OPEN + 60 + 300 + 130)                            # next minute: the lot is stopped, once per lot
    stops = [o for o in eng.orders if o.role == "stop_buyback"]
    assert len(stops) == 2 and {o.right for o in stops} == {"CE", "PE"} and all(o.lots == 1 and o.side == "BUY" for o in stops)
    assert eng.book.short_count("CE", False) == 0 and eng.book.short_count("PE", False) == 0


def test_ladder_sells_calls_on_a_falling_market_and_not_puts():
    def spot(t):
        m = (t - OPEN) / 60.0
        return 24000.0 if m < 80 else 24000.0 - 6.0 * (m - 80)                           # flat, then falls 6 points a minute after 10:35
    eng, feed = make(spot, timetable=[], lump_minute=10 ** 6)
    eng._ladder_event("CE", 20); eng._ladder_event("PE", 20)                           # as if a scheduled/breakout sale had set the references
    eng.spot_bars.tick(0, 24000.0)
    run(eng, feed, OPEN, OPEN + 100 * 60)
    solo = [o for o in eng.orders if o.role == "ladder_solo"]
    assert solo and all(o.right == "CE" and o.lots == 1 for o in solo)


def test_kill_switch_blocks_new_shorts_but_not_protection(tmp_path):
    kill = tmp_path / "STOP"; kill.write_text("x")
    eng, feed = make(lambda t: 24012.0, kill_switch_file=str(kill))
    run(eng, feed, OPEN, OPEN + 120)
    assert not [o for o in eng.orders if o.role == "scheduled_straddle"] and any("halted" in why for _, why in eng.rejected)
    assert any(o.role == "opening_wing_buy" for o in eng.orders)                        # risk-reducing orders still go through


def test_orders_above_freeze_quantity_are_split():
    eng, feed = make(lambda t: 24000.0)
    feed.t = OPEN + 120; eng.spot_bars.tick(2, 24000.0)
    assert eng._submit("CE", 24000.0, 60, "BUY", "protective_wing_buy")
    assert [o.lots for o in eng.orders] == [27, 27, 6]


def test_state_roundtrip(tmp_path):
    f = tmp_path / "state.json"
    eng, feed = make(lambda t: 24012.0, state_file=str(f))
    run(eng, feed, OPEN, OPEN + 130)
    eng.save(); eng2, _ = make(lambda t: 24012.0, state_file=str(f)); eng2.load()
    assert eng2.book.snapshot() == eng.book.snapshot() and eng2.done_waves == eng.done_waves and eng2.spot_bars.close == eng.spot_bars.close


def test_full_day_replay_invariants():
    o, h, l, c, chain = make_day(seed=3)
    feed = ReplayFeed(o, h, l, c, chain.strikes, chain.bars); broker = PaperBroker(feed); eng = D1Engine(config_for("NIFTY", "2026-07-01"), feed, broker)
    run_replay(eng, feed)
    sched = [x for x in eng.orders if x.role == "scheduled_straddle"]
    assert sum(x.lots for x in sched if x.right == "CE") == 33 and sum(x.lots for x in sched if x.right == "PE") == 33
    shorts = {r: eng.book.short_count(r, False) for r in ("CE", "PE")}; wings = {r: eng.book.wing_count(r, False) for r in ("CE", "PE")}
    assert shorts == wings                                                               # wings equal shorts at the end of the day (lump is separate)
    net = broker.positions()
    for (r, k), v in net.items():                                                        # broker position = longs (wings + lump) - shorts, contract by contract
        eb = eng.book.wings.get((r, k), 0) + eng.book.lump.get((r, k), 0) - len(eng.book.shorts.get((r, k), []))
        assert v == eb
    assert len([x for x in eng.orders if x.role == "overnight_lump"]) >= 1
