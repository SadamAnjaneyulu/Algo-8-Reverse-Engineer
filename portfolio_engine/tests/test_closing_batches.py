"""M2-C closing-batch tests: deliberately constructed counterexamples (SYNTHETIC_TEST) + real-ledger checks. Every failure found during development is kept as a regression test."""
import dataclasses as dc, hashlib, json, os, random
import pytest
from conftest import PE, REPO
from pe import closing_batches as cb
from pe.schema import *
from pe.lineage_set import LineageSet
from pe.generators.synthetic import Builder, BASE_TS
M = 'SYNTHETIC_TEST'


def make(spec, extra_inst=None):
    """spec: list of ('open'|'close', instrument_key, ts_offset, qty, parent). Positions are opened as shorts (sell) and closed by buys. instrument_key = (cp, strike, expiry, und)"""
    b = Builder('cb'); ids = {}
    for kind, key, t, q, parent in spec:
        if key not in ids: ids[key] = b.add_inst(cp=key[0], strike=key[1], expiry=key[2], und=key[3])
        b.fill(ids[key], t, -1 if kind == 'open' else 1, q, 10000 if kind == 'open' else 9000, parent=parent)
    ins, fills = b.out(); return LineageSet(fills, ins, M, 'src'), fills


CE = ('CE', 24000, '2026-01-08', 'NIFTY'); PE_ = ('PE', 24000, '2026-01-08', 'NIFTY'); CE2 = ('CE', 24100, '2026-01-08', 'NIFTY')


def views_of(ls):
    parents, unattr, multi = cb.closing_parents(ls); V = cb.all_views(parents)
    for v in V.values(): cb.check_view(v, parents, ls.cp, unattr)
    return parents, unattr, multi, V


def sets(v): return sorted(sorted(p.parent_id for p in b['members']) for b in v['batches'])


def test_C1_identical_timestamps_are_one_batch_and_order_independent():
    spec = [('open', CE, 0, 65, 'o1'), ('open', PE_, 0, 65, 'o2'), ('close', CE, 100, 65, 'A'), ('close', PE_, 100, 65, 'B')]
    ls, fills = make(spec); parents, un, multi, V = views_of(ls); assert sets(V[('C1', 2)]) == [['A', 'B']]
    shuffled = list(fills); random.Random(1).shuffle(shuffled); ls2 = LineageSet(shuffled, ls.instruments, M, 'src'); p2, _, _ = cb.closing_parents(ls2)
    assert [b['batch_id'] for b in cb.build_view(p2, 'C1', 2)['batches']] == [b['batch_id'] for b in V[('C1', 2)]['batches']]       # input order is irrelevant


def test_several_partial_closing_fills_of_one_parent_are_one_decision():
    spec = [('open', CE, 0, 195, 'o'), ('close', CE, 100, 65, 'A'), ('close', CE, 103, 65, 'A'), ('close', CE, 106, 65, 'A')]
    ls, _ = make(spec); parents, *_ , V = views_of(ls); assert len(parents) == 1 and len(parents[0].cps) == 3 and (parents[0].first_ts, parents[0].last_ts) == (BASE_TS + 100, BASE_TS + 106)
    assert all(len(v['batches']) == 1 and len(v['batches'][0]['members']) == 1 for v in V.values())


def test_COUNTEREXAMPLE_mixed_parent_contributes_only_its_closing_portions():
    """M opens X at t=0 and closes Y at t=100; a different parent closes Z at t=2. If M's OPENING execution leaked into its timestamp, M would join Z's batch."""
    Z = ('CE', 24200, '2026-01-08', 'NIFTY'); Y = ('PE', 24000, '2026-01-08', 'NIFTY'); X = ('CE', 24000, '2026-01-08', 'NIFTY')
    spec = [('open', Y, 0, 65, 'oy'), ('open', Z, 0, 65, 'oz'), ('close', Z, 2, 65, 'ZC'), ('open', X, 0, 65, 'M'), ('close', Y, 100, 65, 'M')]
    ls, fills = make(spec); parents, un, multi, V = views_of(ls); M_ = next(p for p in parents if p.parent_id == 'M')
    assert ls.roles['M'] == 'MIXED' and M_.first_ts == BASE_TS + 100 and M_.qty == 65 and len(M_.cps) == 1                         # closing portion only
    assert all(['M', 'ZC'] != sorted(p.parent_id for p in b['members']) for b in V[('C1', 60)]['batches'][:1]) and sets(V[('C1', 10)]) == [['M'], ['ZC']]
    assert M_.qty < sum(f.quantity for f in fills if f.parent_order_id == 'M')                                                       # its opening quantity is not counted


