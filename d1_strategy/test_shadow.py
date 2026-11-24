"""Tests of the shadow recorder and the frozen late-sale rule (software validation only; says nothing about the strategy)."""
import json, os, tempfile, math
import numpy as np
from algo8_d1 import ladder_fires, Config
from d1_algo.shadow import (FrozenLateRule, LateRuleConfig, ShadowRecorder, solo_strike, black_price, implied_vol, net_delta, minute_of_day, SESSION_START_MIN)

T0 = (SESSION_START_MIN) * 60.0


def walk(n, seed, step=3.0):
    rg = np.random.default_rng(seed); c = 22000 + np.cumsum(rg.normal(0, step, n)); o = np.r_[c[0], c[:-1]] + rg.normal(0, step * 0.8, n); h = np.maximum(o, c) + np.abs(rg.normal(0, step / 2, n)); l = np.minimum(o, c) - np.abs(rg.normal(0, step / 2, n)); return o, h, l, c     # gaps: the open is NOT the previous close (this exposed a minute-seeding bug)


def drive(rule, o, h, l, c, events):
    """feed the rule minute by minute, ticks o, (h, l in the order that does not matter), c; real sales at given minutes"""
    ev = {"CE": sorted(events["CE"]), "PE": sorted(events["PE"])}
    for j in range(len(c)):
        for r in ("CE", "PE"):
            for e in ev[r]:
                if e == j - 0 and False: pass
        base = T0 + 60.0 * j
        for k, p in enumerate((o[j], h[j], l[j], c[j])): rule.on_tick(base + 10 * k, p)
        for r in ("CE", "PE"):
            for e in ev[r]:
                if e == j: rule.on_real_sale(r, j)
    rule.flush()


def test_frozen_rule_equals_batch_ladder():
    for seed in range(12):
        n = 300; o, h, l, c = walk(n, seed); rg = np.random.default_rng(100 + seed)
        ev = {"CE": sorted(set(rg.integers(2, 250, 6).tolist())), "PE": sorted(set(rg.integers(2, 250, 6).tolist()))}
        cfg = Config(); cfg.ladder_gate_min = 5; cfg.strike_step = 50.0; batch = ladder_fires(c, h, l, ev, cfg); bset = {(j, r) for j, rs in batch.items() for r in rs}
        rule = FrozenLateRule(LateRuleConfig(window_start=0, window_end=10 ** 6), 50.0); drive(rule, o, h, l, c, ev); live = {(f["minute"], f["right"]) for f in rule.fires}
        assert live == bset, (seed, sorted(live ^ bset)[:5])
        assert np.allclose(rule.hi, h) and np.allclose(rule.lo, l) and np.allclose(rule.cl, c), seed                  # minute bars rebuilt from ticks equal the input bars (gaps included)
        assert len(bset) > 0 or seed > 5


def test_rule_window_and_hash_frozen():
    cfg = LateRuleConfig(); assert (cfg.gate_min, cfg.ladder_step, cfg.window_start, cfg.window_end, cfg.underlying, cfg.lots) == (5, 0.2, 360, 384, "FUT", 1)
    assert cfg.sha() == LateRuleConfig().sha() and LateRuleConfig(gate_min=6).sha() != cfg.sha()
    n = 400; o, h, l, c = walk(n, 3, 6.0); rule = FrozenLateRule(cfg, 50.0); drive(rule, o, h, l, c, {"CE": [5, 100], "PE": [5, 100]}); assert all(360 <= f["minute"] <= 384 for f in rule.fires)


def test_solo_strike_and_black():
    K = np.arange(21900.0, 22100.1, 50.0); prem = {float(k): max(1.0, 80.0 - abs(k - 22000) * 0.5) for k in K}
    assert solo_strike(K, 22000.0, lambda k: prem[k], None, 50.0) == 22000.0
    assert solo_strike(K, 22000.0, lambda k: prem[k], 55.0, 50.0) in (22050.0, 21950.0)           # premium 55 sits one step away
    F, Kk, T, v = 22000.0, 22000.0, 1 / 365, 0.15; pc, pp = black_price(F, Kk, T, v, True), black_price(F, Kk, T, v, False); assert abs((pc - pp) - (F - Kk)) < 1e-6
    assert abs(implied_vol(pc, F, Kk, T, True) - v) < 1e-6
    ltp = lambda r, k: black_price(F, k, T, v, r == "CE"); d = net_delta({("CE", 22000.0): -10, ("PE", 22000.0): -10}, F, T, ltp, 50.0); assert abs(d) < 0.05 * 10 * 50 * 0.5      # near-neutral straddle
    dc = net_delta({("CE", 22000.0): 1}, F, T, ltp, 1.0); dp = net_delta({("PE", 22000.0): 1}, F, T, ltp, 1.0); assert abs((dc - dp) - 1.0) < 1e-6 and 0.45 < dc < 0.56


def _run_recorder(d):
    rg = np.random.default_rng(5); K = np.arange(21800.0, 22201.0, 50.0); rec = ShadowRecorder(d, "NIFTY", "2026-11-24", 75.0, 50.0, T0 + 86400 + 6 * 3600, LateRuleConfig())
    F = 22000.0; pos = {("CE", 22100.0): -3, ("PE", 21900.0): -5, ("CE", 22400.0): 3}
    for sec in range(345 * 60, 385 * 60, 5):
        F += rg.normal(0, 1.2); ts = T0 + sec; vol = 0.15; T = (T0 + 86400 + 6 * 3600 - ts) / (365 * 86400)
        ltp = (lambda Fv, Tv: (lambda r, k: black_price(Fv, k, Tv, vol, r == "CE")))(F - 4, T)
        rec.on_snapshot(ts, F - 30 if sec > 360 * 60 else F, F, ltp, K, pos)
        if sec in (362 * 60 + 15, 368 * 60 + 40): rec.on_real_order(ts + 1, "CE", 22100.0, 1, "sell", 20.0, "open_short")
    rec.close(); return d


def test_recorder_writes_pre_order_state_and_quiet_minutes():
    with tempfile.TemporaryDirectory() as d:
        _run_recorder(d); mins = [json.loads(x) for x in open(f"{d}/minutes_NIFTY_2026-11-24.jsonl")]; ords = [json.loads(x) for x in open(f"{d}/orders_NIFTY_2026-11-24.jsonl")]
        assert len(ords) == 2 and len(mins) >= 35 and all(m["kind"] == "minute" for m in mins)
        js = [m["j"] for m in mins]; assert js == sorted(set(js)) and 345 <= min(js) and max(js) >= 384            # every minute of the window, with or without an order
        o = ords[0]; assert o["book_before"]["short_CE"] == 3 and o["book_before"]["short_PE"] == 5 and o["book_before"]["lighter_side"] == "CE"
        assert o["prices_before"]["FUT"]["prev"] is not None and o["prices_before"]["FUT"]["cur"] is not None and o["prices_before"]["FEED"]["prev"] is not None
        assert o["rule"]["ref"] is not None and "proposed_strike" in o["rule"] and len({m["rule_sha"] for m in mins} | {x["rule_sha"] for x in ords}) == 1
        assert math.isfinite(o["book_before"]["net_delta"]) and mins[-1]["book"] is not None


def test_recorder_is_deterministic():
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        _run_recorder(a); _run_recorder(b)
        for f in os.listdir(a): assert open(f"{a}/{f}").read() == open(f"{b}/{f}").read()
