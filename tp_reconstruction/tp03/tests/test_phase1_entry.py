"""TP-03 Phase 1 tests: attribution classes, no-look-ahead snapshot, order-independent inventory, view consistency, B6 identity, E2 engine calibration, reproducibility."""
import os, sys, copy
import numpy as np, pandas as pd, pytest
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'scripts'))
import tp03_common as tc, e2_engine as eng, seqperm
os.environ.setdefault('ALGO8_MARKET_DIR', '/tmp/claude-0/-home-user-Algo-8-Reverse-Engineer/065db6a7-1cda-57f8-842a-8a8064e9a7d5/scratchpad/ws_ml/data/breeze/normalized')
import entry_common as ec
A = tc.ANALYSIS; ts = pd.Timestamp


def test_config_still_frozen(): tc.assert_frozen()


def test_attribution_classes():
    T = ts('2026-07-20 09:30:00'); win = ec.window_times(ts('2026-07-20'), pd.Timedelta(hours=9, minutes=30)); assert win[3] == ts('2026-07-20 09:29:00')       # snapshot = floor(T - 2 s)
    f = ec.attribution_class
    assert f(ts('2026-07-20 09:28:00'), ts('2026-07-20 09:30:30'), win) == 'SUBMITTED_BEFORE_WINDOW'
    assert f(ts('2026-07-20 09:29:00'), ts('2026-07-20 09:30:30'), win) == 'AMBIGUOUS_BOUNDARY_MINUTE'
    assert f(ts('2026-07-20 09:30:00'), ts('2026-07-20 09:30:30'), win) == 'ENTERED_INSIDE_WINDOW'
    assert f(ts('2026-07-20 09:31:00'), ts('2026-07-20 09:33:30'), win) == 'DECISION_IN_WINDOW_FILL_OUTSIDE'      # entered inside, first fill after the window end (09:33:00)
    assert f(ts('2026-07-20 09:33:00'), ts('2026-07-20 09:33:30'), win) is None                                         # entered at the window end minute: not inside
    assert f(ts('2026-07-20 09:40:00'), ts('2026-07-20 09:40:30'), win) is None


@pytest.fixture(scope='module')
def D(): return ec.Data()


def test_inventory_snapshot_is_order_independent_and_matches_flat_book(D):
    ex = ts('2026-09-10'); f = D.state('SENSEX', ex, ex + pd.Timedelta(hours=13, minutes=44))
    assert f['short_units_CE'] == 0 and f['short_units_PE'] == 0 and f['long_units_CE'] == 0 and f['long_units_PE'] == 0               # whole book liquidated at 13:37 (Phase 0 counts mislabelled these windows)
    D2 = copy.copy(D); D2.ev = {k: v.sample(frac=1.0, random_state=3) for k, v in D.ev.items()}                                         # shuffle row order: result must not change
    t = ts('2026-07-21 11:14:00'); a = D.state('NIFTY', ts('2026-07-21'), t); b = D2.state('NIFTY', ts('2026-07-21'), t)
    for k in ('short_units_CE', 'short_units_PE', 'long_units_CE', 'long_units_PE', 'net_units_CE', 'net_units_PE'): assert a[k] == b[k]


def test_state_features_use_no_data_at_or_after_the_snapshot(D):
    """truncate every source at the snapshot and recompute: features must be identical"""
    rng = np.random.default_rng(5); W = pd.read_parquet(os.path.join(tc.DATA, 'p1_window_dataset.parquet')); samp = W.sample(40, random_state=11)
    for r in samp.itertuples():
        snap = r.snapshot; und = r.und; ex = ts(r.expiry); full = D.state(und, ex, snap, entry_minute=None)
        D2 = copy.copy(D); D2.ev = {k: v[v.t_fill < snap] for k, v in D.ev.items()}; D2.idx = {u: g[g.index < snap] for u, g in D.idx.items()}
        D2.opt = {}
        for c, (t_, c_) in D.opt.items():
            m = t_ < np.datetime64(snap); D2.opt[c] = (t_[m], c_[m])
        D2.parents = D.parents[D.parents.first_fill < snap]; D2.PC = D.PC[D.PC.t_exit < snap]; cut = D2.state(und, ex, snap, entry_minute=None)
        for k in full:
            a, b = full[k], cut[k]
            assert (np.isnan(a) and np.isnan(b)) or a == pytest.approx(b), (r.cycle, r.window, k, a, b)


