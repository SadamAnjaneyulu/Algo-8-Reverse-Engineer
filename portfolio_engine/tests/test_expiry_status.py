"""D-A04: boundary tests of the terminal-status rule with hand-calculated expectations (SYNTHETIC_TEST data only).

EXPIRED_UNCLOSED IS AN INFERENCE, NOT AN OBSERVATION. The data contain no settlement, expiry-processing, exercise or square-off record. The engine labels an instrument/episode
EXPIRED_UNCLOSED when (a) its signed inventory at the end of the data is non-zero AND (b) its expiry DATE is <= the IST date of the last non-duplicate fill in the whole data set.
It therefore cannot distinguish "held to expiry" from "closed by the exchange / broker without a fill in this file". No settlement P&L is invented: realized P&L is the sum of closing allocations only.
The token EXPIRED_UNCLOSED is kept unchanged (delivered outputs contain it); this file pins the RULE, including the branch OPEN_AT_END_OF_DATA, which real data never exercise
(the real ledger ends on its maximum expiry date, 2026-10-22, so no real instrument has expiry after the last data day).

Rule (python/pe/replay.py status loop and python/pe/lineage.py::terminal_status):
  inventory == 0                                      -> CLOSED (episode: CLOSED if it ended flat, REVERSED if it ended by a reversal)
  inventory != 0 and expiry_date <= last_data_day     -> EXPIRED_UNCLOSED
  inventory != 0 and expiry_date  > last_data_day     -> OPEN_AT_END_OF_DATA
last_data_day = IST calendar day of the last non-duplicate fill = (epoch + 19800) // 86400, NOT the UTC day.

Calendar used below: BASE_TS = 2026-01-05 09:16 IST (Monday). Offsets are seconds after BASE_TS; one day = 86400 s. 2026-01-05 + 3 days = 2026-01-08, + 7 = 2026-01-12.
Prices are paise on the 5-paise tick; lot 65."""
import dataclasses as dc
import pytest
from pe import replay as rp
from pe.schema import *
from pe.lineage_set import LineageSet
from pe.generators import synthetic as S
M = 'SYNTHETIC_TEST'
DAY = 86400


def build(*specs, fills):
    """specs: dict(expiry, strike) -> instrument ids in order; fills: (instrument index, ts_off, side, qty, px_paise)"""
    b = S.Builder('expiry_status'); ids = [b.add_inst(expiry=e, strike=k) for e, k in specs]
    for ix, off, side, qty, px in fills: b.fill(ids[ix], off, side, qty, px)
    ins, fl = b.out(); return ids, ins, fl


def run(ins, fills, method='FIFO'): return rp.replay(fills, ins, M, method, 'src', lineage=True)


def instr_status(res):
    """instrument id -> status token from the state dump (INSTR line, last field)"""
    return {l.split('\t')[1]: l.split('\t')[-1] for l in res.dump.splitlines() if l.startswith('INSTR\t')}


def episodes(res):
    """episode id -> dict from episodes.tsv (the lineage layer's terminal_status)"""
    rows = rp.lineage_files(res)['episodes.tsv'].splitlines(); h = rows[0].split('\t'); return {r.split('\t')[0]: dict(zip(h, r.split('\t'))) for r in rows[1:]}


def total(res, key): return next(l.split('\t')[2] for l in res.dump.splitlines() if l.startswith(f'TOTAL\t{key}\t'))


def every_method_agrees(ins, fills):
    """status is convention independent: FIFO, LIFO and AVG give identical statuses"""
    ref = None
    for m in METHODS:
        r = run(ins, fills, m); cur = (instr_status(r), {k: v['terminal_status'] for k, v in episodes(r).items()})
        assert ref is None or cur == ref, m; ref = cur
    return ref


