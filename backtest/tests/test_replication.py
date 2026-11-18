"""Unit, integration, counterexample and regression tests for the Algo 8 ladder reconstruction (backtest/replication). Data-dependent tests skip when the local per-cycle cache is absent."""
import os, sys
import numpy as np, pandas as pd, pytest
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(HERE, 'replication')); sys.path.insert(0, HERE)
import rules as R
RES = os.path.join(HERE, 'replication', 'results')


def test_ladder_totals_and_symmetry():
    assert len(R.LADDER_D1) == 17 and sum(R.LADDER_D1) == 26 and R.LADDER_D1[0] == 3 and R.LADDER_D1[12] == 0


def test_nearest_strike_grid_and_ties():
    ks = np.arange(24000, 24600, 50)
    assert ks[R.nearest_strike(ks, 24324.9, 50)] == 24300 and ks[R.nearest_strike(ks, 24325.0, 50)] == 24350      # half-step rounds up as K = step*floor(S/step+0.5)
    ks2 = np.arange(76000, 77000, 100); assert ks2[R.nearest_strike(ks2, 76349.0, 100)] == 76300


def test_leg_stop_boundaries_and_exemption():                                  # counterexamples included
    assert not R.leg_stop_hit(1.59 * 100, 100) and R.leg_stop_hit(1.6 * 100, 100)
    assert not R.leg_stop_hit(10.0, 3.9) and not R.leg_stop_hit(8.0, 4.0)       # entry <= 4 is exempt even at 2x
    assert R.leg_stop_hit(6.5, 4.01) and not R.leg_stop_hit(6.4, 4.01)


def test_cycle_stop_threshold():
    assert R.cycle_stop_hit(-144000.0) and not R.cycle_stop_hit(-143999.0) and R.cycle_stop_hit(-1.5e5, 144000)


def test_wing_selection_targets_price_ratio_and_is_otm():
    ks = np.arange(100, 200, 10); price = {i: float(max(0.5, 200 - 3 * k / 1)) for i, k in enumerate(ks)}                # synthetic decaying CE prices (ATM at index 0)
    prices = {i: 100.0 * np.exp(-0.9 * i) for i in range(len(ks))}; w = R.wing_strike_index(ks, 'CE', 0, prices[0], lambda i: prices[i])
    assert w is not None and w > 0 and abs(prices[w] - R.WING_RATIO * prices[0]) <= min(abs(prices[i] - R.WING_RATIO * prices[0]) for i in range(1, len(ks))) + 1e-12
    wp = R.wing_strike_index(ks, 'PE', len(ks) - 1, prices[0], lambda i: prices[len(ks) - 1 - i]); assert wp is not None and wp < len(ks) - 1


def _cyc():
    from data import load_cycle, CACHE
    fn = os.path.join(CACHE, 'NIFTY_2026-07-14.pkl')
    if not os.path.exists(fn): pytest.skip('local per-cycle cache not present')
    return load_cycle('NIFTY', '2026-07-14', '2026-07-13', '2026-07-14')


def test_simulation_invariants_on_a_real_cycle():
    from sim import simulate
    c = _cyc(); s = simulate(c, 65, 'R1'); ev = pd.DataFrame(s['events'])
    assert s['open_at_end'] == 0                                                       # everything closed by the 15:14 flatten or a stop
    ent = ev[ev.tag == 'ENTRY']; assert ((ent.d == 0) & ((ent.j - R.SLOT0) % 15 == 0)).all()           # R1 enters only on D-1 ladder minutes
    assert len(ent[ent.role == 'body']) == 2 * sum(R.LADDER_D1) and (ent.role == 'wing').sum() <= (ent.role == 'body').sum()
    sell = ent[ent.role == 'body']; assert (sell.side == -1).all() and (sell.px <= sell.ref).all()                                       # shorts sell at or below the reference (slippage against us)
    assert abs(s['net'] - (s['gross'] - s['costs'] - s['slippage'])) < 1e-6                                                              # accounting identity


def test_no_lookahead_in_strike_choice():
    from sim import simulate
    c = _cyc(); ev = pd.DataFrame(simulate(c, 65, 'R1')['events']); e = ev[(ev.tag == 'ENTRY') & (ev.role == 'body') & (ev.j == R.SLOT0)]
    spot_prev = c[(0, 'spot')][R.SLOT0 - 1]; k = 50 * np.floor(spot_prev / 50 + 0.5); assert (e.strike == k).all()                         # strike from the PREVIOUS minute's close


def test_stop_ends_new_entries():
    from sim import simulate
    c = _cyc(); s = simulate(c, 65, 'R1', stop_limit=1.0)                                                                               # absurdly tight stop: fires immediately
    ev = pd.DataFrame(s['events']); assert s['stopped'] is not None
    g = ev.d * 375 + ev.j; sg = s['stopped'][0] * 375 + s['stopped'][1]
    assert not ((ev.tag == 'ENTRY') & (g >= sg)).any() and (ev[g >= sg].tag.isin(['CYCLE_STOP', 'LEG_STOP', 'WING_WITH_BODY', 'FLATTEN'])).all()
    assert s['open_at_end'] == 0


def test_regression_replay_totals_and_reconciliation():
    f = os.path.join(RES, 'replay_cycle_pnl.csv'); g = os.path.join(RES, 'pnl_streams_live_vs_sim.csv')
    if not (os.path.exists(f) and os.path.exists(g)): pytest.skip('replication results not present')
    r = pd.read_csv(f); r1 = r[r.variant == 'R1']; assert len(r1) == 35 and abs(r1.sim_gross.sum() - 444173) < 5
    st = pd.read_csv(g, header=[0, 1], index_col=0); assert abs(st[('pnl', 'R1')].sum() - r1.sim_gross.sum()) < 5                        # cash-based and FIFO-based gross agree
    live = pd.read_csv(os.path.join(RES, 'live_cycle_pnl.csv')); assert abs(live.gross.sum() - 2618423) < 5 and len(live) == 35


def test_causality_d0_open_decisions_ignore_same_bar_close():
    """regression for the D0-open look-ahead found in independent review: decisions at D0 minute 0 may use only D-1 data and the D0 bar OPEN for fills, never the D0 09:15 bar's close"""
    import copy
    from sim import simulate
    c = _cyc(); c2 = copy.deepcopy(c)
    for r in ('CE', 'PE'): c2[(1, r, 'close')][:, 0] = c2[(1, r, 'close')][:, 0] * 3.0 + 7.0
    e1 = [e for e in simulate(c, 65, 'R1')['events'] if e['d'] == 1 and e['j'] == 0]; e2 = [e for e in simulate(c2, 65, 'R1')['events'] if e['d'] == 1 and e['j'] == 0]
    assert [(e['strike'], e['right'], e['tag']) for e in e1] == [(e['strike'], e['right'], e['tag']) for e in e2]
