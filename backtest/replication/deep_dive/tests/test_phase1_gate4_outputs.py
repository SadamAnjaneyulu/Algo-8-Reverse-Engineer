"""Regression contract of the saved Gate 4 validation report."""
import os, json
HERE = os.path.dirname(os.path.abspath(__file__)); G = f'{HERE}/../outputs/phase1/gate4'
def test_gate4_report_matches_the_standards_as_registered():
    r = json.load(open(f'{G}/gate4_report.json')); v = r['verdict']
    assert v['Q1'] and v['Q3'] and v['Q4'] and v['Q6'] and v['Q7'] and v['Q8'] and v['Q10'] and not v['Q2'] and not v['Q5'] and not v['Q9']
    assert abs(r['Q1']['value'] - 0.7392) < 5e-4 and abs(r['Q3']['value'] - 0.6878) < 5e-4 and r['Q8']['rejected'] == 0 and r['Q5']['failing'] == ['wing_sell'] and r['Q4']['cycles_below_0_60'] == 0
