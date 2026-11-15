"""R1 mutation harness. Mutates a SCRATCH COPY of portfolio_engine/python and runs the R1 tests against it; the repository is never touched.
A mutant counts as KILLED only if a test ASSERTION fails (outcome 'failed'); a collection error / ImportError / crash is reported as 'ERROR' and is NOT a kill.
python3 mutation_harness_R1.py <scratch_dir> <out.json> [--slow]"""
import json, os, re, shutil, subprocess, sys
REPO = '/home/user/Algo-8-Reverse-Engineer'; PE = REPO + '/portfolio_engine'
SCR = sys.argv[1]; OUT = sys.argv[2]; SLOW = '--slow' in sys.argv

# (id, file, old, new, expected detector, run slow tests too?)
MUTANTS = [
 ('R1M01_replay_default_not_primary', 'python/pe/replay.py', "method='FIFO', tie_order='src'", "method='FIFO', tie_order='sells_first'", 'test_default_convention_is_source_row_order', False),
 ('R1M02_lineageset_default_not_primary', 'python/pe/lineage_set.py', "def __init__(self, fills, instruments, mode, tie_order='src'", "def __init__(self, fills, instruments, mode, tie_order='buys_first'", 'test_default_convention_is_source_row_order', False),
 ('R1M03_alias_maps_to_wrong_policy', 'python/pe/tie_policy.py', "ALIASES = {'src': 'source_row'}", "ALIASES = {'src': 'sells_first'}", 'test_default_convention_is_source_row_order / alias byte-identity', False),
 ('R1M04_sells_first_marked_primary', 'python/pe/tie_policy.py', "TiePolicy('sells_first', 'sells_first', False, False, True,", "TiePolicy('sells_first', 'sells_first', True, False, True,", 'test_policy_registry_is_exactly_the_approved_set_and_only_source_row_is_primary', False),
 ('R1M05_convention_id_hides_sensitivity', 'python/pe/tie_policy.py', "return SOURCE_ROW_ORDER_CONVENTION if p.primary else SENSITIVITY_PREFIX + p.name", "return SOURCE_ROW_ORDER_CONVENTION", 'test_policy_registry... / test_sensitivity_policy_cannot_silently_replace', False),
 ('R1M06_require_primary_noop', 'python/pe/tie_policy.py', "    if not is_primary(name): raise EngineError(", "    if False: raise EngineError(", 'test_sensitivity_policy_cannot_silently_replace_the_primary_convention', False),
 ('R1M07_keyed_sort_descending', 'python/pe/replay.py', "return sorted(fills, key=lambda f: (f.timestamp_s, f.tie_key, f.source_row_id, f.fill_id))", "return sorted(fills, key=lambda f: (f.timestamp_s, tuple(-v for v in f.tie_key), f.source_row_id, f.fill_id))", 'test_keyed_policies_reorder_a_same_side_flip', False),
 ('R1M08_keyed_ignored', 'python/pe/replay.py', "return sorted(fills, key=lambda f: (f.timestamp_s, f.tie_key, f.source_row_id, f.fill_id))", "return sorted(fills, key=lambda f: (f.timestamp_s, f.source_row_id, f.fill_id))", 'test_keyed_policies_reorder_a_same_side_flip', False),
 ('R1M09_sensex_floor_not_round', 'python/pe/tie_policy.py', "if (ns + 500_000_000) // 10**9 == epoch_s: return (ns,)", "if ns // 10**9 == epoch_s: return (ns,)", 'test_key_functions', False),
 ('R1M10_sensex_no_consistency_check', 'python/pe/tie_policy.py', "if (ns + 500_000_000) // 10**9 == epoch_s: return (ns,)", "if True: return (ns,)", 'test_key_functions / test_attach_tie_keys_reads_raw_rows', False),
 ('R1M11_sensex_policy_applies_to_nifty', 'python/pe/tie_policy.py', "    if underlying != 'SENSEX': return (0,)\n", "", 'test_key_functions', False),
 ('R1M12_trade_id_drops_suffix', 'python/pe/tie_policy.py', "a, b = trade_id.split('-', 1); return (int(a), int(b))", "a, b = trade_id.split('-', 1); return (int(a), 0)", 'test_key_functions', False),
 ('R1M13_order_no_lexicographic', 'python/pe/tie_policy.py', "def order_no_key(order_no): return (int(order_no),)", "def order_no_key(order_no): return (order_no,)", 'test_key_functions', False),
 ('R1M14_primary_gets_a_key', 'python/pe/tie_policy.py', "    return None\n", "    return (0,)\n", 'test_attach_tie_keys_reads_raw_rows_and_leaves_primary_untouched / test_key_functions', False),
 ('R1M15_alias_not_normalised_in_replay', 'python/pe/replay.py', "    if tie_order == 'source_row': tie_order = 'src'", "    if False: tie_order = 'src'", 'test_source_row_alias_is_byte_identical_to_legacy_src', False),
 ('R1M16_attach_off_by_one_row', 'python/pe/generators/historical.py', "und, tid, ono = keys[f.source_row_id]", "und, tid, ono = keys[max(f.source_row_id - 1, 0) if f.source_row_id in keys and f.source_row_id - 1 in keys else f.source_row_id]", 'test_attach_tie_keys_reads_raw_rows (REAL ledger rows)', False),
 ('R1M17_real_trade_id_sorted_by_sell_side', 'python/pe/tie_policy.py', "    if n == 'trade_id': return trade_id_key(trade_id)", "    if n == 'trade_id': return (0,)", 'test_attach_tie_keys_reads_raw_rows / slow real-ledger pins', True),
]


