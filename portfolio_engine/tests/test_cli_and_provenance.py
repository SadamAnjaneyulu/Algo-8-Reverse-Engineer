"""M2-F E-D07 / E-D12: the infrastructure layer (pe.cli, pe.provenance, schema_version check of the TSV reader, IST offset shared with the C++ core) was untested and 5 system mutants survived.
Fast tests (no real ledger, no C++ build). Expectations are hand-calculated from the fixture `fixtures/synthetic/open_close_full`:
  fill 1: SELL (side -1) 130 units NIFTY|2026-01-08|CE|24000 @ 10000 paise, ts 1767584760;  fill 2: BUY 130 units @ 8000 paise, ts 1767584820
  realized P&L = (10000 - 8000) paise * 130 = 260000 paise; opened 130, closed 130, remaining 0; 2 snapshots at --snapshot-interval 1.
`run_id` = first 16 hex of sha256(json.dumps([config_hash, source_hashes, git_sha, implementation], sort_keys=True)); inside a directory that is not a git repository git_sha is 'UNAVAILABLE'.
Known finding kept visible (E-D02): run_id depends on the git HEAD of the repository holding the events file (test_run_id_depends_on_git_head_of_the_events_directory documents it)."""
import hashlib, json, os, re, shutil, subprocess, sys
import pytest
from conftest import PE
from pe import provenance, schema, tsvio, forensics
from pe.schema import EventValidationError

FIX = os.path.join(PE, 'fixtures', 'synthetic'); EV = 'open_close_full_events.tsv'; INS = 'open_close_full_instruments.tsv'
CPP_TYPES = os.path.join(PE, 'cpp', 'include', 'pe', 'types.hpp'); CPP_IO = os.path.join(PE, 'cpp', 'include', 'pe', 'io.hpp')
GOLDEN_RUN_ID = '412d644cbce43f03'            # python engine, SYNTHETIC_TEST, FIFO, tie src, snapshot_interval 1, fixture bytes as committed, git_sha UNAVAILABLE
EVENTS_SHA = '2c2b2a6eaed8bf5dd775cbf7b55654820d8f3a115167e128d6f0a61bc63770c1'; INSTRUMENTS_SHA = 'bfb044ad58d277100352c56e264f2c300179d7f2540fc3ca13283e016af5e3eb'
MANIFEST_KEYS = sorted(['run_id', 'execution_mode', 'tie_order_convention', 'implementation', 'config', 'config_hash', 'source_hashes', 'git_sha', 'matching_convention', 'tie_order', 'timestamp_range', 'warnings',
                        'invariants_checked', 'dump_sha256', 'reproduce_command', 'created_utc'])


def sha(b): return hashlib.sha256(b).hexdigest()


@pytest.fixture
def work(tmp_path):
    w = tmp_path / 'work'; w.mkdir(); shutil.copy(os.path.join(FIX, EV), w / EV); shutil.copy(os.path.join(FIX, INS), w / INS); return w


def cli(work, *args, out='runs', extra_env=None):
    """python -m pe.cli replay ... in a subprocess; git discovery is confined below tmp_path's parent so the work directory is never inside a repository"""
    env = dict(os.environ, PYTHONPATH=os.path.join(PE, 'python'), GIT_CEILING_DIRECTORIES=os.path.dirname(str(work.parent)), **(extra_env or {}))
    argv = ['replay', '--events', str(work / EV), '--instruments', str(work / INS), '--mode', 'SYNTHETIC_TEST', '--method', 'FIFO', '--tie', 'src', '--snapshot-interval', '1', '--engine', 'python'] if not args else list(args)
    if out: argv += ['--out-dir', str(work / out)]
    return subprocess.run([sys.executable, '-m', 'pe.cli'] + argv, capture_output=True, text=True, env=env, cwd=str(work))


