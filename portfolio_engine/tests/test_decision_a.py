"""Decision A (owner-approved 2026-11-16): case-selection wording. The selection is STRUCTURAL, PRICE-FREE and OUTCOME-FREE (tested); the rules were committed with the outputs;
Git history does NOT show that they were prospectively fixed. The 17 case records and every dataset are unchanged; only approved documentation lines changed."""
import difflib, importlib, json, os, re, shutil, subprocess, sys
import pytest
from conftest import PE, REPO
from pe import cases as K

DOCS = ['portfolio_engine/reports/M2E_POSITION_CASE_STUDIES.md', 'portfolio_engine/reports/M2E_HISTORICAL_FORENSICS_REPORT.md', 'portfolio_engine/reports/m2e_data/review_dispositions.json']
LINT_FILES = ['python/pe/cases.py', 'tools/m2e_cases.py', 'reports/M2E_POSITION_CASE_STUDIES.md', 'reports/M2E_HISTORICAL_FORENSICS_REPORT.md', 'reports/m2e_data/review_dispositions.json', 'docs/EVIDENCE_REGISTRY.md']
FORBIDDEN = [re.compile(r'\bpredefined\b', re.I), re.compile(r'fixed before any case', re.I), re.compile(r'written in code before cases were viewed', re.I)]
PROSPECTIVE_OK = ('not shown to have been prospectively fixed', 'NOT SHOWN TO HAVE BEEN PROSPECTIVELY FIXED', 'does not establish that the individual case rules were prospectively fixed',
                  'not shown to be prospectively fixed', 'not prospectively fixed', 'any claim of prospective preregistration')


@pytest.mark.parametrize('rel', LINT_FILES)
def test_wording_lint_no_unsupported_prospective_selection_claim(rel):
    text = open(os.path.join(PE, rel)).read()
    for pat in FORBIDDEN: assert not pat.search(text), f'{rel}: unsupported wording {pat.pattern!r}'
    for m in re.finditer(r'prospectiv', text, re.I):
        ctx = text[max(0, m.start() - 90): m.end() + 60]
        assert any(ok.lower() in ctx.lower() for ok in PROSPECTIVE_OK), f'{rel}: "prospective" outside a negated disclosure: ...{ctx}...'


def test_terminology_and_statement_are_exactly_the_approved_text():
    assert K.SELECTION_TERMINOLOGY == 'STRUCTURAL, PRICE-FREE, OUTCOME-FREE (TESTED); SELECTION RULES COMMITTED WITH THE OUTPUTS; NOT SHOWN TO HAVE BEEN PROSPECTIVELY FIXED.'
    assert K.SELECTION_STATEMENT == ('Cases were selected using structural, price-independent rules. Outcome-free behavior was tested by perturbing fill prices, and all selections remained unchanged. '
                                     'The selection code was committed with the outputs; available Git history does not establish that the individual case rules were prospectively fixed before inspection.')
    md = open(os.path.join(PE, 'reports', 'M2E_POSITION_CASE_STUDIES.md')).read()
    assert K.SELECTION_STATEMENT in md and f'`{K.SELECTION_TERMINOLOGY}`' in md and md.count('Selection rule (structural, price-free, outcome-free (tested); chronological first') == 17


def test_generated_case_header_uses_the_corrected_wording():
    sys.path.insert(0, os.path.join(PE, 'tools')); mod = importlib.import_module('m2e_cases'); cy = 'NIFTY_2026-06-30'
    rec = json.load(open(os.path.join(PE, 'reports', 'm2e_data', cy, 'case_studies.json')))['records']['CT1_INCREMENTAL_OPENING']
    out = mod.render(rec, cy); assert 'Selection rule (structural, price-free, outcome-free (tested)' in out and 'predefined' not in out.lower()


