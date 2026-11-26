"""Gate 5a regression contract: the standalone D0 engine reproduces the research simulator exactly; the reference is untouched; the engine has no real-order input."""
import os, json, hashlib, re
HERE = os.path.dirname(os.path.abspath(__file__)); BASE = f'{HERE}/..'; A = f'{BASE}/outputs/phase1/5a'; sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
def test_reference_simulator_and_its_outputs_are_unchanged():
    h = json.load(open(f'{A}/reference_hashes.json'))['sha256']; bad = [f for f, v in h.items() if sha(f'{BASE}/{f}') != v]; assert not bad, bad
def test_reference_is_deterministic_and_the_engine_reproduces_every_saved_cycle():
    d = json.load(open(f'{A}/ref_determinism.json')); assert d['cycles'] == d['identical'] == 49 and all(s['params_match_saved_json'] for s in d['splits'].values())
    r = json.load(open(f'{A}/port_check.json'))
    for mode in ('monitor', 'enforce'):
        m = r['modes'][mode]; assert m['cycles'] == m['identical'] == m['reconciled'] == m['deterministic'] == 49 and 'differs_from_reference' not in m and m['rejected_orders'] == 0, mode
        a, b = m['legacy_D0_OOF']['reference'], m['legacy_D0_OOF']['engine']; assert a == b and abs(a['F1'] - 0.4103) < 1e-3 and a['real_lots'] == 40874
    env = json.load(open(f'{A}/real_d0_envelope.json')); assert env['max_orders_per_minute'] == 90 and env['max_net_short_lots_per_right'] == 278
def test_engine_source_never_touches_real_orders():
    src = open(f'{BASE}/../../../d0_strategy/d0_algo/engine.py').read(); assert not re.search(r'load_orders|dayno|px_avg|\bO\(\)|bl_common|read_pickle|read_csv', src)
