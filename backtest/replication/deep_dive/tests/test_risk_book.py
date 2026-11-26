"""Tests of the book-risk reconstruction used in the late-sale investigation (software validation on a synthetic chain + regression of reported numbers)."""
import os, sys, json, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); BASE = os.path.join(HERE, '..'); sys.path.insert(0, f'{BASE}/src'); sys.path.insert(0, f'{BASE}/../..'); sys.path.insert(0, f'{BASE}/../../..')
_cwd = os.getcwd(); os.chdir(f'{BASE}/src')                      # the simulator modules resolve their data paths from the working directory
import bl_risk_book as B
os.chdir(_cwd)
F, T = 22000.0, 1.0 / 365.0; K = np.arange(21000.0, 23001.0, 50.0); SIG = 0.15
def chain():
    Pc = B.bs(F, K, T, SIG, True); Pp = B.bs(F, K, T, SIG, False); return Pc, Pp, B.leg_values(K, Pc, Pp, F, T)
def pos_of(d=None):
    p = np.zeros((len(K), 2))
    for (cp, k), n in (d or {}).items(): p[int(np.argmin(np.abs(K - k))), 0 if cp == 'C' else 1] = n
    return p
def test_implied_vol_recovered_and_parity_forward():
    Pc, Pp, _ = chain(); iv = B.iv_vec(Pc, F, K, T, True); assert np.nanmax(np.abs(iv[(K > 21600) & (K < 22400)] - SIG)) < 1e-4
    assert abs(B.parity_forward(K, Pc, Pp, 22010.0) - F) < 1e-6
def test_sale_signs_and_mirror():
    Pc, Pp, V = chain(); flat = pos_of(); call = pos_of({('C', 22100.0): -1}); put = pos_of({('P', 21900.0): -1})
    d0 = B.state(flat, V, F, 75.0)['delta']; assert B.state(call, V, F, 75.0)['delta'] < d0 < B.state(put, V, F, 75.0)['delta']
    s = B.state(call, V, F, 75.0); assert s['gamma'] < 0 and s['theta'] > 0 and s['vega'] < 0, 'short option: negative gamma and vega, positive theta'
def test_state_is_additive_and_straddle_gap_losses():
    Pc, Pp, V = chain(); a = pos_of({('C', 22000.0): -3}); b = pos_of({('P', 22000.0): -3}); sa, sb, sab = (B.state(x, V, F, 75.0) for x in (a, b, a + b))
    assert abs(sab['delta'] - (sa['delta'] + sb['delta'])) < 1e-9 and np.allclose(sab['gap_pnl'], sa['gap_pnl'] + sb['gap_pnl'])
    assert (sab['gap_pnl'][[0, 1, 4, 5]] < 0).all() and sab['gap_worst'] == sab['gap_pnl'].min() and sab['gap_worst'] < 0
    wing = pos_of({('C', 22600.0): 3, ('P', 21400.0): 3}); sw = B.state(a + b + wing, V, F, 75.0); assert sw['gap_worst'] > sab['gap_worst'], 'long wings reduce the worst gap loss'
def test_reported_numbers_regression():
    t = json.load(open(f'{BASE}/outputs/risk/tests.json')); o = t['orders_post_1515']
    assert o['h1']['n_orders'] == 148 and o['h1']['n_cycles'] == 17 and abs(o['h1']['excess']) < 0.05 and o['h1']['p'] > 0.1 and o['h3']['p'] > 0.1
    assert t['H5']['gap_worst']['improved'] == 5 and t['H5']['gap_worst']['cycles'] == 24 and t['H5']['gap_worst']['p_sign'] < 0.01 and t['H6']['ratio_lower_at_close'] == 26 and t['H6']['cycles'] == 29
    a = json.load(open(f'{BASE}/outputs/risk/attrib_summary.json')); assert a['lump_v_']['reduces_abs_delta'] == 27 and a['lump_v_']['improves_gap_worst'] == 28 and a['lump_v_']['median_gap_effect'] > 5e5 and a['late_shorts_1515+']['improves_gap_worst'] == 5
    H = pd.read_csv(f'{BASE}/outputs/risk/hazard_auc.csv').set_index('feature'); assert H.loc['lighter_side', 'auc'] > 0.6 and H.loc['vwap_dev_trend', 'p'] > 0.1
    O = pd.read_csv(f'{BASE}/outputs/risk/orders_risk.csv'); assert (O[O.cp == 'CE'].delta_rs_pct_a < O[O.cp == 'CE'].delta_rs_pct_b).all() and (O[O.cp == 'PE'].delta_rs_pct_a > O[O.cp == 'PE'].delta_rs_pct_b).all()
    assert os.path.exists(f'{BASE}/reports/LATE_SALE_RISK.md') and os.path.exists(f'{BASE}/reports/LATE_SALE_RISK_PLAN.md')
