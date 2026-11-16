"""Python / C++ parity for the NEW plugin behaviour (not the M2 replay parity): both read the same scenario file and must write byte-identical
decision, action, state, lineage, event, instrument and summary files. Categories are asserted separately so a failure names what differs."""
import os, random, subprocess, sys, tempfile
import pytest
from helpers import *
from pc import generators as G
from pc.engine import Simulation
from pc.scenario import Scenario
from pc._m2 import M2_PATH, m2_replay, m2_tsvio

FILES = ('decisions.tsv', 'actions.tsv', 'states.tsv', 'lineage.tsv', 'events.tsv', 'instruments.tsv', 'summary.tsv')


@pytest.fixture(scope='module')
def build(): return cpp_build()


def both(tmp_path, text, name='x'):
    p = tmp_path / f'{name}.scn'; p.write_text(text)
    sim, f = run(text); r = cpp_run(str(p), str(tmp_path / f'cpp_{name}')); assert r.returncode == 0, r.stderr
    return f, {n: open(tmp_path / f'cpp_{name}' / n, encoding='utf-8').read() for n in FILES}


def compare(py, cp, label):
    h = lambda f, k: table(f[k])
    assert [(d['ts'], d['plugin'], d['plugin_version'], d['basket_id'], d['leg_id'], d['outcome'], d['reason'], d['detail'], d['config_hash'], d['info_ts']) for d in h(py, 'decisions.tsv')] == \
           [(d['ts'], d['plugin'], d['plugin_version'], d['basket_id'], d['leg_id'], d['outcome'], d['reason'], d['detail'], d['config_hash'], d['info_ts']) for d in h(cp, 'decisions.tsv')], f'{label}: plugin decisions'
    for typ, what in (('CUT', 'cut quantities'), ('REENTRY', 're-entry quantities')):
        assert [(a['action_id'], a['qty'], a['status'], a['fill_price_paise']) for a in h(py, 'actions.tsv') if a['type'] == typ] == [(a['action_id'], a['qty'], a['status'], a['fill_price_paise']) for a in h(cp, 'actions.tsv') if a['type'] == typ], f'{label}: {what}'
    assert [(a['action_id'], a['reason'], a['detail']) for a in h(py, 'actions.tsv')] == [(a['action_id'], a['reason'], a['detail']) for a in h(cp, 'actions.tsv')], f'{label}: rejection reasons'
    assert h(py, 'states.tsv') == h(cp, 'states.tsv'), f'{label}: basket state'
    assert h(py, 'lineage.tsv') == h(cp, 'lineage.tsv'), f'{label}: event lineage'
    for k in FILES: assert py[k] == cp[k], f'{label}: {k} bytes differ'


def test_cpp_plugin_unit_tests_pass(build):
    r = subprocess.run([os.path.join(build, 'pc_tests')], capture_output=True, text=True); assert r.returncode == 0, r.stdout + r.stderr; assert 'plugin checks passed' in r.stdout and 'FAILED' not in r.stdout
    n = int(r.stdout.split('/')[0].split()[-1]); assert n >= 70


@pytest.mark.parametrize('name', list(G.all_scenarios()))
def test_generator_scenarios_identical_in_both_languages(tmp_path, build, name):
    py, cp = both(tmp_path, G.all_scenarios()[name].to_text(), name); compare(py, cp, name)


def test_forty_more_random_stress_seeds_identical(tmp_path, build):
    ok = 0
    for seed in range(200, 240):
        py, cp = both(tmp_path, G.s10_random_stress(seed).to_text(), f'r{seed}'); compare(py, cp, f'seed{seed}'); ok += 1
    assert ok == 40


def test_permuted_files_and_configuration_sweeps_identical(tmp_path, build):
    base = scn(example_body())
    variants = [base]
    for k, (key, val) in enumerate([('cooldown_s', 0), ('cooldown_s', 3000), ('band_bp', 100), ('max_wait_s', 100), ('qty_mode', 'UNITS'), ('max_reentries_per_cut', 2), ('max_reentry_fraction_bp', 5000)]):
        variants.append(scn(example_body(cfg('basket_reentry', key, val))))
    pre = plugins(False, False, True) + mark(0, SCE, 10000) + tick(0)
    ga = lambda aid, leg, qty: L('ACTION', T0, aid, '', '', 'CUT', 'B1', leg, qty, '', T0, 'grp')
    variants += [scn(pre + ga('g1', 'SCE', 130) + ga('g2', 'SCE', 130)), scn(pre + ga('g1', 'SCE', 65) + ga('g2', 'SPE', 65)), scn(pre + action(0, 'c1', 'CUT', 'SCE', 65) + action(0, 'c2', 'CUT', 'SCE', 65) + action(0, 'r1', 'REENTRY', 'SCE', 130, 'c1'))]
    variants += [scn(pre + action(0, 'c', 'CUT', 'SPE', 65) + action(0, 'r', 'REENTRY', 'SCE', 65, 'c')), scn(pre + action(0, 'c', 'CUT', 'SCE', 260) + action(0, 'r', 'REENTRY', 'SCE', 65, 'c'))]
    variants += [scn(example_body()).replace(f'MARK\t{T0 + 1200}\t{SCE}\t11000\n', f'MARK\t{T0 + 1200}\t{SCE}\t{px}\n') for px in (10620, 10625, 14375, 14380)]
    for pol in ('SCHEDULED',): variants.append(scn(example_body().replace(L('CONFIG', 'basket_cut', 'policy', 'MARK_ADVERSE_MOVE'), L('CONFIG', 'basket_cut', 'policy', pol))))
    for rk in ('max_short_units', 'max_gross_units'): variants.append(scn(example_body('', risk(rk, 330))))
    for i, t in enumerate(variants): py, cp = both(tmp_path, t, f'v{i}'); compare(py, cp, f'variant{i}')


