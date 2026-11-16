"""M2-F E-D03: do the output manifests cover every output file?  Answer measured here: NO. This test pins the CURRENT set of unmanifested files as a KNOWN GAP, so that
(a) any NEW unmanifested file, (b) any hash that does not match its file, (c) any manifest entry whose file is missing, or (d) any file that silently becomes manifested without the gap list being updated
FAILS. Nothing in reports/ is changed by this test (read-only on the delivered tree; the slow test writes to tmp_path).

Manifests checked: reports/m2c_data/manifest.json and reports/m2d_data/manifest.json (sha256_of_text = sha256 of the UNCOMPRESSED text of the .gz file), reports/m2e_data/<cycle>/manifest.json (sha256 of the file bytes),
reports/m2e_figures/<cycle>/figure_manifest.json and case_figure_manifest.json (data_csv_sha256, additional_data_csv[].sha256, and png_sha256_informational of every figure).

KNOWN GAP (files no manifest records), 28 files in a freshly generated baseline out root (27 in the delivered tree + the hand-written review_dispositions.json; chain.log exists only in a generated out root):
  1. the manifests themselves (8): m2c_data/manifest.json, m2d_data/manifest.json, m2e_data/<cycle>/manifest.json (2), m2e_figures/<cycle>/figure_manifest.json (2), case_figure_manifest.json (2)  [a manifest cannot hash itself]
  2. summaries and coverage that feed the reports (7): m2c_data/m2c_summary.json, m2d_data/m2d_summary.json, m2e_data/m2e_summary.json, m2e_data/<cycle>/coverage.json (2), m2e_data/<cycle>/case_studies.json (2)
  3. figures of the m2c and m2d stages, which have NO figure manifest at all (11): m2c_figures/m2c_batch_map_<cycle>_D0.{csv,png} (4), m2c_precision_sensitivity.png, m2c_threshold_sensitivity.{csv,png} (2),
     m2d_figures/m2d_candidates_per_wing.csv, m2d_dt_hist_W1.csv, m2d_group_ratio_hist.csv, m2d_overview.png
  4. reports/M2E_POSITION_CASE_STUDIES.md (1), the generated case-study report text
  5. chain.log of r1c_scenario_run.py (1, generated out root only) and reports/m2e_data/review_dispositions.json (1, delivered tree only; hand-written, not produced by any generator)
Hash bases differ between stages (m2c/m2d: uncompressed payload; m2e: file bytes), which is why `_actual_sha` is per-manifest. PNG hashes are recorded as informational by the generators; they are checked here as well (they hold on the reference
environment, docs/ENVIRONMENT.md)."""
import gzip, hashlib, json, os, subprocess, sys
import pytest
from conftest import PE

CYCLES = ('NIFTY_2026-06-30', 'SENSEX_2026-07-16')
DELIVERED_ROOTS = ('reports/m2c_data', 'reports/m2c_figures', 'reports/m2d_data', 'reports/m2d_figures', 'reports/m2e_data', 'reports/m2e_figures')
GAP_MANIFESTS = ['reports/m2c_data/manifest.json', 'reports/m2d_data/manifest.json'] + [f'reports/m2e_data/{c}/manifest.json' for c in CYCLES] + \
                [f'reports/m2e_figures/{c}/{n}' for c in CYCLES for n in ('figure_manifest.json', 'case_figure_manifest.json')]
GAP_SUMMARIES = ['reports/m2c_data/m2c_summary.json', 'reports/m2d_data/m2d_summary.json', 'reports/m2e_data/m2e_summary.json'] + [f'reports/m2e_data/{c}/{n}' for c in CYCLES for n in ('coverage.json', 'case_studies.json')]
GAP_STAGE_FIGURES = [f'reports/m2c_figures/m2c_batch_map_{c}_D0.{e}' for c in CYCLES for e in ('csv', 'png')] + ['reports/m2c_figures/m2c_precision_sensitivity.png', 'reports/m2c_figures/m2c_threshold_sensitivity.csv', 'reports/m2c_figures/m2c_threshold_sensitivity.png',
                     'reports/m2d_figures/m2d_candidates_per_wing.csv', 'reports/m2d_figures/m2d_dt_hist_W1.csv', 'reports/m2d_figures/m2d_group_ratio_hist.csv', 'reports/m2d_figures/m2d_overview.png']
GAP_REPORT_TEXT = ['reports/M2E_POSITION_CASE_STUDIES.md']
KNOWN_GAP_GENERATED = set(GAP_MANIFESTS + GAP_SUMMARIES + GAP_STAGE_FIGURES + GAP_REPORT_TEXT + ['chain.log'])
KNOWN_GAP_DELIVERED = set(GAP_MANIFESTS + GAP_SUMMARIES + GAP_STAGE_FIGURES + GAP_REPORT_TEXT + ['reports/m2e_data/review_dispositions.json'])


