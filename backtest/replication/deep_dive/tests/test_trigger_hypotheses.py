"""Tests for the late-sale trigger investigation (reports/LATE_SALE_TRIGGER.md): software validation of the helpers on synthetic inputs with independently derived answers,
plus regression checks of the reported numbers and of the frozen objects."""
import os, sys, json, numpy as np, pandas as pd, pytest
HERE = os.path.dirname(os.path.abspath(__file__)); BASE = os.path.join(HERE, '..'); sys.path.insert(0, f'{BASE}/src'); sys.path.insert(0, f'{BASE}/../..'); sys.path.insert(0, f'{BASE}/../../..'); sys.path.insert(0, f'{BASE}/../../../d1_strategy')
_cwd = os.getcwd(); os.chdir(f'{BASE}/src')
import bl_trig2_events as TE, bl_fwd_eval_v2 as E
os.chdir(_cwd)
T2 = f'{BASE}/outputs/trig2'; W0, W = TE.W0, TE.W
def test_cluster_gap_is_inclusive_and_splits():
    t = np.array([0., 5., 15., 40.]); assert TE.cluster(t, None) == [[0, 1, 2], [3]]            # gaps 5, 10 (kept: <= 10), 25 (split)
    assert TE.cluster(np.array([0., 10.01]), None) == [[0], [1]]
def test_pair_count_needs_both_legs_inside_the_gap():
    assert TE.pair_count(np.array([100.]), np.array([105.])) == (1, 1)
    assert TE.pair_count(np.array([100.]), np.array([200.])) == (0, 2)
    assert TE.pair_count(np.array([100., 101.]), np.array([])) == (0, 1)
def test_shift_is_a_circular_rotation_inside_the_window():
    t = np.array([W0 + 10., W0 + 700., W0 + 1400.]); s = TE.shift(t, 321.0)
    assert ((s >= W0) & (s < W0 + W)).all() and np.allclose(np.sort((s - t) % W), np.sort(np.full(3, 321.0)))
    assert np.allclose(TE.shift(t, 0.0), t) and np.allclose(TE.shift(t, W), t)                 # full turn returns the input
def test_rayleigh_detects_phase_locking_and_not_uniform():
    P = 900; locked = TE.BASE + P * np.arange(20) + 3.0; R, p = TE.rayleigh(locked, P); assert R > 0.99 and p < 1e-6
    u = TE.BASE + np.linspace(0, P, 40, endpoint=False); R2, p2 = TE.rayleigh(u, P); assert R2 < 0.05 and p2 > 0.9
def test_ledger_mirror_flag_is_not_the_observed_flag():
    """regression of the first-run bug (mirror expectation equal to the observed completion): the fixed code uses the OPPOSITE side's other-queue test"""
    src = open(f'{BASE}/src/bl_trig2_events.py').read(); assert "fm = float((qC > 0) if q.cp == 'CE' else (qP > 0))" in src and 'if False else' not in src.split('# ---------------- P3a')[1].split('# ---------------- R2')[0]
    r = json.load(open(f'{T2}/tests_part1.json')); assert abs(r['P3a_all']['excess']) > 0 and r['P3a_all']['observed'] != r['P3a_all']['expected']
def test_event_counts_and_pair_window_regression():
    ev = pd.read_csv(f'{T2}/events.csv'); assert len(ev) == 47 and ev.cyc.nunique() == 17 and (ev.type == 'pair').sum() == 6 and (ev.type == 'solo').sum() == 41
    pr = ev[ev.type == 'pair']; assert pr.t0.between(55680, 55860).all()                       # all six two-leg bursts between 15:28:00 and 15:31:00
    assert (ev.outlier == 0).all() and (ev.era == 'after').all() and ev.t0.between(W0, W0 + W).all()
def test_reported_clock_and_pair_results():
    a = json.load(open(f'{T2}/tests_part1.json')); c = json.load(open(f'{T2}/tests_part3.json'))
    assert a['S1']['p'] < 0.01 and c['S5']['p'] < 0.01 and c['S1b']['p'] > 0.05                  # minute-level concentration yes, second-level timer no
    assert a['P1']['share'] > 0.10 and a['P4']['share'] < a['P4']['null_mean'] and a['R2']['spearman_p'] > 0.5 and a['R3']['p'] > 0.2
    assert c['X1_d_fut_l']['p_two_sided'] > 0.5 and c['X2_fut_lag1']['p'] < 0.01 and c['X2_feed_lag1']['p'] > 0.1
def test_coverage_only_ladder_passes_the_pre_registered_size_rule():
    cov = json.load(open(f'{T2}/tests_part1.json'))['coverage']; passing = [k for k, v in cov.items() if k != 'ANY' and v['excess'] >= 0.15]; assert passing == ['LADDER']
def test_state_hazard_and_incremental_regression():
    H = pd.read_csv(f'{T2}/state_hazard.csv').set_index('feature'); inc = json.load(open(f'{T2}/incremental.json'))
    assert H.loc['sold_deficit', 'auc'] > 0.60 and H.loc['straddle_chg_15', 'auc'] < 0.40 and H.loc['mins_since_cover', 'p'] > 0.5
    assert inc['C_vs_A']['boot95'][0] > 0 and inc['B_vs_A']['delta'] < 0.005 and abs(inc['A_vs_clock']['delta']) < 0.03 and inc['C_vs_A_leave_one_cycle_out']['cycles_positive'] == inc['C_vs_A_leave_one_cycle_out']['of']
def test_package_counterfactual_regression():
    P = json.load(open(f'{T2}/tests_part2.json'))['package']; assert P['theta_up'] == P['cycles'] == 17 and P['median_gap_relative'] < -0.05 and P['gap_not_worse_5pct'] < 0.7 * P['cycles']
def test_bh_family_file_is_consistent():
    F = pd.read_csv(f'{T2}/bh_family.csv'); assert len(F) == 37 and F.p.between(0, 1).all() and (F.p_bh_10 >= F.p - 1e-12).all() and F.id.is_unique
    assert (F.bh_significant_10 == (F.p_bh_10 <= 0.10)).all()
def test_frozen_objects_unchanged():
    assert E.verify_frozen(E.load_config()) is True
