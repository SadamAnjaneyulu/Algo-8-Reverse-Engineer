"""Phase 1 baseline preservation. Records sha256 of every baseline artefact (original F runs, accepted one-lot F run, TF-E runs, ledgers, specs, scorer, frozen late-sale files, data cache) and snapshots the original engine source (baseline B0). 
Usage: python phase1_baseline.py write   (once, at Gate 0)   |   python phase1_baseline.py check   (verifies nothing changed; used by tests/test_phase1_baseline.py)."""
import sys, os, json, hashlib, glob, shutil, datetime
HERE = os.path.dirname(os.path.abspath(__file__)); DD = os.path.abspath(f'{HERE}/..'); ROOT = os.path.abspath(f'{DD}/../../..'); OUT = f'{DD}/outputs'; P1 = f'{OUT}/phase1'
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
# baseline artefacts that must never change during Phase 1 (candidate runs get new directories)
IMMUTABLE_DIRS = ['scoring/d1_F', 'scoring/d1_F_first_execution_class_table_defect', 'scoring/d1_F_v2_onelot', 'scoring/d1_F_v2_onelot_attempt1_guard_blocked', 'scoring/d1_TFE_v2_onelot', 'scoring/d1_TFE_first_v2_onelot', 'scoring/d1_TFE_m_v2_onelot', 'scoring/d1_TFE_m_first_v2_onelot', 'scoring/tfe_comparison', 'bodysell']
IMMUTABLE_FILES = ['scoring/spec_freeze.json', 'scoring/ORDER_LEVEL_SCORING_SPEC_v1.0.md', 'scoring/execution_convention.json', 'scoring/split_comparison/comparison.json', 'scoring/split_comparison/freeze_integrity.json', 'bl_d1eng_orders.pkl.gz', 'fwd/frozen_model.json']
REPO_FILES = ['backtest/replication/deep_dive/reports/ORDER_LEVEL_SCORING_SPEC.md', 'backtest/replication/deep_dive/reports/FORWARD_TEST.md', 'backtest/replication/deep_dive/src/bl_oscore.py', 'backtest/replication/deep_dive/src/bl_fwd_freeze.py', 'd1_strategy/d1_algo/shadow.py']
ENGINE_FILES = ['d1_strategy/d1_algo/' + f for f in ('__init__.py', 'bars.py', 'book.py', 'config.py', 'engine.py', 'interfaces.py', 'models.py', 'risk.py', 'sim.py', 'shadow.py', 'shadow_state.py', 'live_template.py')]
def collect():
    m = {}
    for d in IMMUTABLE_DIRS:
        for f in sorted(glob.glob(f'{OUT}/{d}/**/*', recursive=True)):
            if os.path.isfile(f) and not f.endswith('.pyc') and not f.endswith('.log'): m[os.path.relpath(f, ROOT)] = sha(f)
    for f in IMMUTABLE_FILES:
        if os.path.exists(f'{OUT}/{f}'): m[os.path.relpath(f'{OUT}/{f}', ROOT)] = sha(f'{OUT}/{f}')
    for f in REPO_FILES: m[f] = sha(f'{ROOT}/{f}')
    return m
def engine_hashes(): return {f: sha(f'{ROOT}/{f}') for f in ENGINE_FILES if os.path.exists(f'{ROOT}/{f}')}
if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'check'
    if mode == 'write':
        assert not os.path.exists(f'{P1}/baseline_manifest.json'), 'baseline manifest already written; baselines are never rewritten'
        os.makedirs(P1, exist_ok=True); snap = f'{P1}/baseline_engine_B0'; shutil.copytree(f'{ROOT}/d1_strategy/d1_algo', snap, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        man = dict(written_at=datetime.datetime.utcnow().isoformat() + 'Z', note='Gate 0 baseline. B0 = original freeze_v1 F run; B1 = accepted one_lot_v2 F run (working baseline for body-sell work). Engine snapshot B0 = d1_algo as of Gate 0 (default order_split freeze_v1; one_lot_v2 available).', artefacts=collect(), engine_sha256_at_gate0=engine_hashes(), engine_snapshot={f: sha(f'{snap}/{os.path.basename(f)}') for f in ENGINE_FILES if os.path.exists(f'{snap}/{os.path.basename(f)}')})
        json.dump(man, open(f'{P1}/baseline_manifest.json', 'w'), indent=1); print(len(man['artefacts']), 'artefacts hashed;', len(man['engine_snapshot']), 'engine files snapshotted')
    else:
        man = json.load(open(f'{P1}/baseline_manifest.json')); cur = collect(); bad = [k for k, v in man['artefacts'].items() if cur.get(k) != v]; snapbad = [f for f, h in man['engine_snapshot'].items() if sha(f'{P1}/baseline_engine_B0/{os.path.basename(f)}') != h]
        print('changed baseline artefacts:', bad, '| snapshot corrupted:', snapbad); sys.exit(1 if (bad or snapbad) else 0)