def test_invalid_scenarios_are_refused_by_both(tmp_path, build):
    bad = {'not_synthetic': scn(plugins() + tick(0), 'REAL'), 'conflicting_marks': scn(mark(0, SCE, 10000) + mark(0, SCE, 10005)), 'unknown_plugin': scn(L('PLUGIN', 'ghost', '1.0.0', 1) + tick(0)),
           'incompatible_version': scn(L('PLUGIN', 'basket_cut', '2.0.0', 1) + tick(0)), 'bad_config': scn(plugins() + cfg('basket_cut', 'trigger_bp', -5) + tick(0)), 'unknown_config_key': scn(plugins() + cfg('basket_cut', 'nope', 1) + tick(0)),
           'bad_enum': scn(plugins() + cfg('basket_cut', 'policy', 'MAGIC') + tick(0)), 'bad_risk_key': scn(plugins() + risk('max_everything', 1) + tick(0)), 'seed_not_lot_multiple': scn(L('LEG', 'z', 'B1', 'SCE', SCE, -1, 70, 10000, T0) + tick(0)),
           'duplicate_plugin': scn(plugins() + L('PLUGIN', 'basket_cut', '1.0.0', 1) + tick(0)), 'unknown_line': scn('BOGUS\t1\n')}
    for name, text in bad.items():
        p = tmp_path / f'{name}.scn'; p.write_text(text)
        with pytest.raises(Exception): run(text)
        assert cpp_run(str(p), str(tmp_path / f'o_{name}')).returncode == 2, name


def test_cpp_refuses_every_malformed_scenario_python_refuses(tmp_path, build):
    from test_review_findings import BAD
    for name, text in BAD.items():
        p = tmp_path / f'{name}.scn'; p.write_bytes(text.encode('utf-8'))
        r = cpp_run(str(p), str(tmp_path / f'o_{name}')); assert r.returncode == 2 and 'ERROR' in r.stderr, (name, r.returncode, r.stderr)
        r = subprocess.run([sys.executable, '-m', 'pc.cli', 'run', str(p), '--out', str(tmp_path / f'py_{name}')], capture_output=True, text=True, env=dict(os.environ, PYTHONPATH=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'python')))
        assert r.returncode == 2 and 'ERROR' in r.stderr and 'Traceback' not in r.stderr, (name, r.returncode, r.stderr[-200:])           # clean refusal, no traceback, same exit code
    p = tmp_path / 'bytes.scn'; p.write_bytes(scn(plugins() + tick(0)).encode() + b'\xff\xfe\n'); assert cpp_run(str(p), str(tmp_path / 'ob')).returncode == 2


def test_cpp_creates_the_output_directory_like_python(tmp_path, build):
    p = tmp_path / 's.scn'; p.write_text(G.s05_reentry_success().to_text()); out = tmp_path / 'a' / 'b'; assert cpp_run(str(p), str(out)).returncode == 0 and (out / 'summary.tsv').exists()


def test_no_mark_fill_price_and_distinct_reentry_ids_identical_in_both_languages(tmp_path, build):
    t1 = scn('').replace(L('LEG', 'f1', 'B1', 'SCE', SCE, -1, 195, 10000, T0), L('LEG', 'f1', 'B1', 'SCE', SCE, -1, 65, 10000, T0) + L('LEG', 'f1b', 'B1', 'SCE', SCE, -1, 130, 10050, T0)) + plugins(False, False, True) + tick(0) + action(0, 'c', 'CUT', 'SCE', 65)
    t2 = scn(plugins(False, True, True) + cfg('basket_reentry', 'cooldown_s', 0) + mark(0, SCE, 10000) + tick(0) + tick(300) + action(0, 'c1', 'CUT', 'SCE', 65) + action(0, 'c2', 'CUT', 'SCE', 65))
    for i, t in enumerate((t1, t2)): py, cp = both(tmp_path, t, f'n{i}'); compare(py, cp, f'review{i}')


def test_the_events_written_by_the_plugin_layer_replay_identically_in_m2_python_and_m2_cpp(tmp_path):
    m2_cpp = os.path.join(os.path.dirname(M2_PATH), 'cpp'); b = tempfile.mkdtemp(prefix='m2build_')
    subprocess.check_call(['cmake', '-S', m2_cpp, '-B', b, '-DCMAKE_BUILD_TYPE=Release'], stdout=subprocess.DEVNULL); subprocess.check_call(['cmake', '--build', b], stdout=subprocess.DEVNULL)
    for name, sc in G.all_scenarios().items():
        _, f = run(sc.to_text()); e, i = tmp_path / 'e.tsv', tmp_path / 'i.tsv'; e.write_text(f['events.tsv']); i.write_text(f['instruments.tsv']); dump = tmp_path / 'd.tsv'
        r = subprocess.run([os.path.join(b, 'pe_replay'), '--events', str(e), '--instruments', str(i), '--mode', 'SYNTHETIC_TEST', '--method', 'FIFO', '--tie', 'src', '--dump', str(dump), '--strict'], capture_output=True, text=True); assert r.returncode == 0, r.stderr
        ins = m2_tsvio.read_instruments(str(i)); res = m2_replay.replay(m2_tsvio.read_events(str(e), ins), ins, 'SYNTHETIC_TEST', 'FIFO', 'src', 0, strict=True)
        assert open(dump).read() == res.dump, name