def test_three_views_are_consistent():
    W = pd.read_parquet(os.path.join(tc.DATA, 'p1_window_dataset.parquet'))
    assert (W.view1_class == W.view2_class).all()                                                       # no order is attributed to a different window than its fills
    amb = W.view3_class == 'AMBIGUOUS_ACTION'; assert (W[amb].view2_class == 'ACTION').all() and (W[amb].n_parents_inside + W[amb].n_parents_decision_fill_outside == 0).all()
    assert ((W.view2_class == 'ACTION').sum() - (W.view3_class == 'ACTION').sum()) == amb.sum()
    assert (W.n_parents_before_window == 0).all()                                                       # no body order was submitted before the window that it filled in
    assert len(W[W.kind == 'PRE']) == 672 + 0 and len(W[W.kind == 'D0']) == 759


def test_b6_identity_and_reconciliation_to_tp01():
    c = pd.read_csv(os.path.join(A, 'p1_b6_identity_check.csv')).iloc[0]
    assert c.max_abs_contract_identity_gap == 0 and c.opened_total == 1414545 and c.closed_total == 1377065 and c.remaining_gross == 37480 and bool(c.matches_TP01)


def test_e2_engine_type_one_error_and_power():
    rng = np.random.default_rng(2026); rej = 0; pw = 0
    for _ in range(120):
        X = rng.normal(size=(15, 10)); Y = (rng.random((15, 10)) < 0.5).astype(float); X2 = rng.normal(size=(15, 10)); Y2 = (rng.random((15, 10)) < 0.5).astype(float); d = eng.Design([(X, Y), (X2, Y2)], 'binary')   # two independent underlyings under the null
        o = abs(d.observed()[0]); null = np.array([d.draw_block(rng) for _ in range(199)]); rej += ((null >= o).sum() + 1) / 200 <= 0.05
        Xp = rng.normal(size=(15, 10)); Yp = (Xp + 0.5 * rng.normal(size=(15, 10)) > 0).astype(float); d2 = eng.Design([(Xp, Yp)], 'binary'); o2 = abs(d2.observed()[0]); null2 = np.array([d2.draw_block(rng) for _ in range(199)]); pw += ((null2 >= o2).sum() + 1) / 200 <= 0.05
    assert rej / 120 <= 0.10 and pw / 120 >= 0.9


def test_cycle_block_permutation_preserves_window_alignment():
    """a pure time-of-day effect (window mean of the feature and window rate of the outcome both vary, no within-window link) must not look significant under the cycle-block null"""
    rng = np.random.default_rng(9); rej = 0
    for _ in range(80):
        base = np.linspace(-2, 2, 12); X = base + rng.normal(size=(17, 12)); Y = (rng.random((17, 12)) < (1 / (1 + np.exp(-2 * base)))).astype(float); d = eng.Design([(X, Y)], 'binary')
        o = abs(d.observed()[0]); null = np.array([d.draw_block(rng) for _ in range(199)]); rej += ((null >= o).sum() + 1) / 200 <= 0.05
    assert rej / 80 <= 0.12


def test_sequential_p_is_reproducible_for_a_real_test():
    import p1_e2_run as m
    a = m.one_test(('PRE', 'action', 2, 'rv30_bp', 'primary', 'block')); b = m.one_test(('PRE', 'action', 2, 'rv30_bp', 'primary', 'block'))
    assert a['p'] == b['p'] and a['draws'] == b['draws'] and a['seed_entropy'] == b['seed_entropy'] and a['seed_entropy'] == f"{tc.CFG['inference']['seed']}-{__import__('zlib').crc32(a['test_id'].encode()) & 0xFFFFFFFF}"
