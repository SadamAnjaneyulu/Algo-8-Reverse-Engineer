"""Unit tests of the standalone D0 engine with a synthetic market. The engine has no order input: real D0 orders cannot drive decisions."""
import inspect, numpy as np, pytest
from d0_algo import D0Config, D0Engine, D0Market, D0Opening
from d0_algo.engine import OPEN_S
K = np.arange(20000.0, 28001.0, 50.0); N = 375
def market(price=50.0, spot=24012.0, unit=65.0, **over):
    opt = {(cp, f): np.full((len(K), N), float(price)) for cp in ('CE', 'PE') for f in ('open', 'high', 'low', 'close')}
    spots = np.full(N, spot); m = D0Market(K=K, step=50.0, unit=unit, spot_open=spots.copy(), spot_high=spots.copy(), spot_low=spots.copy(), spot_close=spots.copy(), opt=opt)
    for k, v in over.items(): setattr(m, k, v)
    return m
def opening(lots=(), longs=None, oshort=None, cash=0.0): return D0Opening(lots=[list(l) for l in lots], longs=dict(longs or {}), oshort=dict(oshort or {}), cash=cash)
def run(cfg, mkt=None, op=None):
    mkt = mkt or market(); op = op or opening(); e = D0Engine(cfg, mkt, op); e.run(); return e, op
def kinds(e, cls): return [x for x in e.events if x.cls == cls]
def intraday_bb(e): return [x for x in e.events if x.cls == 'body_buyback' and x.j < 359]                                  # clearance at minute 359 is its own rule
QUIET = dict(enable_hedge=False, enable_cycle_stop=False)
def test_engine_has_no_order_input_and_validates_its_inputs():
    assert list(inspect.signature(D0Engine.__init__).parameters) == ['self', 'cfg', 'market', 'opening']                  # config, market, opening state: nothing else, no real orders
    with pytest.raises(AssertionError): D0Engine(D0Config(), market(), opening(lots=[('CE', 99999.0, 10.0)]))               # carried lot outside the chain
    with pytest.raises(AssertionError): D0Engine(D0Config(), market(), opening(longs={('h_', 'CE', 26000): 0}))             # non-positive opening position
def test_timetable_wave_sells_both_rights_at_the_atm_of_the_previous_close():
    e, _ = run(D0Config(waves=[(OPEN_S + 60 * 5 + 10, 2)], **QUIET)); s = kinds(e, 'body_sell'); assert [(x.cp, x.j, x.strike, x.lots) for x in s] == [('CE', 5, 24000, 2), ('PE', 5, 24000, 2)] and all(x.side == 'sell' and x.module == 'num' for x in s)
def test_buyback_fires_on_the_minute_high_at_theta_and_not_below():
    mk = market(price=10.0); mk.opt[('CE', 'high')][list(K).index(24000.0), 3] = 17.0
    e, _ = run(D0Config(buyback_theta=1.6, **QUIET), mk, opening(lots=[('CE', 24000.0, 10.0)])); b = intraday_bb(e); assert [(x.cp, x.j, x.strike, x.lots) for x in b] == [(('CE', 3, 24000, 1))] and b[0].side == 'buy'
    e2, _ = run(D0Config(buyback_theta=1.8, **QUIET), mk, opening(lots=[('CE', 24000.0, 10.0)])); assert not intraday_bb(e2)
def test_take_profit_and_switches():
    mk = market(price=10.0); mk.opt[('PE', 'low')][list(K).index(24000.0), 7] = 0.5
    e, _ = run(D0Config(buyback_theta=9.9, buyback_tp=0.1, **QUIET), mk, opening(lots=[('PE', 24000.0, 10.0)])); assert [(x.j, x.lots) for x in intraday_bb(e)] == [(7, 1)]
    e2, _ = run(D0Config(buyback_theta=9.9, buyback_tp=0.1, enable_buyback=False, **QUIET), mk, opening(lots=[('PE', 24000.0, 10.0)])); assert not intraday_bb(e2)
def test_cycle_stop_liquidates_everything_once_and_ends_the_day():
    mk = market(price=10.0); mk.opt[('CE', 'close')][list(K).index(24000.0), 10:] = 5000.0                                     # a short at 5,000 against 10: a huge mark-to-market loss
    e, op = run(D0Config(enable_hedge=False, buyback_theta=9.9), mk, opening(lots=[('CE', 24000.0, 10.0)] * 3, longs={('h_', 'CE', 26000): 3})); st = kinds(e, 'stop'); assert len(st) >= 1 and e.stopped and max(x.j for x in e.events) == st[0].j and st[0].j >= 10
    assert e.reconcile(op)                                                                                                     # opening position plus the stop's closing lots nets to flat
