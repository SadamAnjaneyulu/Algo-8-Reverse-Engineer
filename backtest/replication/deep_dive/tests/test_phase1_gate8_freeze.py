"""Gate 8 freeze contract: frozen sources, configurations and key artefacts keep their recorded hashes; the default D0 configuration still reproduces the Gate 5a reference; rejected candidates are off."""
import os, json, hashlib
HERE = os.path.dirname(os.path.abspath(__file__)); BASE = f'{HERE}/..'; ROOT = os.path.abspath(f'{BASE}/../../..'); OD = f'{BASE}/outputs/phase1/8'; OUT = f'{BASE}/outputs'
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest(); M = lambda: json.load(open(f'{OD}/freeze_manifest.json'))
def test_frozen_sources_unchanged_or_changed_only_as_recorded_in_freeze_v2():
    """v1 (Gate 8) hashes must still hold, except for files the Phase 1 final loop edited: those must be listed in freeze v2 with the v1 hash as `old`, the current hash as `new`, and a reason (default-off candidate switches)."""
    m = M(); v2p = f'{BASE}/outputs/phase1/9/freeze_v2/freeze_manifest_v2.json'; ch = json.load(open(v2p))['changed_since_v1'] if os.path.exists(v2p) else {}; bad = []
    for f, h in m['source_sha256'].items():
        cur = sha(f'{ROOT}/{f}')
        if cur == h: continue
        c = ch.get(f); ap = f'{BASE}/outputs/phase1/9/freeze_v2/freeze_v2_addendum_2026-11-26.json'; ad = json.load(open(ap))['changed'].get(f) if os.path.exists(ap) else None
        ok = bool(c and c['old'] == h and c['new'] == cur and c['reason'] != 'UNEXPLAINED') or bool(c and ad and c['old'] == h and ad['old'] == c['new'] and ad['new'] == cur and ad['reason'])      # v1 -> v2 -> addendum chain, each step recorded with a reason
        if not ok: bad.append(f)
    assert not bad, bad
def test_frozen_configs_and_artefacts_unchanged():
    m = M(); assert sha(f'{OD}/frozen_d0_params.json') == m['frozen_d0_params_sha256'] and sha(f'{OD}/frozen_d0_configs_per_cycle.json') == m['frozen_d0_configs_sha256'] and sha(f'{OD}/frozen_d1_configs_per_cycle.json') == m['frozen_d1_configs_sha256']
    bad = [k for k, h in m['artefact_sha256'].items() if sha(f'{OUT}/{k}') != h]; assert not bad, bad
def test_default_regression_and_counts():
    m = M(); r = m['default_regression_vs_gate5a_reference']; assert r['cycles'] == r['identical'] == 49
    assert len(json.load(open(f'{OD}/frozen_d0_configs_per_cycle.json'))) == 30 and len(json.load(open(f'{OD}/frozen_d1_configs_per_cycle.json'))) == 32
def test_frozen_d0_config_has_the_accepted_and_not_the_rejected_candidates():
    c = json.load(open(f'{OD}/frozen_d0_configs_per_cycle.json')); v = list(c.values())
    assert all(x['opening_long_clock'] is False for x in v) and all(x['risk_mode'] == 'enforce' and x['max_short_lots_per_right'] == 306 for x in v)
    pre = [x['clearance_minute'] for k, x in c.items() if k.split('|')[1] < '2026-08-03']; post = [x['clearance_minute'] for k, x in c.items() if k.split('|')[1] >= '2026-08-03']; assert pre and set(pre) == {363} and post and set(post) == {359}
def test_d1_frozen_config_is_b1_one_lot_v2():
    d = json.load(open(f'{OD}/frozen_d1_configs_per_cycle.json')); assert all(x['order_split'] == 'one_lot_v2' and x['ladder_lots_mode'] != 'steps' and x['ladder_book_condition'] is False and x['stop_latency_s'] == 0.0 and x['ladder_late_gate_min'] is None for x in d.values())
def test_frozen_manifest_declares_no_independent_validation():
    m = M(); assert 'no independent validation' in m['evidence_label'] and m['frozen_d0_in_sample_check']['label'].startswith('in-sample')