# ----------------------------------------------------------------------------------------- 1. non-flat at data end, expiry already reached
def test_non_flat_with_expiry_already_reached_is_EXPIRED_UNCLOSED():
    """A (expiry 2026-01-08): short 65 on 01-05. B (expiry 2026-01-29): short 65 on 01-12 = last data day. A is non-flat and 01-08 <= 01-12 -> EXPIRED_UNCLOSED; B: 01-29 > 01-12 -> OPEN_AT_END_OF_DATA."""
    ids, ins, fl = build(('2026-01-08', 24000), ('2026-01-29', 24100), fills=[(0, 0, -1, 65, 10000), (1, 7 * DAY, -1, 65, 11000)])
    r = run(ins, fl); st = instr_status(r)
    assert r.last_day == days_from_civil(2026, 1, 12) and day_iso(r.last_day) == '2026-01-12'
    assert st[ids[0]] == 'EXPIRED_UNCLOSED' and st[ids[1]] == 'OPEN_AT_END_OF_DATA'
    assert total(r, 'remaining_expired_unclosed_units') == '65' and total(r, 'remaining_open_at_end_units') == '65' and r.warnings['EXPIRED_UNCLOSED_INSTRUMENTS'] == 1
    assert total(r, 'realized_pnl_paise') == '0'                                                  # nothing closed: no settlement P&L is invented
    ep = episodes(r); assert {v['instrument_id']: v['terminal_status'] for v in ep.values()} == {ids[0]: 'EXPIRED_UNCLOSED', ids[1]: 'OPEN_AT_END_OF_DATA'}
    every_method_agrees(ins, fl); LineageSet(fl, ins, M, 'src').check(fl)


# ----------------------------------------------------------------------------------------- 2. non-flat at data end, expiry NOT yet reached
def test_non_flat_with_expiry_not_yet_reached_is_OPEN_AT_END_OF_DATA():
    """one contract (expiry 2026-01-15), short 65 on 01-05, the data end on 01-05: 01-15 > 01-05 -> OPEN_AT_END_OF_DATA, the expired counters stay 0."""
    ids, ins, fl = build(('2026-01-15', 24000), fills=[(0, 0, -1, 65, 10000)])
    r = run(ins, fl); assert instr_status(r) == {ids[0]: 'OPEN_AT_END_OF_DATA'}
    assert total(r, 'remaining_open_at_end_units') == '65' and total(r, 'remaining_expired_unclosed_units') == '0' and r.warnings['EXPIRED_UNCLOSED_INSTRUMENTS'] == 0
    assert [v['terminal_status'] for v in episodes(r).values()] == ['OPEN_AT_END_OF_DATA']
    assert 'OPEN_AT_END_OF_DATA' not in 'EXPIRED_UNCLOSED' and every_method_agrees(ins, fl)[0] == {ids[0]: 'OPEN_AT_END_OF_DATA'}
    LineageSet(fl, ins, M, 'src').check(fl)


# ----------------------------------------------------------------------------------------- 3. flat before expiry
def test_flat_before_expiry_is_CLOSED_even_if_the_data_run_past_the_expiry():
    """short 65 @ 100.00 and buy 65 @ 90.00 on 01-05 (expiry 01-15): CLOSED. A filler contract trades on 01-20 (after the expiry): the closed contract stays CLOSED, never EXPIRED_UNCLOSED.
    Realized FIFO = 65 * (10000 - 9000) = 65,000 paise."""
    ids, ins, fl = build(('2026-01-15', 24000), ('2026-02-26', 24100), fills=[(0, 0, -1, 65, 10000), (0, 60, 1, 65, 9000), (1, 15 * DAY, -1, 65, 5000)])
    r = run(ins, fl); st = instr_status(r)
    assert day_iso(r.last_day) == '2026-01-20' and st[ids[0]] == 'CLOSED' and st[ids[1]] == 'OPEN_AT_END_OF_DATA'
    assert total(r, 'realized_pnl_paise') == '65000' and r.warnings['EXPIRED_UNCLOSED_INSTRUMENTS'] == 0
    ep = {v['instrument_id']: v for v in episodes(r).values()}; assert ep[ids[0]]['terminal_status'] == 'CLOSED' and ep[ids[0]]['ended_by'] == 'flat' and ep[ids[0]]['remaining'] == '0'
    every_method_agrees(ins, fl); LineageSet(fl, ins, M, 'src').check(fl)


# ----------------------------------------------------------------------------------------- 4. expiry day equals the last data day
@pytest.mark.parametrize('expiry,status', [('2026-01-05', 'EXPIRED_UNCLOSED'), ('2026-01-04', 'EXPIRED_UNCLOSED'), ('2026-01-06', 'OPEN_AT_END_OF_DATA')])
def test_expiry_day_equal_to_the_last_data_day_counts_as_expired(expiry, status):
    """last data day 2026-01-05: expiry == 01-05 -> EXPIRED_UNCLOSED (the rule is <=, hand-checked: 01-05 <= 01-05), expiry 01-04 -> EXPIRED_UNCLOSED, expiry 01-06 -> OPEN_AT_END_OF_DATA"""
    ids, ins, fl = build((expiry, 24000), fills=[(0, 0, -1, 65, 10000)])
    assert instr_status(run(ins, fl)) == {ids[0]: status} and every_method_agrees(ins, fl)[0] == {ids[0]: status}