def test_clearance_at_minute_359_buys_back_shorts_and_sells_longs_and_stops_the_day():
    e, op = run(D0Config(buyback_theta=9.9, **QUIET), market(), opening(lots=[('CE', 24000.0, 10.0)] * 2, longs={('h_', 'PE', 22000): 4, ('num', 'CE', 26000): 1}))
    assert [(x.j, x.lots) for x in kinds(e, 'body_buyback')] == [(359, 2)] and sorted((x.cls, x.lots) for x in e.events if x.j == 359 and x.cls != 'body_buyback') == [('body_long', 1), ('wing_sell', 4)] and max(x.j for x in e.events) == 359 and e.reconcile(op)
def test_hedge_buys_exactly_the_gap_at_the_strike_nearest_the_premium_target_and_reconciles():
    prices = np.zeros((len(K), N)); atm = list(K).index(24000.0)
    for x, k in enumerate(K): prices[x, :] = max(60.0 - abs(k - 24000.0) / 50.0 * 2.0, 0.5)                                    # premium falls 2 per strike step from 60
    mk = market(); mk.opt[('CE', 'close')] = prices.copy()
    e, op = run(D0Config(buyback_theta=9.9, enable_cycle_stop=False), mk, opening(lots=[('CE', 24000.0, 10.0)] * 3)); w = [x for x in e.events if x.cls == 'wing_buy' and x.cp == 'CE']
    assert w and w[0].lots == 3 and w[0].strike > 24012 and abs(prices[list(K).index(w[0].strike), 0] - 0.025 * 60.0) <= abs(prices[atm + 1, 0] - 1.5) + 1e-9 and e.reconcile(op)
def test_determinism_and_each_rule_switch_removes_only_its_own_events():
    cfg = dict(waves=[(OPEN_S + 600, 1)], opening_wing_lots=4, **QUIET); a, _ = run(D0Config(**cfg)); b, _ = run(D0Config(**cfg)); assert a.events_frame().equals(b.events_frame())
    off, _ = run(D0Config(**{**cfg, 'enable_timetable': False})); assert not kinds(off, 'body_sell') and len([x for x in off.events if x.role == 'open_long']) == len([x for x in a.events if x.role == 'open_long']) == 2
    off2, _ = run(D0Config(**{**cfg, 'enable_opening_wings': False})); assert not [x for x in off2.events if x.role == 'open_long'] and len(kinds(off2, 'body_sell')) == len(kinds(a, 'body_sell'))
def test_cash_accounting_follows_every_fill_at_the_bar_price():
    e, op = run(D0Config(waves=[(OPEN_S + 60 * 5 + 10, 2)], **QUIET), market(price=50.0)); assert e.cash == pytest.approx(2 * 2 * 50.0 * 65.0)           # two rights x two lots sold at 50 x 65 units
    e2, _ = run(D0Config(buyback_theta=9.9, enable_cycle_stop=False), market(price=50.0), opening(lots=[('CE', 24000.0, 50.0)] * 3, cash=0.0)); bought = sum(x.lots for x in e2.events if x.cls == 'wing_buy')
    assert bought == 3 and e2.cash < 0 and e2.cash == pytest.approx(-sum(x.lots for x in e2.events if x.cls == 'wing_buy') * 50.0 * 65.0 + sum(x.lots for x in e2.events if x.cls == 'wing_sell') * 50.0 * 65.0 - sum(x.lots for x in e2.events if x.cls == 'body_buyback') * 50.0 * 65.0)
def test_risk_guard_refuses_sells_beyond_the_short_limit_and_the_sell_cap_monitors_and_can_be_relaxed():
    cfg = dict(waves=[(OPEN_S + 60 * 5 + 10, 3)], buyback_theta=9.9, enable_cycle_stop=False, enable_hedge=False)
    e, _ = run(D0Config(max_short_lots_per_right=4, **cfg), market(), opening(lots=[('CE', 24000.0, 50.0), ('CE', 24000.0, 50.0)]))                 # CE already short 2: a wave of 3 would make 5 > 4
    assert [x.cp for x in kinds(e, 'body_sell')] == ['PE'] and [(r[1], r[2]) for r in e.rejected] == [('CE', 'short lot limit')]
    e2, _ = run(D0Config(max_sell_decisions_per_minute=1, **cfg)); assert len(kinds(e2, 'body_sell')) == 1 and e2.rejected and e2.rejected[0][2] == 'too many sell decisions this minute'
    e3, _ = run(D0Config(max_short_lots_per_right=4, risk_mode='monitor', **cfg), market(), opening(lots=[('CE', 24000.0, 50.0), ('CE', 24000.0, 50.0)]))    # monitor: the breach is recorded and the sell proceeds
    assert not e3.rejected and len(e3.violations) == 1 and len(kinds(e3, 'body_sell')) == 2
    e4, _ = run(D0Config(waves=[(OPEN_S + 600, 1)], buyback_theta=9.9, enable_cycle_stop=False, enable_hedge=False), market(), opening(lots=[("CE", 24000.0, 50.0)] * 310)); assert e4.rejected             # the observed-envelope limit (306 with margin) refuses a further sale on a 310-lot short right

