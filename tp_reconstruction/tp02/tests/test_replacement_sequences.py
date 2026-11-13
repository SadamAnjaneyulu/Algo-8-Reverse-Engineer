import numpy as np, pandas as pd, pytest
from conftest import need_data, c
from build_exit_timelines import counts


def test_counts_helper_counts_a_closed_interval():
    t = np.array([1, 2, 2, 5, 9]); assert counts(t, 2, 5) == 3 and counts(t, 6, 8) == 0 and counts(t, 0, 100) == 5


@need_data
def test_replacement_flag_requires_a_same_right_opening_within_the_registered_window(T):
    s = T[T.direction == -1]; r = s[s.flag_replacement]
    assert (r.first_open_relation.isin(['same_contract', 'same_right_other_strike'])).all() and (r.first_open_dt_s <= c.CFG['replacement']['window_seconds']).all()
    assert not T[T.direction == 1].flag_replacement.any()


@need_data
def test_strict_replacement_is_a_subset_with_sequence_and_quantity_evidence(T):
    s = T[T.direction == -1]; st = s[s.flag_replacement_strict]
    assert s.flag_replacement[s.flag_replacement_strict].all() and (st.first_open_sequence_evidence == 'opening_order_submitted_after').all() and (st.first_open_units == st.qty_closed).all()


@need_data
def test_sequence_evidence_only_inside_one_number_block(TL):
    k = TL[TL.first_open_sequence_evidence != 'unknown']; assert k.first_open_relation.notna().all() and k.num_block.notna().all()
    assert (TL[TL.first_open_relation.isna()].first_open_sequence_evidence == 'unknown').all()


@need_data
def test_next_events_are_after_the_closing_and_inside_the_longest_window(TL):
    f = TL[TL.first_open_dt_s.notna()]; assert (f.first_open_dt_s > 0).all() and (f.first_open_dt_s <= max(c.WINDOWS)).all()
    assert (TL.next_close_same_contract_dt_s.dropna() > -1).all()
    assert ((TL.n_O_short_same_contract_next60s > 0) <= (TL.n_O_short_same_contract_next300s > 0)).all()


@need_data
def test_replacement_relations_are_consistent_with_the_window_counts(TL):
    s = TL[(TL.direction == -1) & (TL.first_open_relation == 'same_contract') & (TL.first_open_dt_s <= 300)]
    assert (s.n_O_short_same_contract_next300s > 0).all()
    o = TL[(TL.first_open_relation == 'opposite_right')]; assert ((o.n_O_short_same_contract_next300s + o.n_O_short_same_right_other_strike_next300s) == 0).all()
