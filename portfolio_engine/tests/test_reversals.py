"""Decision B: the two reversal measures, hand-calculated. Rows = (fill_id, source_row, instrument, parent, second, signed quantity) in processing order; inventory starts at 0 for the instrument,
so an opening fill of +100 is the first row."""
import pytest
from pe import reversals as R, replay as rp
from pe.schema import Fill

I = 'NIFTY|CE'


def m(*rows): return R.measures([(f'F{i}', i, I, p, ts, q) for i, (p, ts, q) in enumerate(rows, 1)])


def counts(r): return r['counts'][R.PER_FILL], r['counts'][R.PARENT_LEVEL]


def test_directive_example_one_parent_two_fills_crossing_zero():
    r = m(('O', 1, +100), ('A', 5, -150), ('A', 5, -50))                    # +100, then parent A sells 150 (+100 -> -50: crosses) and 50 (-50 -> -100)
    assert counts(r) == (1, 1) and r['per_fill'][0]['inventory_before'] == 100 and r['per_fill'][0]['inventory_after'] == -50 and r['parent_level'][0]['n_fills'] == 2
    assert (r['parent_level'][0]['inventory_before'], r['parent_level'][0]['inventory_after']) == (100, -100)


def test_interleaved_parents_make_the_measures_differ():
    """+100; A sells 60 (+40), B sells 100 (-60: B crosses), A sells 30 (-90). Per-fill: only B's fill crosses (1). Parent level: A (+100 before its first fill, -90 after its last) and B (+40 -> -60) both flip (2)."""
    r = m(('O', 1, +100), ('A', 5, -60), ('B', 5, -100), ('A', 5, -30))
    assert counts(r) == (1, 2) and [x['parent_order_id'] for x in r['per_fill']] == ['B'] and sorted(x['parent_order_id'] for x in r['parent_level']) == ['A', 'B']


def test_neither_measure_is_a_subset_of_the_other():
    """one parent crosses zero twice inside the second and ends on its starting sign: two per-fill events, no parent-level flip"""
    r = m(('O', 1, +100), ('A', 5, -150), ('A', 5, +200))                   # +100 -> -50 -> +150
    assert counts(r) == (2, 0)
    r2 = m(('O', 1, +100), ('A', 5, -100), ('A', 5, -50))                   # +100 -> 0 -> -50: reaches zero first, then opens the other side: no single-fill crossing, one parent-level flip
    assert counts(r2) == (0, 1)


def test_exact_zero_boundary_is_not_a_crossing():
    assert counts(m(('O', 1, +100), ('A', 5, -100))) == (0, 0)             # +100 -> 0
    assert counts(m(('A', 5, -50))) == (0, 0)                                # 0 -> -50 (opening from flat)


def test_negative_to_positive_flip_and_partial_fills():
    r = m(('O', 1, -130), ('A', 5, +65), ('A', 5, +65), ('A', 5, +65))      # -130 -> -65 -> 0 -> +65: the third fill is the zero-to-positive opening, no single fill crosses
    assert counts(r) == (0, 1) and r['parent_level'][0]['n_fills'] == 3
    r2 = m(('O', 1, -130), ('A', 5, +195))                                   # -130 -> +65 in ONE fill (390/130-style reversing fill)
    assert counts(r2) == (1, 1)


def test_different_seconds_are_different_groups_for_the_parent_level_measure():
    """A sells 150 in second 5 (+100 -> -50) and buys 200 in second 6 (-50 -> +150): two flips, one per (parent, second) group; merged over both seconds the sign would be unchanged (+100 -> +150)"""
    assert counts(m(('O', 1, +100), ('A', 5, -150), ('A', 6, +200))) == (2, 2)


def _fill(i, inst, parent, ts, side, qty, key):
    return Fill(f'F{i}', i, parent, 'm', inst, ts, side, qty, 100, qty, 'c', False, 'SYNTHETIC_TEST', 't', tie_key=('trade_id', key))


def test_the_measures_are_conditional_on_the_same_second_order_baseline_vs_keyed():
    """+100 then, in one second, A sells 150 (file row 2) and B buys 150 (file row 3). Baseline order A,B: A crosses (+100 -> -50), B crosses (-50 -> +100): 2 per-fill events.
    Keyed order B,A (B has the smaller key): +100 -> +250 -> +100: none."""
    fs = [_fill(1, I, 'O', 1, +1, 100, (1,)), _fill(2, I, 'A', 5, -1, 150, (9,)), _fill(3, I, 'B', 5, +1, 150, (1,))]
    assert counts(R.from_fills(rp.order_events(fs, 'trade_id'))) == (0, 0)
    assert counts(R.from_fills(rp.order_events(fs, 'src'))) == (2, 2)                               # baseline (file) order A then B: both cross, both flip
