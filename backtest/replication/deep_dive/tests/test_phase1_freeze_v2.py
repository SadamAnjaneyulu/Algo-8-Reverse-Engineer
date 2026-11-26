"""Freeze v2 (Phase 1 final loop): sources, configurations and evidence artefacts keep their hashes; the forward configuration has no era rule; the historical-reproduction configuration carries the labelled experimental X1; default-off switches stay off; v1 stays intact."""
import os, json, hashlib
HERE = os.path.dirname(os.path.abspath(__file__)); BASE = f'{HERE}/..'; ROOT = os.path.abspath(f'{BASE}/../../..'); OD = f'{BASE}/outputs/phase1/9/freeze_v2'; OUT = f'{BASE}/outputs'
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest(); M = lambda: json.load(open(f'{OD}/freeze_manifest_v2.json'))
def test_sources_configs_artefacts_keep_their_hashes():
    m = M(); assert not m['unexplained_changes']
    ad = json.load(open(f'{OD}/freeze_v2_addendum_2026-11-26.json'))['changed'] if os.path.exists(f'{OD}/freeze_v2_addendum_2026-11-26.json') else {}      # later documented neutral edits: old = v2 hash, new = current hash, reason recorded
    bad = [f for f, h in m['source_sha256'].items() if sha(f'{ROOT}/{f}') != h and not (f in ad and ad[f]['old'] == h and ad[f]['new'] == sha(f'{ROOT}/{f}') and ad[f]['reason'])]; assert not bad, bad
    assert sha(f'{OD}/frozen_d0_configs_forward.json') == m['frozen_d0_configs_forward_sha256'] and sha(f'{OD}/frozen_d0_configs_historical_reproduction.json') == m['frozen_d0_configs_historical_reproduction_sha256'] and sha(f'{OD}/frozen_d1_configs_per_cycle.json') == m['frozen_d1_configs_sha256']
    bad = [k for k, h in m['artefact_sha256'].items() if sha(f'{OUT}/{k}') != h]; assert not bad, bad
def test_v1_is_intact_and_params_unchanged():
    m = M(); assert sha(f'{OUT}/phase1/8/freeze_manifest.json') == m['v1_manifest_sha256'] and sha(f'{OUT}/phase1/8/frozen_d0_params.json') == m['frozen_d0_params_sha256_v1']
def test_forward_config_has_no_era_rule_and_hr_has_the_experimental_one():
    f = json.load(open(f'{OD}/frozen_d0_configs_forward.json')); h = json.load(open(f'{OD}/frozen_d0_configs_historical_reproduction.json')); assert len(f) == len(h) == 30
    assert {x['clearance_minute'] for x in f.values()} == {359} and all(x['cycle_stop_rupees'] == 125000.0 and x['risk_mode'] == 'enforce' and x['max_short_lots_per_right'] == 306 and x['opening_long_clock'] is False and x['clearance_hazards'] is None for x in f.values())
    assert {x['clearance_minute'] for k, x in h.items() if k.split('|')[1] < '2026-08-03'} == {363} and {x['clearance_minute'] for k, x in h.items() if k.split('|')[1] >= '2026-08-03'} == {359} and all(x['cycle_stop_rupees'] == 125000.0 for x in h.values())
    assert 'EXPERIMENTAL' in M()['d0_configuration_definitions']['historical_reproduction'] and 'not a production default' in M()['d0_configuration_definitions']['historical_reproduction']
def test_d1_frozen_config_is_b1_with_rejected_stop_off():
    d = json.load(open(f'{OD}/frozen_d1_configs_per_cycle.json')); assert len(d) == 32 and all(x['order_split'] == 'one_lot_v2' and x['cycle_stop_rupees'] is None and x['ladder_lots_mode'] != 'steps' and x['ladder_book_condition'] is False and x['stop_latency_s'] == 0.0 for x in d.values())
def test_default_regression_and_no_independent_claim():
    m = M(); r = m['default_regression_vs_gate5a_reference']; assert r['cycles'] == r['identical'] == 49 and 'no independent validation' in m['evidence_label']
