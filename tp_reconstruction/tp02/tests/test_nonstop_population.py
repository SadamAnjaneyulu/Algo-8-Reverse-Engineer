import numpy as np, pandas as pd, pytest
from conftest import need_data, c


@need_data
def test_populations_are_nested_and_conservative(T):
    s = T[T.direction == -1]
    assert (s.pop3_clean_nonstop <= s.pop1_profit_stable).all() and (s.pop4_unexplained_body <= s.pop3_clean_nonstop).all() and (s.pop4_unexplained_body <= s.pop4s_unexplained_strict).all() and (s.pop4s_unexplained_strict <= s.pop3_clean_nonstop).all()
    p3 = s[s.pop3_clean_nonstop]
    assert (p3.module == 'num').all() and (p3.stop_class == 'STOP_NOT_EVIDENCED').all() and (~p3.order_ambiguous).all() and (~p3.dq_flag_any).all() and (p3.consensus_label == 'PROFIT').all()
    assert not (p3.in_cycle_stop_window | p3.stop_adverse_premium | p3.stop_own_price).any()


@need_data
def test_stable_profit_requires_profit_under_all_three_conventions(T):
    s = T[T.direction == -1]; st = s[s.pop1_profit_stable]; assert (st[[f'label_{m}' for m in c.METHODS]] == 'PROFIT').all().all()
    sens = s[s.profit_class == 'SENSITIVE_PROFIT']; assert (sens[[f'label_{m}' for m in c.METHODS]].eq('PROFIT').any(axis=1)).all() and not sens.pop1_profit_stable.any()


@need_data
def test_unexplained_means_no_registered_flag(T):
    p4 = T[T.pop4_unexplained_body]; assert not (p4.flag_clock | p4.flag_expiry_mgmt | p4.flag_replacement | p4.flag_wing_linked).any()
    q = T[T.pop4s_unexplained_strict]; assert not (q.flag_clock | q.flag_expiry_mgmt | q.flag_replacement_strict | q.flag_wing_linked_strict).any()


@need_data
def test_stop_related_population_contains_every_confirmed_short(T):
    s = T[T.direction == -1]; assert s[s.stop_class == 'STOP_CONFIRMED'].pop2_stop_related.all() and not (s.pop2_stop_related & s.pop3_clean_nonstop).any()


@need_data
def test_population_counts_reconcile(T):
    s = T[T.direction == -1]; p1 = s.pop1_profit_stable.sum()
    assert (s.pop1_profit_stable & s.pop2_stop_related).sum() + (s.pop1_profit_stable & ~s.pop2_stop_related).sum() == p1 and s.pop3_clean_nonstop.sum() <= (s.pop1_profit_stable & ~s.pop2_stop_related).sum()


@need_data
def test_candidate_file_matches_the_population_flags(T):
    import os
    Cn = pd.read_parquet(os.path.join(c.DATA, 'profitable_nonstop_candidates.parquet')); s = T[(T.direction == -1) & T.profit_class.isin(['STABLE_PROFIT', 'SENSITIVE_PROFIT'])]
    assert len(Cn) == len(s) and set(Cn.close_row) == set(s.close_row) and Cn.close_row.is_unique
    assert (Cn.population == 'POP3_CLEAN_NONSTOP').sum() + (Cn.population == 'POP4S_UNEXPLAINED_STRICT').sum() + (Cn.population == 'POP4_UNEXPLAINED_REGISTERED').sum() == Cn.pop3_clean_nonstop.sum()
    assert (Cn[Cn.population == 'POP1B_CONVENTION_SENSITIVE'].profit_class == 'SENSITIVE_PROFIT').all()
