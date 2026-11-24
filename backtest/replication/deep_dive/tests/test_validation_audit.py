"""Audit tests of the forward-test validation infrastructure (reports/OVERFITTING_AUDIT.md). Software validation on synthetic data whose answers are derived independently.
Covers: leakage, timestamp alignment, duplicates, cycle grouping, burn-in exclusion, identical sample construction, paired AUC, cluster bootstrap, Pocock constants and alpha spending,
stopping decisions, reproducible power, frozen hashes, no refitting, missing data, CE+PE pairs."""
import os, sys, json, math, tempfile, hashlib, copy
import numpy as np, pandas as pd, pytest
HERE = os.path.dirname(os.path.abspath(__file__)); BASE = os.path.join(HERE, '..'); sys.path.insert(0, f'{BASE}/src'); sys.path.insert(0, f'{BASE}/../../../d1_strategy')
import bl_validation as V, bl_fwd_eval_v2 as E
from d1_algo.shadow import ShadowRecorder, LateRuleConfig, FrozenLateRule, black_price
from sklearn.metrics import roc_auc_score
CFG = E.load_config(); MODEL = json.load(open(f'{BASE}/outputs/fwd/frozen_model.json')); T0 = 555 * 60.0
def make_logs(d, und='NIFTY', d1='2026-12-08', order_secs=(), seed=1, drop_minutes=(), spike=None):
    """synthetic recorder logs. order_secs: list of (seconds since 09:15, right, id). spike: (second, price) tick injected after an order."""
    rg = np.random.default_rng(seed); step = 50.0 if und == 'NIFTY' else 100.0; K = np.arange(21000.0, 23001.0, step); rec = ShadowRecorder(d, und, d1, 75.0, step, T0 + 86400 + 6 * 3600); F = 22000.0; pos = {('CE', 22100.0): -3, ('PE', 21900.0): -5}; orders = {s: (r, i) for s, r, i in order_secs}
    for sec in range(340 * 60, 386 * 60, 5):
        F += rg.normal(0, 3.0); ts = T0 + sec; Tt = (T0 + 86400 + 6 * 3600 - ts) / (365 * 86400); ltp = (lambda Fv, Tv: (lambda r, k: black_price(Fv, k, Tv, 0.15, r == 'CE')))(F - 4, Tt)
        px = spike[1] if spike and sec == spike[0] else F; rec.on_snapshot(ts, F - 30, px, ltp, K, pos)
        for s in [x for x in orders if sec <= x < sec + 5]: rec.on_real_order(ts + (s - sec) + 0.5, orders[s][0], 22100.0, 1, 'sell', 20.0, 'open_short', orders[s][1])
    rec.close()
    if drop_minutes:
        fn = f'{d}/minutes_{und}_{d1}.jsonl'; keep = [l for l in open(fn) if json.loads(l)['j'] not in drop_minutes]; open(fn, 'w').writelines(keep)
    return d
def rows_of(d, tabs=None):
    tabs = tabs or {'B': MODEL['clock_table'], 'A': MODEL['clock_table'], 'development': MODEL['clock_table']}; return E.load_rows(d, MODEL, tabs, CFG)

# ---------------------------------------------------------------- 1 no future information
def test_features_use_no_future_bars():
    with tempfile.TemporaryDirectory() as d:
        make_logs(d, order_secs=[(368 * 60 + 30, 'CE', 'a1')]); _, _, R1, _ = rows_of(d); fn = f'{d}/minutes_NIFTY_2026-12-08.jsonl'; L = [json.loads(l) for l in open(fn)]; J0 = 370
        for r in L:
            if r['j'] > J0 and r.get('fut'): r['fut'] = [v + 500.0 * ((-1) ** k) for k, v in enumerate(r['fut'])]
        open(fn, 'w').writelines(json.dumps(r) + '\n' for r in L); _, _, R2, _ = rows_of(d)
        a = R1[R1.j <= J0].sort_values(['side', 'j']).reset_index(drop=True); b = R2[R2.j <= J0].sort_values(['side', 'j']).reset_index(drop=True)
        assert len(a) > 0 and a[['FUT_ext5', 'FUT_mv1']].equals(b[['FUT_ext5', 'FUT_mv1']]), 'features at minute j changed when only LATER bars changed'
        assert not R1[R1.j == J0 + 1].reset_index(drop=True)[['FUT_mv1']].equals(R2[R2.j == J0 + 1].reset_index(drop=True)[['FUT_mv1']]), 'control: later minutes must react to their own bars'