def prep(name):
    d = os.path.join(SCR, name); shutil.rmtree(d, ignore_errors=True); os.makedirs(d + '/portfolio_engine')
    shutil.copytree(PE + '/python', d + '/portfolio_engine/python', ignore=shutil.ignore_patterns('__pycache__')); shutil.copytree(PE + '/tests', d + '/portfolio_engine/tests', ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copy(PE + '/pytest.ini', d + '/portfolio_engine/pytest.ini'); os.symlink(REPO + '/tp_reconstruction', d + '/tp_reconstruction'); os.symlink(REPO + '/Trades_GKOHNP140.csv', d + '/Trades_GKOHNP140.csv')
    os.symlink(PE + '/tools', d + '/portfolio_engine/tools'); os.makedirs(d + '/portfolio_engine/reports', exist_ok=True)
    for x in os.listdir(PE + '/reports'):
        if not os.path.exists(d + '/portfolio_engine/reports/' + x): os.symlink(PE + '/reports/' + x, d + '/portfolio_engine/reports/' + x)
    return d


def run_tests(d, slow):
    sel = ['tests/test_tie_order_policy.py', '-q', '-p', 'no:cacheprovider', '-x', '--tb=line', '-rf'] + ([] if slow else ['-m', 'not slow'])
    p = subprocess.run([sys.executable, '-m', 'pytest'] + sel, cwd=d + '/portfolio_engine', capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), timeout=3000)
    txt = p.stdout + p.stderr; failed = re.findall(r'^FAILED (\S+)', txt, re.M); err = re.findall(r'^ERROR (\S+)', txt, re.M) or (['collection/import error'] if 'ImportError' in txt or 'Interrupted' in txt else [])
    outcome = 'failed' if failed else ('ERROR' if err else ('survived' if p.returncode == 0 else 'ERROR'))
    return outcome, failed, err, txt.strip().splitlines()[-1] if txt.strip() else ''


res = []
d0 = prep('baseline'); o, f, e, last = run_tests(d0, False); res.append(dict(id='BASELINE_unmutated', outcome=o, failed=f, summary=last)); print('baseline', o, last, flush=True)
assert o == 'survived', 'baseline (unmutated) tests must pass in the mirror'
for mid, rel, old, new, detector, slow_too in MUTANTS:
    d = prep(mid); path = os.path.join(d, 'portfolio_engine', rel); s = open(path).read()
    if old not in s: res.append(dict(id=mid, outcome='NOT_APPLIED', note='pattern not found')); print(mid, 'NOT_APPLIED'); continue
    open(path, 'w').write(s.replace(old, new, 1)); o, f, e, last = run_tests(d, False); stage = 'fast'
    if o == 'survived' and (slow_too or SLOW): o, f, e, last = run_tests(d, True); stage = 'fast+slow'
    res.append(dict(id=mid, file=rel, change=f'{old!r} -> {new!r}', expected_detector=detector, outcome=o, failed_tests=f[:3], errors=e[:2], stage=stage, summary=last)); print(mid, o, f[:1], flush=True)
    json.dump(res, open(OUT, 'w'), indent=1)
json.dump(res, open(OUT, 'w'), indent=1)
print('killed', sum(1 for r in res if r.get('outcome') == 'failed'), 'of', len(MUTANTS), '| survived', [r['id'] for r in res if r.get('outcome') == 'survived'], '| not killed by assertion', [r['id'] for r in res if r.get('outcome') in ('ERROR', 'NOT_APPLIED')])
