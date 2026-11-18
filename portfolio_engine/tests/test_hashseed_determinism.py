"""M2-F E-D01: coverage.json key order depended on PYTHONHASHSEED (forensics.cycle_coverage built parent_roles from a Counter over a SET of parent ids).
The fix is an ordered construction (`forensics.parent_role_counts`, fixed order pe.parents.ROLES = OPENING_ONLY, CLOSING_ONLY, MIXED), which is also exactly the order of the DELIVERED coverage.json,
so no delivered byte changes and the delivered file stays byte-reproducible after (and without) canonical key sorting.
* fast test: the producing function in two subprocesses (PYTHONHASHSEED=1 and 2) on a hand-made parent set; byte equality of the serialised dict, hand-calculated counts.
* slow test: the whole cycle_coverage of the SENSEX cycle in two subprocesses (seeds 1 and 2), serialised exactly as tools/m2e_build.py does (json.dumps indent=1, default=str): byte equal across seeds, and equal to the delivered
  coverage.json for every key the function produces (canonical sorted comparison), with parent_roles in the delivered key order."""
import json, os, subprocess, sys
import pytest
from conftest import PE, REPO

SNIPPET_FAST = '''
import sys, json
sys.path.insert(0, {py!r})
from pe import forensics as F
roles = {{f'P{{i}}': r for i, r in enumerate(['MIXED', 'CLOSING_ONLY', 'OPENING_ONLY', 'MIXED', 'CLOSING_ONLY', 'OPENING_ONLY', 'OPENING_ONLY'])}}
parents = set(roles)
sys.stdout.write(json.dumps(F.parent_role_counts(roles, parents), indent=1))
'''
SNIPPET_FULL = '''
import sys, os, json
REPO = {repo!r}; sys.path.insert(0, os.path.join(REPO, 'portfolio_engine', 'python'))
from pe import forensics as F
und, exp = F.CYCLES[1]; c = F.Cycle(REPO, und, exp)
sc = F.m2c_slice(REPO, c); sd = F.m2d_slice(REPO, c); files_c, R, rm = F.recompute_m2c_m2d(c)
sys.stdout.write(json.dumps(F.cycle_coverage(c, sc, sd, R, rm), indent=1, default=str))
'''


def _run(code, seed):
    env = dict(os.environ, PYTHONHASHSEED=str(seed))
    p = subprocess.run([sys.executable, '-c', code], capture_output=True, env=env, cwd=REPO); assert p.returncode == 0, p.stderr.decode()[-800:]
    return p.stdout


def test_parent_role_counts_bytes_do_not_depend_on_the_hash_seed():
    code = SNIPPET_FAST.format(py=os.path.join(PE, 'python')); a = _run(code, 1); b = _run(code, 2)
    assert a == b, (a, b)
    # hand count of the 7 parents above: MIXED 2 (P0, P3), CLOSING_ONLY 2 (P1, P4), OPENING_ONLY 3 (P2, P5, P6); keys in the canonical order. (With the unordered `dict(Counter(...))` of the defective code these 7 parents
    # give a different key order under PYTHONHASHSEED=1 and 2 on CPython 3.13; the mutant proof in the E-D01 report shows the first assertion catching it.)
    assert json.loads(a, object_pairs_hook=lambda kv: kv) == [('OPENING_ONLY', 3), ('CLOSING_ONLY', 2), ('MIXED', 2)]


def test_parent_role_counts_omits_absent_roles_and_rejects_unknown_roles():
    from pe import forensics as F
    assert list(F.parent_role_counts({'a': 'MIXED', 'b': 'MIXED'}, {'a', 'b'}).items()) == [('MIXED', 2)]
    assert F.parent_role_counts({}, set()) == {}
    with pytest.raises(AssertionError, match='unknown parent role'): F.parent_role_counts({'a': 'BOTH'}, {'a'})


@pytest.mark.slow
def test_cycle_coverage_bytes_equal_across_hash_seeds_and_reproduce_the_delivered_coverage_json():
    code = SNIPPET_FULL.format(repo=REPO); a = _run(code, 1); b = _run(code, 2)
    assert a == b, 'cycle_coverage serialisation depends on PYTHONHASHSEED'
    gen = json.loads(a); delivered = json.load(open(os.path.join(PE, 'reports', 'm2e_data', 'SENSEX_2026-07-16', 'coverage.json')))
    canon = lambda x: json.dumps(x, sort_keys=True)
    assert canon(gen) == canon({k: delivered[k] for k in gen}), 'generated content differs from the delivered coverage.json'
    assert list(gen['fills']['parent_roles']) == list(delivered['fills']['parent_roles']) == ['OPENING_ONLY', 'CLOSING_ONLY', 'MIXED']     # delivered byte order is reproduced, no delivered byte changes