def test_frozen_rule_fires_do_not_depend_on_future_ticks():
    rg = np.random.default_rng(3); px = 22000 + np.cumsum(rg.normal(0, 4, 40 * 60)); r1 = FrozenLateRule(LateRuleConfig(window_start=0, window_end=10 ** 6), 50.0); r2 = FrozenLateRule(LateRuleConfig(window_start=0, window_end=10 ** 6), 50.0)
    for k, p in enumerate(px[:20 * 60]): r1.on_tick(T0 + k, p); r2.on_tick(T0 + k, p)
    r1.on_real_sale('CE', 3); r2.on_real_sale('CE', 3); before = list(r1.fires)
    for k, p in enumerate(px[20 * 60:], start=20 * 60): r2.on_tick(T0 + k, p + 300 * (k % 2))
    assert [f['minute'] for f in r2.fires[:len(before)]] == [f['minute'] for f in before]

# ---------------------------------------------------------------- 2 timestamp alignment
def test_order_timestamp_alignment_and_pre_order_state():
    with tempfile.TemporaryDirectory() as d:
        m = 368; make_logs(d, order_secs=[(m * 60 + 30, 'CE', 'a1')], spike=(m * 60 + 45, 24000.0)); O = [json.loads(l) for l in open(f'{d}/orders_NIFTY_2026-12-08.jsonl')]; o = O[0]
        assert o['j'] == m and o['prices_before']['FUT']['prev'] is not None and o['prices_before']['FUT']['cur'] is not None
        assert o['prices_before']['FUT']['cur'][1] < 23000, 'the running bar at the order must not contain the spike that happens 15 s AFTER the order'
        assert o['book_before']['short_CE'] == 3 and o['book_before']['short_PE'] == 5, 'book state is taken before the order'

# ---------------------------------------------------------------- 3 duplicates
def test_duplicate_orders_not_double_counted():
    with tempfile.TemporaryDirectory() as d:
        make_logs(d, order_secs=[(368 * 60 + 30, 'CE', 'a1')]); fn = f'{d}/orders_NIFTY_2026-12-08.jsonl'; L = open(fn).read(); open(fn, 'a').write(L)     # the same order logged twice (partial-fill style)
        O, F, R, DQ = rows_of(d); assert len(O) == 1 and int(DQ.orders_duplicates_removed.iloc[0]) == 1 and int(R.y.sum()) == 1
    o = pd.DataFrame(dict(cyc=['c', 'c'], ts=[1.0, 1.0], cp=['CE', 'CE'], strike=[1, 1], lots=[1, 1], px=[2.0, 2.0])); d2, n = V.dedupe_orders(o); assert len(d2) == 1 and n == 1

# ---------------------------------------------------------------- 4 cycle grouping
def _synth_rows(n_cycles, seed=0, signal=0.0, n=25):
    rg = np.random.default_rng(seed); rows = []
    for c in range(n_cycles):
        for s in ('CE', 'PE'):
            x = rg.normal(size=n); base = rg.normal(size=n); p = 1 / (1 + np.exp(-(-2.2 + signal * x))); y = (rg.random(n) < p).astype(int)
            rows += [dict(cyc=f'c{c:02d}', side=s, j=360 + i, y=int(y[i]), score=x[i], base=base[i]) for i in range(n)]
    return pd.DataFrame(rows)
