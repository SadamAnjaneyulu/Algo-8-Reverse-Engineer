"""Decision C (owner-approved 2026-11-16): the closing-batch link rule stays INCLUSIVE (`gap <= threshold`); the exclusive reading (`gap < threshold`) exists only as a separate sensitivity artifact.
Exact-boundary behaviour is tested for every threshold, for C1 and C2, with hand-calculated expectations (two closing parents A at second 100 and B at 100 + gap)."""
import gzip, json, os
import pytest
from conftest import PE
from test_closing_batches import make, views_of, sets, CE
from pe import closing_batches as cb


def quick(ls):
    """views WITHOUT the built-in invariant check, so the boundary tests below fail by their own assertion; the invariants are checked separately (test_invariants_...)"""
    parents, un, multi = cb.closing_parents(ls); return parents, un, cb.all_views(parents)

THR = (2, 5, 10, 30, 60)


def two_parents(gap):
    ls, _ = make([('open', CE, 0, 130, 'o'), ('close', CE, 100, 65, 'A'), ('close', CE, 100 + gap, 65, 'B')]); parents, un, V = quick(ls); return ls, parents, un, V


@pytest.mark.parametrize('g', THR)
@pytest.mark.parametrize('m', ('C1', 'C2'))
def test_inclusive_boundary_below_at_and_above_every_threshold(g, m):
    for gap, joined in ((g - 1, True), (g, True), (g + 1, False)):                      # below: joined; exactly the threshold: joined; above: separated
        ls, parents, un, V = two_parents(gap); assert sets(V[(m, g)]) == ([['A', 'B']] if joined else [['A'], ['B']]), (m, g, gap)


@pytest.mark.parametrize('g', THR)
@pytest.mark.parametrize('m', ('C1', 'C2'))
def test_exclusive_sensitivity_boundary_below_at_and_above_every_threshold(g, m):
    for gap, joined in ((g - 1, True), (g, False), (g + 1, False)):                     # exclusive: the threshold itself separates
        ls, parents, un, V = two_parents(gap); v = cb.build_view(parents, m, g, inclusive=False)
        assert sets(v) == ([['A', 'B']] if joined else [['A'], ['B']]), (m, g, gap)


def _multi():
    spec = [('open', CE, 0, 650, 'o')] + [('close', CE, t, 65, f'P{i}') for i, t in enumerate((100, 110, 120, 131, 140, 140, 161, 221))]       # gaps 10, 10, 11, 9, 0, 21, 60
    ls, _ = make(spec); parents, un, multi, V = views_of(ls); return ls, parents, un, V


def test_invariants_hold_for_every_threshold_method_and_link_rule():
    ls, parents, un, V = _multi(); total = sum(r[8] for r in ls.cp.values()); assert total == 8 * 65
    for inclusive in (True, False):
        for m in ('C1', 'C2'):
            for g in THR:
                v = V[(m, g)] if inclusive else cb.build_view(parents, m, g, inclusive=False); cb.check_view(v, parents, ls.cp, un)
                keys = [p.key for b in v['batches'] for p in b['members']]; assert sorted(keys) == sorted(p.key for p in parents) and len(set(keys)) == len(keys)         # every parent exactly once
                assert sum(p.qty for b in v['batches'] for p in b['members']) == total                                                                                    # quantity conserved
                ids = [b['batch_id'] for b in v['batches']]; assert len(set(ids)) == len(ids)                                                                              # no duplicate batch ids
                v2 = V[(m, g)] if inclusive else cb.build_view(parents, m, g, inclusive=False); assert [b['batch_id'] for b in v2['batches']] == ids                           # stable ids on identical input


def test_hand_calculated_inclusive_and_exclusive_partitions_of_the_multi_parent_case():
    ls, parents, un, V = _multi()                     # parents P0..P7 at seconds 100,110,120,131,140,140,161,221 (gaps 10,10,11,9,0,21,60)
    assert sets(V[('C1', 10)]) == [['P0', 'P1', 'P2'], ['P3', 'P4', 'P5'], ['P6'], ['P7']]      # 10 joins (inclusive): P0-P1, P1-P2; 11 splits; 9, 0 join; 21 splits; 60 > 10 splits
    assert sets(cb.build_view(parents, 'C1', 10, inclusive=False)) == [['P0'], ['P1'], ['P2'], ['P3', 'P4', 'P5'], ['P6'], ['P7']]      # exclusive: the exact 10 s gaps (P0-P1, P1-P2) no longer join; 9 and 0 still join