def test_sample_profile_and_d0_eligibility_hand_calculated():
    P = K.sample_profile([('A', 'D-1', '09'), ('A', 'D-1', '09'), ('B', 'D-1', '11')])
    assert P == dict(n=3, by_d_label={'D-1': 3}, d_minus_1_by_ist_hour={'09': 2, '11': 1}, no_d0=True)
    assert K.sample_profile([('A', 'D0', '09')])['no_d0'] is False
    D = dict(episodes=[dict(episode_id='e1', first_ts_utc_s='1', terminal_status='CLOSED'), dict(episode_id='e2', first_ts_utc_s='2', terminal_status='CLOSED'), dict(episode_id='e3', first_ts_utc_s='3', terminal_status='CLOSED'),
                       dict(episode_id='e4', first_ts_utc_s='9', terminal_status='CLOSED')],
             events=[dict(episode_id='e1', event_type=t) for t in ('ADDED', 'ADDED', 'ADDED', 'CLOSED')] + [dict(episode_id='e2', event_type=t) for t in ('PARTIALLY_REDUCED', 'PARTIALLY_REDUCED', 'CLOSED')] +
                    [dict(episode_id='e3', event_type='CLOSED')] + [dict(episode_id='e4', event_type=t) for t in ('ADDED', 'ADDED', 'ADDED')])
    lab = lambda ts: 'D0' if ts <= 3 else 'D-1'
    assert K.d0_eligibility(D, lab) == dict(d0_episodes=3, CT1=1, CT2=1, CT3=2)               # e1 (three ADDED, one CLOSED, no partial/reversal) and e3 both satisfy the CT3 predicate


def test_concentration_section_is_computed_and_matches_the_delivered_paragraph():
    P = K.sample_profile([('N', 'D-1', '09')] * 16 + [('S', 'D-1', '11')]); d0 = {'NIFTY_2026-06-30': dict(d0_episodes=51, CT1=17, CT2=14, CT3=21), 'SENSEX_2026-07-16': dict(d0_episodes=27, CT1=9, CT2=5, CT3=21)}
    lines = K.concentration_section(P, d0); assert lines[1] == '### 1.1 Sample concentration (computed from the selected case records)'
    md = open(os.path.join(PE, 'reports', 'M2E_POSITION_CASE_STUDIES.md')).read(); assert '\n'.join(lines[1:]) in md           # the delivered paragraph is exactly what the function produces for the 17 records and the measured D0 counts
    assert '**no selected case begins on D0**' in lines[3] and '**no selected case begins on D0**' not in K.concentration_section(K.sample_profile([('N', 'D0', '09')]), d0)[3]


def test_case_records_and_datasets_are_unchanged_since_before_decision_a():
    import hashlib
    base = json.load(open(os.path.join(PE, 'reports', 'm2f_audit', 'r1', 'baseline_sha256_before_R1.json')))['sha256']
    for cy in ('NIFTY_2026-06-30', 'SENSEX_2026-07-16'):
        for name in ('case_studies.json', 'episodes.tsv', 'lifecycle_events.tsv', 'opening_items.tsv', 'fills.tsv', 'coverage.json'):
            rel = f'portfolio_engine/reports/m2e_data/{cy}/{name}'
            assert hashlib.sha256(open(os.path.join(REPO, rel), 'rb').read()).hexdigest() == base[rel], rel            # byte-identical to the pre-R1 baseline (562d7eb6): no case record or dataset changed


def _lines(t): return t.split('\n')


def test_only_approved_documentation_lines_changed():
    """every changed line of the three delivered documents removes an unsupported phrase / adds the corrected disclosure; all other lines are byte-identical"""
    removed_ok = [re.compile(p, re.I) for p in (r'predefined', r'fixed before any case', r'written in code before cases were viewed', r'SENSEX has no reversal', r'Only NIFTY has a reversal')]          # the last two are Decision B's approved edits
    added_ok = [re.compile(p) for p in (r'structural, price-free, outcome-free', r'Terminology', r'Cases were selected using structural', r'Sample concentration', r'Of the 17 selected case records', r'^$', r'Reversal measures', r'per-fill zero-crossing', r'parent-level same-second', r'^UNAVAILABLE items are reported, not substituted\. Neither frozen cycle has a position that expired unclosed\.$')]
    total_changed = 0
    for rel in DOCS:
        old = _lines(open(os.path.join(PE, 'reports', 'm2f_audit', 'decision_a', 'before', os.path.basename(rel))).read()); new = _lines(open(os.path.join(REPO, rel)).read())
        for l in difflib.unified_diff(old, new, lineterm='', n=0):
            if l.startswith(('---', '+++', '@@')): continue
            total_changed += 1
            if l.startswith('-'): assert any(p.search(l) for p in removed_ok), f'{rel}: removed line is not an approved wording line: {l[:120]}'
            else: assert any(p.search(l[1:]) or p.search(l) for p in added_ok), f'{rel}: added line is not approved text: {l[:120]}'
    assert total_changed > 0


