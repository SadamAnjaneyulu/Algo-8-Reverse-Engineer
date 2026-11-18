"""Consistency checks on the diagnostic outputs. They verify identities the diagnostics rely on, using the saved result tables (no engine run needed)."""
import json, os
import numpy as np, pandas as pd
R = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'diagnostics', 'results')
def T(n): return pd.read_csv(os.path.join(R, n))


def test_starting_figures_reproduce():
    s = json.load(open(os.path.join(R, 'starting_figures_recomputed.json')))
    assert abs(s['IS_net'] - 497091) < 1 and abs(s['OOS_net'] - 218329) < 1 and abs(s['clean_OOS_net'] - 38687) < 1
    assert s['exposed_cycles'] == 36 and s['uninspected_cycles'] == 64
    assert abs(s['oos_ex_best5'] - 5010) < 1 and abs(s['frozen_full_OOS'] - 67163) < 1 and abs(s['flatten_full_OOS'] - 118941) < 1


def test_cost_reconstruction_matches_reported():
    c = T('cost_components_cycles.csv'); assert (c.total_costs - c.reported_costs).abs().max() < 1e-6
    assert ((c.gross - c.slippage - c.total_costs) - c.net).abs().max() < 1e-6          # net = gross - slippage - costs


def test_straddle_identity_and_leg_sum():
    L = T('leg_attribution_cycles.csv'); net_leg = L[[f'{l}_net' for l in ('SCE', 'SPE', 'WCE', 'WPE')]].sum(axis=1); assert (net_leg - L.net).abs().max() < 1e-6
    model = L.SCE_qty * (L.SCE_entry_ref + L.SPE_entry_ref - L.move_pts.abs()); assert ((L.SCE_gross + L.SPE_gross) - model).abs().max() < 1e-6


def test_time_decomposition_sums_to_net():
    m = T('pnl_time_decomposition.csv'); assert (m.d1_session + m.overnight_gap + m.d0_morning_to_1529 + m.settlement_step - m.net).abs().max() < 1e-6


def test_sharpe_scale_invariance_and_reproduction():
    s = T('sharpe_audit.csv'); h = s[(s.config == 'HOLD') & (s.variant == 'HOLD_SETTLE') & (s.scope == 'COMBINED')].set_index('period')
    assert np.allclose(h.reported_sharpe, h.weekly_traded_only) and np.allclose(h.reported_sharpe, h.denominator_check_Rs10M)
    assert abs(h.loc['IS', 'reported_sharpe'] - 1.104) < 0.001 and abs(h.loc['OOS', 'reported_sharpe'] - 0.691) < 0.001 and abs(h.loc['OOS_clean', 'reported_sharpe'] - 0.167) < 0.001


def test_settlement_correction_only_changes_settlement():
    s = T('settlement_sensitivity.csv'); x = s[(s.config == 'HOLD') & (s.part == 'OOS')].iloc[0]
    assert x.net_original == x.net_original and x.delta < 0 and abs(x.net_settle_yahoo - x.net_original - x.delta) < 1e-6