def test_different_contracts_and_both_rights_share_one_batch_and_are_only_descriptive():
    spec = [('open', CE, 0, 65, 'o1'), ('open', PE_, 0, 65, 'o2'), ('open', CE2, 0, 65, 'o3'), ('close', CE, 100, 65, 'A'), ('close', PE_, 101, 65, 'B'), ('close', CE2, 102, 65, 'C')]
    ls, _ = make(spec); parents, un, multi, V = views_of(ls); b = V[('C1', 5)]['batches']; assert len(b) == 1
    rec = cb.batch_record(b[0], V[('C1', 5)], ls); assert rec['right_class'] == 'MIXED' and rec['n_contracts'] == 3 and rec['n_cp_CE'] == 2 and rec['n_cp_PE'] == 1 and rec['roles'] == 'SHORT_BODY:195'


def test_C2_overlapping_intervals_join_when_C1_does_not_and_are_flagged():
    spec = [('open', CE, 0, 200, 'oa'), ('open', PE_, 0, 65, 'ob'), ('close', CE, 100, 65, 'A'), ('close', CE, 130, 65, 'A'), ('close', PE_, 110, 65, 'B')]
    ls, _ = make(spec); parents, un, multi, V = views_of(ls)
    assert sets(V[('C1', 2)]) == [['A'], ['B']] and sets(V[('C2', 2)]) == [['A', 'B']]                                               # A spans 100..130; B starts at 110 inside it
    link = V[('C2', 2)]['batches'][0]['links'][0]; assert link[0] == -20 and link[1] is True and link[2] is True
    rec = cb.batch_record(V[('C2', 2)]['batches'][0], V[('C2', 2)], ls); assert rec['has_interval_overlap'] == 1 and rec['n_strict_overlap_links'] == 1
    assert V[('C1', 2)]['batch_id' if False else 'token'] != V[('C2', 2)]['token']                                                    # different families never share ids
    assert not ({b['batch_id'] for b in V[('C1', 2)]['batches']} & {b['batch_id'] for b in V[('C2', 2)]['batches']})


def test_long_gap_then_tight_cluster():
    spec = [('open', CE, 0, 65, 'o1'), ('open', PE_, 0, 65, 'o2'), ('open', CE2, 0, 65, 'o3'), ('open', ('PE', 24100, '2026-01-08', 'NIFTY'), 0, 65, 'o4'),
            ('close', CE, 10, 65, 'A'), ('close', PE_, 200, 65, 'B'), ('close', CE2, 201, 65, 'C'), ('close', ('PE', 24100, '2026-01-08', 'NIFTY'), 204, 65, 'D')]
    ls, _ = make(spec); *_, V = views_of(ls); assert sets(V[('C1', 5)]) == [['A'], ['B', 'C', 'D']] and sets(V[('C1', 2)]) == [['A'], ['B', 'C'], ['D']]      # C-D gap is 3 s


def test_transitive_chain_exceeds_the_threshold_and_is_reported():
    """each link is 10 s but the batch lasts 40 s: single linkage chains transitively; the duration must be visible"""
    spec = [('open', CE, 0, 325, 'o')] + [('close', CE, 100 + 10 * k, 65, f'P{k}') for k in range(5)]
    ls, _ = make(spec); parents, un, multi, V = views_of(ls); b = V[('C1', 10)]['batches']; assert len(b) == 1 and len(b[0]['members']) == 5
    rec = cb.batch_record(b[0], V[('C1', 10)], ls); assert rec['duration_s'] == 40 and rec['max_link_gap_s'] == 10
    row = next(r for r in cb.summarize(V, parents, ls) if (r['method'], r['threshold_s']) == ('C1', 10)); assert row['max_duration_over_threshold'] == 4.0
    assert sets(V[('C1', 5)]) == [[f'P{k}'] for k in range(5)]