@pytest.mark.slow
def test_case_selection_is_invariant_under_upstream_price_scrambling(tmp_path):
    """the WHOLE upstream pipeline (ledger -> lineage -> batches -> wing/body -> datasets -> selection) is re-run on a mirror whose fill-ledger prices are scrambled; the selections must not move"""
    import pandas as pd
    root = tmp_path / 'repo'; pe = root / 'portfolio_engine'; os.makedirs(pe / 'reports')
    for d in ('python', 'tools'): shutil.copytree(os.path.join(PE, d), pe / d, ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copy(os.path.join(PE, 'reports', 'demo_cycle_scores.csv'), pe / 'reports' / 'demo_cycle_scores.csv')
    gen = pe / 'python' / 'pe' / 'generators' / 'historical.py'; src = gen.read_text(); call = '    verify_ledger_against_raw(repo_root, list(L.itertuples()))'
    assert src.count(call) == 1; gen.write_text(src.replace(call, '    pass'))       # D-A02: the production generator rightly REJECTS a ledger that differs from the raw csv; this counterfactual experiment needs the unverified path, so only the MIRROR's copy has the check removed
    tp = root / 'tp_reconstruction'; os.makedirs(tp / 'data')
    for n in os.listdir(os.path.join(REPO, 'tp_reconstruction')):
        if n != 'data': os.symlink(os.path.join(REPO, 'tp_reconstruction', n), tp / n)
    for n in os.listdir(os.path.join(REPO, 'tp_reconstruction', 'data')):
        if n != 'fill_event_ledger.parquet': os.symlink(os.path.join(REPO, 'tp_reconstruction', 'data', n), tp / 'data' / n)
    L = pd.read_parquet(os.path.join(REPO, 'tp_reconstruction', 'data', 'fill_event_ledger.parquet')); orig = L.px_fill.copy(); L['px_fill'] = L.px_fill.sample(frac=1, random_state=7).values
    assert (L.px_fill.values != orig.values).mean() > 0.5; L.to_parquet(tp / 'data' / 'fill_event_ledger.parquet'); os.symlink(os.path.join(REPO, 'Trades_GKOHNP140.csv'), root / 'Trades_GKOHNP140.csv')
    out = tmp_path / 'scrambled'
    p = subprocess.run([sys.executable, str(pe / 'tools' / 'r1c_scenario_run.py'), '--scenario=baseline', f'--out-root={out}'], capture_output=True, text=True, cwd=root); assert p.returncode == 0, p.stderr[-1500:]
    for cy in ('NIFTY_2026-06-30', 'SENSEX_2026-07-16'):
        a = json.load(open(os.path.join(PE, 'reports', 'm2e_data', cy, 'case_studies.json'))); b = json.load(open(out / 'reports' / 'm2e_data' / cy / 'case_studies.json'))
        assert a['selection'] == b['selection'] and a['selection_rules'] == b['selection_rules']                                           # the selections did not move
        assert open(out / 'reports' / 'm2e_data' / cy / 'fills.tsv').read() != open(os.path.join(PE, 'reports', 'm2e_data', cy, 'fills.tsv')).read()      # and the prices really changed upstream
        for n in ('episodes.tsv', 'lifecycle_events.tsv'): assert open(out / 'reports' / 'm2e_data' / cy / n).read() == open(os.path.join(PE, 'reports', 'm2e_data', cy, n)).read(), n


def test_selection_code_reads_no_price_or_outcome_column():
    """static complement of the scrambling test (closure review CR-06): the scrambling test only perturbs the ledger px_fill column, so a rule that read price elsewhere (raw csv, another column) would pass it.
    The selection functions must not mention price, P&L or the raw csv at all."""
    import inspect, re
    src = ''.join(inspect.getsource(f) for f in (K.select, K._cands, K.episode_of_fill, K.load_data, K.sample_profile, K.d0_eligibility))
    for tok in ('price', 'px_', 'paise', 'pnl', 'profit', 'realized', 'Trades_GKOHNP140', 'csv.reader', 'read_csv', 'read_parquet'):
        assert not re.search(tok, src, re.I), f'selection code mentions {tok!r}'
