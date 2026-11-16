"""Decision B (owner-approved 2026-11-16): per-fill zero-crossing reversal (primary) and parent-level same-second net sign flip (diagnostic) are reported SEPARATELY and never merged.
Pinned numbers are re-derived here from the loader's fills with an independent loop (not from pe.reversals / pe.replay); wording changes are guarded line by line."""
import collections, csv, difflib, json, os, re
import pytest
from conftest import PE, REPO
from pe import reversals as RV

APPROVED_SENTENCE = ('No per-fill zero-crossing reversal was observed in the frozen cycle; one parent-level same-second sign flip is present under the approved diagnostic definition.')
BEFORE = {'M2E_POSITION_CASE_STUDIES.md': 'reports/M2E_POSITION_CASE_STUDIES.md', 'M2E_CYCLE_COVERAGE_REPORT.md': 'reports/M2E_CYCLE_COVERAGE_REPORT.md',
          'M2E_HISTORICAL_FORENSICS_REPORT.md': 'reports/M2E_HISTORICAL_FORENSICS_REPORT.md', 'review_dispositions.json': 'reports/m2e_data/review_dispositions.json'}


def _independent(policy):
    """own loop: baseline = (second, source row); hybrid = (second, [NIFTY: trade id | SENSEX: embedded ns time if consistent with the epoch else epoch*1e9], source row) inside each (instrument, second), slots of the baseline order kept"""
    from pe.generators import historical as H
    ins, fills, _ = H.generate(REPO); raw = list(csv.reader(open(os.path.join(REPO, 'Trades_GKOHNP140.csv'), newline='')))
    def key(f):
        rr = raw[f.source_row_id]
        if rr[12] == 'SENSEX': ns = int(rr[28].split('-')[0]); return ns if (ns + 500_000_000) // 10**9 == f.timestamp_s else f.timestamp_s * 10**9
        return int(rr[28])
    base = sorted(fills, key=lambda f: (f.timestamp_s, f.source_row_id)); order = list(base)
    if policy == 'hybrid':
        slots = collections.defaultdict(list)
        for i, f in enumerate(base): slots[(f.timestamp_s, f.instrument_id)].append(i)
        for idx in slots.values():
            for i, f in zip(idx, sorted((base[i] for i in idx), key=lambda f: (key(f), f.source_row_id))): order[i] = f
    return ins, order


def _count(order, ins, select=None):
    sgn = lambda x: (x > 0) - (x < 0); inv = collections.defaultdict(int); pf = 0; grp = {}
    for f in order:
        if select and f.instrument_id not in select: continue
        b = inv[f.instrument_id]; a = b + f.side * f.quantity; inv[f.instrument_id] = a
        pf += sgn(b) * sgn(a) < 0; k = (f.instrument_id, f.parent_order_id, f.timestamp_s); g = grp.setdefault(k, [b, a]); g[1] = a
    return pf, sum(1 for b, a in grp.values() if sgn(b) * sgn(a) < 0)


@pytest.mark.slow
def test_reported_values_are_reproduced_independently_for_both_scenarios():
    exp = {'baseline': {'full': (23, 26), 'NIFTY': (1, 1), 'SENSEX': (0, 1)}, 'hybrid': {'full': (21, 22), 'NIFTY': (1, 1), 'SENSEX': (0, 1)}}
    pub = json.load(open(os.path.join(PE, 'reports', 'r1c_dual_scenario', 'reversal_measures.json')))['results']
    for pol, name in (('baseline', 'baseline'), ('hybrid', 'per_contract_id_sequence')):
        ins, order = _independent(pol)
        sel = {'full': None, 'NIFTY': {i for i, x in ins.items() if x.underlying == 'NIFTY' and x.expiry == '2026-06-30'}, 'SENSEX': {i for i, x in ins.items() if x.underlying == 'SENSEX' and x.expiry == '2026-07-16'}}
        for k, s in sel.items():
            assert _count(order, ins, s) == exp[pol][k], (pol, k)
            key = {'full': 'full_ledger', 'NIFTY': 'NIFTY_2026-06-30', 'SENSEX': 'SENSEX_2026-07-16'}[k]; c = pub[key][name]['counts']
            assert (c[RV.PER_FILL], c[RV.PARENT_LEVEL]) == exp[pol][k]                                                              # the published JSON agrees


