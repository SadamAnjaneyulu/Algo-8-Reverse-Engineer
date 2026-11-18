"""Mutation runner: mutates COPIES of pe/closing_batches.py inside a scratch mirror; runs (1) existing tests/test_closing_batches.py (all 25, fast+slow),
(2) own independent detector (mut_detector.py).  Results -> mutation_results_raw.json"""
import os, sys, shutil, subprocess, json, re, concurrent.futures as cf
SC = '/tmp/claude-0/-home-user-Algo-8-Reverse-Engineer/065db6a7-1cda-57f8-842a-8a8064e9a7d5/scratchpad/m2f_b/'
TRACK = '/home/user/Algo-8-Reverse-Engineer/portfolio_engine/reports/m2f_audit/track_b/'
BASE = SC + 'mirror/'
SRC = open(BASE + 'portfolio_engine/python/pe/closing_batches.py').read()
SORT = "(lambda p: (p.first_ts, p.first_src, p.parent_id)) if order == 'src'"
GAP = "gap = p.first_ts - (prev.first_ts if method == 'C1' else ref_last)"
LINK = "link = (gap, p.first_ts <= ref_last, p.first_ts < ref_last) if gap <= g else None"
M = [
 ('M01', "threshold made exclusive: `gap <= g` -> `gap < g`", 'boundary tests (gap==g) ; own: synthetic gap_exactly_threshold + real partition', LINK, LINK.replace('gap <= g', 'gap < g')),
 ('M02', "chain-transitivity break: C1 compares to batch ANCHOR (first member) instead of adjacent previous", 'transitive-chain test; own: long_transitive_chain + real', GAP, "gap = p.first_ts - (cur['members'][0].first_ts if method == 'C1' else ref_last)"),
 ('M03', "tie-order reversal: sort key -first_src (C2-relevant)", 'C2 tie dependence tests; reference_partition inside check_view', SORT, "(lambda p: (p.first_ts, -p.first_src, p.parent_id)) if order == 'src'"),
 ('M04', "C2 collapses to C1: gap uses prev.first_ts for both methods", 'overlap test (C2 joins what C1 does not); own synthetic overlap cases (NOT detectable on real data since C2==C1 there)', GAP, "gap = p.first_ts - prev.first_ts"),
 ('M05', "last/first swap for C2: gap = last(next) - first(prev)", 'C2 overlap tests; own synthetic + real', GAP, "gap = (p.first_ts - prev.first_ts) if method == 'C1' else (p.last_ts - prev.first_ts)"),
 ('M06', "drop one parent per stream (ps = ps[1:])", 'check_view eligible-parent-once invariant; own: partition real', "; cur = None; n = 0; run_max = None", "; ps = ps[1:] if len(ps) > 1 else ps; cur = None; n = 0; run_max = None"),
 ('M07', "merge across sessions: session label constant", 'session-boundary tests (23:59:59 vs 00:00:01 IST)', "sess = day_iso(ist_day(r[6]))", "sess = '0'"),
 ('M08', "merge across expiries: stream expiry replaced by 'ALL'", 'expiry boundary test', "def stream(self): return (self.und, self.expiry, self.session)", "def stream(self): return (self.und, 'ALL', self.session)"),
 ('M09', "merge across underlyings: stream underlying replaced by 'ALL'", 'underlying boundary test', "def stream(self): return (self.und, self.expiry, self.session)", "def stream(self): return ('ALL', self.expiry, self.session)"),
 ('M10', "off-by-one second in gap (gap - 1)", 'inclusive-boundary tests', GAP, GAP + " - 1"),
 ('M11', "ignore MIXED parents (skip their closing portions)", 'check_view portions-exactly-once; mixed-parent tests', "if pid is None or pid == '' or pid == 'NA': unattr.append(cp_id); continue", "if pid is None or pid == '' or pid == 'NA': unattr.append(cp_id); continue\n        if ls.roles.get(pid) == 'MIXED': continue"),
 ('M12', "duplicate a closing portion (every source row % 97 == 0)", 'check_view duplicate-portion invariant', "p.cps.append(r); p.qty += r[8]; streams[pid].add(k[1:])", "p.cps.append(r); p.qty += r[8]; streams[pid].add(k[1:])\n        if r[11] % 97 == 0: p.cps.append(r)"),
 ('M13', "wrong closing-quantity attribution at parent level: qty += min(r[8], 65)", 'check_view summary-vs-portions invariant', "p.cps.append(r); p.qty += r[8];", "p.cps.append(r); p.qty += min(r[8], 65);"),
 ('M14', "wrong closing-quantity attribution in batch record: total_closing_qty counts BUY-side portions only", 'batch_record tests', "total_closing_qty=sum(r[8] for r in cps)", "total_closing_qty=sum(r[8] for r in cps if r[7] == 1)"),
 ('M15', "interval_overlap flag `<=` -> `<`", 'overlap-flag tests (same-second touching)', LINK, LINK.replace('p.first_ts <= ref_last, p.first_ts < ref_last', 'p.first_ts < ref_last, p.first_ts < ref_last')),
 ('M16', "strict_overlap flag `<` -> `<=`", 'strict overlap tests', LINK, LINK.replace('p.first_ts <= ref_last, p.first_ts < ref_last', 'p.first_ts <= ref_last, p.first_ts <= ref_last')),
 ('M17', "parent last_ts never advances (last := first)", 'multi-fill parent test; C2 overlap tests', "if p.last_ts is None or r[6] > p.last_ts: p.last_ts = r[6]", "if p.last_ts is None: p.last_ts = r[6]"),
 ('M18', "C2 default reference = running max of last fills (approved rule is previous parent)", 'C2 rule sensitivity real test', "def build_view(parents, method, g, order='src', c2_ref='previous'):", "def build_view(parents, method, g, order='src', c2_ref='running_max'):"),
 ('M19', "session by UTC date instead of IST date", 'IST-midnight test', "sess = day_iso(ist_day(r[6]))", "sess = day_iso(r[6] // 86400)"),
 ('M20', "parent first_ts = LATEST closing fill (first_ts uses `>`)", 'multi-fill parent test', "if p.first_ts is None or r[6] < p.first_ts: p.first_ts = r[6]", "if p.first_ts is None or r[6] > p.first_ts: p.first_ts = r[6]"),
 ('M21', "tie-break by parent_id only (drop first_src) in build_view", 'tie-order tests', SORT, "(lambda p: (p.first_ts, p.parent_id)) if order == 'src'"),
 ('M22', "summarize: pairs_linked uses `<` instead of `<=`", 'real summary regression (report numbers)', "pairs_linked=sum(1 for x in gaps if x <= g)", "pairs_linked=sum(1 for x in gaps if x < g)"),
 ('M23', "stability: nested forced True", 'stability test', "nested=all(any(x <= y for y in sb) for x in sa))", "nested=True)"),
 ('M24', "batch record duration off by one (end - start + 1)", 'duration tests', "duration_s=end - start,", "duration_s=end - start + 1,"),
 ('M25', "members file join gap sign dropped (abs)", 'member-row tests', "'' if lk is None else lk[0], '' if lk is None else int(lk[1])", "'' if lk is None else abs(lk[0]), '' if lk is None else int(lk[1])"),
 ('M26', "batch numbering skips (n += 2)", 'id tests', "n += 1; cur = dict(batch_id", "n += 2; cur = dict(batch_id"),
 ('M27', "C2 overlap negative gap not linked: gap clipped (abs(gap) for C2 link test)", 'overlap tests', "link = (gap, p.first_ts <= ref_last, p.first_ts < ref_last) if gap <= g else None", "link = (gap, p.first_ts <= ref_last, p.first_ts < ref_last) if abs(gap) <= g else None"),
 ('M28', "closing portions without parent id pooled (unattributable check removed)", 'missing parent id tests', "if pid is None or pid == '' or pid == 'NA': unattr.append(cp_id); continue", "if pid is None: unattr.append(cp_id); continue"),
]
def one(mut):
    mid, desc, exp, old, new = mut
    d = SC + f'mut/{mid}/'; shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    shutil.copytree(BASE + 'portfolio_engine/python', d + 'portfolio_engine/python', ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree(BASE + 'portfolio_engine/tests', d + 'portfolio_engine/tests', ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree(BASE + 'portfolio_engine/tools', d + 'portfolio_engine/tools', ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copy(BASE + 'portfolio_engine/pytest.ini', d + 'portfolio_engine/')
    for n in ('tp_reconstruction', 'Trades_GKOHNP140.csv'): os.symlink(os.path.realpath(BASE + n), d + n)
    for n in ('reports', 'fixtures', 'data_generated', 'docs'): os.symlink(os.path.realpath(BASE + 'portfolio_engine/' + n), d + 'portfolio_engine/' + n)
    p = d + 'portfolio_engine/python/pe/closing_batches.py'
    assert SRC.count(old) == 1 or (mid in ('M08', 'M09', 'M07', 'M19') and SRC.count(old) == 1), (mid, SRC.count(old))
    open(p, 'w').write(SRC.replace(old, new))
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    t = subprocess.run(['python3', '-m', 'pytest', 'tests/test_closing_batches.py', '-q', '-p', 'no:cacheprovider', '--tb=line', '-x' if False else '-q'], cwd=d + 'portfolio_engine', capture_output=True, text=True, env=env)
    txt = t.stdout[-3000:]
    failed = re.findall(r'^FAILED (\S+)', t.stdout, re.M); summ = txt.strip().splitlines()[-1] if txt.strip() else ''
    errl = [l for l in t.stdout.splitlines() if re.search(r'(Error|assert)', l)][:4]
    env2 = dict(env, PE_PY=d + 'portfolio_engine/python', MIRROR_ROOT=d)
    r = subprocess.run(['python3', TRACK + 'mut_detector.py'], cwd=SC, capture_output=True, text=True, env=env2)
    line = [l for l in r.stdout.splitlines() if l.startswith('RESULT ')]
    det = json.loads(line[0][7:]) if line else dict(crash=(r.stderr or r.stdout)[-500:])
    return dict(id=mid, change=desc, expected_detector=exp, pytest_summary=summ, pytest_failed=failed, pytest_error_lines=errl, detector=det)
if __name__ == '__main__':
    ids = sys.argv[1:]; todo = [m for m in M if not ids or m[0] in ids]
    with cf.ThreadPoolExecutor(4) as ex: res = list(ex.map(one, todo))
    json.dump(res, open(TRACK + 'mutation_results_raw.json', 'w'), indent=1)
    for r in res: print(r['id'], r['pytest_summary'], len(r['pytest_failed']), '| A', r['detector'].get('A'), 'B', r['detector'].get('B'), 'REPRO', len(r['detector'].get('REPRO', [])), r['detector'].get('errors') or r['detector'].get('crash'))
