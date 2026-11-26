"""Regression checks for the re-centring tests (reports/LATE_SALE_RECENTER.md) and software checks of the side-share helper on a synthetic table."""
import os, sys, json, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); BASE = os.path.join(HERE, '..'); sys.path.insert(0, f'{BASE}/src'); sys.path.insert(0, f'{BASE}/../..'); sys.path.insert(0, f'{BASE}/../../..'); sys.path.insert(0, f'{BASE}/../../../d1_strategy')
_cwd = os.getcwd(); os.chdir(f'{BASE}/src')
import bl_trig4_recenter as R, bl_fwd_eval_v2 as E
os.chdir(_cwd)
T4 = f'{BASE}/outputs/trig4'
def test_side_share_helper_on_synthetic_table():
    rows = []
    for c in ('A', 'B', 'C', 'D'):
        for j in range(360, 366):
            ce_sold = j % 2 == 0; rows += [dict(cyc=c, j=j, side='CE', y=int(ce_sold), D=2.0 if ce_sold else 1.0), dict(cyc=c, j=j, side='PE', y=int(not ce_sold), D=1.0 if ce_sold else 2.0)]
    r = R.side_share(pd.DataFrame(rows), 'synthetic'); assert r['share_sold_side_has_larger_D'] == 1.0 and r['single_side_minutes_with_both_D'] == 24 and r['ci95'] == [1.0, 1.0]
def test_reported_recenter_results():
    r = json.load(open(f'{T4}/recenter.json')); F = pd.read_csv(f'{T4}/family.csv')
    assert len(F) == 5 and not F.bh_significant_10.any() and r['R1']['auc'] < 0.60 and r['R3']['R_vs_T']['lin95'][0] < 0 < r['R3']['R_vs_T']['lin95'][1]
    assert r['R4']['after']['late_sales'] == 148 and r['R4']['after']['new_strike_closer_to_money'] < 0.2 and r['R4']['after']['same_strike'] > 0.35
def test_frozen_objects_unchanged():
    assert E.verify_frozen(E.load_config()) is True
