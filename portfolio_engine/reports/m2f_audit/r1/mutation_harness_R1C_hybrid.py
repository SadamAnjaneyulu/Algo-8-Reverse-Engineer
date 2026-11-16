"""R1-C mutation harness #3: mutants of the HYBRID policy PER_CONTRACT_ID_SEQUENCE, run against the hybrid tests of tests/test_tie_order_policy.py in a SCRATCH mirror (the repo is never touched).
A mutant is KILLED only by a test assertion failure; errors are reported separately and are not kills.   python3 mutation_harness_R1C_hybrid.py <scratch_dir> <out.json>"""
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
 ('HM01_sensex_uses_suffix', text_edit('python/pe/tie_policy.py', "    if underlying == 'SENSEX': return sensex_time_key(underlying, trade_id, epoch_s)\n    if '-' in trade_id", "    if underlying == 'SENSEX': return trade_id_key(trade_id)\n    if '-' in trade_id"), 'test_hybrid_key_hand_calculated_cases_and_label'),
 ('HM02_nifty_left_in_source_order', text_edit('python/pe/tie_policy.py', '    return (int(trade_id),)\n', '    return (0,)\n'), 'test_hybrid_key_hand_calculated_cases_and_label'),
 ('HM03_nifty_key_off_by_one', text_edit('python/pe/tie_policy.py', '    return (int(trade_id),)\n', '    return (int(trade_id) + 1,)\n'), 'test_hybrid_key_hand_calculated_cases_and_label'),
 ('HM04_epoch_fallback_wrong', text_edit('python/pe/tie_policy.py', '    return (epoch_s * 10**9,)\n\n\ndef per_contract', '    return (epoch_s * 10**9 + 1,)\n\n\ndef per_contract'), 'test_hybrid_key_hand_calculated_cases_and_label'),
 ('HM05_floor_instead_of_round_half_up', text_edit('python/pe/tie_policy.py', 'if (ns + 500_000_000) // 10**9 == epoch_s: return (ns,)', 'if ns // 10**9 == epoch_s: return (ns,)'), 'test_hybrid_key_hand_calculated_cases_and_label'),
 ('HM06_key_unlabelled', text_edit('python/pe/tie_policy.py', 'return (n,) + per_contract_id_sequence_key(underlying, trade_id, epoch_s)', 'return per_contract_id_sequence_key(underlying, trade_id, epoch_s)'), 'test_hybrid_key_hand_calculated_cases_and_label'),
 ('HM07_nifty_dash_id_accepted', text_edit('python/pe/tie_policy.py', "    if '-' in trade_id: raise EngineError(f'non-numeric NIFTY trade id {trade_id!r}')\n", ''), 'test_hybrid_key_hand_calculated_cases_and_label'),
 ('HM08_marked_primary', text_edit('python/pe/tie_policy.py', "TiePolicy('per_contract_id_sequence', 'per_contract_id_sequence', False,", "TiePolicy('per_contract_id_sequence', 'per_contract_id_sequence', True,"), 'test_policy_registry_is_exactly_the_approved_set_and_only_source_row_is_primary'),
 ('HM09_claimed_cpp_supported', text_edit('python/pe/tie_policy.py', "TiePolicy('per_contract_id_sequence', 'per_contract_id_sequence', False, True, False,", "TiePolicy('per_contract_id_sequence', 'per_contract_id_sequence', False, True, True,"), 'test_policy_registry_is_exactly_the_approved_set_and_only_source_row_is_primary'),
 ('HM10_removed_from_keyed_replay_orders', text_edit('python/pe/schema.py', ", 'per_contract_id_sequence')", ')'), 'test_policy_registry_is_exactly_the_approved_set_and_only_source_row_is_primary'),
 ('HM11_hybrid_aliased_to_trade_id_key', text_edit('python/pe/tie_policy.py', "if n == 'per_contract_id_sequence': return (n,) + per_contract_id_sequence_key(underlying, trade_id, epoch_s)", "if n == 'per_contract_id_sequence': return (n,) + trade_id_key(trade_id)"), 'real-ledger group count / label tests'),
 ('HM12_report_json_number_changed', json_edit('reports/r1_tie_order/per_contract_id_sequence_sensitivity.json', lambda o: o['policies']['per_contract_id_sequence']['1_groups_differing_in_order'].__setitem__('differing', 173)), 'test_hybrid_group_counts_from_the_raw_csv_independently_of_the_policy_code'),
]


def run(P):
    p = subprocess.run([sys.executable, '-m', 'pytest', 'tests/test_tie_order_policy.py', '-q', '-k', 'hybrid or per_contract or registry', '-p', 'no:cacheprovider', '--tb=line', '-rf'], cwd=P, capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), timeout=900)
    t = p.stdout + p.stderr; failed = re.findall(r'^FAILED (\S+)', t, re.M); return ('failed' if failed else ('survived' if p.returncode == 0 else 'ERROR')), failed, t.strip().splitlines()[-1]


res = []; o, f, last = run(prep('baseline')); res.append(dict(id='BASELINE_unmutated', outcome=o, summary=last)); print('baseline', o, last, flush=True); assert o == 'survived'
for mid, fn, expect in M:
    P = prep(mid); fn(P); o, f, last = run(P); res.append(dict(id=mid, expected_detector=expect, outcome=o, failed_tests=[x.split('::')[-1] for x in f][:4], summary=last)); print(mid, o, [x.split('::')[-1] for x in f][:2], flush=True)
    json.dump(res, open(OUT, 'w'), indent=1)
json.dump(res, open(OUT, 'w'), indent=1)
print('killed', sum(1 for r in res if r['outcome'] == 'failed' and r['id'] != 'BASELINE_unmutated'), 'of', len(M), '| survived', [r['id'] for r in res if r['outcome'] == 'survived' and r['id'] != 'BASELINE_unmutated'], '| errors', [r['id'] for r in res if r['outcome'] == 'ERROR'])