def test_cycle_level_grouping_and_bootstrap_weights():
    T = _synth_rows(8, 1, 1.0); C = V.components(T, ['score', 'base']); assert list(C.index) == sorted(T.cyc.unique()) and len(C) == 8
    d_manual = {c: sum(g.y.sum() * (len(g) - g.y.sum()) for _, g in T[T.cyc == c].groupby('side')) for c in C.index}; assert all(abs(C.d[c] - d_manual[c]) < 1e-9 for c in C.index), 'd must aggregate BOTH sides of a cycle'
    rng = np.random.default_rng(5); x = V.boot_deltas(C, 'score', 'base', 50, rng); rng = np.random.default_rng(5); W = rng.multinomial(8, np.ones(8) / 8, size=50).astype(float)
    assert np.allclose(x, (W @ (C.U_score - C.U_base).values) / (W @ C.d.values)) and (W.sum(1) == 8).all()
def test_bootstrap_matches_analytic_variance():
    C = pd.DataFrame(dict(d=np.ones(40), U_score=np.r_[np.ones(20), np.zeros(20)], U_base=np.zeros(40))); x = V.boot_deltas(C, 'score', 'base', 20000, np.random.default_rng(1)); assert abs(x.std() - math.sqrt(0.25 / 40)) < 0.004 and abs(x.mean() - 0.5) < 0.003
    lo, hi = V.boot_ci(pd.DataFrame(dict(d=np.ones(10), U_score=np.ones(10), U_base=np.zeros(10))), 'score', 'base', 0.95, 500, np.random.default_rng(2)); assert lo == hi == 1.0
    l, h, se = V.lin_ci(C, 'score', 'base', 0.95); assert abs(se - math.sqrt(0.25 / 40)) < 0.003 and l < 0.5 < h

# ---------------------------------------------------------------- 5 burn-in exclusion / chronology
def test_burn_in_excluded_and_roles_are_chronological():
    dates = pd.date_range('2026-12-08', periods=80, freq='3D').strftime('%Y-%m-%d'); cyc = pd.DataFrame(dict(cyc=[f'N|{x}' for x in dates], d1=dates)); dev = pd.DataFrame(dict(cyc=['N|2026-10-01'], d1=['2026-10-01'])); A = pd.DataFrame(dict(cyc=['N|2026-11-30'], d1=['2026-11-30']))
    R = V.assign_roles(pd.concat([dev, A, cyc]), dict(freeze_date='2026-11-25', regime_B_start='2026-12-07', burn_in_cycles=10, confirmatory=dict(looks_cumulative=[30, 60]))); V.assert_chronological_disjoint(R)
    vc = R.role.value_counts().to_dict(); assert vc == dict(development=1, regime_A_forward_exploratory=1, burn_in=10, confirmatory=60, beyond_protocol=10); assert (R[R.role == 'confirmatory'].look.value_counts().to_dict() == {1: 30, 2: 30}) and R[R.role == 'burn_in'].d1.max() < R[R.role == 'confirmatory'].d1.min()
    bad = R.copy(); bad.loc[bad.role == 'burn_in', 'd1'] = '2027-06-01'
    with pytest.raises(AssertionError): V.assert_chronological_disjoint(bad)
def test_confirmatory_primary_not_computed_before_the_look_and_never_from_burn_in():
    with tempfile.TemporaryDirectory() as d:
        for k in range(12): make_logs(d, d1=f'2026-12-{8 + k:02d}', order_secs=[(368 * 60 + 30, 'CE', f'o{k}')], seed=k)
        out = E.evaluate_confirmatory(d, CFG, look=1); roles = pd.DataFrame(out['roles']); assert (roles.role == 'burn_in').sum() == 10 and (roles.role == 'confirmatory').sum() == 2
        assert out['primary'] is None and out['status'].startswith('not_ready'), '12 cycles = 10 burn-in + 2 confirmatory: look 1 needs 30, so nothing may be computed (no peeking)'

