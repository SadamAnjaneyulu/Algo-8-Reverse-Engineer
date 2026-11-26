"""Regression contract of the saved Gate 3b/3c outputs."""
import os, json
HERE = os.path.dirname(os.path.abspath(__file__)); O = f'{HERE}/../outputs/phase1'
def test_no_wing_or_lump_rule_is_supported_and_key_values_recorded():
    r = json.load(open(f'{O}/3BC.json')); assert r['with_two_or_more_held'] == 589 and abs(r['rules']['W1'] - 0.411) < 1e-3 and abs(r['chance'] - 0.262) < 1e-3
    assert not any(v['supported'] for v in r['vs_W1'].values()) and not any(v['supported'] for v in r['lump']['vs_M1'].values())
    assert r['lump']['cycles_with_lump'] == 30 and r['lump']['lots'] == 1489 and abs(r['lump']['side_agreement'] - 0.9333) < 1e-3