def _sha(b): return hashlib.sha256(b).hexdigest()


def _read(root, rel): return open(os.path.join(root, *rel.split('/')), 'rb').read()


def list_files(root, whole):
    """whole=True: every file under root (a generated out root); False: the six delivered output roots plus the generated case-study text (reports/ holds many hand-written documents too)"""
    if whole: return {os.path.relpath(os.path.join(d, f), root).replace(os.sep, '/') for d, _, fs in os.walk(root) for f in fs}
    out = {os.path.relpath(os.path.join(d, f), root).replace(os.sep, '/') for r in DELIVERED_ROOTS for d, _, fs in os.walk(os.path.join(root, r)) for f in fs}
    return out | {'reports/M2E_POSITION_CASE_STUDIES.md'}


def audit(root, whole):
    """-> dict(files, covered={rel: manifest it is recorded in}, mismatched=[...], missing=[...], unmanifested=sorted list)"""
    covered, mismatched, missing = {}, [], []
    def rec(rel, expect, manifest, actual):
        covered.setdefault(rel, manifest)
        if not os.path.isfile(os.path.join(root, *rel.split('/'))): missing.append((manifest, rel)); return
        if actual(rel) != expect: mismatched.append((manifest, rel))
    for d in ('m2c_data', 'm2d_data'):                                                                   # hash of the uncompressed text of the .gz
        mf = f'reports/{d}/manifest.json'
        for n, v in json.loads(_read(root, mf))['files'].items(): rec(f'reports/{d}/{n}', v['sha256_of_text'], mf, lambda r: _sha(gzip.decompress(_read(root, r))))
    for c in CYCLES:
        mf = f'reports/m2e_data/{c}/manifest.json'
        for n, v in json.loads(_read(root, mf))['files'].items(): rec(f'reports/m2e_data/{c}/{n}', v['sha256'], mf, lambda r: _sha(_read(root, r)))
        for name in ('figure_manifest.json', 'case_figure_manifest.json'):
            mf = f'reports/m2e_figures/{c}/{name}'
            for fig in json.loads(_read(root, mf))['figures']:
                pairs = [(fig['png'], fig['png_sha256_informational']), (fig['data_csv'], fig['data_csv_sha256'])] + [(x['data_csv'], x['sha256']) for x in fig.get('additional_data_csv', [])]
                for rel, h in pairs: rec(rel, h, mf, lambda r: _sha(_read(root, r)))
    files = list_files(root, whole)
    return dict(files=files, covered=covered, mismatched=sorted(mismatched), missing=sorted(missing), unmanifested=sorted(files - set(covered)), outside=sorted(set(covered) - files))


def _assert_pinned(res, gap, n_files):
    assert not res['mismatched'], f"manifest hash does not match its file: {res['mismatched']}"
    assert not res['missing'], f"manifest lists a file that does not exist: {res['missing']}"
    assert not res['outside'], f"manifest records a path outside the checked file set: {res['outside']}"
    new = sorted(set(res['unmanifested']) - gap); healed = sorted(gap - set(res['unmanifested']))
    assert not new, f'NEW files not recorded in any manifest (E-D03 gap grew): {new}'
    assert not healed, f'files in the KNOWN GAP list are now manifested or gone: update the list and the docstring: {healed}'
    assert len(res['files']) == n_files and len(res['covered']) == n_files - len(gap)


def test_delivered_outputs_manifest_coverage_equals_the_pinned_known_gap():
    res = audit(PE, whole=False)
    _assert_pinned(res, KNOWN_GAP_DELIVERED, 168)                                                       # 168 delivered output files, 140 recorded in a manifest, 28 not (KNOWN_GAP_DELIVERED)
    assert len(res['covered']) == 140 and len(KNOWN_GAP_DELIVERED) == 28


@pytest.mark.slow
def test_freshly_generated_baseline_outputs_manifest_coverage_equals_the_pinned_known_gap(tmp_path):
    out = tmp_path / 'out'
    p = subprocess.run([sys.executable, os.path.join(PE, 'tools', 'r1c_scenario_run.py'), '--scenario=baseline', f'--out-root={out}'], capture_output=True, text=True); assert p.returncode == 0, p.stderr[-800:]
    res = audit(str(out), whole=True)
    _assert_pinned(res, KNOWN_GAP_GENERATED, 169 + 1)                                                   # 169 files in the delivered roots + case-study text (incl. 2 scenario-only intra-second flag files) + chain.log; 142 recorded
    assert len(res['covered']) == 142 and len(KNOWN_GAP_GENERATED) == 28
    flags = {f'reports/m2e_data/{c}/inventory_series_intra_second_flags.tsv' for c in CYCLES}; assert flags <= set(res['covered'])      # the only generated files that are manifested but not delivered