# ---- Gate 5c candidate switches (default off)
def test_opening_long_clock_default_off_changes_nothing():
    cfg = dict(waves=[(OPEN_S + 60 * 1 + 10, 3)], **QUIET)
    a, _ = run(D0Config(**cfg)); b, _ = run(D0Config(opening_long_clock=False, **cfg)); assert a.events_frame().equals(b.events_frame())
def test_opening_long_clock_buys_as_many_longs_as_lots_sold_in_that_minute_and_never_earlier():
    e, op = run(D0Config(waves=[(OPEN_S + 60 * 1 + 10, 3), (OPEN_S + 60 * 5 + 10, 4)], opening_long_clock=True, **QUIET)); L = kinds(e, 'body_long')
    longs = [x for x in L if x.role == 'open_long']; assert sorted((x.cp, x.j, x.lots) for x in longs) == [('CE', 1, 3), ('PE', 1, 3)] and all(x.side == 'buy' and x.module == 'num' for x in longs)   # sells at j=5 do not create longs
    assert e.reconcile(op)
def test_opening_long_clock_uses_only_sells_of_that_minute_no_lookahead():
    e0, _ = run(D0Config(waves=[(OPEN_S + 60 * 2 + 10, 3)], opening_long_clock=True, **QUIET)); assert not [x for x in kinds(e0, 'body_long') if x.role == 'open_long']      # sells at j=2: nothing at j=1
    e1, _ = run(D0Config(waves=[(OPEN_S + 60 * 1 + 10, 3)], opening_long_clock=True, **QUIET)); assert all(x.j == 1 for x in kinds(e1, 'body_long') if x.role == 'open_long')
def test_opening_long_clock_ignores_sells_of_earlier_minutes():
    e, _ = run(D0Config(waves=[(OPEN_S + 10, 5), (OPEN_S + 60 * 1 + 10, 2)], opening_long_clock=True, **QUIET)); assert sorted((x.cp, x.lots) for x in kinds(e, 'body_long') if x.role == 'open_long') == [('CE', 2), ('PE', 2)]
def test_era_clearance_clock_helper_and_engine_clears_at_that_minute():
    from d0_algo.config import clearance_minute_for
    assert clearance_minute_for('2026-07-30') == 363 and clearance_minute_for('2026-08-02') == 363 and clearance_minute_for('2026-08-03') == 359 and clearance_minute_for('2026-10-22') == 359
    e, _ = run(D0Config(clearance_minute=clearance_minute_for('2026-07-07'), enable_hedge=False, enable_cycle_stop=False), op=opening(lots=[('CE', 24000.0, 50.0)])); bb = [x for x in e.events if x.cls == 'body_buyback']; assert [(x.j, x.lots) for x in bb] == [(363, 1)]
def test_clearance_hazards_default_off_and_staggered_buyback_conserves_lots():
    lots = [('CE', 24000.0, 50.0)] * 10 + [('PE', 24000.0, 50.0)] * 4
    a, op = run(D0Config(clearance_minute=363, **QUIET), op=opening(lots=lots)); b, _ = run(D0Config(clearance_minute=363, clearance_hazards=None, **QUIET), op=opening(lots=lots)); assert a.events_frame().equals(b.events_frame())
    assert [(x.j, x.lots) for x in a.events if x.cls == 'body_buyback' and x.cp == 'CE'] == [(363, 10)]                      # baseline: everything at the single clearance minute
    e, op = run(D0Config(clearance_minute=363, clearance_hazards=(0.0, 0.5, 0.0, 1.0), **QUIET), op=opening(lots=lots)); ce = [(x.j, x.lots) for x in e.events if x.cls == 'body_buyback' and x.cp == 'CE']; pe = [(x.j, x.lots) for x in e.events if x.cls == 'body_buyback' and x.cp == 'PE']
    assert ce == [(361, 5), (363, 5)] and pe == [(361, 2), (363, 2)]                                                           # offsets -3..0 = minutes 360..363: hazard 0.5 at 361, nothing at 360 and 362, the rest at 363
    assert sum(l for _, l in ce) == 10 and e.reconcile(op) and not e.lots
def test_clearance_hazards_never_act_before_their_window():
    lots = [('CE', 24000.0, 50.0)] * 10; e, _ = run(D0Config(clearance_minute=363, clearance_hazards=(0.3, 0.3, 1.0), **QUIET), op=opening(lots=lots)); assert min(x.j for x in e.events if x.cls == 'body_buyback') == 361
