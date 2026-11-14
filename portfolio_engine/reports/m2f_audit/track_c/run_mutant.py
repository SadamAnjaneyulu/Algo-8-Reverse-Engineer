"""usage: python3 run_mutant.py M01 -> builds scratch mirror from mirror_base, patches wing_body.py, runs (a) the EXISTING test_wing_body.py inside the mirror, (b) own_check.py against the mirror. Writes scratch/mut_<id>.json"""
import sys, os, shutil, subprocess, json, re
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from mutants_def import M
SC = '/tmp/claude-0/-home-user-Algo-8-Reverse-Engineer/065db6a7-1cda-57f8-842a-8a8064e9a7d5/scratchpad/m2f_c/'
mid = sys.argv[1]; m = next(x for x in M if x['id'] == mid); d = SC + f'mirror_{mid}'
if os.path.exists(d): shutil.rmtree(d, ignore_errors=True)
shutil.copytree(SC + 'mirror_base', d, symlinks=True)
p = d + '/portfolio_engine/python/pe/wing_body.py'; src = open(p).read()
for old, new, cnt in m['reps']:
    assert src.count(old) == cnt, (mid, 'pattern count', src.count(old), old[:80])
    src = src.replace(old, new)
open(p, 'w').write(src)
r = subprocess.run(['python3', '-m', 'pytest', 'tests/test_wing_body.py', '-q', '-p', 'no:cacheprovider', '--no-header', '-rf'], cwd=d + '/portfolio_engine', capture_output=True, text=True, timeout=900)
txt = r.stdout[-6000:]; failed = sorted(set(re.findall(r'FAILED tests/test_wing_body.py::(\S+)', r.stdout))); last = txt.strip().splitlines()[-1] if txt.strip() else ''
err_only = ('ERROR' in r.stdout and not failed)
env = dict(os.environ, M2F_PYPATH=d + '/portfolio_engine/python'); oc = subprocess.run(['python3', HERE + '/own_check.py', SC + f'own_{mid}.json'], env=env, capture_output=True, text=True, timeout=900)
own = json.load(open(SC + f'own_{mid}.json')) if os.path.exists(SC + f'own_{mid}.json') else dict(verdict='NO_OUTPUT', reasons=[oc.stderr[-300:]])
res = dict(id=mid, change=m['change'], expected_detector=m['expected_detector'], existing_failed=failed, existing_summary=last, existing_collection_error=err_only, own_verdict=own['verdict'], own_reasons=own['reasons'])
json.dump(res, open(SC + f'mut_{mid}.json', 'w'), indent=1); print(mid, res['existing_summary'], '| own:', own['verdict'], own['reasons']); shutil.rmtree(d, ignore_errors=True)
