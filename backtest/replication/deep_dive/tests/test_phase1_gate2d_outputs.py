"""Regression contract of the saved Gate 2D outputs: BK0 equals the baseline, no variant is accepted, criteria applied as registered."""
import os, json, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); D = f'{HERE}/../outputs/phase1/2D'; S = f'{HERE}/../outputs/scoring'
def test_BK0_equals_B1_and_no_variant_is_accepted():
    a = pd.read_csv(f'{D}/BK0/sim_orders.csv'); b = pd.read_csv(f'{S}/d1_F_v2_onelot/sim_orders.csv'); cols = list(b.columns); assert a[cols].astype(str).equals(b[cols].astype(str))
    r = json.load(open(f'{D}/evaluation.json')); assert all(not x['passes_A1_A8'] for x in r['variants'].values()) and all(os.path.exists(f'{D}/{v}/run_record.json') for v in ('BK0', 'BK1', 'BK2', 'BK3'))
    assert r['variants']['BK1']['criteria']['A1'] is False and r['variants']['BK1']['criteria']['A2'] is False