def test_inclusive_threshold_boundary_and_one_second_sensitivity_is_counted():
    spec = [('open', CE, 0, 130, 'o'), ('close', CE, 100, 65, 'A'), ('close', CE, 110, 65, 'B')]
    ls, _ = make(spec); parents, un, multi, V = views_of(ls); assert sets(V[('C1', 10)]) == [['A', 'B']] and sets(V[('C1', 5)]) == [['A'], ['B']]
    row = next(r for r in cb.summarize(V, parents, ls) if (r['method'], r['threshold_s']) == ('C1', 10)); assert row['pairs_gap_exactly_threshold'] == 1
    row5 = next(r for r in cb.summarize(V, parents, ls) if (r['method'], r['threshold_s']) == ('C1', 5)); assert row5['pairs_gap_threshold_plus_1s'] == 0 and row5['pairs_linked'] == 0


def test_equal_first_timestamps_are_ordered_by_source_row_then_parent_id():
    spec = [('open', CE, 0, 195, 'o'), ('close', CE, 100, 65, 'B'), ('close', CE, 100, 65, 'A')]
    ls, _ = make(spec); parents, *_ = views_of(ls); ordered = sorted(parents, key=lambda p: (p.first_ts, p.first_src, p.parent_id)); assert [p.parent_id for p in ordered] == ['B', 'A']          # source row decides, not the id
    ties = [p for p in parents if p.first_ts == parents[0].first_ts]; assert len(ties) == 2


def test_C2_tie_dependence_is_deterministic_and_input_order_independent():
    """A: first 0 last 5; B: first 0 last 0; C: first 3. Which of A/B precedes C (source-row order) decides the C2 gap; the rule is fixed, the result reproducible"""
    spec = [('open', CE, 0, 300, 'o'), ('close', CE, 100, 65, 'A'), ('close', CE, 105, 65, 'A'), ('close', CE, 100, 65, 'B'), ('close', CE, 103, 65, 'C')]
    ls, fills = make(spec); parents, *_ = views_of(ls); v1 = cb.build_view(parents, 'C2', 2)
    ls2 = LineageSet(list(reversed(fills)), ls.instruments, M, 'src'); p2, *_ = cb.closing_parents(ls2); v2 = cb.build_view(p2, 'C2', 2)
    assert [[p.parent_id for p in b['members']] for b in v1['batches']] == [[p.parent_id for p in b['members']] for b in v2['batches']]


def test_COUNTEREXAMPLE_session_expiry_and_underlying_boundaries_are_never_crossed():
    ND = ('CE', 24000, '2026-01-08', 'NIFTY'); NE = ('CE', 24000, '2026-01-15', 'NIFTY'); SX = ('CE', 77000, '2026-01-08', 'SENSEX')
    b = Builder('bounds'); a = b.add_inst(cp='CE', strike=24000, expiry='2026-01-08'); e = b.add_inst(cp='CE', strike=24000, expiry='2026-01-15'); s = b.add_inst(cp='CE', strike=77000, expiry='2026-01-08', und='SENSEX')
    for i_ in (a, e, s): b.fill(i_, 0, -1, 65, 10000, parent=f'open_{i_}')
    b.fill(a, 100, 1, 65, 9000, parent='N1'); b.fill(e, 101, 1, 65, 9000, parent='N2'); b.fill(s, 101, 1, 65, 9000, parent='S1')
    d = 86400 - (9 * 3600 + 16 * 60)                                               # BASE_TS + d is 00:00:00 IST of the next day
    b.fill(a, d - 500, -1, 130, 10000, parent='open_late'); b.fill(a, d - 1, 1, 65, 9000, parent='L1'); b.fill(a, d + 1, 1, 65, 9000, parent='L2')
    ins, fills = b.out(); ls = LineageSet(fills, ins, M, 'src'); *_, V = views_of(ls)
    for key in (('C1', 60), ('C2', 60)):
        grouped = [sorted(p.parent_id for p in x['members']) for x in V[key]['batches']]; assert ['N1', 'N2'] not in grouped and ['N1', 'S1'] not in grouped and ['L1', 'L2'] not in grouped
        assert len(V[key]['batches']) == 5                                           # N1, N2 (other expiry), S1 (other underlying), L1 | L2 (23:59:59 vs 00:00:01 IST: different sessions)