@pytest.mark.parametrize('off,expiry,status', [
    (53039, '2026-01-06', 'OPEN_AT_END_OF_DATA'),          # 09:16 IST + 14:43:59 = 23:59:59 IST on 01-05 (18:29:59 UTC): the IST day is 01-05, expiry 01-06 is later
    (53040, '2026-01-06', 'EXPIRED_UNCLOSED'),             # +14:44:00 = 00:00:00 IST on 01-06 (18:30:00 UTC on 01-05): the IST day is 01-06 == expiry
    (22 * 60, '2026-01-05', 'EXPIRED_UNCLOSED')])          # +22 min = 09:38 IST on 01-05 == expiry day
def test_last_data_day_is_the_IST_calendar_day_not_the_UTC_day(off, expiry, status):
    ids, ins, fl = build((expiry, 24000), fills=[(0, off, -1, 65, 10000)])
    assert instr_status(run(ins, fl)) == {ids[0]: status}


def test_last_data_day_ignores_flagged_duplicate_fills():
    """a duplicate-flagged fill on 01-12 is not applied and must not move the last data day: the data end on 01-05, contract expiry 01-08 -> OPEN_AT_END_OF_DATA (if the duplicate counted, 01-08 <= 01-12 would give EXPIRED_UNCLOSED)"""
    ids, ins, fl = build(('2026-01-08', 24000), fills=[(0, 0, -1, 65, 10000), (0, 7 * DAY, -1, 65, 10000)]); fl[1] = dc.replace(fl[1], is_duplicate_fill=True)
    r = run(ins, fl); assert day_iso(r.last_day) == '2026-01-05' and instr_status(r) == {ids[0]: 'OPEN_AT_END_OF_DATA'}


# ----------------------------------------------------------------------------------------- 5. position reversed at expiry
def test_position_reversed_on_the_expiry_day_splits_into_REVERSED_and_EXPIRED_UNCLOSED():
    """contract expiry 01-08. long 65 @ 50.00 on 01-05; on 01-08 (= expiry = last data day) sell 130 @ 60.00: closes 65 (realized 65 * (6000 - 5000) = 65,000 paise) and opens a 65 short in a NEW episode.
    Episode #1: opened 65, closed 65, ended by reversal -> REVERSED. Episode #2: opened 65, remaining 65, expiry 01-08 <= 01-08 -> EXPIRED_UNCLOSED. Instrument inventory -65 -> EXPIRED_UNCLOSED. No settlement P&L for the 65 short."""
    ids, ins, fl = build(('2026-01-08', 24000), fills=[(0, 0, 1, 65, 5000), (0, 3 * DAY, -1, 130, 6000)])
    r = run(ins, fl); ep = episodes(r)
    assert instr_status(r) == {ids[0]: 'EXPIRED_UNCLOSED'} and total(r, 'reversal_fills') == '1' and total(r, 'reversal_units_reopened') == '65'
    e1, e2 = ep[f'{ids[0]}#1'], ep[f'{ids[0]}#2']
    assert (e1['direction'], e1['opened'], e1['closed'], e1['ended_by'], e1['terminal_status']) == ('1', '65', '65', 'reversal', 'REVERSED')
    assert (e2['direction'], e2['opened'], e2['closed'], e2['remaining'], e2['started_by_reversal'], e2['terminal_status']) == ('-1', '65', '0', '65', '1', 'EXPIRED_UNCLOSED')
    assert total(r, 'realized_pnl_paise') == '65000' and total(r, 'remaining_expired_unclosed_units') == '65' and total(r, 'remaining_open_at_end_units') == '0'
    every_method_agrees(ins, fl); LineageSet(fl, ins, M, 'src').check(fl)


def test_position_reversed_before_expiry_leaves_OPEN_AT_END_OF_DATA_for_the_new_episode():
    """same fills, contract expiry 01-15 (> last data day 01-08): episode #1 REVERSED, episode #2 OPEN_AT_END_OF_DATA; nothing is expired"""
    ids, ins, fl = build(('2026-01-15', 24000), fills=[(0, 0, 1, 65, 5000), (0, 3 * DAY, -1, 130, 6000)])
    r = run(ins, fl); ep = episodes(r)
    assert [ep[f'{ids[0]}#1']['terminal_status'], ep[f'{ids[0]}#2']['terminal_status']] == ['REVERSED', 'OPEN_AT_END_OF_DATA'] and instr_status(r) == {ids[0]: 'OPEN_AT_END_OF_DATA'}
    assert total(r, 'remaining_expired_unclosed_units') == '0' and total(r, 'remaining_open_at_end_units') == '65' and r.warnings['EXPIRED_UNCLOSED_INSTRUMENTS'] == 0


