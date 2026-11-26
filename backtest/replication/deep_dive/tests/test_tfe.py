"""Verification of the per-event teacher-forced harness (reports/D1_TFE_PLAN.md, software checks 1-7), BEFORE any TF-E number is read. Synthetic scenarios with answers known independently, plus the real-log book check."""
import os, sys, numpy as np, pandas as pd, pytest
HERE = os.path.dirname(os.path.abspath(__file__)); BASE = os.path.join(HERE, '..')
for p in (f'{BASE}/src', f'{BASE}/../..', f'{BASE}/../../..', f'{BASE}/../../../d1_strategy'): sys.path.insert(0, p)
_cwd = os.getcwd(); os.chdir(f'{BASE}/src')
import bl_tfe as T
os.chdir(_cwd)
from d1_algo.book import Book
from d1_algo.models import Lot
from test_d1_algo import make, run, OPEN
END = OPEN + 700
def row(t, role, cp="CE", k=24000.0, n=1, side=None, module="num", px=50.0, rid=[0]):
    rid[0] += 1; return dict(t=int(t), row=rid[0], cp=cp, strike=float(k), side=side or ("Sell" if role in ("open_short", "close_long") else "Buy"), lots=n, role=role, module=module, px=px)
def tf(real, variant="book", **cfg):
    eng, feed = make(lambda t: 24012.0, timetable=[10, 200], lump_minute=10 ** 6, **cfg); return T.run_teacher_forced(eng, feed, real, variant, OPEN, END)
def free(**cfg):
    eng, feed = make(lambda t: 24012.0, timetable=[10, 200], lump_minute=10 ** 6, **cfg); run(eng, feed, OPEN, END); return eng
def key(o): return (o.ts, o.right, o.strike, o.lots, o.side, o.role, o.decision_id)
# ------------------------------------------------------------------------------------------------------ 1. rebuilt real book vs the real log
def test_rebuilt_book_equals_cumulative_real_position_after_every_real_order():
    os.chdir(f'{BASE}/src')
    try: import bl_fr_sim as S
    finally: os.chdir(_cwd)
    n = bad = 0
    for (u, e), g in S.REAL.sort_values(['und', 'expiry', 'row']).groupby(['und', 'expiry']):
        b = Book(); net = {}
        for r in T.real_rows_of(S.REAL.assign(row=S.REAL.row), u, e):
            pass
        for r in sorted(T.real_rows_of(S.REAL, u, e), key=lambda r: r['row']):
            T.apply_real(b, r); k = (r['cp'], r['strike']); net[k] = net.get(k, 0) + (r['lots'] if r['side'] == 'Buy' else -r['lots']); n += 1; bad += T.net_positions(b).get(k, 0) != net[k]
        assert T.net_positions(b) == {k: v for k, v in net.items() if v}
    assert n == 9915 and bad == 0
def test_apply_real_roles_and_excess_close_long():
    b = Book(); T.apply_real(b, row(100, "open_short", n=2, px=7.0)); assert len(b.shorts[("CE", 24000.0)]) == 2 and b.shorts[("CE", 24000.0)][0].entry_price == 7.0 and b.shorts[("CE", 24000.0)][0].minute == (100 - OPEN) // 60
    T.apply_real(b, row(101, "cover_short", n=1)); assert len(b.shorts[("CE", 24000.0)]) == 1
    T.apply_real(b, row(102, "open_long", cp="PE", k=22000.0, n=3)); T.apply_real(b, row(103, "open_long", cp="PE", k=22500.0, n=4, module="v_")); assert b.wings[("PE", 22000.0)] == 3 and b.lump[("PE", 22500.0)] == 4
    T.apply_real(b, row(104, "close_long", cp="PE", k=22500.0, n=6, side="Sell")); assert b.lump[("PE", 22500.0)] == 0 and len(b.shorts[("PE", 22500.0)]) == 2          # lump 4 reduced, excess 2 becomes a short: net -2 exactly
    with pytest.raises(ValueError): T.apply_real(b, row(105, "mystery"))
# ------------------------------------------------------------------------------------------------------ 2-3. empty log == F; oracle
def test_empty_real_log_equals_free_running():
    eng, drift, shadow = tf([]); f = free(); assert [key(o) for o in eng.orders] == [key(o) for o in f.orders] and drift == [] and len(eng.orders) > 0
def engine_role_to_log(o):
    return {"scheduled_straddle": ("open_short", "num"), "breakout_straddle": ("open_short", "num"), "breakout_extra": ("open_short", "num"), "ladder_solo": ("open_short", "num"), "stop_buyback": ("cover_short", "num"), "opening_wing_buy": ("open_long", "num"),
            "protective_wing_buy": ("open_long", "h_"), "protective_wing_sell": ("close_long", "h_"), "overnight_lump": ("open_long", "v_")}[o]
