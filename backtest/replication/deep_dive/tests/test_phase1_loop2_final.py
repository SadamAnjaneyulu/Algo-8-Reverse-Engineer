"""Final combined validation of the best defensible configuration (Phase 1 final loop): D0 forward and historical-reproduction, integrated mode F, robustness. Pins the results and the relationships the report states."""
import json, os
OD = os.path.join(os.path.dirname(__file__), '..', 'outputs', 'phase1', '9'); J = lambda n: json.load(open(os.path.join(OD, n)))
def test_d0_final_configs_standards_and_relationship_to_the_5d_candidate():
    for cfg in ('hr', 'fwd'):
        st = J(f'final_{cfg}/standards.json'); assert {k for k, v in st.items() if v['passed']} == {'D6', 'D7', 'D8', 'D10', 'D11', 'D12', 'D13'}
    hr, fw = J('final_hr/summary.json')['OOF_events'], J('final_fwd/summary.json')['OOF_events']; assert hr['keys_F1_60s'] > fw['keys_F1_60s'] and hr['keys_F1_60s'] - fw['keys_F1_60s'] < 0.005      # X1's contribution is small
    assert abs(hr['keys_F1_60s'] - 0.4220) < 5e-4 and abs(fw['keys_F1_60s'] - 0.4201) < 5e-4 and hr['placebo_keys_F1_60s'] < 0.6 * hr['keys_F1_60s']
def test_forward_sets_do_not_depend_on_the_era_rule():
    a, b = J('final_hr/summary.json'), J('final_fwd/summary.json')
    for k in ('forwardA_events', 'forwardB_events'): assert a[k]['keys_F1_60s'] == b[k]['keys_F1_60s']
def test_integrated_final_runs_identity_determinism_risk():
    for cfg in ('hr', 'fwd'):
        s = J(f'final_{cfg}_integrated/summary.json')['sets']; assert sum(v['meta']['runs'] for v in s.values()) == 49
        for v in s.values(): m = v['meta']; assert m['identity_ok'] == m['runs'] == m['reconciled'] == m['deterministic'] and not m['handoff_errors'] and m['rejected'] == 0 and m['peak_short'] <= 306
        o = s['OOF']; assert o['both']['keys_F1_60s'] >= o['both']['placebo'] + 0.10 and o['d0']['keys_F1_60s'] >= 0.8 * J(f'final_{cfg}/summary.json')['OOF_events']['keys_F1_60s'] and abs(o['d1']['keys_F1_60s'] - 0.739) < 0.02
def test_final_robustness():
    r = J('final_robust.json'); assert r['R5']['passed'] and r['R5']['n'] == 18 and {x['engine'] for x in r['R5']['tests']} == {'D0', 'D1+stop'} and all(r['R6_disjoint'].values())
    assert r['LOCO_hr']['keys_F1_60s'] >= J('final_hr/summary.json')['OOF_events']['keys_F1_60s'] - 0.03 and r['LOCO_fwd']['keys_F1_60s'] >= J('final_fwd/summary.json')['OOF_events']['keys_F1_60s'] - 0.03
    s = r['R4_shift_hr']; assert s['-120'] < s['0'] and s['120'] < s['0'] and s['-60'] < s['0'] and s['60'] >= 0.8 * s['0']
