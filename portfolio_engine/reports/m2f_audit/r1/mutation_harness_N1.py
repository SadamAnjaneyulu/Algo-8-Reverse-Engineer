"""N1 mutation harness: mutants of the LOCAL (instrument, second) keyed ordering and of the per-instrument key semantics, run against the N1 tests of tests/test_tie_order_policy.py in a SCRATCH mirror (the repo is never touched).
A mutant is KILLED only by a test assertion failure; errors are reported separately and are not kills.   python3 mutation_harness_N1.py <scratch_dir> <out.json>"""
import json, os, re, shutil, subprocess, sys
REPO = '/home/user/Algo-8-Reverse-Engineer'; PE = REPO + '/portfolio_engine'; SCR = sys.argv[1]; OUT = sys.argv[2]


def prep(name):
    """scratch mirror = every tracked + new non-ignored file of portfolio_engine (working-tree versions), tp_reconstruction and the raw csv symlinked"""
    d = os.path.join(SCR, name); shutil.rmtree(d, ignore_errors=True); P = d + '/portfolio_engine'; os.makedirs(P)
    files = subprocess.run(['git', 'ls-files', '-co', '--exclude-standard', 'portfolio_engine'], cwd=REPO, capture_output=True, text=True).stdout.split('\n')
    for f in files:
        if not f or '__pycache__' in f or not os.path.isfile(REPO + '/' + f): continue
        os.makedirs(os.path.dirname(d + '/' + f), exist_ok=True); shutil.copy(REPO + '/' + f, d + '/' + f)
    os.symlink(REPO + '/tp_reconstruction', d + '/tp_reconstruction'); os.symlink(REPO + '/Trades_GKOHNP140.csv', d + '/Trades_GKOHNP140.csv'); return P


def text_edit(rel, old, new):
    def f(P):
        s = open(P + '/' + rel).read(); assert old in s, (rel, old[:40]); open(P + '/' + rel, 'w').write(s.replace(old, new, 1))
    return f


def json_edit(rel, fn):
    def f(P):
        o = json.load(open(P + '/' + rel)); fn(o); open(P + '/' + rel, 'w').write(json.dumps(o, indent=1) if 'manifest' in rel else json.dumps(o, indent=1, sort_keys=True))
    return f


def append_bytes(rel):
    def f(P): open(P + '/' + rel, 'ab').write(b'\x00')
    return f


M = [
 ('N1M01_global_keyed_sort_across_instruments', text_edit('python/pe/replay.py', '        return _local_keyed_order(fills)\n', '        return sorted(fills, key=lambda f: (f.timestamp_s, f.tie_key, f.source_row_id, f.fill_id))\n'), 'test_keyed_order_never_compares_keys_across_instruments_hand_calculated'),
 ('N1M02_source_row_tiebreak_reversed', text_edit('python/pe/replay.py', 'key=lambda f: (f.tie_key, f.source_row_id, f.fill_id))):', 'key=lambda f: (f.tie_key, -f.source_row_id, f.fill_id))):'), 'test_keyed_order_is_bounded_by_the_second_and_ties_fall_back_to_ascending_source_row'),
 ('N1M03_policy_name_dropped_from_key', text_edit('python/pe/tie_policy.py', 'return (n,) + per_contract_id_sequence_key(underlying, trade_id, epoch_s)', 'return per_contract_id_sequence_key(underlying, trade_id, epoch_s)'), 'test_hybrid_key_hand_calculated_cases_and_label'),
 ('N1M04_sensex_keyed_by_its_numeric_suffix_like_a_nifty_counter', text_edit('python/pe/tie_policy.py', "    if underlying == 'SENSEX': return sensex_time_key(underlying, trade_id, epoch_s)\n    if '-' in trade_id", "    if underlying == 'SENSEX': return (int(trade_id.split('-')[-1]),)\n    if '-' in trade_id"), 'test_hybrid_keys_built_by_the_policy_function_keep_nifty_and_sensex_separate'),
 ('N1M05_sensex_time_rule_applied_to_nifty', text_edit('python/pe/tie_policy.py', '    return (int(trade_id),)\n', "    return sensex_time_key('SENSEX', trade_id, epoch_s)\n"), 'test_hybrid_keys_built_by_the_policy_function_keep_nifty_and_sensex_separate'),
 ('N1M06_second_bucket_boundary_widened_to_two_seconds', text_edit('python/pe/replay.py', 'slots.setdefault((f.timestamp_s, f.instrument_id), []).append(i)', 'slots.setdefault((f.timestamp_s // 2, f.instrument_id), []).append(i)'), 'test_keyed_order_is_bounded_by_the_second_and_ties_fall_back_to_ascending_source_row'),
 ('N1M07_bucket_ignores_the_second', text_edit('python/pe/replay.py', 'slots.setdefault((f.timestamp_s, f.instrument_id), []).append(i)', 'slots.setdefault((f.instrument_id,), []).append(i)'), 'test_keyed_order_is_bounded_by_the_second_and_ties_fall_back_to_ascending_source_row'),
 ('N1M08_bucket_ignores_the_instrument', text_edit('python/pe/replay.py', 'slots.setdefault((f.timestamp_s, f.instrument_id), []).append(i)', 'slots.setdefault((f.timestamp_s,), []).append(i)'), 'test_keyed_order_never_compares_keys_across_instruments_hand_calculated'),
 ('N1M09_trade_id_policy_left_global', text_edit('python/pe/replay.py', '        return _local_keyed_order(fills)\n', "        return _local_keyed_order(fills) if tie_order == 'per_contract_id_sequence' else sorted(fills, key=lambda f: (f.timestamp_s, f.tie_key, f.source_row_id, f.fill_id))\n"), 'test_other_keyed_policies_are_also_local'),
]


def run(P):
    p = subprocess.run([sys.executable, '-m', 'pytest', 'tests/test_tie_order_policy.py', '-q', '-k', 'keyed_order or hybrid_key or hybrid_keys or other_keyed', '-p', 'no:cacheprovider', '--tb=line', '-rf'], cwd=P, capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), timeout=900)
    t = p.stdout + p.stderr; failed = re.findall(r'^FAILED (\S+)', t, re.M); return ('failed' if failed else ('survived' if p.returncode == 0 else 'ERROR')), failed, t.strip().splitlines()[-1]


res = []; o, f, last = run(prep('baseline')); res.append(dict(id='BASELINE_unmutated', outcome=o, summary=last)); print('baseline', o, last, flush=True); assert o == 'survived'
for mid, fn, expect in M:
    P = prep(mid); fn(P); o, f, last = run(P); res.append(dict(id=mid, expected_detector=expect, outcome=o, failed_tests=[x.split('::')[-1] for x in f][:4], summary=last)); print(mid, o, [x.split('::')[-1] for x in f][:2], flush=True)
    json.dump(res, open(OUT, 'w'), indent=1)
json.dump(res, open(OUT, 'w'), indent=1)
print('killed', sum(1 for r in res if r['outcome'] == 'failed' and r['id'] != 'BASELINE_unmutated'), 'of', len(M), '| survived', [r['id'] for r in res if r['outcome'] == 'survived' and r['id'] != 'BASELINE_unmutated'], '| errors', [r['id'] for r in res if r['outcome'] == 'ERROR'])
