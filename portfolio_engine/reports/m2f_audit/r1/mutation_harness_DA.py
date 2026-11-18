"""Decision A mutation harness: mutants of the case-selection algorithm, wording and case data, run against tests/test_decision_a.py in a SCRATCH mirror (the repo is never touched).
A mutant is KILLED only by a test assertion failure; errors are reported separately and are not kills.   python3 mutation_harness_DA.py <scratch_dir> <out.json>"""
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
 ('DA01_selection_takes_the_highest_first_fill_price', text_edit('python/pe/cases.py', '        fresh = [c for c in cands if c[0] not in used]; chosen = (fresh or cands)[0];', "        fresh = [c for c in cands if c[0] not in used]; chosen = max((fresh or cands), key=lambda c: int(D['fills'][next(e['fill_id'] for e in D['events'] if e['episode_id'] == c[0])]['exec_price_paise']));"), 'scrambling'),
 ('DA02_selection_prefers_profitable_episodes_outcome', text_edit('python/pe/cases.py', '        fresh = [c for c in cands if c[0] not in used];', "        cands = ([c for c in cands if -sum(int(D['fills'][e['fill_id']]['side']) * int(D['fills'][e['fill_id']]['quantity']) * int(D['fills'][e['fill_id']]['exec_price_paise']) for e in D['events'] if e['episode_id'] == c[0]) > 0] or cands)\n        fresh = [c for c in cands if c[0] not in used];"), 'scrambling'),
 ('DA03_unsupported_wording_reintroduced_in_generator', text_edit('tools/m2e_cases.py', 'structural, price-free, outcome-free (tested); chronological first', 'predefined, outcome-free; chronological first'), 'not scrambling'),
 ('DA04_approved_statement_altered', text_edit('python/pe/cases.py', 'does not establish that the individual case rules were prospectively fixed before inspection.', 'establishes that the individual case rules were fixed before inspection.'), 'not scrambling'),
 ('DA05_case_record_changed_in_delivered_json', json_edit('reports/m2e_data/NIFTY_2026-06-30/case_studies.json', lambda o: o['selection']['CT1_INCREMENTAL_OPENING'].__setitem__('episode_id', 'X')), 'not scrambling'),
 ('DA06_unapproved_line_changed_in_case_markdown', text_edit('reports/M2E_POSITION_CASE_STUDIES.md', '**Purpose:** make single positions inspectable.', '**Purpose:** make single positions comparable.'), 'not scrambling'),
 ('DA07_dataset_changed_after_wording_fix', append_bytes('reports/m2e_data/SENSEX_2026-07-16/episodes.tsv'), 'not scrambling'),
 ('DA08_concentration_disclosure_dropped', text_edit('python/pe/cases.py', "'### 1.1 Sample concentration (computed from the selected case records)'", "'### 1.1 Notes (computed from the selected case records)'"), 'not scrambling'),
]


def run(P, k):
    p = subprocess.run([sys.executable, '-m', 'pytest', 'tests/test_decision_a.py', '-q', '-k', k, '-p', 'no:cacheprovider', '--tb=line', '-rf'], cwd=P, capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), timeout=900)
    t = p.stdout + p.stderr; failed = re.findall(r'^FAILED (\S+)', t, re.M); lines = re.findall(r'^(?:/|tests/|python/).*?:\d+: (?:AssertionError|Assert|assert).*$', t, re.M)[:2]; kind = 'failed' if failed else ('survived' if p.returncode == 0 else 'ERROR')
    if failed and not lines: kind = 'FAILED_WITHOUT_ASSERTION'          # a crash is not a kill
    return kind, failed, t.strip().splitlines()[-1] + ' | ' + ' || '.join(re.sub(r'^.*/(?=[^/]+:\d+:)', '', x)[:170] for x in lines)


res = []; o, f, last = run(prep('baseline'), 'not scrambling'); res.append(dict(id='BASELINE_unmutated', outcome=o, summary=last)); print('baseline', o, last, flush=True); assert o == 'survived'
for mid, fn, expect in M:
    P = prep(mid); fn(P); o, f, last = run(P, expect); res.append(dict(id=mid, expected_detector=expect, outcome=o, failed_tests=[x.split('::')[-1] for x in f][:4], summary=last)); print(mid, o, [x.split('::')[-1] for x in f][:2], flush=True)
    json.dump(res, open(OUT, 'w'), indent=1)
json.dump(res, open(OUT, 'w'), indent=1)
print('killed', sum(1 for r in res if r['outcome'] == 'failed' and r['id'] != 'BASELINE_unmutated'), 'of', len(M), '| survived', [r['id'] for r in res if r['outcome'] == 'survived' and r['id'] != 'BASELINE_unmutated'], '| errors', [r['id'] for r in res if r['outcome'] == 'ERROR'])