def test_the_measures_are_not_nested_in_the_published_data_and_sentence_is_exact():
    pub = json.load(open(os.path.join(PE, 'reports', 'r1c_dual_scenario', 'reversal_measures.json')))['results']
    assert pub['full_ledger']['baseline']['parent_level_without_a_per_fill_event'] == 3 and pub['full_ledger']['baseline']['per_fill_without_a_parent_level_flip'] == 0
    assert pub['SENSEX_2026-07-16']['baseline']['sentence'].startswith(APPROVED_SENTENCE.replace('the frozen cycle', 'SENSEX 2026-07-16')[:60])
    assert RV.sentence(0, 1) == APPROVED_SENTENCE and RV.sentence(1, 1).startswith('1 per-fill zero-crossing reversal was observed') and RV.sentence(2, 0) == '2 per-fill zero-crossing reversals were observed in the frozen cycle; no parent-level same-second sign flip is present under the approved diagnostic definition.'


def test_published_tables_use_the_two_measures_and_never_the_old_unqualified_claim():
    for rel in BEFORE.values():
        t = open(os.path.join(PE, rel)).read()
        assert 'SENSEX has no reversal' not in t and 'Reversal in SENSEX | none' not in t and 'Only NIFTY has a reversal' not in t, rel
    assert APPROVED_SENTENCE in open(os.path.join(PE, 'reports', 'M2E_POSITION_CASE_STUDIES.md')).read()
    assert APPROVED_SENTENCE in open(os.path.join(PE, 'reports', 'M2E_CYCLE_COVERAGE_REPORT.md')).read()


def test_the_delivered_fills_table_gives_the_same_measures_as_the_engine_order():
    from pe import forensics as F
    for cy, want in (('NIFTY_2026-06-30', (1, 1)), ('SENSEX_2026-07-16', (0, 1))):
        rows = F.read_tsv_text(open(os.path.join(PE, 'reports', 'm2e_data', cy, 'fills.tsv')).read())[1]; c = RV.from_table_rows(rows)['counts']
        assert (c[RV.PER_FILL], c[RV.PARENT_LEVEL]) == want


def test_only_approved_reversal_lines_changed_and_data_are_unchanged():
    import hashlib
    removed_ok = [re.compile(p) for p in (r'SENSEX has no reversal', r'Reversal in SENSEX', r'Only NIFTY has a reversal')]
    added_ok = [re.compile(p) for p in (r'Reversal measures', r'per-fill zero-crossing', r'parent-level same-second', r'^\+$', r'^\+UNAVAILABLE items are reported, not substituted\. Neither frozen cycle has a position that expired unclosed\.$')]
    changed = 0
    for name, rel in BEFORE.items():
        old = open(os.path.join(PE, 'reports', 'm2f_audit', 'decision_b', 'before', name)).read().split('\n'); new = open(os.path.join(PE, rel)).read().split('\n')
        for l in difflib.unified_diff(old, new, lineterm='', n=0):
            if l.startswith(('---', '+++', '@@')): continue
            changed += 1
            if l.startswith('-'): assert any(p.search(l) for p in removed_ok), f'{rel}: removed line is not approved: {l[:110]}'
            else: assert any(p.search(l) for p in added_ok), f'{rel}: added line is not approved: {l[:110]}'
    assert changed > 0
    base = json.load(open(os.path.join(PE, 'reports', 'm2f_audit', 'r1', 'baseline_sha256_before_R1.json')))['sha256']
    for cy in ('NIFTY_2026-06-30', 'SENSEX_2026-07-16'):
        for name in ('case_studies.json', 'episodes.tsv', 'lifecycle_events.tsv', 'fills.tsv', 'coverage.json'):
            rel = f'portfolio_engine/reports/m2e_data/{cy}/{name}'; assert hashlib.sha256(open(os.path.join(REPO, rel), 'rb').read()).hexdigest() == base[rel], rel


def test_published_counts_are_the_owner_table_fast_pin():
    """pinned to the values re-derived independently by test_reported_values_are_reproduced_independently_for_both_scenarios (slow)"""
    pub = json.load(open(os.path.join(PE, 'reports', 'r1c_dual_scenario', 'reversal_measures.json')))['results']
    want = {('full_ledger', 'baseline'): (23, 26), ('full_ledger', 'per_contract_id_sequence'): (21, 22), ('NIFTY_2026-06-30', 'baseline'): (1, 1), ('NIFTY_2026-06-30', 'per_contract_id_sequence'): (1, 1),
            ('SENSEX_2026-07-16', 'baseline'): (0, 1), ('SENSEX_2026-07-16', 'per_contract_id_sequence'): (0, 1)}
    for (k, sc), (a, b) in want.items(): assert (pub[k][sc]['counts'][RV.PER_FILL], pub[k][sc]['counts'][RV.PARENT_LEVEL]) == (a, b), (k, sc)
