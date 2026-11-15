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
 ('R1M18_half_ns_boundary_shifted', 'python/pe/tie_policy.py', "if (ns + 500_000_000) // 10**9 == epoch_s: return (ns,)", "if (ns + 499_999_999) // 10**9 == epoch_s: return (ns,)", 'test_sensex_time_rounding_boundary_is_half_up_at_the_half_nanosecond (reviewer R2M02)', False),
 ('R1M19_keyed_key_before_timestamp', 'python/pe/replay.py', "key=lambda f: (f.timestamp_s, f.tie_key, f.source_row_id, f.fill_id))\n    tk", "key=lambda f: (f.tie_key, f.timestamp_s, f.source_row_id, f.fill_id))\n    tk", 'test_keyed_order_is_timestamp_first_then_key_then_source_row (reviewer R2M04)', False),
 ('R1M20_partial_key_guard_any_to_all', 'python/pe/replay.py', "if any(f.tie_key is None for f in fills): raise EngineError(f'tie order", "if all(f.tie_key is None for f in fills): raise EngineError(f'tie order", 'test_partial_or_missing_keys_are_rejected... (reviewer R2M05)', False),
 ('R1M21_keyed_source_row_tiebreak_dropped', 'python/pe/replay.py', "key=lambda f: (f.timestamp_s, f.tie_key, f.source_row_id, f.fill_id))\n    tk", "key=lambda f: (f.timestamp_s, f.tie_key))\n    tk", 'test_keyed_order_is_timestamp_first_then_key_then_source_row (reviewer R2M06)', False),
 ('R1M22_raw_hash_guard_removed', 'python/pe/generators/historical.py', "    if provenance.sha256_file(raw) != man['sha256']: raise EngineError('raw trade file hash differs from the TP-01 manifest')\n    need", "    need", 'test_attach_tie_keys_refuses_a_raw_file_that_does_not_match_the_manifest (reviewer R2M07)', False),
 ('R1M23_extra_alias_onto_sensitivity_policy', 'python/pe/tie_policy.py', "ALIASES = {'src': 'source_row'}", "ALIASES = {'src': 'source_row', 'latest': 'trade_id'}", 'test_alias_table_is_exactly_the_legacy_token... (reviewer R2M14)', False),
 ('R1M24_primary_order_depends_on_input_order', 'python/pe/replay.py', "    return sorted(fills, key=lambda f: (f.timestamp_s, tk(f.side), f.source_row_id, f.fill_id))", "    return sorted(fills, key=lambda f: (f.timestamp_s, tk(f.side)))", 'test_primary_order_does_not_depend_on_input_order (reviewer R2M15)', False),
 ('R1M25_sensex_policy_disabled_for_all_but_the_exception', 'python/pe/tie_policy.py', "if (ns + 500_000_000) // 10**9 == epoch_s: return (ns,)", "if (ns + 500_000_000) // 10**9 == epoch_s: return (epoch_s * 10**9,)", 'test_sensex_policy_orders_by_the_embedded_nanosecond_time... (reviewer R2M18)', False),
 ('R1M26_keys_unlabelled', 'python/pe/tie_policy.py', "if n == 'trade_id': return (n,) + trade_id_key(trade_id)", "if n == 'trade_id': return trade_id_key(trade_id)", 'test_keys_are_labelled_and_a_foreign_policy_key_is_rejected (R1R-08)', False),
 ('R1M27_foreign_key_check_removed', 'python/pe/replay.py', "        if any(f.tie_key[0] != tie_order for f in fills): raise EngineError(f'Fill.tie_key was built for another policy than {tie_order}')\n", "", 'test_keys_are_labelled_and_a_foreign_policy_key_is_rejected (R1R-08)', False),
 ('R1M28_order_events_alias_not_normalised', 'python/pe/replay.py', "    if tie_order == 'source_row': tie_order = 'src'                          # alias of the primary convention\n", "", 'test_alias_table_is_exactly_the_legacy_token... (R1R-09)', False),
 ('R1M29_cli_cpp_guard_removed', 'python/pe/cli.py', "    if not pol.cpp_supported: raise SystemExit(", "    if False: raise SystemExit(", 'test_cli_refuses_python_only_policies_for_the_cpp_core (R1R-09)', False),
 ('R1M17_real_trade_id_sorted_by_sell_side', 'python/pe/tie_policy.py', "    if n == 'trade_id': return (n,) + trade_id_key(trade_id)", "    if n == 'trade_id': return (n, 0)", 'test_attach_tie_keys_reads_raw_rows / slow real-ledger pins', True),
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