def test_provenance_identifies_the_link_semantics_and_the_primary_is_unchanged():
    ls, parents, un, V = _multi(); ex = cb.build_view(parents, 'C1', 10, inclusive=False)
    assert V[('C1', 10)]['token'] == 'CB_FIRST_FILL_GAP_10S' and V[('C1', 10)]['inclusive'] is True and ex['token'] == 'CB_FIRST_FILL_GAP_10S__SENS_exclusive' and ex['inclusive'] is False
    assert V[('C1', 10)]['parameter_hash'] != ex['parameter_hash'] and cb.LINK_TEXT[True].startswith('gap<=') and cb.LINK_TEXT[False].startswith('gap<')
    assert all(b['batch_id'].startswith('INF:CLOSING_BATCH@CB_FIRST_FILL_GAP_10S__SENS_exclusive:') for b in ex['batches'])
    delivered = gzip.decompress(open(os.path.join(PE, 'reports', 'm2c_data', 'closing_batches_C1.tsv.gz'), 'rb').read()).decode().split('\n'); cols = delivered[0].split('\t')
    seen = {}
    for line in delivered[1:]:
        if line: r = line.split('\t'); seen[(r[cols.index('grouping_method')], int(r[cols.index('threshold_s')]))] = r[cols.index('parameter_hash')]
    assert all(seen[('C1', g)] == cb.param_hash('C1', g) for g in THR), 'the primary parameter hash changed: the delivered C1 views would no longer be reproducible'


def test_published_exclusive_artifact_equals_the_independent_m2f_reference_and_states_its_semantics():
    pub = json.load(open(os.path.join(PE, 'reports', 'r1c_dual_scenario', 'm2c_exclusive_threshold', 'exclusive_sensitivity_summary.json')))['rows']
    ref = json.load(open(os.path.join(PE, 'reports', 'm2f_audit', 'track_b', 'ambiguity_result.json')))                     # independent Track B reference (raw csv; no pe imports)
    for r in pub:
        a = ref[f"EXCLUSIVE_gap_lt_g|{r['method']}|{r['threshold_s']}"]
        assert (r['exclusive_batches'], r['inclusive_batches'], r['exclusive_batches_not_in_inclusive'], r['inclusive_batches_not_in_exclusive']) == (a['batches_alt'], a['batches_base'], a['batches_only_alt'], a['batches_only_base'])
        assert r['link_semantics_primary'] == 'inclusive: gap <= threshold' and r['link_semantics_this_artifact'].startswith('EXCLUSIVE')
    man = json.load(open(os.path.join(PE, 'reports', 'r1c_dual_scenario', 'm2c_exclusive_threshold', 'manifest.json'))); assert 'SENSITIVITY ONLY' in man['link_semantics'] and all(n.endswith('_EXCLUSIVE.tsv.gz') for n in man['files'])
    assert [r['pairs_with_gap_exactly_threshold'] for r in pub if r['method'] == 'C1'] == [661, 441, 79, 25, 33]


@pytest.mark.parametrize('g', THR)
def test_c2_measures_the_gap_from_the_previous_parents_LAST_closing_fill_at_every_threshold(g):
    """parent A closes at seconds 100 and 200 (last = 200); parent B closes at 200 + d. C2 gap = d (from A's last fill): joined iff d <= g. C1 gap = 100 + d (from A's first): always separated here."""
    for d, joined in ((g - 1, True), (g, True), (g + 1, False)):
        ls, _ = make([('open', CE, 0, 195, 'o'), ('close', CE, 100, 65, 'A'), ('close', CE, 200, 65, 'A'), ('close', CE, 200 + d, 65, 'B')]); parents, un, V = quick(ls)
        assert sets(V[('C2', g)]) == ([['A', 'B']] if joined else [['A'], ['B']]), (g, d); assert sets(V[('C1', g)]) == [['A'], ['B']]