# ---------------------------------------------------------------- 6/7 identical samples, paired AUC
def test_paired_auc_known_values_and_ties():
    T = pd.DataFrame(dict(cyc=['c'] * 8, side=['CE'] * 8, j=range(8), y=[1, 0, 0, 0, 1, 0, 0, 0], score=[9, 1, 2, 3, 8, 4, 5, 6], base=[1.0] * 8)); C = V.components(T, ['score', 'base'])
    assert V.auc_from(C, 'score') == 1.0 and V.auc_from(C, 'base') == 0.5 and V.delta_from(C, 'score', 'base') == 0.5          # perfect score; constant baseline = all ties = 0.5
    rg = np.random.default_rng(0); T2 = _synth_rows(5, 3, 0.8); C2 = V.components(T2, ['score', 'base']); per = []; w = []
    for (c, s), g in T2.groupby(['cyc', 'side']):
        n1 = g.y.sum(); n0 = len(g) - n1
        if n1 and n0: per.append(roc_auc_score(g.y, g.score)); w.append(n1 * n0)
    assert abs(V.auc_from(C2, 'score') - np.average(per, weights=w)) < 1e-12, 'pooled stratified AUC = pair-weighted mean of block AUCs (sklearn reference)'
def test_model_and_baseline_use_identical_observations():
    T = _synth_rows(6, 2, 1.0); T.loc[T.sample(frac=0.1, random_state=1).index, 'score'] = np.nan; C = V.components(T, ['score', 'base'])
    assert np.isfinite(V.auc_from(C, 'score')) and np.isfinite(V.auc_from(C, 'base')); assert abs(V.delta_from(C, 'score', 'base') - (V.auc_from(C, 'score') - V.auc_from(C, 'base'))) < 1e-12      # one shared denominator d
    assert (C.filter(like='U_').notna()).all().all()

# ---------------------------------------------------------------- 9/10 sequential design
def test_pocock_constants_independent_and_alpha_spending():
    assert abs(V.pocock_constant(1) - 1.96) < 1e-3 and abs(V.pocock_constant(2) - 2.178) < 4e-3 and abs(V.pocock_constant(3) - 2.289) < 5e-3
    assert abs(V.pocock_nominal(2) - 0.0294) < 5e-4 and abs(V.pocock_nominal(3) - 0.0221) < 5e-4
    rg = np.random.default_rng(1); z = rg.normal(size=(300000, 2)); S = np.c_[z[:, 0], (z[:, 0] + z[:, 1]) / math.sqrt(2)]; c = V.pocock_constant(2); assert abs((np.abs(S) > c).any(1).mean() - 0.05) < 0.004     # overall type I of the 2-look design
    assert abs(V.pocock_nominal(2) - 0.05) > 0.02, 'the per-look level is NOT 5%: using a 95% interval at each look inflates the overall error'
def test_stopping_decisions():
    assert V.sequential_decision(1, 2, 0.10, 0.01) == 'confirmed' and V.sequential_decision(2, 2, 0.10, 0.01) == 'confirmed'
    assert V.sequential_decision(1, 2, -0.01, -0.08) == 'futility' and V.sequential_decision(1, 2, 0.00, -0.08) == 'futility' and V.sequential_decision(1, 2, 0.03, -0.04) == 'continue'
    assert V.sequential_decision(2, 2, -0.02, -0.09) == 'not_confirmed' and V.sequential_decision(2, 2, 0.03, -0.01) == 'not_confirmed', 'futility is only a look-1 rule; at the last look an interval including 0 is not confirmed'
    assert V.sequential_decision(1, 2, 0.05, 0.0) != 'confirmed', 'lower bound exactly 0 is not > 0'

