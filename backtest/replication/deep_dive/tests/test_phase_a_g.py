"""Regression tests for the Phase A investigations G1-G6 (reports/PHASE_A_G1_G6_RESULT.md): helper checks on synthetic inputs and checks of the reported numbers."""
import os, sys, json, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); BASE = os.path.join(HERE, '..'); sys.path.insert(0, f'{BASE}/src'); sys.path.insert(0, f'{BASE}/../..'); sys.path.insert(0, f'{BASE}/../../..'); sys.path.insert(0, f'{BASE}/../../../d1_strategy')
_cwd = os.getcwd(); os.chdir(f'{BASE}/src')
import bl_pa_g1 as G1, bl_pa_g6 as G6, bl_fwd_eval_v2 as E, algo8_d1 as A
os.chdir(_cwd)
PA = f'{BASE}/outputs/phaseA'; J = lambda f: json.load(open(f'{PA}/{f}.json'))
def test_burst_clustering_gap_is_inclusive():
    assert G1.clusters([0.0, 5.0, 15.0, 40.0]) == [[0, 1, 2], [3]] and G1.clusters([0.0, 10.01]) == [[0], [1]]
def test_breakout_rule_extension_only_adds_fires_after_the_old_gate():
    """the engine rule with its gate end moved from 15:15 to the end of data keeps every earlier fire and only adds later ones (no new parameter)"""
    rng = np.random.default_rng(3); n = 385; c = 22000 + np.cumsum(rng.normal(0, 4, n)); h = c + np.abs(rng.normal(0, 3, n)); l = c - np.abs(rng.normal(0, 3, n)); cfg = A.Config(); cfg.breakout_end_min = 360; v0 = A.breakout_fires(h, l, cfg); cfg.breakout_end_min = n - 1; v1 = A.breakout_fires(h, l, cfg)
    assert all(f in v1 for f in v0) and all(j > 360 for j, s, d in v1 if (j, s, d) not in v0)
def test_stats_helper_iqr_and_loss_share():
    s = pd.Series([0.5, 1.0, 1.5, 2.0]); r = G6.stats(s); assert abs(r['median'] - 1.25) < 1e-12 and abs(r['iqr'] - (s.quantile(.75) - s.quantile(.25))) < 1e-12 and r['share_in_loss'] == 0.5
def test_g1_and_g1b_results():
    g1, g1b = J('g1'), J('g1b'); assert g1['G1']['pair_bursts'] == 8 and g1['G1']['v1_matched'] == 0 and not g1['G1']['supported'] and g1['G1']['null_mean'] > 0.3
    assert g1b['burst_cycles'] == 8 and g1b['burst_cycles_with_condition'] == 7 and g1b['supported'] and g1b['fisher_p_one_sided'] < 0.01 and g1b['table'] == dict(cond_burst=7, cond_noburst=5, nocond_burst=1, nocond_noburst=16)
def test_g2_accounting_is_consistent():
    g2 = J('g2'); s = {x['tolerance_min']: x for x in g2['sensitivity']}; assert g2['orders'] == 176 and s[1]['unexplained'] == 43 and s[1]['explained_any'] + s[1]['unexplained'] == 176 and s[5]['unexplained'] < s[2]['unexplained'] < s[1]['unexplained']
    assert g2['unexplained_tol1']['post'] == 34 and sum(g2['unexplained_tol1']['by_cycle'].values()) == 43
def test_g3_lag_is_not_the_limiter_and_forward_reference_correction():
    g3 = J('g3'); p = g3['post_auction']; assert p['low_lag_share'] > 0.85 and p['median_drift'] < 0.05 < 0.15 < p['median_gap'] and p['verdict'] == 'rule incomplete' and g3['all_eras']['verdict'] == 'inconclusive'
    o = pd.read_csv(f'{PA}/g3_orders.csv'); g2 = pd.read_csv(f'{PA}/g2_orders.csv')[['cyc', 'j', 'cp', 'lad1']].drop_duplicates(['cyc', 'j', 'cp']); m = o.merge(g2, on=['cyc', 'j', 'cp']); m = m[m.post]
    assert int(m.lad1.sum()) == 98 and abs(m[m.lad1 == True].exact.mean() - 0.541) < 0.005                     # live-definition reference: 0.54 on the 98 matched orders (the dev dry run's 0.306 used a minute-lagged reference)
def test_g4_classification():
    g4 = J('g4'); D = pd.read_csv(f'{PA}/g4_orders.csv'); assert g4['orders'] == 134 and abs(g4['opening_wing_share'] - 0.925) < 0.01 and not g4['success'] and int(D.entry.isna().sum()) == 10
    ex = pd.DataFrame(g4['exceptions']); assert ex[ex.cyc == 'SENSEX|2026-09-09'].cls.all() and not ex[ex.cyc == 'NIFTY|2026-08-03'].cls.any()
def test_g5_stop_constant():
    g5 = J('g5'); c = g5['c_prev_close_plus_decision_prices']; assert g5['stops'] == 11 and g5['gap_stops_before_0916'] == 4 and c['n'] == 7 and c['within_10pct_of_median'] == 7 and -1.6e5 < c['min'] < c['max'] < -1.3e5 and c['non_stop_min_above_smallest_stop']
    assert g5['a_prev_close']['spread_over_median'] > 0.4 and g5['verdict'].startswith('consistent') and g5['non_stop_worst_minute_close_mtm'] > c['max']
def test_g6_no_price_structure():
    g6 = J('g6'); ref = g6['known stop class (type 3, reference)']['iqr']; assert abs(ref - 0.304) < 0.01
    for k in ('carried residual (entry on D-1, types 5-8)', '"other" (type 8)', 'burst members (type 7)'): assert not g6[k]['candidate'] and g6[k]['iqr'] > 1.5 * ref and g6[k]['median'] < 1.2
def test_frozen_objects_unchanged():
    assert E.verify_frozen(E.load_config()) is True
