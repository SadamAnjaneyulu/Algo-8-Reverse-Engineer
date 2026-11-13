"""M2-B lineage tests: synthetic edge cases and counterexamples (SYNTHETIC_TEST). Counterexample-driven: the separation of observed closing quantities from convention-dependent allocations is attacked directly."""
import dataclasses as dc, os, pytest
from pe import replay as rp, lineage as ln, parents as pa, tsvio
from pe.schema import *
from pe.lineage_set import LineageSet
from pe.generators import synthetic_m2 as S2, synthetic as S
M = 'SYNTHETIC_TEST'


def LS(name, parents=None):
    ins, fills = S2.M2_SCENARIOS[name](); return LineageSet(fills, ins, M, 'src', parents), fills


# ------------------------------------------------------------------ allocation semantics
def test_ab_lots_fifo_lifo_avg_confined_to_analytical_layer():
    ls, fills = LS('ab_lots_close')
    fifo = ls.trace_backward('CP:S000003', 'FIFO'); lifo = ls.trace_backward('CP:S000003', 'LIFO'); avg = ls.trace_backward('CP:S000003', 'AVG')
    assert fifo['sources'] == ['OA:S000001'] and lifo['sources'] == ['OA:S000002']                       # different sources by convention
    assert [r[7] for r in fifo['allocations']] == [-65 * 1000] and [r[7] for r in lifo['allocations']] == [65 * 1000]       # short 100 bought back at 110 loses; short 120 bought back at 110 gains and float(avg['allocations'][0][7]) == 0.0
    assert avg['sources'] == [f'POOL:{ls.cp["CP:S000003"][5]}'] and avg['allocations'][0][9] == 'NOT_IDENTIFIABLE'   # average cost claims no opening-source ownership
    assert fifo['sensitivity'] == 'CONVENTION_SENSITIVE'
    assert ls.cp['CP:S000003'][8] == 65 and len(ls.oa) == 2                                                  # the OBSERVED closing quantity is convention-free
    ls.check(fills)


def test_average_cost_pool_is_the_quantity_weighted_average():
    ls, _ = LS('ab_lots_close'); r = ls.ca['AVG'][0]; assert float(r[5]) == 11000.0 and r[8] == 65                  # (100 + 120) / 2 = 110 rupees = 11000 paise; 65 left in the pool


def test_every_scenario_passes_all_invariants_and_observed_layer_is_identical():
    for name, fn in S2.M2_SCENARIOS.items():
        ins, fills = fn(); ls = LineageSet(fills, ins, M, 'src'); ls.check(fills)
        for a in ('LIFO', 'AVG'):
            for f in ('observed_allocations.tsv', 'lifecycle.tsv', 'episodes.tsv'): assert ls.files[a][f] == ls.files['FIFO'][f], (name, a, f)


def test_COUNTEREXAMPLE_a_leak_of_the_convention_into_the_observed_layer_is_caught(monkeypatch):
    """a recorder whose closing-portion quantity depends on the convention must be rejected by the separation guard"""
    orig = ln.LineageRecorder.closing_portion
    def leaky(self, f, ep, q): orig(self, f, ep, q + (1 if self.method == 'AVG' else 0))
    monkeypatch.setattr(ln.LineageRecorder, 'closing_portion', leaky)
    ins, fills = S2.ab_lots_close()
    with pytest.raises(InvariantViolation): LineageSet(fills, ins, M, 'src')


def test_COUNTEREXAMPLE_an_ownership_claim_under_avg_is_impossible():
    for name in S2.M2_SCENARIOS:
        ins, fills = S2.M2_SCENARIOS[name](); ls = LineageSet(fills, ins, M)
        assert all(r[9] == 'NOT_IDENTIFIABLE' and r[3].startswith('POOL:') and 'OA:' not in r[3] for r in ls.ca['AVG']), name