# ---------------------------------------------------------------- 11 reproducible power
def test_power_simulation_reproducible_and_fast_path_exact():
    os.environ['R_REPS'] = '5'; import bl_audit_power as P
    r1 = P.simulate(0.8, P.solve_a(0.8), 'burnin', np.random.default_rng(11)); r2 = P.simulate(0.8, P.solve_a(0.8), 'burnin', np.random.default_rng(11)); assert r1 == r2
    rng = np.random.default_rng(5); idx, Y = P.draw_cycles(rng, 20, 1.0, P.solve_a(1.0)); Sc, Bl = P.score_arrays(idx, P.ZC_TRUE); aa, dd = P.comp_fast(Sc, Bl, Y); rows = []
    for k in range(20):
        for s in range(2): rows += [dict(cyc=f'c{k:02d}', side=s, j=i, y=int(Y[k, s, i]), score=Sc[k, s, i], base=Bl[k, s, i]) for i in range(25)]
    C = V.components(pd.DataFrame(rows), ['score', 'base']).loc[[f'c{k:02d}' for k in range(20)]]; assert np.allclose(aa, (C.U_score - C.U_base).values) and np.allclose(dd, C.d.values)
    lam, a, pv = P.calibrate(0.05, np.random.default_rng(0)); assert abs(pv - 0.05) < 0.006

# ---------------------------------------------------------------- 12/13 frozen objects, no refitting
def test_frozen_hashes_verified_and_tampering_detected():
    assert E.verify_frozen(CFG) is True and LateRuleConfig().sha() == CFG['frozen']['rule_sha256'] == 'ca1306cfdd505f34cbbc4ee9470326eb96a8bab45716019d5214673e8a430e03' and MODEL['sha256_of_above'] == '7788f7394e87c04d117fdf512243386159bcecb56659c995dc495d769820d69c'
    bad = copy.deepcopy(CFG); bad['frozen']['rule_sha256'] = '0' * 64
    with pytest.raises(AssertionError): E.verify_frozen(bad)
    bad = copy.deepcopy(CFG); bad['frozen']['model_coef'][0] += 1e-6
    with pytest.raises(AssertionError): E.verify_frozen(bad)
    fp = open(f'{BASE}/outputs/audit/fingerprints_before.txt').read().split('\n'); got = {l.split()[1]: l.split()[0] for l in fp if l.strip()}
    for rel in ('d1_strategy/d1_algo/shadow.py', 'backtest/replication/deep_dive/outputs/fwd/frozen_model.json', 'backtest/replication/deep_dive/src/bl_fwd_freeze.py', 'backtest/replication/deep_dive/reports/FORWARD_TEST.md', 'backtest/replication/deep_dive/reports/D0_CLEAR_AND_LATE_TRIGGER_PLAN.md'):
        assert hashlib.sha256(open(f'{BASE}/../../../{rel}', 'rb').read()).hexdigest()[:16] == got[rel], f'{rel} changed since the audit started'
def test_no_refitting_during_evaluation(monkeypatch):
    import sklearn.linear_model as lm
    def boom(*a, **k): raise AssertionError('refit attempted')
    monkeypatch.setattr(lm.LogisticRegression, 'fit', boom); before = open(f'{BASE}/outputs/fwd/frozen_model.json').read()
    with tempfile.TemporaryDirectory() as d:
        make_logs(d, order_secs=[(368 * 60 + 30, 'CE', 'a1')]); E.evaluate_confirmatory(d, CFG, look=1)
    assert open(f'{BASE}/outputs/fwd/frozen_model.json').read() == before
    with pytest.raises(Exception): LateRuleConfig().gate_min.__class__; setattr(LateRuleConfig(), 'gate_min', 6)
    with tempfile.TemporaryDirectory() as d:
        p = f'{d}/t.json'; assert len(E.freeze_regime_B_table({'360|CE': 0.1}, p, ['c1'])) == 64
        with pytest.raises(FileExistsError): E.freeze_regime_B_table({'360|CE': 0.9}, p, ['c1'])

