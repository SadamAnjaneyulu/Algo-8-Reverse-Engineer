"""Regression contract of the saved Gate 3a outputs."""
import os, json
HERE = os.path.dirname(os.path.abspath(__file__)); O = f'{HERE}/../outputs/phase1'
def test_step1_reconciles_to_B1_and_upstream_share_is_recorded():
    r = json.load(open(f'{O}/3A_step1.json')); assert r['reconciles_to_B1_by_class'] and r['real_buybacks'] == 1324 and r['sim_buybacks'] == 933 and r['missing'] == 675 and r['extra'] == 290
    assert sum(r['missing_by_class'].values()) == 675 and sum(r['extra_by_class'].values()) == 290 and abs(r['missing_upstream']['share'] - 0.5452) < 5e-4
def test_no_stop_mechanism_is_supported_and_k6_fails_every_variant():
    r = json.load(open(f'{O}/3A_step2.json'))
    for k, v in r['vs_K1'].items(): assert not (v['diff'] >= 0.03 and v['ci95'][0] > 0 and v['cycles_ge_K1'] >= 20), k
    k6 = json.load(open(f'{O}/3A/evaluation_K6.json')); assert all(not c['all'] for c in k6['criteria'].values()) and abs(k6['table']['B1']['le5'] - 0.0899) < 5e-4
    assert os.path.exists(f'{O}/3A_step2_first_execution_repeat_counting.json')                       # the first execution is archived, not deleted
