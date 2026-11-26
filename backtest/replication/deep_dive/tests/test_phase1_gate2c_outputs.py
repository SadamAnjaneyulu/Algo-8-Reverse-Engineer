"""Regression contract of the saved Gate 2C outputs and the no-look-ahead criterion L8."""
import os, json, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); BASE = f'{HERE}/..'; D = f'{BASE}/outputs/phase1/2C'; sys.path.insert(0, f'{BASE}/src'); sys.path.insert(0, f'{BASE}/..'); sys.path.insert(0, f'{BASE}/../..')
def test_C0_equals_B1_and_neither_candidate_passes_all_criteria():
    a = pd.read_csv(f'{D}/C0/sim_orders.csv'); b = pd.read_csv(f'{BASE}/outputs/scoring/d1_F_v2_onelot/sim_orders.csv'); cols = list(b.columns); assert a[cols].astype(str).equals(b[cols].astype(str))
    r = json.load(open(f'{D}/evaluation.json')); assert r['C1']['passes_all'] is False and r['C2']['passes_all'] is False and r['C1']['criteria']['L4'] is True and r['C1']['criteria']['L3'] is True
    assert abs(r['B1_window']['F1'] - 0.2009) < 5e-4 and r['B1_window']['real'] == 165
def test_L8_rebased_series_equals_the_index_series_before_minute_360_in_every_post_auction_cycle():
    cwd = os.getcwd(); os.chdir(f'{BASE}/src')
    try: import bl_fr_sim as S, bl_common
    finally: os.chdir(cwd)
    n = 0
    for r in S.CY.itertuples():
        if r.d1 < '2026-08-03': continue
        c = pd.read_pickle(f'{bl_common.OUT}/bt3u/{r.und}_{r.expiry}.pkl.gz')['spot1']; o = S.OH[(r.und, r.expiry)]
        for col in ('open', 'high', 'low', 'close'): assert np.allclose(c[col].values[:360], o[col].values[:360]), (r.und, r.expiry, col)
        n += 1
    assert n == 21
