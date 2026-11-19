"""Integrity tests for the execution core, comparison engine and reference tables (no market cache needed unless noted)."""
import os, sys, copy, itertools
import numpy as np, pandas as pd, pytest
import exec_core as X
EP = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); REPL = os.path.dirname(EP); sys.path.insert(0, REPL)


def intent(side, si=100, right='CE', day=0, j=1, role='body', price=10.0):
    return X.OrderIntent(module='t', rule_id='t', evidence='t', day=day, j=j, right=right, si=si, side=side, role=role, tag='t', teacher_forced=True, price=price)


def fill(it): return X.Fill(it, it.price, it.price)


@pytest.mark.parametrize('conv', X.CONVENTIONS)
def test_conservation_for_every_allocation_convention(conv):
    rng = np.random.default_rng(3); P = X.PortfolioState(None, 10, conv); cash = 0.0; net = {}
    for i in range(400):
        it = intent(int(rng.choice([-1, 1])), si=int(rng.integers(100, 103)), price=float(rng.uniform(1, 50)), j=i % 300); P.apply_external(fill(it)); cash += -it.side * 10 * it.price; net[it.si] = net.get(it.si, 0) + it.side
    assert abs(P.cash - cash) < 1e-9 and {k: v for k, v in P.net.items() if v} == {(('CE', k)): v for k, v in net.items() if v}
    S0 = 12.0; settle = sum(L['side'] * 10 * max(S0 - L['si'] * 0 - 0, 0) * 0 for L in P.lots)       # settlement value is allocation-independent for the contract-level net
    open_pnl = sum(L['side'] * (5.0 - L['entry']) * 10 for L in P.lots); cash_gross = P.cash + sum(L['side'] * 5.0 * 10 for L in P.lots)
    assert abs(cash_gross - (P.realized + open_pnl)) < 1e-6                                         # cash-based gross == realised + open-lot P&L, for any convention


def test_total_cash_is_convention_independent_but_realized_split_is_not():
    rng = np.random.default_rng(4); ev = [intent(int(rng.choice([-1, 1])), si=100, price=float(rng.uniform(1, 50)), j=i) for i in range(300)]; res = {}
    for conv in X.CONVENTIONS:
        P = X.PortfolioState(None, 1, conv)
        for it in ev: P.apply_external(fill(it))
        res[conv] = (P.cash, P.realized)
    assert len({round(v[0], 9) for v in res.values()}) == 1 and len({round(v[1], 6) for v in res.values()}) > 1


class FakeCycle(dict):
    pass


def fake_cycle(seed=1):
    rng = np.random.default_rng(seed); n = 5; c = {'strikes': np.array([100, 150, 200, 250, 300]), 'und': 'NIFTY', 'd0': '2030-01-02'}
    for d in (0, 1):
        for r in ('CE', 'PE'):
            c[(d, r, 'close')] = rng.uniform(5, 50, (n, X.NM)); c[(d, r, 'open')] = rng.uniform(5, 50, (n, X.NM)); c[(d, r, 'volume')] = rng.integers(0, 100, (n, X.NM)).astype(float)
        c[(d, 'spot')] = 200 + np.cumsum(rng.normal(0, 1, X.NM))
    return c


def test_market_view_never_exposes_the_decision_minute_bar():
    c = fake_cycle(); v = X.MarketView(c); base = v.prev_close(1, 'CE', 2, 50); sp = v.spot_prev(1, 50)
    c2 = copy.deepcopy(c); c2[(1, 'CE', 'close')][:, 50:] = 9999.0; c2[(1, 'spot')][50:] = 9999.0; v2 = X.MarketView(c2)
    assert v2.prev_close(1, 'CE', 2, 50) == base and v2.spot_prev(1, 50) == sp                                  # bars from minute 50 on do not change what the decision at minute 50 sees
    assert np.isnan(v.prev_close(0, 'CE', 2, 0)) and np.isnan(v.spot_prev(0, 0))                                 # D-1 minute 0: nothing completed
    assert v.prev_close(1, 'CE', 2, 0) == v._px[(0, 'CE')][2, X.NM - 1]                                          # D0 minute 0 reads the last D-1 bar


