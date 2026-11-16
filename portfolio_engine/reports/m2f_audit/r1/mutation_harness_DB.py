"""Decision B mutation harness: mutants of the two reversal measures and of the reporting wording, run against tests/test_reversals.py and tests/test_decision_b.py in a SCRATCH mirror (the repo is never touched).
A mutant is KILLED only by a test assertion failure; errors are reported separately and are not kills.   python3 mutation_harness_DB.py <scratch_dir> <out.json>"""
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
 ('DB01_per_fill_counts_reaching_zero', text_edit('python/pe/reversals.py', 'if sgn(before) * sgn(after) < 0: per_fill.append', 'if sgn(before) * sgn(after) <= 0 and before != 0: per_fill.append'), 'exact_zero'),
 ('DB02_parent_level_groups_ignore_the_second', text_edit('python/pe/reversals.py', 'g = groups.setdefault((inst, parent, ts),', 'g = groups.setdefault((inst, parent, 0),'), 'different_seconds'),
 ('DB03_parent_level_uses_only_the_parents_own_fills', text_edit('python/pe/reversals.py', "        g['inventory_after'] = after; g['fills'].append(row)", "        g['own'] = g.get('own', 0) + q; g['inventory_after'] = g['inventory_before'] + g['own']; g['fills'].append(row)"), 'interleaved'),
 ('DB04_parent_level_only_where_a_per_fill_event_exists', text_edit('python/pe/reversals.py', "parent_level = [dict(g, n_fills=len(g['fills'])) for g in groups.values() if sgn(g['inventory_before']) * sgn(g['inventory_after']) < 0]", "parent_level = [dict(g, n_fills=len(g['fills'])) for g in groups.values() if sgn(g['inventory_before']) * sgn(g['inventory_after']) < 0 and any(p['parent_order_id'] == g['parent_order_id'] and p['timestamp_s'] == g['timestamp_s'] for p in per_fill)]"), 'not_a_subset'),
 ('DB05_counts_merged_into_one_number', text_edit('python/pe/reversals.py', 'counts={PER_FILL: len(per_fill), PARENT_LEVEL: len(parent_level)}', 'counts={PER_FILL: len(per_fill) + len(parent_level), PARENT_LEVEL: len(parent_level)}'), 'directive_example'),
 ('DB06_sign_treats_zero_as_positive', text_edit('python/pe/reversals.py', 'sgn = lambda x: (x > 0) - (x < 0)', 'sgn = lambda x: 1 if x >= 0 else -1'), 'exact_zero'),
 ('DB07_parent_level_uses_the_last_fills_before_inventory', text_edit('python/pe/reversals.py', "g = groups.setdefault((inst, parent, ts), dict(instrument_id=inst, parent_order_id=parent, timestamp_s=ts, inventory_before=before, inventory_after=after, fills=[]))\n        g['inventory_after'] = after;", "g = groups.setdefault((inst, parent, ts), dict(instrument_id=inst, parent_order_id=parent, timestamp_s=ts, inventory_before=before, inventory_after=after, fills=[]))\n        g['inventory_before'] = before; g['inventory_after'] = after;"), 'directive_example'),
 ('DB08_approved_sentence_altered', text_edit('python/pe/reversals.py', "under the approved diagnostic definition.'", "under the approved definition.'"), 'sentence_is_exact'),
 ('DB09_report_json_count_changed', json_edit('reports/r1c_dual_scenario/reversal_measures.json', lambda o: o['results']['SENSEX_2026-07-16']['baseline']['counts'].__setitem__('PARENT_LEVEL_SAME_SECOND_NET_SIGN_FLIP', 0)), 'published'),
 ('DB10_old_unqualified_claim_reintroduced', text_edit('reports/M2E_POSITION_CASE_STUDIES.md', '**Reversal measures (computed; never merged):**', 'SENSEX has no reversal. **Reversal measures (computed; never merged):**'), 'old_unqualified'),
]


def run(P, k):
    p = subprocess.run([sys.executable, '-m', 'pytest', 'tests/test_reversals.py', 'tests/test_decision_b.py', '-q', '-k', k, '-p', 'no:cacheprovider', '--tb=line', '-rf'], cwd=P, capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), timeout=900)
    t = p.stdout + p.stderr; failed = re.findall(r'^FAILED (\S+)', t, re.M); lines = re.findall(r'^(?:/|tests/|python/).*?:\d+: (?:AssertionError|Assert|assert).*$', t, re.M)[:2]; kind = 'failed' if failed else ('survived' if p.returncode == 0 else 'ERROR')
    if failed and not lines: kind = 'FAILED_WITHOUT_ASSERTION'          # a crash is not a kill
    return kind, failed, t.strip().splitlines()[-1] + ' | ' + ' || '.join(re.sub(r'^.*/(?=[^/]+:\d+:)', '', x)[:170] for x in lines)


res = []; o, f, last = run(prep('baseline'), 'not independently'); res.append(dict(id='BASELINE_unmutated', outcome=o, summary=last)); print('baseline', o, last, flush=True); assert o == 'survived'
for mid, fn, expect in M:
    P = prep(mid); fn(P); o, f, last = run(P, 'not independently'); res.append(dict(id=mid, expected_detector=expect, outcome=o, failed_tests=[x.split('::')[-1] for x in f][:4], summary=last)); print(mid, o, [x.split('::')[-1] for x in f][:2], flush=True)
    json.dump(res, open(OUT, 'w'), indent=1)
json.dump(res, open(OUT, 'w'), indent=1)
print('killed', sum(1 for r in res if r['outcome'] == 'failed' and r['id'] != 'BASELINE_unmutated'), 'of', len(M), '| survived', [r['id'] for r in res if r['outcome'] == 'survived' and r['id'] != 'BASELINE_unmutated'], '| errors', [r['id'] for r in res if r['outcome'] == 'ERROR'])
