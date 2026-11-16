"""Task E: reviewer's NEW mutants (R2M01..), run in a scratch mirror. A mutant is KILLED only if a test ASSERTION fails; crashes / collection errors are classified separately.
usage: python3 e_mutants.py <scratch_dir> <out.json> [--only ID,ID] """
import json, os, re, shutil, subprocess, sys, time
REPO = '/home/user/Algo-8-Reverse-Engineer'; PE = REPO + '/portfolio_engine'
SCR = sys.argv[1]; OUT = sys.argv[2]; ONLY = None
for a in sys.argv[3:]:
    if a.startswith('--only='): ONLY = set(a[7:].split(','))
FILES = ['python', 'tests', 'tools', 'fixtures']
T = 'tests/test_tie_order_policy.py tests/test_tie_order_metadata.py'
# (id, file, old, new, run_slow_if_survives_fast, description of what it breaks, copy-extra-reports)
M = [
 ('R2M01_attach_passes_wrong_epoch_to_sensex_key', 'python/pe/generators/historical.py', "tp.tie_key(pol.name, und, tid, ono, f.timestamp_s)", "tp.tie_key(pol.name, und, tid, ono, f.timestamp_s + 1)", True, 'sensex key silently falls back to epoch*1e9 for every fill (policy disabled)'),
 ('R2M02_sensex_round_half_down', 'python/pe/tie_policy.py', "(ns + 500_000_000) // 10**9 == epoch_s", "(ns + 499_999_999) // 10**9 == epoch_s", False, 'rounding boundary off by 1 ns'),
 ('R2M03_sensex_tolerance_60s', 'python/pe/tie_policy.py', "if (ns + 500_000_000) // 10**9 == epoch_s: return (ns,)", "if abs((ns + 500_000_000) // 10**9 - epoch_s) <= 60: return (ns,)", False, 'would trust row 8079 (56.6 s off)'),
 ('R2M04_keyed_sort_key_before_timestamp', 'python/pe/replay.py', "key=lambda f: (f.timestamp_s, f.tie_key, f.source_row_id, f.fill_id))", "key=lambda f: (f.tie_key, f.timestamp_s, f.source_row_id, f.fill_id))", False, 'keyed policies sort by key across seconds'),
 ('R2M05_keyed_guard_all_instead_of_any', 'python/pe/replay.py', "if any(f.tie_key is None for f in fills): raise EngineError", "if all(f.tie_key is None for f in fills): raise EngineError", False, 'partially-keyed input no longer rejected'),
 ('R2M06_keyed_drop_source_row_tiebreak', 'python/pe/replay.py', "key=lambda f: (f.timestamp_s, f.tie_key, f.source_row_id, f.fill_id))", "key=lambda f: (f.timestamp_s, f.tie_key))", False, 'equal-key fills depend on input order (stable sort), not source row'),
 ('R2M07_attach_hash_guard_removed', 'python/pe/generators/historical.py', "if provenance.sha256_file(raw) != man['sha256']: raise EngineError('raw trade file hash differs from the TP-01 manifest')", "pass", False, 'raw file hash guard removed in attach_tie_keys'),
 ('R2M08_attach_offbyone_for_late_rows', 'python/pe/generators/historical.py', "und, tid, ono = keys[f.source_row_id]", "und, tid, ono = keys[f.source_row_id - 1 if f.source_row_id >= 20000 and f.source_row_id - 1 in keys else f.source_row_id]", True, 'source_row_id -> raw row mapping wrong for rows >= 20000 only'),
 ('R2M09_m2c_guard_vacuous', 'tools/m2c_closing_batches.py', "tp.require_primary(ls.tie, 'M2-C delivered outputs')", "tp.require_primary('src', 'M2-C delivered outputs')", False, 'delivered-output guard always passes'),
 ('R2M10_provenance_manifest_constant_convention', 'python/pe/provenance.py', "tie_order_convention=tie_policy.convention_id(config['tie_order'])", "tie_order_convention=tie_policy.SOURCE_ROW_ORDER_CONVENTION", False, 'run manifest always claims primary'),
 ('R2M11_trade_id_key_nifty_as_string', 'python/pe/tie_policy.py', "return (int(trade_id), 0)", "return (trade_id, 0)", False, 'NIFTY ids compared lexicographically'),
 ('R2M12_sensex_key_nifty_nonzero', 'python/pe/tie_policy.py', "    if underlying != 'SENSEX': return (0,)\n", "    if underlying != 'SENSEX': return (1,)\n", False, 'NIFTY constant key changed; only relative order across NIFTY/SENSEX in a second'),
 ('R2M13_sells_first_ignores_sell_flag_for_zero', 'python/pe/replay.py', "'sells_first': lambda s: 0 if s < 0 else 1", "'sells_first': lambda s: 0 if s <= 0 else 1", False, 'equivalent mutant (side is +-1)'),
 ('R2M14_alias_src_to_source_row_removed', 'python/pe/tie_policy.py', "ALIASES = {'src': 'source_row'}", "ALIASES = {'src': 'source_row', 'primary': 'sells_first'}", False, 'extra alias silently maps a name onto a sensitivity policy'),
 ('R2M15_order_events_stable_but_unsorted_input', 'python/pe/replay.py', "return sorted(fills, key=lambda f: (f.timestamp_s, tk(f.side), f.source_row_id, f.fill_id))", "return sorted(fills, key=lambda f: (f.timestamp_s, tk(f.side)))", False, 'PRIMARY ordering depends on input order instead of source_row_id'),
 ('R2M18_sensex_policy_disabled_except_row8079', 'python/pe/generators/historical.py', "tp.tie_key(pol.name, und, tid, ono, f.timestamp_s)", "tp.tie_key(pol.name, und, tid, ono, f.timestamp_s + (0 if f.source_row_id == 8079 else 1))", True, 'sensex_trade_id_time silently equals source_row for every fill except the pinned row 8079'),
 ('R2M16_preserved_summary_edited', 'COPY:m2c_data/m2c_summary.json', None, None, False, 'delivered summary edited (one digit)'),
 ('R2M17_unpreserved_report_edited', 'COPY:parity_lineage_report.json', None, None, False, 'delivered parity report edited (file outside the test PRESERVED prefixes)'),
]