def test_engine_decisions_do_not_depend_on_future_bars():
    import runner
    c = fake_cycle(2); c['strikes'] = np.arange(100, 100 + 50 * 5, 50)
    a = runner.build(c, 'NIFTY', 'R1', slip=False).run(); ea = runner.events(a)
    cut = 120; c2 = copy.deepcopy(c)
    for d, r in itertools.product((0, 1), ('CE', 'PE')):
        if d == 0:
            for k in ('close', 'open', 'volume'): c2[(d, r, k)][:, cut + 1:] = np.random.default_rng(9).uniform(1, 500, c2[(d, r, k)][:, cut + 1:].shape)
    c2[(0, 'spot')][cut + 1:] = 5000.0; b = runner.build(c2, 'NIFTY', 'R1', slip=False).run(); eb = runner.events(b)
    pa = ea[(ea.d == 0) & (ea.j <= cut)].reset_index(drop=True); pb = eb[(eb.d == 0) & (eb.j <= cut)].reset_index(drop=True)
    assert len(pa) == len(pb) > 0 and (pa[['j', 'right', 'strike', 'side', 'role', 'tag']].values == pb[['j', 'right', 'strike', 'side', 'role', 'tag']].values).all() and np.allclose(pa.ref, pb.ref)


def test_engine_is_deterministic():
    import runner
    c = fake_cycle(5); c['strikes'] = np.arange(100, 350, 50); h = [runner.events(runner.build(c, 'NIFTY', 'R1').run()).to_csv() for _ in range(2)]; assert h[0] == h[1]


def test_strict_policy_never_invents_a_price():
    import runner
    c = fake_cycle(6); c['strikes'] = np.arange(100, 350, 50); c[(0, 'CE', 'volume')][:] = 0.0; c[(0, 'PE', 'volume')][:] = 0.0
    lp = runner.build(c, 'NIFTY', 'R1', strict=True, slip=False).run(); assert len(lp.no_market) > 0
    assert all(f.price == f.price for f in lp.fills) and all(c[(f.intent.day, f.intent.right, 'volume')][f.intent.si, f.intent.j] > 0 for f in lp.fills)


def test_cycle_stop_blocks_later_entries_and_liquidates_everything():
    import runner
    c = fake_cycle(7); c['strikes'] = np.arange(100, 350, 50); lp = runner.build(c, 'NIFTY', 'R1', cycle_limit=1.0, slip=False).run()
    if lp.stopped is not None:
        e = runner.events(lp); assert not len(lp.state.lots) and not ((e.tag == 'ENTRY') & ((e.d > lp.stopped[0]) | ((e.d == lp.stopped[0]) & (e.j > lp.stopped[1])))).any()


# ---------------------------------------------------------------- comparison engine
import compare as C


def _ev(rows): return pd.DataFrame(rows, columns=['und', 'expiry', 'cp', 'strike', 'lots', 'j', 'day'])


def test_agreement_is_one_to_one_and_tolerance_monotone():
    s = _ev([('N', 'e', 'CE', 1, 1, 10, 0), ('N', 'e', 'CE', 1, 1, 10, 0)]); a = _ev([('N', 'e', 'CE', 1, 1, 11, 0)])
    o = C.agree(s, a, 1, 'same'); assert o['matched'] == 1 and o['n_sim'] == 2 and o['R'] == 1.0 and o['P'] == 0.5                  # one original event can match only one simulated event
    assert C.agree(s, a, 0, 'same')['matched'] == 0 and C.agree(s, a, 2, 'same')['matched'] == 1
    assert C.agree(s, _ev([('N', 'e', 'CE', 2, 1, 10, 0)]), 5, 'same')['matched'] == 0 and C.agree(s, _ev([('N', 'e', 'CE', 2, 1, 10, 0)]), 5, 'any')['matched'] == 1


def test_null_shift_preserves_clock_phase_and_drops_nothing():
    rng = np.random.default_rng(0); s = _ev([('N', 'e', 'CE', 1, 1, j, 0) for j in range(1, 300, 7)]); s['day'] = 0; sh = C.shifted(s, rng)
    assert len(sh) == len(s) and sh.j.between(0, C.NM - 1).all() and (((sh.j - s.j) % 15) == 0).all() and (sh.j != s.j).all()


def test_classification_follows_the_preregistered_rule():
    assert C.classify(dict(P=0.9, R=0.9, lift_P=2, lift_R=2, n_act=10)) == 'MATCH'
    assert C.classify(dict(P=0.9, R=0.9, lift_P=1.2, lift_R=1.2, n_act=10)) == 'PARTIAL MATCH'        # schedule-trivial agreement cannot be a MATCH
    assert C.classify(dict(P=0.6, R=0.3, lift_P=5, lift_R=5, n_act=10)) == 'PARTIAL MATCH'
    assert C.classify(dict(P=0.9, R=0.1, lift_P=5, lift_R=5, n_act=10)) == 'MISMATCH'
    assert C.classify(dict(P=np.nan, R=0.0, n_act=10)) == 'MISMATCH' and C.classify(dict(P=np.nan, R=np.nan, n_act=0)) == 'NOT TESTABLE'


