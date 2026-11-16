"""M2-B on the REAL ledger: reference counts, TP-01 / TP-02 reconciliation, tie-order conditionality, parents.tsv. Reference counts come from existing research; they are checked, never forced."""
import pytest as _pt
import os, pytest
import pandas as pd
from conftest import REPO, PE
from pe import parents as pa
from pe.schema import *
from pe.lineage_set import LineageSet
from pe.generators import historical as H
TP = os.path.join(REPO, 'tp_reconstruction'); M = 'HISTORICAL_OBSERVED_REPLAY'


@pytest.fixture(scope='module')
def real():
    ins, fills, src = H.generate(REPO); return ins, fills, LineageSet(fills, ins, M, 'src')


def test_reference_counts(real):
    ins, fills, ls = real
    assert len(ls.oa) == 23684 and len(ls.cp) == 17760 and len(ls.episodes) == 2667 and len(ls.mixed_parents()) == 26
    assert sum(r[8] for r in ls.oa.values()) == 1414545 and sum(r[8] for r in ls.cp.values()) == 1377065


def test_mixed_parents_are_23_reversals_plus_3_others_without_double_counting(real):
    ins, fills, ls = real; mixed = set(ls.mixed_parents()); rev = {r[3] for r in ls.cp.values() if f'OA:{r[2]}' in ls.oa}
    assert len(mixed & rev) == 23 and len(mixed - rev) == 3
    q = {}
    for f in fills: q[f.parent_order_id] = q.get(f.parent_order_id, 0) + f.quantity
    for p in mixed: assert sum(r[8] for r in list(ls.oa.values()) + list(ls.cp.values()) if r[3] == p) == q[p]


def test_all_invariants_hold_on_real_data(real):
    ins, fills, ls = real; done = ls.check(fills); assert {'I1', 'I2', 'I3', 'I4', 'I5', 'I6', 'I7', 'I10', 'I11'} <= set(done)


def test_realized_pnl_from_allocations_equals_tp01_for_every_convention(real):
    ins, fills, ls = real; S = pd.read_csv(os.path.join(TP, 'data', 'reconciliation_summary.csv')).set_index('method')
    for m in METHODS:
        tot = sum(float(r[7]) for r in ls.ca[m]) if m == 'AVG' else sum(int(r[7]) for r in ls.ca[m]); assert tot / 100 == pytest.approx(S.loc[m].realized_gross_pnl_rupees, abs=0.01)


def test_episode_identity_and_fields_equal_tp01_for_every_convention(real):
    ins, fills, ls = real; E = pd.read_parquet(os.path.join(TP, 'data', 'position_episodes.parquet'))
    for m in METHODS:
        e = E[E.method == m].set_index('episode_id'); mine = ls.runs[m].state.episodes; assert set(e.index) == set(mine)
        for k, v in mine.items(): assert (v['opened'], v['closed'], v['direction'], v['ended_by']) == (e.loc[k].opened_units, e.loc[k].closed_units, e.loc[k].direction, e.loc[k].ended_by)


def test_closing_portions_match_tp02_timeline_rows_without_assuming_identical_semantics(real):
    ins, fills, ls = real; tl = pd.read_parquet(os.path.join(TP, 'tp02', 'data', 'exit_event_timelines.parquet'), columns=['close_row', 'qty_closed'])
    assert len(tl) == 17760 and {int(r[11]) for r in ls.cp.values()} == set(tl.close_row.astype(int))           # same rows (observed); semantics of the TP-02 table are not relied upon
    assert all(ls.cp[f'CP:F{int(r.close_row):06d}'][8] == r.qty_closed for r in tl.itertuples())


def test_observed_layer_identical_across_conventions_and_remaining_slices_reconcile(real):
    ins, fills, ls = real
    for m in ('LIFO', 'AVG'): assert all(ls.files[m][n] == ls.files['FIFO'][n] for n in ('observed_allocations.tsv', 'lifecycle.tsv', 'episodes.tsv'))
    status = [l.split('\t')[8] for l in ls.files['FIFO']['episodes.tsv'].splitlines()[1:]]; assert status.count('EXPIRED_UNCLOSED') == 81 and status.count('REVERSED') == 23 and status.count('CLOSED') == 2563 and 'INCOMPLETE_SOURCE_HISTORY' not in status
    from pe import lineage as ln
    for m in METHODS: assert sum(int(t.split('\t')[5]) for t in ln.slices_tsv(ls.runs[m].state, ls.runs[m].lineage).splitlines()[1:]) == 37480


def test_tie_order_changes_identities_only_in_instruments_with_mixed_side_same_second_fills(real):
    """identity is invariant to FIFO/LIFO/AVG but conditional on the tie-order convention; the conditionality is confined and documented"""
    from pe import replay as rp
    ins, fills, ls = real; base = {t: {(x[0], x[1], x[5], x[8]) for x in rp.replay(fills, ins, M, 'FIFO', t, lineage=True).lineage.observed} for t in TIE_ORDERS}
    diff = (base['src'] | base['sells_first'] | base['buys_first']) - (base['src'] & base['sells_first'] & base['buys_first']); inst = {f.fill_id: f.instrument_id for f in fills}
    grp = {}
    for f in fills: grp.setdefault((f.instrument_id, f.timestamp_s), set()).add(f.side)
    mixed = {k[0] for k, v in grp.items() if len(v) == 2}; di = {inst[x[1].split(':', 1)[1]] for x in diff}
    assert di <= mixed and len(di) == 5 and len(diff) == 42 and len({x[1].split(':', 1)[1] for x in diff}) == 20           # documented: 20 fills (42 rows) in 5 instruments; fill-level differences include downstream fills of the same instrument


def test_parents_tsv_from_the_real_export(real, tmp_path):
    ins, fills, ls = real; rows = H.generate_parents(REPO, ls.roles); p = tmp_path / 'parents.tsv'; pa.write_parents(str(p), rows); back = pa.read_parents(str(p))
    assert len(back) == 39874 and sum(r['filled_units'] for r in back.values()) == sum(f.quantity for f in fills)
    missing = {c: sum(1 for r in back.values() if r[c] is None) for c in pa.PARENT_COLUMNS}; assert {c: n for c, n in missing.items() if n} == {'algo_id': 1}             # the one empty raw cell stays NA
    assert not any(v == 'CONFLICT' for r in rows for v in r.values()) and all(r['app_key_last6'] == r['app_key_full'][-6:] for r in back.values())
    assert {r['parent_role'] for r in back.values()} == set(pa.ROLES)

pytestmark = _pt.mark.slow