def test_cli_replay_writes_runs_mode_run_id_with_dump_and_manifest(work):
    p = cli(work); assert p.returncode == 0, p.stderr
    d = p.stdout.strip(); assert d == str(work / 'runs' / 'SYNTHETIC_TEST' / GOLDEN_RUN_ID)           # layout runs/<MODE>/<run_id>/, the directory is printed on stdout
    assert sorted(os.listdir(d)) == ['manifest.json', 'state_dump.tsv'] and os.listdir(work / 'runs') == ['SYNTHETIC_TEST']
    m = json.load(open(os.path.join(d, 'manifest.json'))); dump = open(os.path.join(d, 'state_dump.tsv'), 'rb').read()
    assert sorted(m) == MANIFEST_KEYS
    cfg = dict(mode='SYNTHETIC_TEST', method='FIFO', tie_order='src', snapshot_interval=1)
    assert m['run_id'] == GOLDEN_RUN_ID and m['execution_mode'] == 'SYNTHETIC_TEST' and m['implementation'] == 'python' and m['matching_convention'] == 'FIFO' and m['tie_order'] == 'src'
    assert m['config'] == cfg and m['config_hash'] == sha(b'{"method": "FIFO", "mode": "SYNTHETIC_TEST", "snapshot_interval": 1, "tie_order": "src"}')   # canonical sorted JSON, hand-written
    assert m['source_hashes'] == {'events_sha256': EVENTS_SHA, 'instruments_sha256': INSTRUMENTS_SHA} == {'events_sha256': sha(open(work / EV, 'rb').read()), 'instruments_sha256': sha(open(work / INS, 'rb').read())}
    assert m['git_sha'] == 'UNAVAILABLE' and m['tie_order_convention'] == 'SOURCE_ROW_ORDER_CONVENTION' and m['timestamp_range'] == [1767584760, 1767584820]
    assert m['warnings'] == {'MISSING_MARKS': 1}                                                      # only non-zero warnings are listed; MISSING_MARKS is always 1 (no marks in the model)
    assert m['dump_sha256'] == sha(dump) and len(m['invariants_checked']) == 9 and m['invariants_checked'] == sorted(set(m['invariants_checked']))
    assert m['reproduce_command'] == 'python3 -m pe.cli ' + ' '.join(['replay', '--events', str(work / EV), '--instruments', str(work / INS), '--mode', 'SYNTHETIC_TEST', '--method', 'FIFO', '--tie', 'src', '--snapshot-interval', '1', '--engine', 'python', '--out-dir', str(work / 'runs')])
    assert re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ', m['created_utc'])
    lines = dump.decode().split('\n')                                                                  # hand-calculated economics: opened 130, closed 130, realized (10000-8000)*130 = 260000 paise
    assert '#PE_STATE_DUMP v1' == lines[0] and 'TOTAL\topened_units\t130' in lines and 'TOTAL\tclosed_units\t130' in lines and 'TOTAL\tremaining_units\t0' in lines and 'TOTAL\trealized_pnl_paise\t260000' in lines
    assert sum(1 for l in lines if l.startswith('SNAP\t')) == 2 and m['tie_order'] == 'src'


def test_run_id_is_deterministic_and_changes_with_each_hashed_input(work):
    a = json.load(open(os.path.join(cli(work, out='r1').stdout.strip(), 'manifest.json'))); b = json.load(open(os.path.join(cli(work, out='r2').stdout.strip(), 'manifest.json')))
    assert a['run_id'] == b['run_id'] == GOLDEN_RUN_ID and {k: v for k, v in a.items() if k not in ('created_utc', 'reproduce_command')} == {k: v for k, v in b.items() if k not in ('created_utc', 'reproduce_command')}
    assert open(os.path.join(work, 'r1', 'SYNTHETIC_TEST', GOLDEN_RUN_ID, 'state_dump.tsv'), 'rb').read() == open(os.path.join(work, 'r2', 'SYNTHETIC_TEST', GOLDEN_RUN_ID, 'state_dump.tsv'), 'rb').read()
    base = ['replay', '--events', str(work / EV), '--instruments', str(work / INS), '--mode', 'SYNTHETIC_TEST']
    ids = {GOLDEN_RUN_ID}
    for extra in (['--method', 'LIFO', '--tie', 'src', '--snapshot-interval', '1'], ['--method', 'FIFO', '--tie', 'sells_first', '--snapshot-interval', '1'], ['--method', 'FIFO', '--tie', 'src', '--snapshot-interval', '2']):
        r = cli(work, *(base + extra + ['--engine', 'python']), out='r3'); assert r.returncode == 0, r.stderr; ids.add(r.stdout.strip().split(os.sep)[-1])
    assert len(ids) == 4                                                                               # method, tie order and snapshot interval each enter the config hash -> a different run id
    (work / EV).write_text((work / EV).read_text().replace('10000', '10005'))                          # changed source bytes -> changed events_sha256 -> a different run id
    r = cli(work, out='r4'); assert r.returncode == 0 and r.stdout.strip().split(os.sep)[-1] not in ids