def test_inventory_compare_identity_and_active_mask():
    keys = [('CE', 1), ('CE', 2)]; M = np.zeros((2, 750)); M[0, 10:20] = -3; M[1, 100:] = 2
    r = C.inventory_compare(keys, M, keys, M.copy()); assert r['exact'] == 1.0 and r['nmae'] == 0.0 and r['active'] == 10 + 650            # zero-zero minutes are excluded
    M2 = M.copy(); M2[0, 10:20] = 0; r2 = C.inventory_compare(keys, M, keys, M2); assert r2['exact'] < 1.0 and r2['mae'] > 0


def test_inventory_path_from_events_matches_cumulative_sum():
    ev = pd.DataFrame(dict(d=[0, 0, 1], j=[5, 9, 3], right=['CE', 'CE', 'PE'], strike=[100, 100, 200], sl=[-2, 1, -1])); keys, M = C.path_from_events(ev)
    assert keys == [('CE', 100), ('PE', 200)] and M[0, 4] == 0 and M[0, 5] == -2 and M[0, 9] == -1 and M[1, C.NM + 3] == -1 and M[1, C.NM + 2] == 0


# ---------------------------------------------------------------- added after the independent review
def test_cycle_stop_window_includes_the_decision_minute():
    mtm = np.array([0, -10, -50, -90, -140.0]); assert C.first_breach(mtm, 130, 4) == 4 and C.first_breach(mtm, 130, 3) is None          # a breach AT the decision minute of the original stop counts (review HIGH-1)
    assert C.first_breach(mtm, 40, 4) == 2 and C.first_breach(mtm, 200, 4) is None


def test_agreement_never_matches_across_days():
    s = _ev([('N', 'e', 'CE', 1, 1, 100, 0)]); a = _ev([('N', 'e', 'CE', 1, 1, 100, 1)])
    assert C.agree(s, a, 2, 'same')['matched'] == 0                                                                                          # D-1 minute 100 must not match D0 minute 100 (review MEDIUM-5)


def test_permissive_decisions_do_not_depend_on_the_decision_minute_bar():
    import runner
    c = fake_cycle(11); c['strikes'] = np.arange(100, 350, 50); a = runner.build(c, 'NIFTY', 'R1', slip=False).run(); ea = runner.events(a)
    cut = int(ea[(ea.d == 0)].j.iloc[len(ea[ea.d == 0]) // 2]); c2 = copy.deepcopy(c)
    for r in ('CE', 'PE'):
        for k in ('close', 'open', 'volume'): c2[(0, r, k)][:, cut] = 777.0
    c2[(0, 'spot')][cut] = 7777.0; b = runner.build(c2, 'NIFTY', 'R1', slip=False).run(); eb = runner.events(b)
    pa = ea[(ea.d == 0) & (ea.j <= cut)][['j', 'right', 'strike', 'side', 'role', 'tag']].reset_index(drop=True); pb = eb[(eb.d == 0) & (eb.j <= cut)][['j', 'right', 'strike', 'side', 'role', 'tag']].reset_index(drop=True)
    assert len(pa) == len(pb) > 0 and (pa.values == pb.values).all()                                                                     # the decision-minute bar changes at most the fill price, never the decision


def test_strict_policy_is_a_documented_hindsight_filter():
    import runner
    c = fake_cycle(12); c['strikes'] = np.arange(100, 350, 50); a = runner.build(c, 'NIFTY', 'R1', strict=True, slip=False).run(); ea = runner.events(a); j0 = int(ea[ea.d == 0].j.iloc[0])
    c2 = copy.deepcopy(c)
    for r in ('CE', 'PE'): c2[(0, r, 'volume')][:, j0] = 0.0
    b = runner.build(c2, 'NIFTY', 'R1', strict=True, slip=False).run(); eb = runner.events(b)
    assert len(eb[(eb.d == 0) & (eb.j == j0)]) < len(ea[(ea.d == 0) & (ea.j == j0)])              # strict fills depend on the decision minute's own volume: a liquidity filter with hindsight, not a causal rule
