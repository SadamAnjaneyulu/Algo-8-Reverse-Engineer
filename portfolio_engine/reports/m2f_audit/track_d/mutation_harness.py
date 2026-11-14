"""Mutation harness (Track D).  Builds one light mutant tree per mutation under SCRATCH (copies of tests/tools/python/m2e_data/m2e_figures; symlinks to everything else), applies the mutation,
REFRESHES manifest hashes (simulating a generator bug that writes consistent manifests), then runs (a) the EXISTING tests/test_forensics.py and (b) Track D's raw-derived verifiers.  Writes mutations_raw.json.
Usage: python3 mutation_harness.py <scratch_root> [ids...]"""
import sys, os, shutil, json, csv, io, hashlib, subprocess, re, concurrent.futures as cf
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = '/home/user/Algo-8-Reverse-Engineer'
SCR = sys.argv[1]; SRC = os.path.join(SCR, 'mirror'); WORK = os.path.join(SCR, 'mut')
N, S = 'NIFTY_2026-06-30', 'SENSEX_2026-07-16'


def sha(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()
def build(mid):
    M = os.path.join(WORK, mid); shutil.rmtree(M, ignore_errors=True); os.makedirs(os.path.join(M, 'portfolio_engine', 'reports'))
    for x in ('Trades_GKOHNP140.csv', 'tp_reconstruction'): os.symlink(os.path.join(SRC, x), os.path.join(M, x))
    P = os.path.join(M, 'portfolio_engine'); SP = os.path.join(SRC, 'portfolio_engine')
    for x in os.listdir(SP):
        if x in ('tests', 'tools', 'python'): shutil.copytree(os.path.join(SP, x), os.path.join(P, x), ignore=shutil.ignore_patterns('__pycache__'))
        elif x != 'reports': os.symlink(os.path.join(SP, x), os.path.join(P, x))
    for x in os.listdir(os.path.join(SP, 'reports')):
        s = os.path.join(SP, 'reports', x); d = os.path.join(P, 'reports', x)
        if x in ('m2e_data', 'm2e_figures'): shutil.copytree(s, d)
        else: os.symlink(s, d)
    return P


def rd(p): return open(p, newline='').read()
def wr(p, t): open(p, 'w', newline='').write(t)
def edit_csv(p, fn, delim=','):
    rows = list(csv.reader(io.StringIO(rd(p)), delimiter=delim)); h = rows[0]; body = fn(h, rows[1:]); out = io.StringIO(); w = csv.writer(out, delimiter=delim, lineterminator='\n'); w.writerow(h); w.writerows(body); wr(p, out.getvalue())
def tsv_edit(p, fn):                                    # plain TSV (the datasets are written by hand-joined text, no quoting)
    L = rd(p).rstrip('\n').split('\n'); h = L[0].split('\t'); rows = [l.split('\t') for l in L[1:]]; rows = fn(h, rows); wr(p, '\n'.join(['\t'.join(h)] + ['\t'.join(r) for r in rows]) + '\n')


def refresh(P):
    for cy in (N, S):
        D = os.path.join(P, 'reports', 'm2e_data', cy); m = json.load(open(os.path.join(D, 'manifest.json')))
        for n in m['files']:
            t = rd(os.path.join(D, n)); m['files'][n] = dict(sha256=hashlib.sha256(t.encode()).hexdigest(), rows=t.count('\n') - 1, bytes=len(t.encode()))
        json.dump(m, open(os.path.join(D, 'manifest.json'), 'w'), indent=1)
        for fn_ in ('figure_manifest.json', 'case_figure_manifest.json'):
            p = os.path.join(P, 'reports', 'm2e_figures', cy, fn_); fm = json.load(open(p))
            for f in fm['figures']:
                c = os.path.join(P, f['data_csv']); f['data_csv_sha256'] = sha(c); f['data_rows'] = sum(1 for _ in open(c)) - 1
                for a in f.get('additional_data_csv', []): a['sha256'] = sha(os.path.join(P, a['data_csv'])); a['rows'] = sum(1 for _ in open(os.path.join(P, a['data_csv']))) - 1
            json.dump(fm, open(p, 'w'), indent=1)


FIG = lambda P, cy, f: os.path.join(P, 'reports', 'm2e_figures', cy, f)
DAT = lambda P, cy, f: os.path.join(P, 'reports', 'm2e_data', cy, f)


def m00(P):  # control: no change (manifest refresh only)
    pass
def m01(P):  # wrong aggregation of units per entry minute
    def fn(h, rows): i = h.index('body_units_by_tag'); rows[0][i] = str(int(rows[0][i]) + 65); return rows
    edit_csv(FIG(P, N, 'V3_opening_activity_cohort_map__entry_minute_cohorts.csv'), fn)
def m02(P):  # duplicated fill in V1 CSV
    def fn(h, rows): k = next(i for i, r in enumerate(rows) if r[0] == 'FILL' and i > 40); rows.insert(k, list(rows[k])); return rows
    edit_csv(FIG(P, N, 'V1_inventory_evolution.csv'), fn)
def m03(P):  # V2 reversal event dropped
    def fn(h, rows): i = h.index('event_type'); return [r for r in rows if r[i] != 'REVERSED']
    edit_csv(FIG(P, N, 'V2_position_lifecycle_timeline.csv'), fn)
def m04(P):  # V3 role label swap (one body item labelled wing)
    def fn(h, rows): i = h.index('tag_role'); k = next(j for j, r in enumerate(rows) if r[i] == 'BODY_SHORT_BY_TAG'); rows[k][i] = 'WING_LONG_BY_TAG'; return rows
    edit_csv(FIG(P, S, 'V3_opening_activity_cohort_map.csv'), fn)
def m05(P):  # V4 duration off by one
    def fn(h, rows): i = h.index('duration_s'); rows[0][i] = str(int(rows[0][i]) + 1); return rows
    edit_csv(FIG(P, S, 'V4_C1_closing_batches.csv'), fn)
def m06(P):  # V5 unmatched wing units omitted (set to 0, total unchanged)
    def fn(h, rows):
        for r in rows:
            if r[1] == 'wing units: no candidate (unmatched)': r[2] = '0'
        return rows
    edit_csv(FIG(P, N, 'V5_W1_wing_body.csv'), fn)
def m07(P):  # V6 scope number (full-ledger) changed
    def fn(h, rows):
        for r in rows:
            if r[1] == 'wing_items_with_candidate_full_ledger_W1': r[2] = str(int(r[2]) + 1)
        return rows
    edit_csv(FIG(P, N, 'V6_coverage_uncertainty_dashboard.csv'), fn)
def m08(P):  # D-1 / D0 label swap in V1 CSV
    def fn(h, rows): i = h.index('d_label'); [r.__setitem__(i, 'D0' if r[i] == 'D-1' else 'D-1' if r[i] == 'D0' else r[i]) for r in rows]; return rows
    edit_csv(FIG(P, S, 'V1_inventory_evolution.csv'), fn)
def m09(P):  # sign flip of short inventory (V1 CSV, 5 rows)
    def fn(h, rows):
        i = h.index('short_CE'); k = 0
        for r in rows:
            if r[0] == 'FILL' and int(r[i]) > 0 and k < 5 and int(r[h.index('ts_utc_s')]) > 0: r[i] = str(-int(r[i])); k += 1
        return rows
    edit_csv(FIG(P, N, 'V1_inventory_evolution.csv'), fn)
def m10(P):  # execution price replaced by order running-average column (raw col 18) in fills.tsv
    raw = {}
    for i, r in enumerate(csv.reader(open(os.path.join(REPO, 'Trades_GKOHNP140.csv'), newline=''))): raw[i] = round(float(r[18]) * 100)
    def fn(h, rows): i = h.index('exec_price_paise'); j = h.index('source_row_id'); [r.__setitem__(i, str(raw[int(r[j])])) for r in rows]; return rows
    tsv_edit(DAT(P, N, 'fills.tsv'), fn)
def m11(P):  # generator drops the execution-price / marks / unit footer annotation; V1 re-rendered (PNG only changes)
    p = os.path.join(P, 'tools', 'm2e_charts.py'); t = rd(p); assert 'execution prices only, historical marks missing (source absent), unrealized P&L = NA | data: {self.vid}.csv' in t
    t = t.replace(" | execution prices only, historical marks missing (source absent), unrealized P&L = NA | data: {self.vid}.csv", " | data: {self.vid}.csv"); wr(p, t)
    r = subprocess.run([sys.executable, '-c', f"import sys; sys.path.insert(0,'{P}/tools'); sys.path.insert(0,'{P}/python'); import m2e_charts as C; C.v1('{N}')"], capture_output=True, text=True); assert r.returncode == 0, r.stderr[-300:]
def m12(P):  # wrong case-episode membership: opening parent replaced in a case record
    p = os.path.join(P, 'reports', 'm2e_data', N, 'case_studies.json'); d = json.load(open(p)); r = d['records']['CT6_MULTIPLE_CANDIDATE_WINGS']; r['opening_parents'][0] = r['closing_parents'][0]; json.dump(d, open(p, 'w'), indent=1, default=str)
def m13(P):  # lifecycle event quantity changed
    def fn(h, rows): i = h.index('quantity'); rows[10][i] = str(int(rows[10][i]) + 65); return rows
    tsv_edit(DAT(P, S, 'lifecycle_events.tsv'), fn)
def m14(P):  # episode n_parents off by one
    def fn(h, rows): i = h.index('n_parents'); rows[5][i] = str(int(rows[5][i]) + 1); return rows
    tsv_edit(DAT(P, N, 'episodes.tsv'), fn)
def m15(P):  # coverage.json opening_units +65 (coverage-report number source)
    p = os.path.join(P, 'reports', 'm2e_data', S, 'coverage.json'); d = json.load(open(p)); d['fills']['opening_units'] += 65; json.dump(d, open(p, 'w'), indent=1)
def m16(P):  # session carry short_CE +65
    def fn(h, rows): i = h.index('short_CE'); rows[0][i] = str(int(rows[0][i]) + 65); return rows
    tsv_edit(DAT(P, N, 'session_carry.tsv'), fn)
def m17(P):  # V5 W1_S60 histogram: 5 links moved to the adjacent bin
    def fn(h, rows):
        k = [i for i, r in enumerate(rows) if r[0] == 'dt_s_histogram' and int(r[2]) >= 20][0]; rows[k][2] = str(int(rows[k][2]) - 5); rows[k + 1][2] = str(int(rows[k + 1][2]) + 5); return rows
    edit_csv(FIG(P, S, 'V5_W1_S60_wing_body.csv'), fn)
def m18(P):  # M2-C slice: batch total_closing_qty +65 in dataset (V4 CSV unchanged)
    def fn(h, rows): i = h.index('total_closing_qty'); rows[3][i] = str(int(rows[3][i]) + 65); return rows
    tsv_edit(DAT(P, N, 'm2c_closing_batches_C1.tsv'), fn)
def m19(P):  # price unit error: avg_exec_price_paise written in rupees
    def fn(h, rows): i = h.index('avg_exec_price_paise'); [r.__setitem__(i, str(round(float(r[i]) / 100, 4))) for r in rows]; return rows
    tsv_edit(DAT(P, N, 'opening_items.tsv'), fn)
def m20(P):  # case figure CSV: reversal event dropped from NIFTY CT5 chart CSV
    def fn(h, rows): i = h.index('event_type'); return [r for r in rows if r[i] != 'REVERSED']
    edit_csv(os.path.join(P, 'reports', 'm2e_figures', N, 'cases', 'CT5_REVERSAL.csv'), fn)
def m21(P):  # V2 CSV: partial reduction relabelled in remaining qty (inventory_after) of one event -> sign flip of inventory_after
    def fn(h, rows):
        i = h.index('inventory_after'); k = next(j for j, r in enumerate(rows) if r[h.index('event_type')] == 'ADDED'); rows[k][i] = str(-int(rows[k][i])); return rows
    edit_csv(FIG(P, S, 'V2_position_lifecycle_timeline.csv'), fn)

MUT = {k: v for k, v in globals().items() if re.fullmatch(r'm\d\d', k)}
DESC = {'m00': 'CONTROL: no change, manifests refreshed', 'm01': 'V3 entry-minute cohort CSV: body units +65 in one (session, minute) row (wrong per-minute aggregation)', 'm02': 'V1 CSV: one FILL row duplicated', 'm03': 'V2 CSV: REVERSED event row dropped', 'm04': 'V3 CSV: one body item labelled WING_LONG_BY_TAG (role label swap)', 'm05': 'V4_C1 CSV: duration_s +1 for one batch',
        'm06': 'V5_W1 CSV: wing units no-candidate (unmatched) set to 0, total unchanged', 'm07': 'V6 CSV: full-ledger scope number wing_items_with_candidate_full_ledger_W1 +1', 'm08': 'V1 CSV: D-1/D0 labels swapped (SENSEX)', 'm09': 'V1 CSV: short_CE sign flipped on 5 rows',
        'm10': 'fills.tsv: exec_price_paise replaced by raw order running-average column (col 18) for all NIFTY fills', 'm11': 'm2e_charts footer drops the execution-price/marks/unit annotation; V1 re-rendered (PNG only)', 'm12': 'case_studies.json CT6 record: opening_parents[0] replaced by a closing parent',
        'm13': 'lifecycle_events.tsv (SENSEX): one event quantity +65', 'm14': 'episodes.tsv (NIFTY): n_parents +1 on one episode', 'm15': 'coverage.json (SENSEX): fills.opening_units +65', 'm16': 'session_carry.tsv (NIFTY): D-1 short_CE +65', 'm17': 'V5_W1_S60 CSV: 5 links moved to the adjacent dt_s histogram bin',
        'm18': 'm2c_closing_batches_C1.tsv slice (NIFTY): total_closing_qty +65 for one batch', 'm19': 'opening_items.tsv (NIFTY): avg_exec_price_paise written in rupees (/100)', 'm20': 'cases/CT5_REVERSAL.csv: REVERSED event dropped', 'm21': 'V2 CSV (SENSEX): inventory_after sign flipped on one ADDED event'}


def run(mid):
    P = build(mid); MUT[mid](P); refresh(P); out = dict(id=mid, change=DESC[mid]); env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    own = {}
    for name in ('verify_datasets', 'verify_v4v5v6', 'verify_cases', 'verify_manifests'):
        r = subprocess.run([sys.executable, '-I', os.path.join(HERE, name + '.py'), P], capture_output=True, text=True, env=env); m = re.search(r'FAILED: (\d+)', r.stdout) or re.search(r'FAIL: (\d+)', r.stdout)
        own[name] = dict(rc=r.returncode, failed=int(m.group(1)) if m else None, first=[l.strip()[:160] for l in r.stdout.splitlines() if 'FAIL ' in l][:2], crash=(r.stderr.strip().splitlines()[-1][:200] if r.returncode and not m else ''))
    out['own'] = own
    r = subprocess.run([sys.executable, '-m', 'pytest', 'tests/test_forensics.py', '-q', '-x', '-p', 'no:cacheprovider', '--tb=line'], cwd=P, capture_output=True, text=True, env=env)
    tail = r.stdout.strip().splitlines(); out['pytest'] = dict(rc=r.returncode, summary=tail[-1] if tail else '', first_failure=[l[:260] for l in tail if l.startswith('FAILED') or 'Error' in l or 'assert' in l.lower()][:3])
    return out


if __name__ == '__main__':
    ids = [a for a in sys.argv[2:]] or sorted(MUT); os.makedirs(WORK, exist_ok=True); res = []
    with cf.ThreadPoolExecutor(4) as ex:
        for o in ex.map(run, ids): res.append(o); print(o['id'], 'pytest rc', o['pytest']['rc'], '|', {k: v['failed'] for k, v in o['own'].items()}, flush=True)
    json.dump(res, open(os.path.join(HERE, 'mutations_raw.json'), 'w'), indent=1)
