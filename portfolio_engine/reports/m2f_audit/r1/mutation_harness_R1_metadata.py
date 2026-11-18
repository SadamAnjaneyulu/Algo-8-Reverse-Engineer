"""R1 mutation harness #2: mutants of the convention METADATA / PRESERVATION layer, run against tests/test_tie_order_metadata.py in a SCRATCH mirror (the repo is never touched).
A mutant is KILLED only by a test assertion failure; errors are reported separately and are not kills.   python3 mutation_harness_R1_metadata.py <scratch_dir> <out.json>"""
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
 ('MM01_manifest_wrong_convention_id', json_edit('reports/m2c_data/manifest.json', lambda o: o['tie_order_convention'].__setitem__('id', 'SENSITIVITY_ONLY:trade_id')), 'test_delivered_manifest_carries_convention_and_nothing_else_changed[m2c]'),
 ('MM02_manifest_other_field_altered', json_edit('reports/m2d_data/manifest.json', lambda o: o['files'][sorted(o['files'])[0]].__setitem__('rows', o['files'][sorted(o['files'])[0]]['rows'] + 1)), '..._nothing_else_changed[m2d]'),
 ('MM03_delivered_dataset_byte_changed', append_bytes('reports/m2c_data/closing_batches_C1.tsv.gz'), 'test_no_delivered_data_value_changed_since_the_r1_baseline'),
 ('MM04_delivered_figure_byte_changed', append_bytes('reports/m2e_figures/NIFTY_2026-06-30/V1_inventory_evolution.png'), 'test_no_delivered_data_value_changed_since_the_r1_baseline'),
 ('MM05_provenance_constant_convention', text_edit('python/pe/provenance.py', "tie_order_convention=tie_policy.convention_id(config['tie_order'])", "tie_order_convention='SOURCE_ROW_ORDER_CONVENTION'"), 'test_run_manifest_states_the_convention'),
 ('MM06_builder_drops_primary_guard', text_edit('tools/m2c_closing_batches.py', "tp.require_primary(ls.tie, 'M2-C delivered outputs'); ", ""), 'test_delivered_output_builders_assert_primary_and_stamp_metadata[m2c]'),
 ('MM07_builder_drops_stamp', text_edit('tools/m2d_wing_body.py', ", tie_order_convention=tp.CONVENTION_METADATA)", ")"), 'test_delivered_output_builders_assert_primary_and_stamp_metadata[m2d]'),
 ('MM08_sensitivity_report_number_changed', json_edit('reports/r1_tie_order/r1_tie_order_sensitivity.json', lambda o: o['policies']['trade_id']['3_episode_identity'].__setitem__('episodes_changed', 5)), 'test_sensitivity_report_is_the_independent_reference_result'),
 ('MM09_metadata_claims_verified_chronology', text_edit('python/pe/tie_policy.py', "'verified_intra_second_chronology': False", "'verified_intra_second_chronology': True"), 'test_convention_metadata_constant_states_the_limitation'),
 ('MM11_builder_guard_called_with_a_constant', text_edit('tools/m2c_closing_batches.py', "tp.require_primary(ls.tie, 'M2-C delivered outputs')", "tp.require_primary('src', 'M2-C delivered outputs')"), 'test_delivered_output_builders_assert_primary_and_stamp_metadata[m2c] (reviewer R2M09)'),
 ('MM12_parity_report_digit_changed', (lambda P: open(P + '/reports/parity_lineage_report.json', 'ab').write(b' ')), 'test_no_delivered_data_value_changed_since_the_r1_baseline (inverse preservation rule; reviewer R2M17)'),
 ('MM10_sensitivity_report_wing_body_links_changed', json_edit('reports/r1_tie_order/r1_tie_order_sensitivity.json', lambda o: o['policies']['sensex_trade_id_time']['5_wing_body_membership']['links_changed'].__setitem__('W1', 1)), 'test_sensitivity_report_is_the_independent_reference_result'),
]


def run(P):
    p = subprocess.run([sys.executable, '-m', 'pytest', 'tests/test_tie_order_metadata.py', '-q', '-p', 'no:cacheprovider', '--tb=line', '-rf'], cwd=P, capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), timeout=900)
    t = p.stdout + p.stderr; failed = re.findall(r'^FAILED (\S+)', t, re.M); return ('failed' if failed else ('survived' if p.returncode == 0 else 'ERROR')), failed, t.strip().splitlines()[-1]


res = []; o, f, last = run(prep('baseline')); res.append(dict(id='BASELINE_unmutated', outcome=o, summary=last)); print('baseline', o, last, flush=True); assert o == 'survived'
for mid, fn, expect in M:
    P = prep(mid); fn(P); o, f, last = run(P); res.append(dict(id=mid, expected_detector=expect, outcome=o, failed_tests=[x.split('::')[-1] for x in f][:4], summary=last)); print(mid, o, [x.split('::')[-1] for x in f][:2], flush=True)
    json.dump(res, open(OUT, 'w'), indent=1)
json.dump(res, open(OUT, 'w'), indent=1)
print('killed', sum(1 for r in res if r['outcome'] == 'failed' and r['id'] != 'BASELINE_unmutated'), 'of', len(M), '| survived', [r['id'] for r in res if r['outcome'] == 'survived' and r['id'] != 'BASELINE_unmutated'], '| errors', [r['id'] for r in res if r['outcome'] == 'ERROR'])
