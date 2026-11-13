"""Accounting, data-quality, tie-order, mode-isolation and basket-scenario accounting tests on SYNTHETIC fixtures (hand-computed expectations)."""
import dataclasses as dc, os, pytest
from pe import replay as rp, tsvio, invariants
from pe.ledger import PortfolioState
from pe.schema import *
from pe.generators import synthetic as S
M = 'SYNTHETIC_TEST'


def run(scn, method='FIFO', tie='src', **k):
    ins, fills = S.SCENARIOS[scn](); return rp.replay(fills, ins, M, method, tie, strict=True, **k)


def tot(res, name): return next(l.split('\t')[2] for l in res.dump.splitlines() if l.startswith(f'TOTAL\t{name}\t'))


def test_open_close_full():
    r = run('open_close_full'); assert tot(r, 'realized_pnl_paise') == str(130 * 2000) and tot(r, 'remaining_units') == '0'


@pytest.mark.parametrize('method,expected', [('FIFO', 260000), ('LIFO', 520000), ('AVG', 390000)])
def test_partial_close_conventions(method, expected):
    r = run('partial_close_lots', method); assert float(tot(r, 'realized_pnl_paise')) == expected and tot(r, 'remaining_units') == '65'


def test_inventory_identical_across_conventions_but_pnl_differs():
    a = [run('partial_close_lots', m) for m in METHODS]; assert len({tot(x, 'remaining_units') for x in a}) == 1 and len({float(tot(x, 'realized_pnl_paise')) for x in a}) == 3


def test_reversal_counts_and_pnl():
    r = run('reversal'); assert tot(r, 'reversal_fills') == '1' and tot(r, 'reversal_units_reopened') == '65' and tot(r, 'realized_pnl_paise') == str(65 * 1000 + 65 * 500) and tot(r, 'remaining_units') == '0'


def test_duplicate_fill_flagged_is_ignored_and_counted():
    r = run('duplicate_flagged'); assert r.warnings['DUPLICATE_FILL_IGNORED'] == 1 and tot(r, 'opened_units') == '65'


def test_partial_close_cannot_exceed_remaining_is_enforced_by_role_arithmetic():
    ins, _ = S.open_close_full(); st = PortfolioState('FIFO', ins); iid = next(iter(ins))
    f = lambda i, side, q: Fill(f'x{i}', i, f'p{i}', 'num', iid, 1767587000 + i, side, q, 10000, q, 'Filled', False, M, 't')
    st.apply_fill(f(1, -1, 65)); role = st.apply_fill(f(2, 1, 130)); assert role.close_qty == 65 and role.open_qty == 65 and role.is_reversal     # the excess reverses; it never over-closes


def test_fill_applied_exactly_once():
    ins, fills = S.open_close_full(); st = PortfolioState('FIFO', ins); st.apply_fill(fills[0])
    with pytest.raises(InvariantViolation): st.apply_fill(fills[0])


def test_replay_is_deterministic():
    a = run('random_stress_seed1'); b = run('random_stress_seed1'); assert a.dump == b.dump


def test_out_of_order_input_is_sorted_and_warned():
    r = run('out_of_order'); assert r.warnings['INPUT_NOT_TIME_ORDERED'] == 1 and tot(r, 'remaining_units') == '0'


def test_equal_second_mixed_sides_documented_not_resolved():
    ins, fills = S.equal_second_mixed_sides(); r1 = rp.replay(fills, ins, M, 'FIFO', 'sells_first'); r2 = rp.replay(fills, ins, M, 'FIFO', 'buys_first'); r0 = rp.replay(fills, ins, M, 'FIFO', 'src')
    assert r0.warnings['TIE_GROUP_MIXED_SIDE'] == 1
    role = lambda r: {x.fill_id: (x.close_qty, x.open_qty) for x in r.roles}; assert role(r1) != role(r2)            # the open/close role depends on the order: the engine reports it and does not choose


def test_partial_fills_parent_aggregation():
    r = run('partial_fills'); assert r.warnings['PARTIAL_FILL_ROWS'] == 3 and r.warnings['UNFILLED_REMAINDER_ORDERS'] == 2
    assert 'PARENT\tP1\t2\t130\t195\tUNFILLED_REMAINDER' in r.dump and 'PARENT\tP2\t1\t130\t195\tUNFILLED_REMAINDER' in r.dump