def test_oracle_the_simulators_own_fills_as_the_real_log_change_nothing_and_drift_is_zero():
    f = free(); real = [row(fl.ts, engine_role_to_log(fl.role)[0], cp=fl.right, k=fl.strike, n=fl.lots, side="Buy" if fl.side == "BUY" else "Sell", module=engine_role_to_log(fl.role)[1], px=fl.price) for fl in f.fills]; assert len(real) >= 6
    eng, drift, shadow = tf(real); assert [key(o) for o in eng.orders] == [key(o) for o in f.orders]
    assert len(drift) > 0 and all(d["l1"] == 0 and d["S_sim_CE"] == d["S_real_CE"] and d["L_sim_PE"] == d["L_real_PE"] for d in drift)
    assert T.net_positions(eng.book) == T.net_positions(shadow) == T.net_positions(f.book)
# ------------------------------------------------------------------------------------------------------ 4. reconciliation correctness and drift diagnostic
def test_book_is_replaced_by_the_real_book_including_entry_prices_and_drift_is_measured_before_the_reset():
    real = [row(OPEN + 400, "open_short", cp="PE", k=23000.0, n=2, px=12.5), row(OPEN + 450, "open_long", cp="PE", k=21000.0, n=1)]      # the real system did something the simulator did not; the simulator's own waves at +11 s and +201 s are not in the real log
    eng, drift, shadow = tf(real); assert eng.book.shorts.keys() == {("PE", 23000.0)} and [l.entry_price for l in eng.book.shorts[("PE", 23000.0)]] == [12.5, 12.5] and eng.book.wings == {("PE", 21000.0): 1}   # simulator waves are gone: book == real book
    d0 = drift[0]; assert d0["t"] == OPEN + 400 and d0["S_sim_CE"] > 0 and d0["S_real_CE"] == 0 and d0["l1"] > 0                                      # before the reset the simulator had its own wave shorts the real log did not have
    assert len(eng.orders) > 0 and any(o.role == "scheduled_straddle" for o in eng.orders)                                                           # its orders stay in the scored stream: only the book is reset
# ------------------------------------------------------------------------------------------------------ 5. no leakage of the real order at its own second
def test_the_simulator_decides_at_second_t_without_knowing_real_orders_at_or_after_t():
    t_wave = OPEN + 60 + 200                                                                                                                       # a scheduled wave second
    real_same_second = [row(OPEN + 20, "open_short", cp="CE", k=24100.0, n=5, px=9.0), row(t_wave, "open_short", cp="PE", k=23800.0, n=3, px=8.0), row(t_wave + 100, "cover_short", cp="CE", k=24000.0, n=1)]
    a = tf(real_same_second)[0]; b = tf([r for r in real_same_second if r["t"] < t_wave])[0]                                                         # b: every real order at or after the wave second removed
    assert [key(o) for o in a.orders if o.ts <= t_wave] == [key(o) for o in b.orders if o.ts <= t_wave] and any(o.ts == t_wave for o in a.orders)
    c = tf([r for r in real_same_second if r["t"] < t_wave - 5])[0]; assert [key(o) for o in a.orders if o.ts <= t_wave - 6] == [key(o) for o in c.orders if o.ts <= t_wave - 6]
def test_a_real_order_before_t_does_change_later_decisions():
    base = tf([])[0]; a = tf([row(OPEN + 30, "open_short", cp="CE", k=24000.0, n=6, px=50.0)])[0]                                                   # real shorts early: the wing controller sees a bigger short book after the reset
    assert [key(o) for o in a.orders] != [key(o) for o in base.orders]
# ------------------------------------------------------------------------------------------------------ 6. window
def test_real_order_outside_the_replay_window_raises():
    with pytest.raises(ValueError): tf([row(OPEN - 5, "open_short")])
    with pytest.raises(ValueError): tf([row(END + 5, "open_short")])
# ------------------------------------------------------------------------------------------------------ 7. TF-E-m differs only through the two named inputs
def test_memory_variant_sets_only_last_sale_and_the_wing_timer():
    real = [row(OPEN + 400, "open_short", cp="CE", k=24000.0, n=1, px=33.0)]
    a = tf(real, "book")[0]; m = tf(real, "memory")[0]
    assert a.last_sale_price["CE"] != 33.0 and m.last_sale_price["CE"] == 33.0
    pre = lambda e: [key(o) for o in e.orders if o.ts <= OPEN + 400]; assert pre(a) == pre(m)                                                       # identical decisions up to the real order
    late = lambda e: [o for o in e.orders if o.role == "protective_wing_buy" and o.ts > OPEN + 400]; assert len(late(m)) > 0 and len(late(a)) == 0         # the real body order armed the wing controller in the variant only (a consequence of the named input)
    nobody = [row(OPEN + 400, "open_long", cp="CE", k=26000.0, n=1, module="h_")]; x = tf(nobody, "memory")[0]; y = tf(nobody, "book")[0]; assert [key(o) for o in x.orders] == [key(o) for o in y.orders]   # a wing order (not body) changes nothing in the memory variant