# ---------------------------------------------------------------- 14 missing data, 15 CE+PE pairs
def test_missing_bars_are_counted_not_silently_dropped():
    with tempfile.TemporaryDirectory() as d:
        make_logs(d, order_secs=[(368 * 60 + 30, 'CE', 'a1')], drop_minutes=(368,)); O, F, R, DQ = rows_of(d); q = DQ.iloc[0]
        assert q.rows_expected == 50 and q.rows_missing > 0 and q.rows_built == len(R) and q.positives_lost_to_missing == 1 and q.share_rows < 1.0
        assert len(O) == 1, 'the order itself is kept for order-level metrics'
    assert V.missing_minutes(pd.DataFrame(dict(cyc=['a'] * 40 + ['b'] * 50)), (360, 384)).to_dict() == {'a': 10, 'b': 0}
def test_ce_pe_pair_handled_as_two_events_and_one_burst():
    with tempfile.TemporaryDirectory() as d:
        make_logs(d, order_secs=[(370 * 60 + 10, 'CE', 'p1'), (370 * 60 + 11, 'PE', 'p2'), (375 * 60 + 5, 'CE', 'p3')]); O, F, R, DQ = rows_of(d)
        r = R[R.j == 370]; assert dict(zip(r.side, r.y)) == {'CE': 1, 'PE': 1} and int(R.y.sum()) == 3
        assert V.pair_events(O) == (1, 2)
        dm = E.decision_metrics(O.assign(regime='B'), pd.DataFrame(columns=['cyc', 'j', 'cp'])); assert dm['events'] == 3 and dm['orders'] == 3


# ---------------------------------------------------------------- level at each look, and burn-in really excluded when there is enough data
def test_primary_uses_the_pocock_level_at_each_look():
    T = _synth_rows(10, 4, 1.0).rename(columns={'score': 'FUT_mv1'}); T['FUT_ext5'] = (T.FUT_mv1 > 0.5).astype(float); T['clock'] = T.base
    r = E.primary_at_look(T, MODEL, CFG, look=1, B=300); assert abs(r['ci_level'] - (1 - V.pocock_nominal(2))) < 1e-12 and abs(r['ci_level'] - 0.9706) < 5e-4 and r['K'] == 2
    assert r['evidence'] == 'confirmatory' and r['cycles'] == 10 and r['effective_cycles'] <= 10 and set(r) >= {'auc_model', 'auc_clock', 'delta', 'boot_ci', 'linearised_ci', 'leave_one_cycle_out', 'events', 'negatives'}
    wide = V.lin_ci(V.components(T.assign(score=0.0), ['score', 'base']), 'score', 'base', 0.95)    # a 95% interval would be narrower than the 97.06% one used at each look
    c2 = V.components(T.assign(score=E.frozen_score(T, MODEL), base=T.clock), ['score', 'base']); l95 = V.lin_ci(c2, 'score', 'base', 0.95); l97 = V.lin_ci(c2, 'score', 'base', 1 - V.pocock_nominal(2)); assert l97[0] < l95[0] and l97[1] > l95[1]
def test_burn_in_cycles_never_enter_the_confirmatory_sample():
    with tempfile.TemporaryDirectory() as d:
        for k in range(40): make_logs(d, d1=f'2027-01-{1 + k:02d}' if k < 31 else f'2027-02-{k - 30:02d}', order_secs=[(368 * 60 + 30, 'CE', f'o{k}')], seed=k)
        out = E.evaluate_confirmatory(d, CFG, look=1, tables={'B': MODEL['clock_table']}); roles = pd.DataFrame(out['roles'])
        assert (roles.role == 'burn_in').sum() == 10 and (roles.role == 'confirmatory').sum() == 30 and out['primary'] is not None
        assert out['primary']['cycles'] == 30, 'the 10 burn-in cycles must not be in the primary sample'; assert out['primary']['events'] <= 30 and out['primary']['evidence'] == 'confirmatory' and out['secondary_exploratory']['evidence'] == 'exploratory'