def test_reversed_and_then_flat_on_the_expiry_day_has_no_expired_episode():
    """long 65 (01-05), sell 130 (01-08), buy 65 (01-08, expiry day): #1 REVERSED, #2 CLOSED (flat), instrument CLOSED; realized = 65 * (6000 - 5000) + 65 * (6000 - 5500) = 65,000 + 32,500 = 97,500 paise"""
    ids, ins, fl = build(('2026-01-08', 24000), fills=[(0, 0, 1, 65, 5000), (0, 3 * DAY, -1, 130, 6000), (0, 3 * DAY + 60, 1, 65, 5500)])
    r = run(ins, fl); ep = episodes(r)
    assert [ep[f'{ids[0]}#1']['terminal_status'], ep[f'{ids[0]}#2']['terminal_status']] == ['REVERSED', 'CLOSED'] and instr_status(r) == {ids[0]: 'CLOSED'}
    assert total(r, 'realized_pnl_paise') == '97500' and r.warnings['EXPIRED_UNCLOSED_INSTRUMENTS'] == 0
    every_method_agrees(ins, fl); LineageSet(fl, ins, M, 'src').check(fl)


# ----------------------------------------------------------------------------------------- the rule is applied identically by the lineage layer
def test_lineage_terminal_status_function_matches_the_replay_rule_at_the_boundary():
    """call lineage.terminal_status directly with hand-built episodes: last_day vs expiry"""
    from pe import lineage as ln
    ins = {'X': dc.replace(S.inst(expiry='2026-01-08'), instrument_id='X')}; ep = dict(instrument_id='X', opened=65, closed=0, ended_by='open')
    d = days_from_civil(2026, 1, 8)
    assert ln.terminal_status(None, ep, ins, d - 1) == 'OPEN_AT_END_OF_DATA' and ln.terminal_status(None, ep, ins, d) == 'EXPIRED_UNCLOSED' and ln.terminal_status(None, ep, ins, d + 1) == 'EXPIRED_UNCLOSED'
    assert ln.terminal_status(None, dict(ep, closed=65, ended_by='flat'), ins, d + 5) == 'CLOSED' and ln.terminal_status(None, dict(ep, closed=65, ended_by='reversal'), ins, d + 5) == 'REVERSED'
    assert 'INCOMPLETE_SOURCE_HISTORY' in ln.TERMINAL and ln.terminal_status(None, ep, ins, d) != 'INCOMPLETE_SOURCE_HISTORY'        # reserved token is never produced from the ledger alone


# ----------------------------------------------------------------------------------------- real data: the rule's footprint (read-only)
@pytest.mark.slow
def test_real_ledger_footprint_of_the_rule_81_expired_and_no_open_at_end():
    """real ledger (TP-01 ledger via the historical generator, FIFO replay): the last data day equals the maximum expiry (2026-10-22), so OPEN_AT_END_OF_DATA never occurs and no expiry is after the last data day.
    81 instruments are non-flat; their last fill is 0 days before the expiry day for 54 and 1 day before for 27 (audit track A expiry_analysis); this is the only evidence for 'held to expiry' (an inference, no settlement data)."""
    from conftest import REPO
    from pe.generators import historical as H
    ins, fills, _ = H.generate(REPO); r = rp.replay(fills, ins, 'HISTORICAL_OBSERVED_REPLAY', 'FIFO', 'src')
    st = instr_status(r); exp = {k: v.expiry for k, v in ins.items()}
    assert day_iso(r.last_day) == '2026-10-22' == max(exp.values())
    assert sum(1 for v in st.values() if v == 'EXPIRED_UNCLOSED') == 81 and sum(1 for v in st.values() if v == 'OPEN_AT_END_OF_DATA') == 0
    live = [f for f in fills if not f.is_duplicate_fill]; last = {}
    for f in live: last[f.instrument_id] = max(last.get(f.instrument_id, 0), f.timestamp_s)
    gaps = {}
    for k, v in st.items():
        if v == 'EXPIRED_UNCLOSED': g = iso_day(exp[k]) - ist_day(last[k]); gaps[g] = gaps.get(g, 0) + 1
    assert gaps == {0: 54, 1: 27}
    assert sum(1 for k, v in st.items() if v == 'EXPIRED_UNCLOSED' and exp[k] == '2026-10-22') == 0      # no non-flat instrument expires on the last data day: the <= boundary is not exercised by real data