def test_modes_never_share_a_run_directory(work):
    (work / EV).write_text((work / EV).read_text().replace('SYNTHETIC_TEST', 'RESEARCH_POLICY_SIMULATION'))
    p = cli(work, 'replay', '--events', str(work / EV), '--instruments', str(work / INS), '--mode', 'RESEARCH_POLICY_SIMULATION', '--snapshot-interval', '1'); assert p.returncode == 0, p.stderr
    parts = p.stdout.strip().split(os.sep); assert parts[-3:-1] == ['runs', 'RESEARCH_POLICY_SIMULATION'] and re.fullmatch(r'[0-9a-f]{16}', parts[-1])
    q = cli(work); assert q.returncode != 0 and 'ModeContaminationError' in q.stderr                    # SYNTHETIC_TEST run over RESEARCH_POLICY_SIMULATION events is refused before anything is written
    assert sorted(os.listdir(work / 'runs')) == ['RESEARCH_POLICY_SIMULATION']


def test_cpp_engine_is_refused_for_python_only_tie_policies_before_any_binary_is_needed(work):
    for pol in ('trade_id', 'order_no', 'sensex_trade_id_time', 'per_contract_id_sequence'):
        p = cli(work, 'replay', '--events', str(work / EV), '--instruments', str(work / INS), '--mode', 'SYNTHETIC_TEST', '--tie', pol, '--engine', 'cpp'); assert p.returncode == 1 and not (work / 'runs').exists()
        assert f"tie policy '{pol}' is Python-only" in p.stderr and 'supports source_row, sells_first and buys_first' in p.stderr, p.stderr
    p = cli(work, 'replay', '--events', str(work / EV), '--instruments', str(work / INS), '--mode', 'SYNTHETIC_TEST', '--tie', 'nonsense', '--engine', 'cpp'); assert p.returncode != 0 and "unknown tie-order policy 'nonsense'" in p.stderr


def test_cli_rejects_bad_input_without_writing_a_run(work):
    (work / EV).write_text((work / EV).read_text().replace('pe.fill.v1', 'pe.fill.v2'))
    p = cli(work); assert p.returncode != 0 and "schema_version 'pe.fill.v2'" in p.stderr and not (work / 'runs').exists()


def test_schema_version_other_than_pe_fill_v1_is_rejected_with_the_line_number(tmp_path):
    ins = tsvio.read_instruments(os.path.join(FIX, INS)); good = open(os.path.join(FIX, EV)).read().split('\n')
    assert [f.fill_id for f in tsvio.read_events(os.path.join(FIX, EV), ins)] == ['S000001', 'S000002'] and schema.SCHEMA_FILL == 'pe.fill.v1'
    for bad in ('pe.fill.v2', 'pe.fill.v0', '', 'PE.FILL.V1'):
        lines = list(good); k = next(i for i, l in enumerate(lines) if l.startswith('pe.fill.v1') and '\tS000002\t' in l); lines[k] = bad + lines[k][len('pe.fill.v1'):]
        p = tmp_path / 'e.tsv'; p.write_text('\n'.join(lines))
        with pytest.raises(EventValidationError, match=re.escape(f"e.tsv:{k + 1}: schema_version {bad!r}")): tsvio.read_events(str(p), ins)            # k is 0-based; the message line number is 1-based
    lines = list(good); lines[1 if lines[0].startswith('#') else 0] = lines[1 if lines[0].startswith('#') else 0].replace('schema_version', 'schema_ver')
    (tmp_path / 'h.tsv').write_text('\n'.join(lines))
    with pytest.raises(EventValidationError, match='bad header'): tsvio.read_events(str(tmp_path / 'h.tsv'), ins)


def _cpp_const(path, name):
    m = re.search(name + r'\s*=\s*([^;]+);', open(path).read()); assert m, f'{name} not found in {path}'; return m.group(1).strip()


def test_ist_offset_is_19800_in_python_and_in_the_cpp_header():
    assert 5 * 3600 + 30 * 60 == 19800                                                                 # IST = UTC+05:30
    assert schema.IST_OFFSET_S == 19800 and forensics.IST == 19800
    assert int(_cpp_const(CPP_TYPES, r'constexpr i64 kIstOffsetS')) == schema.IST_OFFSET_S
    assert 'ist_day(i64 ts) { return (ts + kIstOffsetS) / 86400; }' in open(CPP_TYPES).read()          # the constant is the one used for the day split
    assert _cpp_const(CPP_TYPES, r'inline const char\* kSchemaFill') == '"%s"' % schema.SCHEMA_FILL and 'p[0] != kSchemaFill' in open(CPP_IO).read()     # the C++ reader checks the same schema_version token
    assert re.findall(r'"([A-Z_]+)"', _cpp_const(CPP_TYPES, r'inline const std::vector<std::string> kModes')) == list(schema.MODES)


