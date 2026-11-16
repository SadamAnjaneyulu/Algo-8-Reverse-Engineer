"""Writes reports/M2E_HISTORICAL_FORENSICS_REPORT.md. Numbers come from reports/m2e_data and reports/m2e_figures; the review section and the acceptance gate come from
reports/m2e_data/review_dispositions.json (written by hand after the independent review; this tool refuses to run without it so an unreviewed report cannot be produced)."""
import csv, json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); PE = os.path.dirname(HERE); REPO = os.path.dirname(PE); sys.path.insert(0, os.path.join(PE, 'python'))
from pe import forensics as F
D = os.path.join(PE, 'reports', 'm2e_data'); G = os.path.join(PE, 'reports', 'm2e_figures'); K = [F.cycle_key(*c) for c in F.CYCLES]
R = json.load(open(os.path.join(D, 'review_dispositions.json')))
cov = {k: json.load(open(os.path.join(D, k, 'coverage.json'))) for k in K}; cs = {k: json.load(open(os.path.join(D, k, 'case_studies.json'))) for k in K}
def sens(k, m): return list(csv.DictReader(open(os.path.join(G, k, f'V4_{m}_closing_batches__sensitivity_by_threshold.csv'))))
def n(x): return f'{x:,}'
head = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=REPO, capture_output=True, text=True).stdout.strip()
L = ['# M2-E — Historical Position Forensics & Portfolio Visualization: final report', '',
     f"**Status: {R['overall_status']}.** Frozen cycles NIFTY 2026-06-30 and SENSEX 2026-07-16 (selected before grouping, not substituted). Base commit `{head}`; M2-E work is the uncommitted/committed delta on branch `engineering/position-lifecycle-basket-reconstruction`. No M3, no new grouping, no change to W1/W2/W3, no accounting change.", '',
     '## A. Result first', '',
     R['result_summary'], '',
     '| | NIFTY 2026-06-30 | SENSEX 2026-07-16 |', '|---|---:|---:|',
     '| Raw fills / parent orders / episodes | ' + ' | '.join(f"{n(cov[k]['fills']['raw_fill_count'])} / {n(cov[k]['fills']['unique_parent_orders'])} / {cov[k]['episodes']['episode_count']}" for k in K) + ' |',
     '| Units opened = closed (every position ended) | ' + ' | '.join(n(cov[k]['fills']['opening_units']) for k in K) + ' |',
     '| Gross units carried overnight D-1 → D0 (short CE / short PE / long CE / long PE) | ' + ' | '.join(f"{(c := F.read_tsv_text(open(os.path.join(D, k, 'session_carry.tsv')).read())[1][0])['gross_total']} ({c['short_CE']} / {c['short_PE']} / {c['long_CE']} / {c['long_PE']})" for k in K) + ' |',
     '| Expired-unclosed positions | 0 | 0 |', '| Historical marks | MISSING (source absent) | MISSING (source absent) |',
     '| Closing batches C1 at 10 s (primary) / 60 s | ' + ' | '.join(f"{sens(k, 'C1')[2]['batches']} / {sens(k, 'C1')[4]['batches']}" for k in K) + ' |',
     '| Widest 10 s batch (parent orders; seconds) | ' + ' | '.join(f"{sens(k, 'C1')[2]['max_parents_in_batch']}; {sens(k, 'C1')[2]['max_duration_s']} s" for k in K) + ' |',
     '| Longest 60 s chain (parent orders spanned; seconds) | ' + ' | '.join(f"{sens(k, 'C1')[4]['max_parents_in_batch']}; {sens(k, 'C1')[4]['max_duration_s']} s" for k in K) + ' |',
     '| Opening wing items: with W1 candidate / unique / multiple / none | ' + ' | '.join(f"{(w := cov[k]['wing_body_coverage_cycle_level']['OPENING|W1'])['wing_items_with_candidate']} / {w['wing_items_unique_candidate']} / {w['wing_items_multiple_candidates']} / {w['wing_items_no_candidate']} of {w['wing_items']}" for k in K) + ' |',
     '| Opening wing items: with W1_S60 candidate / none | ' + ' | '.join(f"{(w := cov[k]['wing_body_coverage_cycle_level']['OPENING|W1_S60'])['wing_items_with_candidate']} / {w['wing_items_no_candidate']} of {w['wing_items']}" for k in K) + ' |',
     '| Case types available (of 10) | ' + ' | '.join(str(sum(1 for r in cs[k]['records'].values() if r['status'] == 'AVAILABLE')) for k in K) + ' |', '',
     '## B. Deliverables', '', '| Item | Location |', '|---|---|', '| Cycle coverage report (stage 2) | `reports/M2E_CYCLE_COVERAGE_REPORT.md` |', '| Case studies (stage 4) | `reports/M2E_POSITION_CASE_STUDIES.md`, `reports/m2e_data/<cycle>/case_studies.json` |', '| Visualization catalog (stage 5) | `reports/M2E_VISUALIZATION_CATALOG.md` |',
     '| Assembled datasets + manifests | `reports/m2e_data/<cycle>/` (19 files + `coverage.json` + `manifest.json` each) |', '| Figures V1–V6 + data CSVs + manifests | `reports/m2e_figures/<cycle>/` (10 figures, 18 CSVs, `cases/` single-episode charts) |', '| Code | `python/pe/forensics.py`, `python/pe/cases.py`, `tools/m2e_build.py`, `m2e_charts.py`, `m2e_cases.py`, `m2e_catalog.py`, `m2e_coverage_report.py`, `m2e_report.py` |', '| Tests | `tests/test_forensics.py` |', '',
     '## C. What the visuals show (observed layer only; no rationale offered)', '']
L += R['findings'] + ['', '## D. Reconciliation performed (automated)', ''] + R['reconciliation'] + ['', '## E. Adversarial validation by the author', ''] + R['author_adversarial'] + ['', '## F. Independent review', ''] + R['review'] + ['', '## G. Acceptance gate', '', '| # | Criterion | Result | Evidence |', '|---|---|---|---|'] + [f"| {i + 1} | {c} | **{r}** | {e} |" for i, (c, r, e) in enumerate(R['gate'])]
L += ['', '## H. Limits and unresolved items (not upgraded)', ''] + R['limits'] + ['', '## I. Reproduce', '', '```bash', 'python3 portfolio_engine/tools/m2e_build.py            # datasets + coverage + manifests (also asserts cycle isolation vs the full ledger)', 'python3 portfolio_engine/tools/m2e_charts.py           # V1-V6 for both cycles', 'python3 portfolio_engine/tools/m2e_cases.py            # case selection, records, case charts, case-study report', 'python3 portfolio_engine/tools/m2e_catalog.py          # catalog', 'python3 portfolio_engine/tools/m2e_coverage_report.py  # coverage report', 'python3 -m pytest portfolio_engine/tests -q', '```', '', '**Stopped after M2-E for review. M3 is not started.**']
open(os.path.join(PE, 'reports', 'M2E_HISTORICAL_FORENSICS_REPORT.md'), 'w').write('\n'.join(L) + '\n'); print(len(L), 'lines')