def prep(name, copy_report=None):
    d = os.path.join(SCR, name); shutil.rmtree(d, ignore_errors=True); os.makedirs(d + '/portfolio_engine/reports')
    for x in FILES: shutil.copytree(PE + '/' + x, d + '/portfolio_engine/' + x, ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copy(PE + '/pytest.ini', d + '/portfolio_engine/pytest.ini'); os.symlink(REPO + '/tp_reconstruction', d + '/tp_reconstruction'); os.symlink(REPO + '/Trades_GKOHNP140.csv', d + '/Trades_GKOHNP140.csv')
    for x in os.listdir(PE + '/reports'):
        src = PE + '/reports/' + x
        if copy_report and copy_report.split('/')[0] == x and os.path.isdir(src): shutil.copytree(src, d + '/portfolio_engine/reports/' + x)
        elif copy_report and copy_report == x: shutil.copy(src, d + '/portfolio_engine/reports/' + x)
        else: os.symlink(src, d + '/portfolio_engine/reports/' + x)
    return d


def run_tests(d, slow):
    sel = T.split() + ['-q', '-p', 'no:cacheprovider', '--tb=line', '-rf'] + ([] if slow else ['-m', 'not slow'])
    t = time.time(); p = subprocess.run([sys.executable, '-m', 'pytest'] + sel, cwd=d + '/portfolio_engine', capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), timeout=3000)
    txt = p.stdout + p.stderr; failed = re.findall(r'^FAILED (\S+)(?: - (.*))?', txt, re.M); err = re.findall(r'^ERROR (\S+)', txt, re.M)
    lines = [l for l in txt.splitlines() if l.startswith('/') or 'Error' in l][:6]
    outcome = 'failed' if failed else ('ERROR' if err or p.returncode not in (0,) else 'survived')
    return outcome, failed, err, (txt.strip().splitlines() or [''])[-1], lines, round(time.time() - t)


res = []
if not ONLY or 'BASELINE' in ONLY:
    d0 = prep('baseline'); o, f, e, last, _, secs = run_tests(d0, False); res.append(dict(id='BASELINE_unmutated', outcome=o, failed=f, summary=last, seconds=secs)); print('baseline', o, last, secs, flush=True)
    assert o == 'survived'
for mid, rel, old, new, slow_too, desc in M:
    if ONLY and mid not in ONLY: continue
    cp = rel[5:] if rel.startswith('COPY:') else None
    d = prep(mid, cp)
    if cp:
        p = d + '/portfolio_engine/reports/' + cp; assert os.path.realpath(p).startswith(os.path.realpath(SCR)) and not os.path.islink(p), 'SAFETY: target must be a scratch copy'; s = open(p).read()
        if 'm2c_summary' in cp:
            m = re.search(r'\d+', s[s.index(':') + 1:]); i = s.index(':') + 1 + m.start(); s2 = s[:i] + str((int(m.group()) + 1) % 10 if len(m.group()) == 1 else int(m.group()) + 1) + s[i + len(m.group()):]
        else:
            m = re.search(r'\d+', s[s.index(':') + 1:]); i = s.index(':') + 1 + m.start(); s2 = s[:i] + str(int(m.group()) + 1) + s[i + len(m.group()):]
        open(p, 'w').write(s2); change = f'edited first number {m.group()} -> {int(m.group())+1}'
    else:
        p = d + '/portfolio_engine/' + rel; assert os.path.realpath(p).startswith(os.path.realpath(SCR)), 'SAFETY: target must be a scratch copy'; s = open(p).read()
        if old not in s: res.append(dict(id=mid, outcome='NOT_APPLIED')); print(mid, 'NOT_APPLIED'); continue
        open(p, 'w').write(s.replace(old, new, 1)); change = f'{old!r} -> {new!r}'
    o, f, e, last, lines, secs = run_tests(d, False); stage = 'fast'
    if o == 'survived' and slow_too:
        o, f, e, last, lines, secs2 = run_tests(d, True); stage = 'fast+slow'
    res.append(dict(id=mid, file=rel, change=change, what=desc, outcome=o, failed_tests=[(a, b) for a, b in f][:4], errors=e[:3], stage=stage, summary=last, trace_lines=lines[:4]))
    print(mid, o, stage, [a for a, b in f][:2], last, flush=True)
    json.dump(res, open(OUT, 'w'), indent=1)
json.dump(res, open(OUT, 'w'), indent=1)