def test_ist_day_boundary_is_1830_utc_hand_calculated():
    d = (2026 - 1970) * 365 + 14 + 7                                                                   # days from 1970-01-01 to 2026-01-08 (14 leap days 1972..2024): 20461
    assert d == 20461 and schema.days_from_civil(2026, 1, 8) == d and schema.iso_day('2026-01-08') == d
    t0 = d * 86400                                                                                     # 2026-01-08 00:00:00 UTC
    assert schema.ist_day(t0 + 18 * 3600 + 29 * 60 + 59) == d and schema.ist_day(t0 + 18 * 3600 + 30 * 60) == d + 1       # 23:59:59 IST is still Jan 8, 00:00:00 IST is Jan 9
    assert schema.day_iso(schema.ist_day(t0 + 18 * 3600 + 30 * 60)) == '2026-01-09' and schema.ist_day(t0) == d


def test_git_sha_is_UNAVAILABLE_outside_a_repository_and_the_head_inside_one(tmp_path, monkeypatch):
    monkeypatch.setenv('GIT_CEILING_DIRECTORIES', str(tmp_path.parent))
    plain = tmp_path / 'plain'; plain.mkdir(); assert provenance.git_sha(str(plain)) == 'UNAVAILABLE' and provenance.git_sha(str(tmp_path / 'does_not_exist')) == 'UNAVAILABLE'
    repo = tmp_path / 'repo'; repo.mkdir(); env = dict(os.environ, GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@t', GIT_COMMITTER_NAME='t', GIT_COMMITTER_EMAIL='t@t')
    for a in (['init', '-q'], ['commit', '-q', '--allow-empty', '-m', 'x']): subprocess.run(['git'] + a, cwd=repo, check=True, env=env, capture_output=True)
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, env=env).decode().strip()
    assert re.fullmatch(r'[0-9a-f]{40}', head) and provenance.git_sha(str(repo)) == head and provenance.git_sha(str(repo)) != 'UNAVAILABLE'


def test_run_id_depends_on_git_head_of_the_events_directory(work, tmp_path):
    """documents E-D02: the same inputs and config give a different run_id when the events file lives in a repository (HEAD enters the hash); the manifest records that head"""
    env = dict(os.environ, GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@t', GIT_COMMITTER_NAME='t', GIT_COMMITTER_EMAIL='t@t')
    for a in (['init', '-q'], ['add', '.'], ['commit', '-q', '-m', 'x']): subprocess.run(['git'] + a, cwd=work, check=True, env=env, capture_output=True)
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=work, env=env).decode().strip()
    p = cli(work); assert p.returncode == 0, p.stderr; m = json.load(open(os.path.join(p.stdout.strip(), 'manifest.json')))
    assert m['git_sha'] == head and m['run_id'] != GOLDEN_RUN_ID
    assert m['run_id'] == sha(json.dumps([m['config_hash'], m['source_hashes'], head, 'python'], sort_keys=True).encode())[:16]


def test_sha256_helpers_and_run_dir(tmp_path):
    assert provenance.sha256_text('abc') == 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad' and provenance.sha256_text('') == 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
    f = tmp_path / 'f.bin'; f.write_bytes(b'abc' * 1000000); assert provenance.sha256_file(str(f)) == hashlib.sha256(b'abc' * 1000000).hexdigest()       # larger than the 1 MiB read block
    d = provenance.run_dir(str(tmp_path / 'root'), 'SYNTHETIC_TEST', 'abc123'); assert d == str(tmp_path / 'root' / 'SYNTHETIC_TEST' / 'abc123') and os.path.isdir(d) and provenance.run_dir(str(tmp_path / 'root'), 'SYNTHETIC_TEST', 'abc123') == d


# ---- E-D02: code_fingerprint (helper only; stamping it into SCENARIO manifests is a proposal, delivered manifests are untouched) ----
def _tree(root, files):
    for rel, b in files.items():
        p = root / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(b)


