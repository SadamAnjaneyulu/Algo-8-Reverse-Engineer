"""Decisions C and D mutation harness: mutants of the closing-batch link rule, parameter provenance, stream boundary, tie-break and C2 predecessor, run against tests/test_decision_c.py and tests/test_decision_d.py in a SCRATCH mirror (the repo is never touched).
A mutant is KILLED only by a test assertion failure; errors are reported separately and are not kills.   python3 mutation_harness_DCD.py <scratch_dir> <out.json>"""
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
 ('DC01_inclusive_threshold_becomes_exclusive', text_edit('python/pe/closing_batches.py', '(gap <= g if inclusive else gap < g)', '(gap < g if inclusive else gap < g)'), 'boundary'),
 ('DC02_exclusive_reading_uses_less_or_equal', text_edit('python/pe/closing_batches.py', '(gap <= g if inclusive else gap < g)', '(gap <= g if inclusive else gap <= g)'), 'exclusive_sensitivity_boundary'),
 ('DC03_parameter_hash_ignores_the_link_rule', text_edit('python/pe/closing_batches.py', 'link=LINK_TEXT[inclusive], precision', 'link=LINK_TEXT[True], precision'), 'provenance'),
 ('DC04_exclusive_token_suffix_dropped', text_edit('python/pe/closing_batches.py', "+ ('' if inclusive else '__SENS_exclusive')", "+ ''"), 'provenance'),
 ('DC05_primary_link_text_changed_so_delivered_hashes_would_break', text_edit('python/pe/closing_batches.py', "True: 'gap<=threshold (inclusive), adjacent parents, single linkage'", "True: 'gap<=threshold (inclusive), adjacent parents, single linkage '"), 'provenance'),
 ('DC06_c2_predecessor_uses_the_previous_parents_first_fill', text_edit('python/pe/closing_batches.py', "ref_last = prev.last_ts if c2_ref == 'previous' else run_max", "ref_last = prev.first_ts if c2_ref == 'previous' else run_max"), 'c2_measures'),
 ('DC07_published_exclusive_count_changed', json_edit('reports/r1c_dual_scenario/m2c_exclusive_threshold/exclusive_sensitivity_summary.json', lambda o: o['rows'][2].__setitem__('exclusive_batches', 9999)), 'published_exclusive'),
 ('DD01_stream_boundary_drops_the_expiry', text_edit('python/pe/closing_batches.py', 'def stream(self): return (self.und, self.expiry, self.session)', "def stream(self): return (self.und, '', self.session)"), 'different_expiry'),
 ('DD02_stream_boundary_drops_the_session', text_edit('python/pe/closing_batches.py', 'def stream(self): return (self.und, self.expiry, self.session)', "def stream(self): return (self.und, self.expiry, '')"), 'different_session'),
 ('DD03_stream_boundary_drops_the_underlying', text_edit('python/pe/closing_batches.py', 'def stream(self): return (self.und, self.expiry, self.session)', "def stream(self): return ('', self.expiry, self.session)"), 'different_underlying'),
 ('DD04_tiebreak_uses_the_largest_closing_row', text_edit('python/pe/closing_batches.py', 'if p.first_src is None or r[11] < p.first_src: p.first_src = r[11]', 'if p.first_src is None or r[11] > p.first_src: p.first_src = r[11]'), 'CLOSING_source_row'),
 ('DD05_parent_last_second_ignored', text_edit('python/pe/closing_batches.py', 'if p.last_ts is None or r[6] > p.last_ts: p.last_ts = r[6]', 'if p.last_ts is None: p.last_ts = r[6]'), 'multiple_closing_fills'),
 ('DD06_expired_unclosed_inference_wording_removed_from_docs', text_edit('docs/BASKET_GROUPING_METHODOLOGY.md', 'inferred from the expiry date and missing closing fills', 'observed at expiry'), 'expired_unclosed'),
 ('DD07_parent_identity_note_changed_in_schema_doc_is_not_enough_raw_counts_pinned', text_edit('docs/SCHEMAS.md', 'giving 37,258 distinct values', 'giving 40,000 distinct values'), 'parent_identity'),
]


def run(P, k):
    p = subprocess.run([sys.executable, '-m', 'pytest', 'tests/test_decision_c.py', 'tests/test_decision_d.py', '-q', '-k', k, '-p', 'no:cacheprovider', '--tb=line', '-rf'], cwd=P, capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), timeout=900)
    t = p.stdout + p.stderr; failed = re.findall(r'^FAILED (\S+)', t, re.M); lines = re.findall(r'^(?:/|tests/|python/).*?:\d+: (?:AssertionError|Assert|assert).*$', t, re.M)[:2]; kind = 'failed' if failed else ('survived' if p.returncode == 0 else 'ERROR')
    if failed and not lines: kind = 'FAILED_WITHOUT_ASSERTION'          # a crash is not a kill
    return kind, failed, t.strip().splitlines()[-1] + ' | ' + ' || '.join(re.sub(r'^.*/(?=[^/]+:\d+:)', '', x)[:170] for x in lines)


res = []; o, f, last = run(prep('baseline'), ''); res.append(dict(id='BASELINE_unmutated', outcome=o, summary=last)); print('baseline', o, last, flush=True); assert o == 'survived'
for mid, fn, expect in M:
    P = prep(mid); fn(P); o, f, last = run(P, ''); res.append(dict(id=mid, expected_detector=expect, outcome=o, failed_tests=[x.split('::')[-1] for x in f][:4], summary=last)); print(mid, o, [x.split('::')[-1] for x in f][:2], flush=True)
    json.dump(res, open(OUT, 'w'), indent=1)
json.dump(res, open(OUT, 'w'), indent=1)
print('killed', sum(1 for r in res if r['outcome'] == 'failed' and r['id'] != 'BASELINE_unmutated'), 'of', len(M), '| survived', [r['id'] for r in res if r['outcome'] == 'survived' and r['id'] != 'BASELINE_unmutated'], '| errors', [r['id'] for r in res if r['outcome'] == 'ERROR'])