# ------------------------------------------------------------------ reversals, lifecycle, identity
def test_reversal_100_130_closes_100_and_opens_30_in_a_new_episode():
    ls, fills = LS('reversal_100_130'); cp = ls.cp['CP:S000002']; oa = ls.oa['OA:S000002']
    assert cp[8] == 100 and oa[8] == 30 and cp[5] != oa[5] and cp[5].endswith('#1') and oa[5].endswith('#2')     # not a 130-unit close
    assert ls.episodes[cp[5]]['ended_by'] == 'reversal' and ls.episodes[oa[5]]['started_by_reversal'] and ls.episodes[oa[5]]['direction'] == 1
    ev = [(e[1][-2:], e[3]) for e in ls.events if e[4] == 'S000002']; assert ev == [('#1', 'REVERSED'), ('#2', 'CREATED')]
    assert ls.roles['rev'] == 'MIXED'; ls.check(fills)


def test_lifecycle_sequence_and_stable_episode_ids():
    ls, _ = LS('multi_cycle_episodes'); first = [e for e in ls.events if e[1].endswith('#1')]
    assert [e[3] for e in first][:5] == ['CREATED', 'ADDED', 'ADDED', 'PARTIALLY_REDUCED', 'ADDED']
    assert {m: sorted(ls.runs[m].state.episodes) for m in METHODS}['FIFO'] == sorted(ls.runs['LIFO'].state.episodes) == sorted(ls.runs['AVG'].state.episodes)      # identity does not depend on the convention
    for e in ls.events: assert e[8] == 0 or abs(e[8]) > 0
    last = {}
    for e in ls.events: last[e[1]] = e
    for eid, e in last.items(): assert abs(e[8]) == ls.episodes[eid]['opened'] - ls.episodes[eid]['closed'] or e[3] in ('CLOSED', 'REVERSED')


def test_partial_fills_of_one_parent_are_three_allocations_one_parent():
    ls, _ = LS('parent_partial_fills'); pv = ls.parent_view('P1'); assert len(pv['opening_allocations']) == 3 and pv['opened_units'] == 195 and pv['role'] == 'OPENING_ONLY' and len(ls.roles) == 2


def test_mixed_parent_without_reversal_is_represented_without_double_counting():
    ls, fills = LS('mixed_parent_two_contracts'); pv = ls.parent_view('M')
    assert pv['role'] == 'MIXED' and pv['opened_units'] == 65 and pv['closed_units'] == 65 and len(pv['opening_allocations']) == 1 and len(pv['closing_portions']) == 1
    assert not any(f'OA:{r[2]}' in ls.oa and f'CP:{r[2]}' in ls.cp for r in ls.cp.values())                      # no fill is both (it is not a reversal)
    assert pv['opened_units'] + pv['closed_units'] == sum(f.quantity for f in fills if f.parent_order_id == 'M'); ls.check(fills)


def test_mixed_parent_from_a_reversal_fill():
    ls, fills = LS('mixed_parent_reversal'); assert ls.mixed_parents() == ['R'] and ls.parent_view('R')['opened_units'] == 65 and ls.parent_view('R')['closed_units'] == 65


def test_expired_unclosed_has_no_settlement_pnl():
    ls, fills = LS('expired_unclosed'); st = ls.runs['FIFO'].state; ev = ls.episode_view(sorted(ls.episodes)[0])
    assert ev['observed']['terminal_status'] == 'EXPIRED_UNCLOSED' and ev['observed']['remaining'] == 65 and ls.ca['FIFO'] == [] and st.realized_total() == 0
    assert ev['analytical']['remaining_slices'] and ls.check(fills)


def test_duplicate_flagged_fill_creates_no_allocation():
    ls, fills = LS('duplicate_flagged'); assert len(ls.oa) == 1 and not any(r[2] == fills[1].fill_id for r in ls.oa.values())


def test_reserved_status_is_never_produced_without_evidence():
    for name in S2.M2_SCENARIOS:
        ins, fills = S2.M2_SCENARIOS[name](); ls = LineageSet(fills, ins, M)
        assert all(l.split('\t')[8] != 'INCOMPLETE_SOURCE_HISTORY' for l in ls.files['FIFO']['episodes.tsv'].splitlines()[1:])


