"""Regression tests for the reconstructed-Algo-8 performance backtest outputs (backtest/recon_bt). Structural identities, determinism of the stop logic, and pinned headline relationships."""
import os, json, pickle
import numpy as np, pandas as pd
RES = os.path.join(os.path.dirname(__file__), '..', 'results'); RUNS = lambda: pickle.load(open(os.path.join(RES, 'runs.pkl'), 'rb'))
def frames():
    r = RUNS(); return {lv: pd.DataFrame([v for (n, u, e), v in r.items() if n == lv]).set_index(['und', 'expiry']).sort_index() for lv in ('NONE', 'S125', 'S200')}
def test_pipeline_validation_passed_and_all_cycles_present():
    v = json.load(open(os.path.join(RES, 'pipeline_validation.json'))); assert v['passed'] and v['d1_orders_identical'] == 32 and v['total_orders'] == v['b1_total'] == 9035
    F = frames(); assert all(len(f) == 275 for f in F.values()) and set(F['NONE'].index) == set(F['S200'].index)
    assert F['NONE'].index.get_level_values(0).value_counts().to_dict() == {'NIFTY': 154, 'SENSEX': 121}
def test_every_cycle_hands_off_and_ends_flat():
    for f in frames().values(): assert f.handoff_error.isna().all() and (f.residual_d0_contracts == 0).all() and (f.settle == 0).all()
def test_accounting_identity_and_costs_positive():
    for f in frames().values():
        assert np.allclose(f.net, f.gross - f.slippage - f.costs, atol=1e-6) and (f.costs > 0).all() and (f.slippage > 0).all()
def test_stop_logic_is_deterministic_and_nested():
    F = frames(); n, a, b = F['NONE'], F['S125'], F['S200']; assert not n.stopped.any()
    assert (b.stopped & ~a.stopped).sum() == 0                                            # a stop at 2.0 lakh implies one at 1.25 lakh (same path until the first crossing)
    same = ~a.stopped; assert np.allclose(a.net[same], n.net[same], atol=1e-6)            # no stop fired: identical to no stop
    same = ~b.stopped; assert np.allclose(b.net[same], n.net[same], atol=1e-6)
    only_a = a.stopped & ~b.stopped; assert np.allclose(b.net[only_a], n.net[only_a], atol=1e-6)      # stopped at 1.25 only: S200 equals the unstopped run
def test_splits_and_summary_consistent_with_ledger():
    L = pd.read_csv(os.path.join(RES, 'cycle_ledger.csv')); assert L.split.value_counts().to_dict() == {'PRE': 234, 'DEV': 36, 'POST': 5}
    T = pd.read_csv(os.path.join(RES, 'summary_table.csv')); r = T[(T.level == 'S200') & (T.scope == 'ALL') & (T.split == 'ALL_PERIODS')].iloc[0]; assert abs(r.net_pnl - L.net_S200.sum()) < 1e-3 and r.cycles == 275
    r = T[(T.level == 'S200') & (T.scope == 'ALL') & (T.split == 'ALL_PERIODS')].iloc[0]; assert abs(r.win_rate_pct - 100 * (L.net_S200 > 0).mean()) < 1e-9
    for sc in ('NIFTY', 'SENSEX'):
        x = T[(T.level == 'S200') & (T.scope == sc) & (T.split == 'ALL_PERIODS')].iloc[0]; assert abs(x.net_pnl - L[L.und == sc].net_S200.sum()) < 1e-3
def test_headline_relationships_and_stop_verdict():
    J = json.load(open(os.path.join(RES, 'summary.json'))); v = J['stop_verdict']; assert not v['S200_better_supported'] and not v['a_paired_ci_lower_gt0_in_PRE'] and not v['c_positive_after_removing_top5_in_PRE']
    T = pd.read_csv(os.path.join(RES, 'summary_table.csv')); g = lambda lv: T[(T.level == lv) & (T.scope == 'ALL') & (T.split == 'ALL_PERIODS')].iloc[0]; assert g('NONE').net_pnl > g('S200').net_pnl > g('S125').net_pnl and g('S200').max_dd_rs > g('S125').max_dd_rs
def test_calibration_file_matches_the_stated_ordering():
    c = json.load(open(os.path.join(RES, 'calibration_vs_real.json'))); assert c['NONE']['ratio_to_real_gross'] > 2 and 0.9 < c['S200']['ratio_to_real_gross'] < 1.2 and c['S125']['ratio_to_real_gross'] < 0.6 and c['S200']['corr_cycle_gross'] > c['S125']['corr_cycle_gross'] > 0.4
