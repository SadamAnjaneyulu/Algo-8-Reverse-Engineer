"""Regression contract of the saved Gate 2A runs: V00 equals the B1 baseline exactly, every preregistered variant is archived, the criteria were applied as registered, and no variant is silently accepted."""
import os, json, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); D = f'{HERE}/../outputs/phase1/2A'; S = f'{HERE}/../outputs/scoring'
def test_V00_equals_B1_and_all_variants_are_archived():
    a = pd.read_csv(f'{D}/V00/sim_orders.csv'); b = pd.read_csv(f'{S}/d1_F_v2_onelot/sim_orders.csv'); cols = list(b.columns); assert a[cols].astype(str).equals(b[cols].astype(str))
    for v in ['V00', 'V01', 'V02', 'V03', 'V04', 'V05', 'V06', 'V07', 'V08']: assert os.path.exists(f'{D}/{v}/run_record.json'), v
def test_criteria_were_applied_as_registered_and_no_variant_was_accepted():
    r = json.load(open(f'{D}/evaluation.json')); assert r['baseline_values']['F1'] == 0.7586 and r['baseline_values']['strict_F1'] == 0.5954
    acc = [v for v, x in r['variants'].items() if v != 'V00' and x['passes_A1_A8']]; assert acc == []                    # no variant passes A1-A8: the correction is rejected
    c = r['variants']['V01']['criteria']; assert c['A1'] is False and c['A2'] is True and c['A3'] is False and c['A4'] is False
def test_scheduled_straddles_did_not_regress_in_any_variant():
    r = json.load(open(f'{D}/evaluation.json')); assert all(x['metrics']['scheduled_matched'] >= 2076 for x in r['variants'].values())
