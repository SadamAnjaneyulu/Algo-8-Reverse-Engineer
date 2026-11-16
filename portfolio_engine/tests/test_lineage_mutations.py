"""Mutation-style regression tests. Each mutation was found by the independent reviewer to SURVIVE an earlier version of the checks (check() was partly tautological); every one must now be rejected.
The failing scenarios are kept on purpose (not deleted after the fix)."""
import pytest
from pe import lineage as ln, replay as rp
from pe.schema import *
from pe.lineage_set import LineageSet
from pe.generators import synthetic as S, synthetic_m2 as S2
M = 'SYNTHETIC_TEST'


def fresh(name='reversal_100_130'):
    ins, fills = S2.M2_SCENARIOS[name](); ls = LineageSet(fills, ins, M, 'src'); ls.check(fills); return ls, fills            # baseline must pass


def rows(ls): return ls.runs['FIFO'].lineage.observed


def test_M1_duplicate_oa_row_is_detected():
    ls, fills = fresh(); rows(ls).append(rows(ls)[0])
    with pytest.raises(InvariantViolation, match='duplicate'): ls.check(fills)


def test_M2_reversed_event_carrying_the_whole_fill_quantity_is_detected():
    """the '130-unit close' mistake written into the lifecycle file"""
    ls, fills = fresh(); i = next(k for k, e in enumerate(ls.events) if e[3] == 'REVERSED'); e = ls.events[i]; ls.events[i] = e[:7] + (130,) + e[8:]
    with pytest.raises(InvariantViolation): ls.check(fills)


def test_M3_flipped_oa_side_is_detected():
    ls, fills = fresh(); r = rows(ls); i = next(k for k, x in enumerate(r) if x[0] == 'OA'); old = r[i]; new = old[:7] + (-old[7],) + old[8:]; r[i] = new; ls.oa[old[1]] = new
    with pytest.raises(InvariantViolation): ls.check(fills)


@pytest.mark.parametrize('field,delta', [(5, 5), (6, 5)])
def test_M4_ca_entry_or_exit_price_off_by_one_tick_is_detected(field, delta):
    ls, fills = fresh('ab_lots_close'); r = ls.ca['FIFO'][0]; ls.ca['FIFO'][0] = r[:field] + (r[field] + delta,) + r[field + 1:]
    with pytest.raises(InvariantViolation): ls.check(fills)


def test_M5_wrong_pnl_sign_is_detected():
    ls, fills = fresh('ab_lots_close'); r = ls.ca['LIFO'][0]; ls.ca['LIFO'][0] = r[:7] + (-r[7],) + r[8:]
    with pytest.raises(InvariantViolation): ls.check(fills)


def test_M6_wrong_slice_price_is_detected(monkeypatch):
    ls, fills = fresh('ab_lots_close'); orig = ln.slices_tsv
    def bad(state, rec):
        t = orig(state, rec).splitlines()
        if state.method == 'FIFO' and len(t) > 1: x = t[1].split('\t'); x[6] = str(int(x[6]) + 5); t[1] = '\t'.join(x)
        return '\n'.join(t) + '\n'
    monkeypatch.setattr(ln, 'slices_tsv', bad)
    with pytest.raises(InvariantViolation): ls.check(fills)


def test_M7_dropped_started_by_reversal_flag_is_detected():
    ls, fills = fresh(); i = next(k for k, e in enumerate(ls.events) if e[9] == 1); e = ls.events[i]; ls.events[i] = e[:9] + (0,)
    with pytest.raises(InvariantViolation): ls.check(fills)


def test_M8_non_unique_ca_ids_and_flipped_ownership_label_are_detected():
    ls, fills = fresh('fifo_lifo_diverge'); a = ls.ca['FIFO']; a[1] = (a[0][0],) + a[1][1:]
    with pytest.raises(InvariantViolation): ls.check(fills)
    ls, fills = fresh('ab_lots_close'); r = ls.ca['FIFO'][0]; ls.ca['FIFO'][0] = r[:9] + ('NOT_IDENTIFIABLE',)
    with pytest.raises(InvariantViolation): ls.check(fills)


def test_M9_zero_or_negative_quantity_is_rejected_by_the_in_memory_api():
    import dataclasses as dc
    ins, fills = S.open_close_full()
    for bad in (dc.replace(fills[1], quantity=0), dc.replace(fills[1], quantity=-5), dc.replace(fills[1], price_paise=0), dc.replace(fills[1], side=0)):
        with pytest.raises(EventValidationError): rp.replay([fills[0], bad], ins, M)


def test_M10_terminal_status_distinguishes_closed_reversed_and_expired():
    ls, _ = fresh('reversal_100_130'); st = {l.split('\t')[0]: l.split('\t')[8] for l in ls.files['FIFO']['episodes.tsv'].splitlines()[1:]}; assert sorted(st.values()) == ['OPEN_AT_END_OF_DATA', 'REVERSED']
    ins, fills = S.open_close_full(); ls = LineageSet(fills, ins, M); assert [l.split('\t')[8] for l in ls.files['FIFO']['episodes.tsv'].splitlines()[1:]] == ['CLOSED']


@pytest.mark.parametrize('expiry,status', [('2026-01-05', 'EXPIRED_UNCLOSED'), ('2026-01-06', 'OPEN_AT_END_OF_DATA'), ('2026-01-04', 'EXPIRED_UNCLOSED')])
def test_M11_expiry_boundary_is_exact(expiry, status):
    """expiry == last data day counts as expired (TP-01 rule `expiry <= last data date`); the day after does not"""
    b = S.Builder('expiry_boundary'); i = b.add_inst(expiry=expiry); b.fill(i, 0, -1, 65, 10000); ins, fills = b.out(); ls = LineageSet(fills, ins, M)
    assert ls.files['FIFO']['episodes.tsv'].splitlines()[1].split('\t')[8] == status


def test_M12_episode_timestamps_and_fill_counts_follow_the_events():
    ls, _ = fresh('multi_cycle_episodes')
    for eid, e in ls.episodes.items():
        evs = [x for x in ls.events if x[1] == eid]; assert e['last_ts'] == evs[-1][6] and e['first_ts'] == evs[0][6]
        assert e['n_close_fills'] == sum(1 for x in evs if x[3] in ('PARTIALLY_REDUCED', 'CLOSED', 'REVERSED')) and e['n_open_fills'] == sum(1 for x in evs if x[3] in ('CREATED', 'ADDED'))


def test_M13_large_notionals_pass_strict_invariants_for_every_convention():
    """reviewer: M1's absolute AVG tolerance failed strict mode on large synthetic notionals; the tolerance is now relative as well"""
    for seed in (7, 12, 21):
        ins, fills = S.random_stress(seed, 3000, 12); fills = [__import__('dataclasses').replace(f, price_paise=f.price_paise * 4000, quantity=f.quantity * 100) for f in fills]
        for m in METHODS: rp.replay(fills, ins, M, m, 'src', strict=True)