def test_FIFO_and_LIFO_diverge_multi_close_but_totals_agree():
    ls, fills = LS('fifo_lifo_diverge'); assert sum(v == 'CONVENTION_SENSITIVE' for v in ls.sensitivity.values()) >= 2
    rem = {m: {x[3]: int(x[5]) for x in (t.split('\t') for t in ln.slices_tsv(ls.runs[m].state, ls.runs[m].lineage).splitlines()[1:])} for m in ('FIFO', 'LIFO')}
    assert rem['FIFO'] != rem['LIFO'] and sum(rem['FIFO'].values()) == sum(rem['LIFO'].values()) == 65 * 4 - 240                 # per-OA remaining is convention dependent, the total is not


# ------------------------------------------------------------------ M1 semantics untouched and queries
def test_lineage_recording_does_not_change_M1_outputs():
    for name in list(S2.M2_SCENARIOS) + list(S.SCENARIOS):
        ins, fills = (S2.M2_SCENARIOS.get(name) or S.SCENARIOS[name])()
        for m in METHODS: assert rp.replay(fills, ins, M, m, 'src', lineage=True).dump == rp.replay(fills, ins, M, m, 'src', lineage=False).dump, (name, m)


def test_position_view_keeps_observed_and_analytical_apart():
    ls, _ = LS('ab_lots_close'); eid = sorted(ls.episodes)[0]
    for conv in METHODS:
        v = ls.episode_view(eid, conv); assert v['observed']['layer'].startswith('OBSERVED') and v['analytical']['layer'].startswith('ANALYTICAL') and v['analytical']['convention'] == conv
        assert v['observed']['opened'] == 130 and v['observed']['closed'] == 65 and v['observed']['remaining'] == 65
    assert 'NONE' in ls.episode_view(eid, 'AVG')['analytical']['ownership_claim']


def test_forward_and_backward_traces_are_consistent():
    ls, _ = LS('fifo_lifo_diverge')
    for conv in ('FIFO', 'LIFO'):
        for oa_id, oa in ls.oa.items():
            fw = ls.trace_forward(oa_id, conv); assert fw['allocated_qty'] + fw['remaining_qty'] == oa[8]
            for ca in fw['closing_allocations']: assert oa_id in ls.trace_backward(ca[2], conv)['sources']


# ------------------------------------------------------------------ missing metadata (parents.tsv)
def test_missing_source_metadata_stays_missing(tmp_path):
    rows = [dict(parent_order_id='A', module_tag='num', order_entry_minute_s=None, app_key_full=None, app_key_last6=None, order_number=None, algo_id=None, first_fill_ts=1, last_fill_ts=2, n_fills=1, filled_units=65, requested_units=65, first_source_row=1, last_source_row=1, parent_role='OPENING_ONLY')]
    p = tmp_path / 'parents.tsv'; pa.write_parents(str(p), rows); back = pa.read_parents(str(p))
    assert all(back['A'][c] is None for c in ('order_entry_minute_s', 'app_key_full', 'app_key_last6', 'order_number', 'algo_id'))           # NA is kept, nothing is derived
    ls, fills = LS('ab_lots_close', parents={'A': back['A']}); assert ls.parent_view('A')['metadata']['order_number'] is None
    bad = open(p).read().replace('\tNA\t', '\tabc\t', 1).replace('num\tabc', 'num\tNA'); (tmp_path / 'bad.tsv').write_text(open(p).read().replace('OPENING_ONLY', 'SOMETHING'))
    with pytest.raises(EventValidationError): pa.read_parents(str(tmp_path / 'bad.tsv'))


def test_parent_roles_are_convention_independent_and_complete():
    for name in S2.M2_SCENARIOS:
        ins, fills = S2.M2_SCENARIOS[name](); ls = LineageSet(fills, ins, M); live = {f.parent_order_id for f in fills if not f.is_duplicate_fill}
        assert set(ls.roles) == live, name