def test_missing_parent_id_is_unattributable_never_pooled_and_reconciles():
    b = Builder('missing'); i = b.add_inst(); b.fill(i, 0, -1, 195, 10000, parent='o'); b.fill(i, 100, 1, 65, 9000, parent='x1'); b.fill(i, 101, 1, 65, 9000, parent='x2'); b.fill(i, 102, 1, 65, 9000, parent='A')
    ins, fills = b.out(); fills = [dc.replace(f, parent_order_id='') if f.parent_order_id in ('x1', 'x2') else f for f in fills]; ls = LineageSet(fills, ins, M, 'src'); parents, un, multi = cb.closing_parents(ls); assert len(un) == 2 and len(parents) == 1
    for v in cb.all_views(parents).values(): cb.check_view(v, parents, ls.cp, un)                                                  # batched + unattributable = every closing portion


def test_duplicate_parent_id_across_sessions_is_two_members_and_is_reported():
    b = Builder('dup'); i = b.add_inst(); d = 86400
    b.fill(i, 0, -1, 130, 10000, parent='o'); b.fill(i, 100, 1, 65, 9000, parent='SAME'); b.fill(i, d + 100, 1, 65, 9000, parent='SAME')
    ins, fills = b.out(); ls = LineageSet(fills, ins, M, 'src'); parents, un, multi = cb.closing_parents(ls); assert len(parents) == 2 and multi == ['SAME']
    *_, V = (parents, un, multi, cb.all_views(parents)); assert all(len(v['batches']) == 2 for v in V.values())


def test_opening_only_parent_never_enters_and_a_duplicated_member_is_rejected():
    spec = [('open', CE, 0, 130, 'o'), ('close', CE, 100, 65, 'A'), ('close', CE, 101, 65, 'B')]
    ls, _ = make(spec); parents, un, multi, V = views_of(ls); assert 'o' not in {p.parent_id for p in parents}
    v = cb.build_view(parents, 'C1', 10); v['batches'][0]['members'].append(v['batches'][0]['members'][0])
    with pytest.raises(InvariantViolation): cb.check_view(v, parents, ls.cp, un)                                                  # a parent twice in one view is rejected
    ghost = cb.ParentClose('ghost', 'NIFTY', '2026-01-08', '2026-01-05'); v = cb.build_view(parents, 'C1', 10); v['batches'][0]['members'].append(ghost)
    with pytest.raises(InvariantViolation): cb.check_view(v, parents, ls.cp, un)                                                  # a parent without closing portions is rejected


def test_grouping_never_mutates_the_observed_ledger_and_ignores_the_matching_convention():
    spec = [('open', CE, 0, 195, 'o1'), ('open', CE, 5, 65, 'o2'), ('close', CE, 100, 100, 'A'), ('close', CE, 101, 100, 'B')]
    ls, fills = make(spec); h = lambda: hashlib.sha256(''.join(ls.files['FIFO'][n] for n in ('observed_allocations.tsv', 'lifecycle.tsv', 'episodes.tsv')).encode()).hexdigest()
    before = h(); parents, *_ , V = views_of(ls); cb.summarize(V, parents, ls); cb.files_for_method(V, 'C1', ls); assert h() == before
    for m in ('LIFO', 'AVG'): assert ls.files[m]['observed_allocations.tsv'] == ls.files['FIFO']['observed_allocations.tsv']           # batches read only the observed layer: identical under every convention
    rec = cb.batch_record(V[('C1', 10)]['batches'][0], V[('C1', 10)], ls); assert 'FIFO' not in str(rec) and 'LIFO' not in str(rec) and rec['grouping_convention'] == 'CB_FIRST_FILL_GAP_10S' and rec['membership_provenance'] == 'INFERRED:CLOSING_BATCH'


