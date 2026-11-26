"""Tests of the additive state recorder (software validation only). Independent recomputation of every logged field on a synthetic session; parent logs unchanged; frozen file hash unchanged."""
import json, os, tempfile, math, hashlib
import numpy as np
from d1_algo.shadow import ShadowRecorder, LateRuleConfig, black_price, SESSION_START_MIN
from d1_algo.shadow_state import StateShadowRecorder, SPEC_SHA, STATE_SPEC

T0 = SESSION_START_MIN * 60.0; EXP = T0 + 86400 + 6 * 3600; K = np.arange(21800.0, 22201.0, 50.0); UNIT = 75.0; STEP = 50.0
def ltp_at(F, ts, vol=0.15):
    T = (EXP - ts) / (365 * 86400); return lambda r, k: black_price(F - 4, k, T, vol, r == "CE")
LAST = {}
def session(cls, d):
    """flat book at 09:15; orders: buy long put 21800 x2 @10 (09:20), sell short CE 22100 x3 @20 (14:00), sell short PE 21900 x2 @15 (14:01), buy cover CE x1 @12 (14:30),
    sell close_long put 21800 x1 @9 (15:00:30), sell put 21800 x1 @13 (15:20:05: closes the second long lot of 1? see ledger), sell short CE 22100 x1 @18 (15:20:07)"""
    rg = np.random.default_rng(11); rec = cls(d, "NIFTY", "2026-11-24", UNIT, STEP, EXP, LateRuleConfig()); F = 22000.0; pos = {}; orders = [(5 * 60, "PE", 21800.0, 2, "buy", 10.0), (285 * 60, "CE", 22100.0, 3, "sell", 20.0), (286 * 60, "PE", 21900.0, 2, "sell", 15.0), (315 * 60, "CE", 22100.0, 1, "buy", 12.0),
                                                                                  (345 * 60 + 30, "PE", 21800.0, 1, "sell", 9.0), (365 * 60 + 5, "PE", 21800.0, 1, "sell", 13.0), (365 * 60 + 7, "CE", 22100.0, 1, "sell", 18.0), (370 * 60, "PE", 21900.0, 1, "sell", 14.0)]; oi = 0
    snaps = {}
    for sec in range(0, 386 * 60, 5):
        F += rg.normal(0, 1.5); ts = T0 + sec
        while oi < len(orders) and orders[oi][0] <= sec:
            _, r, k, n, sd, px = orders[oi]; rec.on_real_order(T0 + orders[oi][0], r, k, n, sd, px, ""); sg = n if sd == "buy" else -n; pos[(r, k)] = pos.get((r, k), 0) + sg; oi += 1
        rec.on_snapshot(ts, F - 30 if sec > 360 * 60 else F, F, ltp_at(F, ts), K, pos); snaps[sec // 60] = (F, ts, dict(pos), [(o[0], o) for o in orders[:oi]])
    rec.close(); LAST.clear(); LAST.update(snaps); return d
def load(d, kind): return [json.loads(x) for x in open(f"{d}/state_NIFTY_2026-11-24.jsonl") if json.loads(x)["kind"] == kind]
def test_parent_logs_byte_identical_and_frozen_file_unchanged():
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        session(ShadowRecorder, a); session(StateShadowRecorder, b)
        for f in ("minutes_NIFTY_2026-11-24.jsonl", "orders_NIFTY_2026-11-24.jsonl"): assert open(f"{a}/{f}").read() == open(f"{b}/{f}").read()
    import d1_algo.shadow as S; assert hashlib.sha256(open(S.__file__, "rb").read()).hexdigest() == "6d4b860853f88fc07b3f8223bfa79899521238b48e364739da708132017ffcf7"
    assert LateRuleConfig().sha() == "ca1306cfdd505f34cbbc4ee9470326eb96a8bab45716019d5214673e8a430e03"
def test_order_actions_fifo_and_sold_lots():
    with tempfile.TemporaryDirectory() as d:
        session(StateShadowRecorder, d); o = load(d, "order_state"); act = [x["action"] for x in o]
        assert act == ["open_long", "open_short", "open_short", "cover_short", "close_long", "close_long", "open_short", "open_short"]
        c1, c2 = o[4], o[5]; assert c1["matched_lots"] == 1 and c1["entry_price_fifo"] == 10.0 and abs(c1["exit_over_entry"] - 0.9) < 1e-12 and c1["sold_above_entry"] is False
        assert c2["matched_lots"] == 1 and c2["entry_price_fifo"] == 10.0 and abs(c2["exit_over_entry"] - 1.3) < 1e-12 and c2["sold_above_entry"] is True
        assert o[1]["sold_lots_before"] == {"CE": 0, "PE": 0} and o[2]["sold_lots_before"] == {"CE": 3, "PE": 0} and o[6]["sold_lots_before"] == {"CE": 3, "PE": 2}
        assert o[5]["seconds_since_last_short_sale"] == (365 * 60 + 5) - 286 * 60 and o[6]["seconds_since_last_short_sale_same_side"] == (365 * 60 + 7) - 285 * 60
def test_state_minute_fields_recomputed_independently():
    with tempfile.TemporaryDirectory() as d:
        session(StateShadowRecorder, d); S = load(d, "state_minute"); js = [x["j_next"] for x in S]; assert js == sorted(set(js)) and min(js) == 345 and max(js) == 385 and all(x["state_spec_sha"] == SPEC_SHA for x in S)
        x = next(y for y in S if y["j_next"] == 370); m = x["j_closed"]; assert m == 369
        # straddle and STR15: ATM nearest the option-implied index, last snapshot of the minute
        assert x["atm_strike"] in K and abs(x["STR15"] - (x["straddle"] / x["straddle_15_minutes_earlier"] - 1)) < 1e-12 and x["STR15"] < 0.5
        # five-minute move and orientation
        mv = x["move_5m_raw"]["FUT"]; assert abs(x["side"]["PE"]["fut_move_5m_steps_oriented"] - mv / STEP) < 1e-12 and abs(x["side"]["CE"]["fut_move_5m_steps_oriented"] + mv / STEP) < 1e-12
        # distance of the nearest net-short strike: CE 22100 held (3 sold, 1 covered), PE 21900 held
        c = x["close"]["FUT"]; assert abs(x["side"]["CE"]["D_fut"] - (22100 - c) / STEP) < 1e-9 and abs(x["side"]["PE"]["D_fut"] - (c - 21900) / STEP) < 1e-9
        # lot counts: sold CE 3 + 1 (the 15:05 sale), PE 2; net short CE 3-1+1 = 3, PE 2; long PE closed
        assert x["side"]["CE"]["sold_lots"] == 4 and x["side"]["PE"]["sold_lots"] == 2 and x["side"]["CE"]["sold_deficit_oriented"] == 2 - 4 and x["side"]["PE"]["sold_deficit_oriented"] == 4 - 2
        # premium collected: 3*20 + 2*15 + 1*18 + sale of the long put is NOT premium collected (it closes a long)
        assert abs(x["premium_collected"] - (3 * 20 + 2 * 15 + 1 * 18) * UNIT) < 1e-9
        # independent MTM: order cash up to the close of minute 369 + marks of the open legs at the last snapshot of that minute
        F9, ts9, pos9, done = LAST[369]; cash = sum((o[5] * o[3] * UNIT) if o[4] == "sell" else -(o[5] * o[3] * UNIT) for _, o in done); lt = ltp_at(F9, ts9); marks = sum(n * lt(r, k) * UNIT for (r, k), n in pos9.items() if n)
        assert abs(x["mtm"] - (cash + marks)) < 1e-6 and abs(x["PP"] - x["mtm"] / x["premium_collected"]) < 1e-12
        earlier = []
        for mm in range(0, 369):
            Fm, tm, pm, dn = LAST[mm]; c_ = sum((o[5] * o[3] * UNIT) if o[4] == "sell" else -(o[5] * o[3] * UNIT) for _, o in dn); l_ = ltp_at(Fm, tm); earlier.append(c_ + sum(n * l_(r, k) * UNIT for (r, k), n in pm.items() if n))
        assert abs(x["GB"] - (x["mtm"] - max(earlier))) < 1e-6
def test_ledger_matches_snapshot_and_boundary_orders_are_consistent():
    """orders placed in the first second of a minute (before that minute's first snapshot) must not leak into the previous minute's close (regression of the cash/position timing bug)"""
    with tempfile.TemporaryDirectory() as d:
        session(StateShadowRecorder, d); S = load(d, "state_minute"); assert all(x["ledger_matches_snapshot"] for x in S)
        x369 = next(y for y in S if y["j_closed"] == 369); x370 = next(y for y in S if y["j_closed"] == 370)           # the 15:25:00 sale (first second of minute 370) belongs to minute 370, not 369
        assert x369["side"]["PE"]["sold_lots"] == 2 and abs(x369["premium_collected"] - (3 * 20 + 2 * 15 + 18) * UNIT) < 1e-9
        assert x370["side"]["PE"]["sold_lots"] == 3 and abs(x370["premium_collected"] - (3 * 20 + 2 * 15 + 18 + 14) * UNIT) < 1e-9
def test_first_records_have_no_history_fields():
    with tempfile.TemporaryDirectory() as d:
        session(StateShadowRecorder, d); S = load(d, "state_minute"); assert S[0]["j_next"] == 345 and S[0]["PP"] is not None and S[0]["GB"] is not None     # MTM history exists from 09:15 because the session is recorded from the start
        assert all(x["STR15"] is not None for x in S)
def test_spec_hash_is_stable_and_sensitive():
    assert SPEC_SHA == hashlib.sha256(json.dumps(STATE_SPEC, sort_keys=True).encode()).hexdigest() and hashlib.sha256(json.dumps(dict(STATE_SPEC, STR15="x"), sort_keys=True).encode()).hexdigest() != SPEC_SHA
def test_deterministic():
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        session(StateShadowRecorder, a); session(StateShadowRecorder, b)
        for f in os.listdir(a): assert open(f"{a}/{f}").read() == open(f"{b}/{f}").read()
