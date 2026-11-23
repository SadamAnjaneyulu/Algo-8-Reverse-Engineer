"""Unit tests (run: python -m pytest test_algo8_d1.py -q). Synthetic data only."""
import numpy as np
import pytest
from algo8_d1 import (Config, D1Strategy, SCHEDULE_A, SCHEDULE_B, MINUTES, atm_strike, breakout_fires, config_for, ladder_fires, minute_of)
from example_synthetic import make_day


@pytest.fixture(scope="module")
def day():
    return make_day(seed=3)


def test_timetable_lengths_and_minutes():
    assert len(SCHEDULE_A) == 33 and len(SCHEDULE_B) == 33
    assert minute_of(1) == 1 and minute_of(900) == 16 and minute_of(18840) == 315


def test_scheduled_straddles_are_atm_pairs_one_lot_each(day):
    o, h, l, c, chain = day
    res = D1Strategy(Config()).run(o, h, l, c, chain)
    sched = [x for x in res.orders if x.role == "scheduled_straddle"]
    assert sum(x.lots for x in sched if x.right == "CE") == 33 and sum(x.lots for x in sched if x.right == "PE") == 33
    for x in sched:
        j = x.minute; assert x.strike == atm_strike(chain.strikes, c[j - 1])          # strike = ATM of the previous close


def test_every_short_has_a_long_on_the_same_right(day):
    o, h, l, c, chain = day
    res = D1Strategy(Config(lump_minute=10 ** 6)).run(o, h, l, c, chain)               # no lump: long lots must equal short lots right by right
    for right in ("CE", "PE"):
        s = sum(v for (r, _), v in res.short_lots.items() if r == right); L = sum(v for (r, _), v in res.long_lots.items() if r == right)
        assert s == L


def test_wings_are_out_of_the_money(day):
    o, h, l, c, chain = day
    res = D1Strategy(Config()).run(o, h, l, c, chain)
    for x in res.orders:
        if x.role == "protective_wing_buy":
            s = c[x.minute - 1]; assert (x.strike > s) if x.right == "CE" else (x.strike < s)


def test_breakout_fires_once_per_side_per_candle_and_inside_window():
    n = MINUTES; high = np.full(n, 100.0); low = np.full(n, 99.0)
    high[70] = 110.0                                                                  # inside an earlier candle, defines the channel
    high[80] = 130.0; high[85] = 140.0                                                # two breaks in the same candle -> one fire
    fires = breakout_fires(high, low, Config(strike_step=1.0))
    assert [f for f in fires if f[1] == 1] and len([f for f in fires if f[1] == 1 and f[0] < 90]) == 1
    assert all(75 <= f[0] <= 360 for f in fires)


def test_ladder_needs_fresh_extreme_and_step():
    n = MINUTES; close = np.full(n, 100.0); high = close + 0.1; low = close - 0.1
    low[100:] = 90.0; close[100:] = 90.0                                              # a drop: calls should be sold
    out = ladder_fires(close, high, low, {"CE": [5], "PE": [5]}, Config(strike_step=10.0))
    assert 100 in out and "CE" in out[100] and not any("PE" in v for v in out.values())


def test_stop_buys_back_a_lot_when_price_reaches_ratio(day):
    o, h, l, c, chain = day
    res = D1Strategy(Config(stop_ratio=1.01)).run(o, h, l, c, chain)                  # very tight stop -> some buy-backs must appear
    assert any(x.role == "stop_buyback" for x in res.orders)
    res2 = D1Strategy(Config(stop_ratio=1000.0)).run(o, h, l, c, chain)               # unreachable stop -> none
    assert not any(x.role == "stop_buyback" for x in res2.orders)


def test_overnight_lump_on_heavier_side_after_close_minute(day):
    o, h, l, c, chain = day
    res = D1Strategy(Config(lump_minute=356)).run(o, h, l, c, chain)
    lump = [x for x in res.orders if x.role == "overnight_lump"]
    assert len(lump) == 1 and lump[0].minute == 356 and lump[0].side == "buy"


def test_config_regimes():
    assert config_for("NIFTY", "2026-07-01").timetable == SCHEDULE_A and config_for("NIFTY", "2026-10-01").timetable == SCHEDULE_B
    assert config_for("SENSEX", "2026-07-01").strike_step == 100.0 and config_for("NIFTY", "2026-09-01").lump_minute == 375