def test_views_are_independent_ids_unique_and_nested_properties_hold():
    ins, fills = __import__('pe.generators.synthetic', fromlist=['x']).random_stress(5, 3000, 12); ls = LineageSet(fills, ins, M, 'src'); parents, un, multi, V = views_of(ls)
    ids = [b['batch_id'] for v in V.values() for b in v['batches']]; assert len(ids) == len(set(ids)) and all(i.startswith('INF:CLOSING_BATCH@CB_') for i in ids)
    st = cb.stability(V); assert all(x['nested'] for x in st['across_thresholds']) and all(x['c1_nested_in_c2'] for x in st['c1_vs_c2'])        # smaller thresholds refine larger ones; C2 coarsens C1
    for (m, g), v in V.items(): assert sum(len(b['members']) for b in v['batches']) == len(parents)                                         # each view alone accounts for every parent once; views are never added


def test_files_have_provenance_and_reconcile_to_closing_portions():
    spec = [('open', CE, 0, 130, 'o'), ('close', CE, 100, 65, 'A'), ('close', CE, 101, 65, 'B')]
    ls, _ = make(spec); parents, un, multi, V = views_of(ls); F = cb.files_for_method(V, 'C1', ls); rows = [l.split('\t') for l in F['closing_batch_portions_C1.tsv'].splitlines()[1:]]
    assert len(rows) == 2 * 5 and sum(int(r[11]) for r in rows) == 5 * 130 and all(r[1].startswith('CB_FIRST_FILL_GAP_') for r in rows)
    hdr = F['closing_batches_C1.tsv'].splitlines()[0].split('\t'); first = dict(zip(hdr, F['closing_batches_C1.tsv'].splitlines()[1].split('\t'))); assert first['membership_provenance'] == 'INFERRED:CLOSING_BATCH' and first['grouping_version'] == 'CB1' and first['parameter_hash']
    assert not any('C2' in n for n in F)                                                                                       # a C1 file set never contains C2 content


# ----------------------------------------------------------------------------- real ledger (slow)
@pytest.fixture(scope='module')
def real():
    from pe.generators import historical as H
    ins, fills, src = H.generate(REPO); ls = LineageSet(fills, ins, 'HISTORICAL_OBSERVED_REPLAY', 'src'); parents, un, multi = cb.closing_parents(ls); return ins, fills, ls, parents, un, multi, cb.all_views(parents)


@pytest.mark.slow
def test_real_scope_and_all_ten_views_partition_exactly(real):
    ins, fills, ls, parents, un, multi, V = real
    assert len(parents) == 16817 and len(ls.cp) == 17760 and sum(r[8] for r in ls.cp.values()) == 1377065 and un == [] and multi == [] and len(V) == 10
    for v in V.values(): cb.check_view(v, parents, ls.cp, un)
    assert sum(1 for p in parents if ls.roles[p.parent_id] == 'MIXED') == 26 and not any(ls.roles[p.parent_id] == 'OPENING_ONLY' for p in parents)
    mp = [p for p in parents if ls.roles[p.parent_id] == 'MIXED']; assert sum(p.qty for p in mp) == 7620 < sum(f.quantity for f in fills if f.parent_order_id in {p.parent_id for p in mp})


@pytest.mark.slow
def test_real_nesting_and_C2_equals_C1_on_this_data_because_one_parent_spreads_over_seconds(real):
    ins, fills, ls, parents, un, multi, V = real; st = cb.stability(V)
    assert all(x['nested'] for x in st['across_thresholds']) and all(x['c1_nested_in_c2'] for x in st['c1_vs_c2'])
    assert sum(1 for p in parents if p.last_ts > p.first_ts) == 1 and all(x['links_only_c1'] == 0 for x in st['c1_vs_c2'])           # C2 can only add links; here none are added


@pytest.mark.slow
def test_real_outputs_reproduce_the_committed_manifest(real):
    ins, fills, ls, parents, un, multi, V = real; man = json.load(open(os.path.join(PE, 'reports', 'm2c_data', 'manifest.json')))
    for m in ('C1', 'C2'):
        for name, text in cb.files_for_method(V, m, ls).items(): assert hashlib.sha256(text.encode()).hexdigest() == man['files'][name + '.gz']['sha256_of_text'], name
