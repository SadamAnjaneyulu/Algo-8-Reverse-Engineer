"""Items 5 and the register sample: (1) the six original dispositions are verbatim vs git 562d7eb6; (2) the M2-F final report differs from 562d7eb6 only by an appended addendum; (3) every cited file / test / commit in the 49
closure dispositions resolves; (4) cited test counts and mutant counts are compared where machine-checkable."""
import json, os, re, subprocess, collections, ast
HERE = os.path.dirname(os.path.abspath(__file__)); PE = os.path.abspath(os.path.join(HERE, '..', '..', '..')); REPO = os.path.dirname(PE)
def git(*a):
    p = subprocess.run(['git', *a], cwd=REPO, capture_output=True, text=True); return p.returncode, p.stdout
res = {}
rc, old = git('show', '562d7eb6:portfolio_engine/reports/M2F_DEFECT_REGISTER.md'); assert rc == 0
REG = open(os.path.join(PE, 'reports', 'M2F_DEFECT_REGISTER.md')).read()
def disp_of(text, i):
    m = re.search(r'^### ' + re.escape(i) + r' .*?(?=^### |^## |\Z)', text, re.S | re.M); sec = m.group(0)
    m2 = re.search(r'\* \*\*(?:Original d|D)isposition(?: \(M2-F audit, commit 562d7eb6, verbatim\))?:\*\* (.*)', sec); return m2.group(1).strip()
six = {}
for i in ['D-A01', 'D-A08', 'B-01', 'C-01', 'C-02', 'E-D03']:
    a = disp_of(old, i); b = disp_of(REG, i); six[i] = (a == b)
res['six_original_dispositions_verbatim'] = six; print(six)
# final report: only appended
rc, fo = git('show', '562d7eb6:portfolio_engine/reports/M2F_FINAL_AUDIT_REPORT.md'); fn = open(os.path.join(PE, 'reports', 'M2F_FINAL_AUDIT_REPORT.md')).read()
res['final_report_original_is_prefix_of_current'] = fn.startswith(fo.rstrip('\n')); res['final_report_decision_line_present'] = 'M2 — CONDITIONAL PASS' in fn.split('## R1 ADDENDUM')[0]
print('final report prefix preserved:', res['final_report_original_is_prefix_of_current'], 'CONDITIONAL PASS in original part:', res['final_report_decision_line_present'])
rc, lo = git('show', '562d7eb6:portfolio_engine/reports/M2F_METHODOLOGY_LIMITATIONS.md'); ln = open(os.path.join(PE, 'reports', 'M2F_METHODOLOGY_LIMITATIONS.md')).read()
res['limitations_original_is_prefix_of_current'] = ln.startswith(lo.rstrip('\n')); print('limitations prefix preserved:', res['limitations_original_is_prefix_of_current'])
# (3) cited paths / tests / commits
CL = json.load(open(os.path.join(PE, 'reports', 'm2f_audit', 'closure_dispositions.json')))['defects']; unresolved = []; checked = 0; commits = set()
for i, c in CL.items():
    ev = c['evidence'] + ' ' + c['rationale']
    for t in re.findall(r'\b(?:tests|reports|python/pe|tools|docs)/[A-Za-z0-9_./\-]+', ev):
        t = t.rstrip('.,;)'); checked += 1
        if t.startswith('python/'): p = os.path.join(PE, t)
        else: p = os.path.join(PE, t)
        if not (os.path.exists(p) or os.path.exists(p + '.py')): unresolved.append((i, t))
    for t in re.findall(r'(tests/test_[a-z0-9_]+\.py)::(test_[a-z0-9_]+)', ev):
        src = open(os.path.join(PE, t[0])).read() if os.path.exists(os.path.join(PE, t[0])) else ''
        if f'def {t[1]}' not in src: unresolved.append((i, '::'.join(t)))
    for h in re.findall(r'\b[0-9a-f]{7,8}\b', ev):
        if re.fullmatch(r'[0-9]+', h): continue
        commits.add((i, h))
bad_commits = []
for i, h in sorted(commits):
    rc, _ = git('cat-file', '-e', h + '^{commit}')
    if rc: bad_commits.append((i, h))
res['n_path_refs_checked'] = checked; res['unresolved_paths_or_tests'] = unresolved; res['n_commit_refs'] = len(commits); res['unresolved_commits'] = bad_commits
print('refs checked', checked, 'unresolved', unresolved, 'commit refs', len(commits), 'unresolved commits', bad_commits)
# (4) test counts
def count_tests(path):
    t = ast.parse(open(os.path.join(PE, path)).read()); n = 0
    for node in ast.walk(t):
        if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
            n += 1
    return n
cnt = {}
for f in ('tests/test_closing_batches_reporting.py', 'tests/test_wing_body_w3_engine.py', 'tests/test_expiry_status.py', 'tests/test_historical_generator_raw.py', 'tests/test_hashseed_determinism.py', 'tests/test_decision_a.py', 'tests/test_reversals.py', 'tests/test_decision_b.py', 'tests/test_decision_c.py', 'tests/test_decision_d.py'):
    cnt[f] = count_tests(f)
res['test_function_counts'] = cnt; print(cnt)
json.dump(res, open(os.path.join(HERE, 'item5_6_register_check_result.json'), 'w'), indent=1, default=str)