def _mini_tree(root):
    """a minimal tree in the shape of the real outputs: one m2c-style gz manifest, one m2e cycle manifest, one figure manifest (png + csv + additional csv) and one case manifest, for both cycles"""
    def w(rel, b):
        p = os.path.join(root, *rel.split('/')); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, 'wb').write(b)
    def j(rel, o): w(rel, json.dumps(o).encode())
    w('reports/m2c_data/a.tsv.gz', gzip.compress(b'h\nx\n', mtime=0)); j('reports/m2c_data/manifest.json', dict(files={'a.tsv.gz': dict(sha256_of_text=_sha(b'h\nx\n'))}))
    w('reports/m2d_data/b.tsv.gz', gzip.compress(b'h\ny\n', mtime=0)); j('reports/m2d_data/manifest.json', dict(files={'b.tsv.gz': dict(sha256_of_text=_sha(b'h\ny\n'))}))
    for c in CYCLES:
        w(f'reports/m2e_data/{c}/f.tsv', b'h\nz\n'); j(f'reports/m2e_data/{c}/manifest.json', dict(files={'f.tsv': dict(sha256=_sha(b'h\nz\n'))}))
        w(f'reports/m2e_figures/{c}/V1.png', b'PNG'); w(f'reports/m2e_figures/{c}/V1.csv', b'c1'); w(f'reports/m2e_figures/{c}/V1__x.csv', b'c2'); w(f'reports/m2e_figures/{c}/cases/C.png', b'PNG2'); w(f'reports/m2e_figures/{c}/cases/C.csv', b'c3')
        d = f'reports/m2e_figures/{c}'
        j(f'{d}/figure_manifest.json', dict(figures=[dict(png=f'{d}/V1.png', png_sha256_informational=_sha(b'PNG'), data_csv=f'{d}/V1.csv', data_csv_sha256=_sha(b'c1'), additional_data_csv=[dict(data_csv=f'{d}/V1__x.csv', sha256=_sha(b'c2'))])]))
        j(f'{d}/case_figure_manifest.json', dict(figures=[dict(png=f'{d}/cases/C.png', png_sha256_informational=_sha(b'PNG2'), data_csv=f'{d}/cases/C.csv', data_csv_sha256=_sha(b'c3'), additional_data_csv=[])]))
    w('reports/m2e_data/m2e_summary.json', b'{}')


def test_the_audit_itself_detects_altered_hashes_missing_files_and_new_unmanifested_files(tmp_path):
    _mini_tree(str(tmp_path)); res = audit(str(tmp_path), whole=True)
    assert not res['mismatched'] and not res['missing'] and not res['outside']
    assert set(res['unmanifested']) == set(GAP_MANIFESTS) | {'reports/m2e_data/m2e_summary.json'}        # exactly the manifests themselves + the summary; the 6 data/figure files per cycle and the 2 gz files are covered
    assert len(res['covered']) == 2 + 2 * 6 and res['covered']['reports/m2e_figures/NIFTY_2026-06-30/V1__x.csv'] == 'reports/m2e_figures/NIFTY_2026-06-30/figure_manifest.json'
    for rel, body in (('reports/m2e_data/NIFTY_2026-06-30/f.tsv', b'h\nZ\n'), ('reports/m2e_figures/SENSEX_2026-07-16/V1.png', b'PNX'), ('reports/m2d_data/b.tsv.gz', gzip.compress(b'h\nq\n', mtime=0)), ('reports/m2e_figures/NIFTY_2026-06-30/cases/C.csv', b'c4')):
        old = _read(str(tmp_path), rel); open(os.path.join(tmp_path, *rel.split('/')), 'wb').write(body); r = audit(str(tmp_path), whole=True)
        assert [x[1] for x in r['mismatched']] == [rel], rel; open(os.path.join(tmp_path, *rel.split('/')), 'wb').write(old)
    os.remove(tmp_path / 'reports/m2e_figures/NIFTY_2026-06-30/V1__x.csv'); r = audit(str(tmp_path), whole=True); assert [x[1] for x in r['missing']] == ['reports/m2e_figures/NIFTY_2026-06-30/V1__x.csv']
    open(tmp_path / 'reports/m2e_data/NIFTY_2026-06-30/extra.tsv', 'wb').write(b'new'); r = audit(str(tmp_path), whole=True); assert 'reports/m2e_data/NIFTY_2026-06-30/extra.tsv' in r['unmanifested']