def test_code_fingerprint_hand_calculated_small_tree(tmp_path):
    _tree(tmp_path, {'python/pe/a.py': b'A=1\n', 'tools/t.py': b'T=2\n'})
    # sha256 over b'python/pe/a.py\0' b'4\0' b'A=1\n' b'tools/t.py\0' b'4\0' b'T=2\n' (sorted relative paths, <path>\0<length>\0<bytes>)
    assert provenance.code_fingerprint(str(tmp_path)) == '69d40d60b1167874c8d11886a5a9912c73df5833aa9faf217c3daebd68b8c63b'
    t2 = tmp_path / 'second'                                                                            # sorted POSIX path order: 'python/pe/sub/b.py' < 'python/pe/z.py' < 'tools/t.py' (a directory walk lists z.py first)
    _tree(t2, {'python/pe/z.py': b'Z', 'python/pe/sub/b.py': b'B', 'tools/t.py': b'T'})
    assert provenance.code_fingerprint(str(t2)) == '2f71bb65c2f69f65ccfa65e8cfa785487d64d305b3f8a068a2d0ab1f03f4abe2'


def test_code_fingerprint_covers_exactly_python_pe_py_files_and_top_level_tools_py(tmp_path):
    base = {'python/pe/a.py': b'A=1\n', 'python/pe/sub/b.py': b'B=2\n', 'tools/t.py': b'T=3\n'}; _tree(tmp_path, base); f0 = provenance.code_fingerprint(str(tmp_path))
    assert re.fullmatch(r'[0-9a-f]{64}', f0)
    _tree(tmp_path, {'python/pe/c.txt': b'x', 'python/pe/__pycache__/a.cpython-313.pyc': b'x', 'python/pe/sub/__pycache__/q.py': b'x', 'tools/sub/deep.py': b'x', 'tests/test_x.py': b'x', 'cpp/x.py': b'x', 'reports/r.py': b'x', 'tools/notes.md': b'x'})
    assert provenance.code_fingerprint(str(tmp_path)) == f0                                              # files outside the covered set never change it
    for rel in ('python/pe/a.py', 'python/pe/sub/b.py', 'tools/t.py'):                                  # one byte changed in any covered file changes it
        old = (tmp_path / rel).read_bytes(); (tmp_path / rel).write_bytes(old + b' '); assert provenance.code_fingerprint(str(tmp_path)) != f0, rel; (tmp_path / rel).write_bytes(old)
    assert provenance.code_fingerprint(str(tmp_path)) == f0
    _tree(tmp_path, {'python/pe/new.py': b''}); assert provenance.code_fingerprint(str(tmp_path)) != f0     # a new (even empty) covered file changes it
    (tmp_path / 'python/pe/new.py').unlink(); os.rename(tmp_path / 'tools/t.py', tmp_path / 'tools/u.py'); assert provenance.code_fingerprint(str(tmp_path)) != f0      # a rename changes it


def test_code_fingerprint_is_independent_of_creation_order_and_location_and_has_no_concatenation_ambiguity(tmp_path):
    a = tmp_path / 'a'; b = tmp_path / 'b'; files = {'python/pe/x.py': b'1', 'python/pe/y.py': b'2', 'tools/z.py': b'3'}
    _tree(a, files); _tree(b, dict(reversed(list(files.items()))))
    assert provenance.code_fingerprint(str(a)) == provenance.code_fingerprint(str(b)) == provenance.code_fingerprint(str(a) + os.sep + '.')
    c = tmp_path / 'c'; _tree(c, {'python/pe/x.py': b'12', 'python/pe/y.py': b'', 'tools/z.py': b'3'}); assert provenance.code_fingerprint(str(c)) != provenance.code_fingerprint(str(a))     # bytes moved between files


def test_code_fingerprint_refuses_a_directory_that_is_not_a_portfolio_engine_root(tmp_path):
    with pytest.raises(schema.EngineError, match='not a directory'): provenance.code_fingerprint(str(tmp_path))
    _tree(tmp_path, {'python/pe/a.py': b'x'})
    with pytest.raises(schema.EngineError, match='tools'): provenance.code_fingerprint(str(tmp_path))


def test_code_fingerprint_of_this_checkout_is_stable_and_equal_for_a_copy(tmp_path):
    f = provenance.code_fingerprint(PE); assert f == provenance.code_fingerprint(PE) and re.fullmatch(r'[0-9a-f]{64}', f)
    shutil.copytree(os.path.join(PE, 'python', 'pe'), tmp_path / 'python' / 'pe', ignore=shutil.ignore_patterns('__pycache__')); (tmp_path / 'tools').mkdir()
    for n in os.listdir(os.path.join(PE, 'tools')):
        if n.endswith('.py'): shutil.copy(os.path.join(PE, 'tools', n), tmp_path / 'tools' / n)
    assert provenance.code_fingerprint(str(tmp_path)) == f
