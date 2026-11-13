import os
import numpy as np, pandas as pd, pytest
from conftest import need_data, c
CFG = c.CFG


def test_tag_time_decoding_from_the_tag_specification():
    t = pd.Timestamp('2026-07-14 09:15:19')
    d = c.decode_tag_time('s_14034517101019', t)            # DD=14 HH=03 MM=45 SS=17 us=101019 UTC -> 09:15:17.101019 IST
    assert d == pd.Timestamp('2026-07-14 09:15:17.101019')
    assert pd.isna(c.decode_tag_time('12345678', t)) and pd.isna(c.decode_tag_time('s_15034517101019', t))      # no tag / wrong day
    assert pd.isna(c.decode_tag_time('s_14034517101019', pd.Timestamp('2026-07-14 12:00:00')))                   # inconsistent with the fill time


def test_session_phases_follow_the_registered_windows():
    assert c.phase_of([9 * 60 + 15, 12 * 60, 14 * 60 + 30, 15 * 60 + 10, 15 * 60 + 30, 8 * 60]).tolist() == ['OPEN', 'MIDDAY', 'LATE', 'FINAL', 'POST', 'OUTSIDE']


def test_number_blocks_split_on_a_jump():
    L = pd.DataFrame({'parent_oid': list('abcd'), 'date': pd.Timestamp('2026-07-14'), 'app_key': 'x', 'order_no': ['100', '101', '5000', '5001']})
    b = c.number_blocks(L); assert b.loc['a', 'block'] == b.loc['b', 'block'] == 0 and b.loc['c', 'block'] == b.loc['d', 'block'] == 1


@need_data
def test_stop_classes_partition_every_closing_and_s_module_is_confirmed(T):
    assert T.stop_class.isin(['STOP_CONFIRMED', 'STOP_POSSIBLE', 'STOP_NOT_EVIDENCED']).all()
    assert ((T.module == 's_') == (T.stop_class == 'STOP_CONFIRMED')).all()
    assert not (T.stop_class == 'STOP_POSSIBLE').loc[T.module == 's_'].any()


@need_data
def test_stop_possible_sensitivity_thresholds_are_nested(T):
    s = T[T.direction == -1]
    assert (s['stop_adverse_premium_1.5'] <= s.stop_adverse_premium).all() and (s.stop_adverse_premium <= s['stop_adverse_premium_1.15']).all()
    assert CFG['stop']['adverse_ratio'] == 1.25 and CFG['stop']['adverse_ratio_sensitivity'] == [1.15, 1.5]


@need_data
def test_stop_possible_reasons_match_the_flags(T):
    p = T[T.stop_class == 'STOP_POSSIBLE']; assert (p.in_cycle_stop_window | p.stop_adverse_premium | p.stop_own_price).all() and (p.stop_reasons != '').all()
    n = T[T.stop_class == 'STOP_NOT_EVIDENCED']; assert not (n.in_cycle_stop_window | n.stop_adverse_premium | n.stop_own_price).any()


@need_data
def test_clock_flag_uses_every_registered_minute_not_only_three(T):
    reg = pd.read_csv(os.path.join(c.REPO, CFG['inputs']['clock_clusters'])).query('is_cluster').key.tolist()
    assert len(reg) == 7 and set(T[T.flag_clock].exec_minute) == set(reg)


@need_data
def test_candidate_mechanism_values_and_order_ambiguity_is_unresolved(T):
    ok = {'STOP_CONFIRMED', 'STOP_POSSIBLE', 'CLOCK', 'EXPIRY_MGMT', 'REPLACEMENT', 'WING_LINKED', 'MULTIPLE_POSSIBLE_MECHANISMS', 'UNEXPLAINED_BODY', 'MANUAL', 'LUMP_MODULE', 'UNRESOLVED', 'INSUFFICIENT_EVIDENCE'}
    assert set(T.candidate_mechanism) <= ok and (T[T.order_ambiguous].candidate_mechanism == 'UNRESOLVED').all() and (T[T.module == 'm_'].candidate_mechanism == 'MANUAL').all()


@need_data
def test_expiry_flag_and_categories(T):
    e = T[T.flag_expiry_mgmt]; assert (e.day_type == 'EXPIRY_DAY').all() and e.phase.isin(['LATE', 'FINAL', 'POST']).all()
    assert (T[T.day_type == 'CARRY_DAY'].expiry_category == 'D1_CARRY_DAY_REDUCTION').all() and T[T.day_type == 'EXPIRY_DAY'].expiry_category.str.startswith('D0_').all()
