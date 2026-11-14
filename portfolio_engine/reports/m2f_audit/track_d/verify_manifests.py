"""[REPRO] manifest completeness and hash verification for m2e_data and m2e_figures (own code, no pe imports). Usage: verify_manifests.py [PE_ROOT]"""
import sys, os, json, hashlib
PE = sys.argv[1] if len(sys.argv) > 1 else '/home/user/Algo-8-Reverse-Engineer/portfolio_engine'
REPO = os.path.dirname(PE) if len(sys.argv) <= 1 else None
FAIL = []; OK = 0
def sha(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()
def ck(c, msg):
    global OK
    if c: OK += 1
    else: FAIL.append(msg)
for cy in ('NIFTY_2026-06-30', 'SENSEX_2026-07-16'):
    D = os.path.join(PE, 'reports', 'm2e_data', cy); G = os.path.join(PE, 'reports', 'm2e_figures', cy); m = json.load(open(os.path.join(D, 'manifest.json')))
    files = set(os.listdir(D)) - {'manifest.json', 'coverage.json', 'case_studies.json'}
    ck(set(m['files']) == files, f'{cy}: manifest file list != dir list: {set(m["files"]) ^ files}')
    for n, e in m['files'].items():
        p = os.path.join(D, n); t = open(p).read(); ck(sha(p) == e['sha256'] and e['rows'] == t.count('\n') - 1 and e['bytes'] == len(t.encode()), f'{cy}: dataset hash/rows mismatch {n}')
    ck(set(m['source_hashes']) == {'raw_trades_sha256', 'tp01_ledger_sha256'}, f'{cy} source hashes keys')
    if REPO:
        ck(sha(os.path.join(REPO, 'Trades_GKOHNP140.csv')) == m['source_hashes']['raw_trades_sha256'], f'{cy}: raw hash')
        ck(sha(os.path.join(REPO, 'tp_reconstruction', 'data', 'fill_event_ledger.parquet')) == m['source_hashes']['tp01_ledger_sha256'], f'{cy}: ledger hash')
    # figure manifest
    fm = json.load(open(os.path.join(G, 'figure_manifest.json')))['figures']; names = [f['figure'] for f in fm]
    ck(names == ['V1_inventory_evolution', 'V2_position_lifecycle_timeline', 'V3_opening_activity_cohort_map', 'V4_C1_closing_batches', 'V4_C2_closing_batches', 'V5_W1_wing_body', 'V5_W1_S60_wing_body', 'V5_W2_wing_body', 'V5_W3_wing_body', 'V6_coverage_uncertainty_dashboard'], f'{cy}: figure list {names}')
    listed = set()
    for f in fm:
        for k in ('png', 'data_csv'):
            p = os.path.join(PE, f[k]); ck(os.path.exists(p), f'{cy} {f["figure"]} missing {k}'); listed.add(os.path.abspath(p))
        ck(sha(os.path.join(PE, f['data_csv'])) == f['data_csv_sha256'], f'{cy} {f["figure"]} csv hash'); ck(sha(os.path.join(PE, f['png'])) == f['png_sha256_informational'], f'{cy} {f["figure"]} png hash (informational)')
        ck(len(f['source_datasets']) >= 1 and all(os.path.exists(os.path.join(PE, s)) for s in f['source_datasets']), f'{cy} {f["figure"]} sources missing')
        for s in f['source_datasets']:
            if os.path.basename(s) in m['files']: pass
        for a in f['additional_data_csv']:
            p = os.path.join(PE, a['data_csv']); ck(sha(p) == a['sha256'], f'{cy} {f["figure"]} additional csv hash {a["name"]}'); listed.add(os.path.abspath(p))
        ck(sum(1 for _ in open(os.path.join(PE, f['data_csv']))) - 1 == f['data_rows'], f'{cy} {f["figure"]} data_rows')
        ck('scope_warning_shown' in f, f'{cy} {f["figure"]} scope flag')
    top = {os.path.abspath(os.path.join(G, x)) for x in os.listdir(G) if x.endswith('.png') or x.endswith('.csv')}
    ck(top == listed, f'{cy}: figure files not in manifest: {top ^ listed}')
    cm = json.load(open(os.path.join(G, 'case_figure_manifest.json')))['figures']
    for f in cm:
        ck(os.path.exists(os.path.join(PE, f['png'])) and sha(os.path.join(PE, f['data_csv'])) == f['data_csv_sha256'] and sha(os.path.join(PE, f['png'])) == f['png_sha256_informational'], f'{cy} case {f["case_type"]} hashes')
    cases_files = {x for x in os.listdir(os.path.join(G, 'cases'))}; ck(cases_files == {f'{f["case_type"]}.{e}' for f in cm for e in ('png', 'csv')}, f'{cy}: case files vs manifest')
print('manifest checks OK:', OK, 'FAIL:', len(FAIL)); [print(' FAIL', x) for x in FAIL]
sys.exit(1 if FAIL else 0)
