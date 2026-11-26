"""Phase 1 baseline immutability and B0 regression: (1) no baseline artefact changed since Gate 0 (hash manifest), (2) the engine snapshot B0 is intact, (3) the LIVE engine with default configuration still replays identically to the B0 snapshot (so any candidate switch must default to baseline behaviour)."""
import os, sys, json, importlib.util, hashlib, pytest
HERE = os.path.dirname(os.path.abspath(__file__)); BASE = os.path.join(HERE, '..'); sys.path.insert(0, f'{BASE}/src')
import phase1_baseline as PB
def test_no_baseline_artefact_changed_and_snapshot_intact():
    man = json.load(open(f'{PB.P1}/baseline_manifest.json')); cur = PB.collect(); bad = [k for k, v in man['artefacts'].items() if cur.get(k) != v]; assert not bad, f'baseline artefacts changed: {bad[:5]}'
    snapbad = [f for f, h in man['engine_snapshot'].items() if PB.sha(f'{PB.P1}/baseline_engine_B0/{os.path.basename(f)}') != h]; assert not snapbad
def _load_b0():
    snap = f'{PB.P1}/baseline_engine_B0'; spec = importlib.util.spec_from_file_location('d1_algo_b0', f'{snap}/__init__.py', submodule_search_locations=[snap]); m = importlib.util.module_from_spec(spec); sys.modules['d1_algo_b0'] = m; spec.loader.exec_module(m); return m
@pytest.mark.parametrize('cycle', [0, 17, 31])
def test_live_engine_default_replays_identically_to_the_B0_snapshot(cycle):
    for p in (f'{BASE}/src', f'{BASE}/..', f'{BASE}/../..', f'{BASE}/../../..', f'{BASE}/../../../d1_strategy'): sys.path.insert(0, p)
    cwd = os.getcwd(); os.chdir(f'{BASE}/src')
    try: import bl_fr_sim as S
    finally: os.chdir(cwd)
    import d1_algo as LIVE; B0 = _load_b0(); r = S.CY.iloc[cycle]; d = S.prep(cycle); o = S.OH[(r.und, r.expiry)]; op = d['op']; frames = []
    for pkg in (LIVE, B0):
        feed = pkg.ReplayFeed(o.open.values, o.high.values, o.low.values, o.close.values, d['K'], {k: v for k, v in op.items() if isinstance(k, tuple)}); eng = pkg.D1Engine(pkg.config_for(r.und, r.d1), feed, pkg.PaperBroker(feed)); pkg.run_replay(eng, feed); frames.append(eng.orders_frame())
    cols = [c for c in frames[1].columns if c in frames[0].columns]; assert len(frames[0]) == len(frames[1]) > 0 and frames[0][cols].astype(str).equals(frames[1][cols].astype(str))