# ------------------------------------------------------------------------------------------------------ Addendum 2: re-decision flag (post hoc)
def tf_quiet(real, variant="book"):
    eng, feed = make(lambda t: 24012.0, lambda r, k, s, t: 50.0, timetable=[], lump_minute=10 ** 6, order_split="one_lot_v2"); return T.run_teacher_forced(eng, feed, real, variant, OPEN, END)
def stops(eng): return [(o.ts, f) for o, f in zip(eng.orders, eng.tfe_redecision) if o.role == "stop_buyback"]
def test_redecision_flag_marks_only_stops_that_repeat_a_buyback_the_reset_undid():
    real = [row(OPEN + 100, "open_short", cp="PE", k=23000.0, n=3, px=10.0)] + [row(OPEN + 200 + 10 * i, "open_long", cp="CE", k=26000.0 + 50 * i, n=1, module="h_") for i in range(4)]       # real keeps 3 lots the simulator wants to stop; four unrelated real events follow
    eng = tf_quiet(real)[0]; st = stops(eng)
    assert len(eng.tfe_redecision) == len(eng.orders) and len(st) >= 9 and [f for _, f in st[:3]] == [False] * 3                                    # the first epoch's three buy-backs are first decisions (including lots the simulator never held)
    assert all(f for _, f in st[3:]) and len({ts for ts, _ in st}) >= 4                                                                           # every later epoch only repeats them
def test_no_redecision_flag_when_the_real_system_covered_the_lots_too():
    real = [row(OPEN + 100, "open_short", cp="PE", k=23000.0, n=3, px=10.0), row(OPEN + 125, "cover_short", cp="PE", k=23000.0, n=3, side="Buy"), row(OPEN + 200, "open_long", cp="CE", k=26000.0, n=1, module="h_")]
    eng = tf_quiet(real)[0]; st = stops(eng); assert len(st) == 3 and not any(f for _, f in st)                                                      # the simulator stopped once, the real book agrees afterwards: nothing is restored, nothing repeats
def test_only_stop_buybacks_are_flagged_and_flags_never_change_the_order_stream():
    real = [row(OPEN + 100, "open_short", cp="PE", k=23000.0, n=3, px=10.0)] + [row(OPEN + 200 + 10 * i, "open_long", cp="CE", k=26000.0 + 50 * i, n=1, module="h_") for i in range(4)]
    eng = tf_quiet(real)[0]; assert all(o.role == "stop_buyback" for o, f in zip(eng.orders, eng.tfe_redecision) if f)
    again = tf_quiet(real)[0]; assert [key(o) for o in eng.orders] == [key(o) for o in again.orders] and eng.tfe_redecision == again.tfe_redecision      # deterministic; the flag is metadata only
def tf_price(real, price_fn, variant="book"):
    eng, feed = make(lambda t: 24012.0, price_fn, timetable=[], lump_minute=10 ** 6, order_split="one_lot_v2"); return T.run_teacher_forced(eng, feed, real, variant, OPEN, END)
def test_pool_is_capped_by_the_real_short_lots_so_a_real_cover_cancels_the_pending_repeat():
    px = lambda r, k, s, t: 5.0 if OPEN + 200 <= t < OPEN + 300 else 50.0                                                                          # price high (stop), then low (no stop), then high again
    real = [row(OPEN + 100, "open_short", cp="PE", k=23000.0, n=3, px=10.0), row(OPEN + 200, "open_long", cp="CE", k=26000.0, n=1, module="h_"), row(OPEN + 250, "cover_short", cp="PE", k=23000.0, n=3, side="Buy"),
            row(OPEN + 310, "open_short", cp="PE", k=23000.0, n=2, px=10.0), row(OPEN + 400, "open_long", cp="CE", k=26050.0, n=1, module="h_")]
    eng = tf_price(real, px)[0]; st = stops(eng); late = [f for ts, f in st if OPEN + 310 < ts < OPEN + 400]
    assert [f for ts, f in st if ts < OPEN + 200] == [False] * 3 and late == [False, False]                                                # lots sold by the real system at +310 are new lots: their stops are first decisions, not repeats of the cancelled +120 stops
def test_only_lots_the_simulator_itself_bought_back_can_be_repeats():
    real = [row(OPEN + 100, "open_short", cp="PE", k=23000.0, n=3, px=10.0), row(OPEN + 130, "open_short", cp="PE", k=23000.0, n=2, px=10.0), row(OPEN + 400, "open_long", cp="CE", k=26000.0, n=1, module="h_")]
    eng = tf_quiet(real)[0]; ep = [(ts, f) for ts, f in stops(eng) if OPEN + 130 < ts < OPEN + 400]
    assert sum(f for _, f in ep) == 3 and sum(not f for _, f in ep) == 2                                                                              # of the 5 restored lots, 3 repeat the simulator's own buy-backs, 2 are lots it never held and is deciding on for the first time