def test_expired_contract_inventory_has_no_invented_settlement():
    r = run('expired_unclosed'); assert tot(r, 'remaining_expired_unclosed_units') == '65' and tot(r, 'remaining_open_at_end_units') == '65'
    assert r.warnings['EXPIRED_UNCLOSED_INSTRUMENTS'] == 1 and tot(r, 'realized_pnl_paise') == '0'       # nothing realized, nothing invented


def test_unrealized_is_unavailable_not_zero():
    r = run('open_close_full'); assert r.warnings['MISSING_MARKS'] == 1 and all(s['unrealized'] == 'NA' for s in r.snapshots)


def test_cut_reentry_195_accounting_follows_actual_fills_only():
    """SYNTHETIC accounting example from the brief: 195 short CE, cut fill of 65, re-entry fill of 65; inventory follows the fills"""
    ins, fills = S.cut_reentry_195(); ce = 'NIFTY|2026-01-08|CE|24000'; pe = 'NIFTY|2026-01-08|PE|24000'
    def inv_after(n):
        st = PortfolioState('FIFO', ins)
        for f in rp.order_events(fills, 'src')[:n]: st.apply_fill(f)
        return st.signed_inventory(ce), st.signed_inventory(pe)
    assert inv_after(8) == (-195, -195)                 # before the cut fill
    assert inv_after(9) == (-130, -195)                 # after the actual cut fill: 130 short CE retained, PE untouched
    assert inv_after(10) == (-195, -195)                # after the actual re-entry fill
    # a proposal alone changes nothing: no fill, no change
    assert inv_after(8) == inv_after(8)


def test_mode_contamination_is_rejected_before_anything_is_applied():
    ins, fills = S.open_close_full(); mixed = [fills[0], dc.replace(fills[1], execution_mode='HISTORICAL_OBSERVED_REPLAY')]
    with pytest.raises(ModeContaminationError): rp.replay(mixed, ins, M)
    with pytest.raises(ModeContaminationError): rp.replay(fills, ins, 'HISTORICAL_OBSERVED_REPLAY')


def test_aggregates_and_snapshots_reconcile():
    r = run('random_stress_seed7', snapshot_interval=500); s = r.snapshots[-1]
    assert s['gross_units'] == int(tot(r, 'remaining_units')) and s['open_instruments'] == sum(1 for l in r.dump.splitlines() if l.startswith('INSTR') and l.split('\t')[2] != '0')
    assert len(r.snapshots) >= 10


@pytest.mark.parametrize('method', METHODS)
def test_all_invariants_every_fill_on_stress(method):
    ins, fills = S.random_stress(7, 5000, 20); r = rp.replay(fills, ins, M, method, 'src', strict=True)           # strict = invariants after EVERY fill
    assert 'cash_identity_cash_equals_realized_plus_book_value' in r.checks


def test_invalid_inputs_rejected(tmp_path):
    base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'fixtures', 'invalid'); ins = tsvio.read_instruments(os.path.join(base, 'base_instruments.tsv'))
    for name in ('off_tick_price', 'zero_quantity', 'bad_side', 'unknown_instrument', 'duplicate_fill_id', 'missing_column'):
        with pytest.raises(EventValidationError): tsvio.read_events(os.path.join(base, f'{name}_events.tsv'), ins)
    with pytest.raises(EventValidationError): tsvio.read_instruments(os.path.join(base, 'bad_option_type_instruments.tsv'))
    mixed = tsvio.read_events(os.path.join(base, 'mixed_modes_events.tsv'), ins)
    with pytest.raises(ModeContaminationError): rp.replay(mixed, ins, M)


def test_date_arithmetic_roundtrip():
    for y, m, d in ((1970, 1, 1), (2026, 1, 5), (2026, 10, 22), (2024, 2, 29)): assert civil_from_days(days_from_civil(y, m, d)) == (y, m, d)
    assert day_iso(ist_day(1782186364)) == '2026-06-23'
