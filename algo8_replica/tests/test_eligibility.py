import os, pandas as pd, yaml, pytest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REG = f'{ROOT}/experiments/results/cycle_eligibility_register.csv'
pytestmark = pytest.mark.skipif(not os.path.exists(REG), reason='register not built')


def reg(): return pd.read_csv(REG)


def test_every_expected_cycle_is_classified_once():
    R = reg(); assert len(R) == 319 and not R.duplicated(['und', 'expiry']).any()
    assert set(R.eligibility) <= {'FULLY_FEASIBLE', 'FEASIBLE_WITH_DECLARED_SUBSTITUTION', 'PARTIAL', 'UNUSABLE'}


def test_no_silent_drops_reasons_recorded():
    R = reg(); bad = R[R.eligibility.isin(['PARTIAL', 'UNUSABLE', 'FEASIBLE_WITH_DECLARED_SUBSTITUTION'])]; assert bad.reasons.fillna('').str.len().gt(0).all()


def test_fully_feasible_requires_exact_wings_and_windows():
    F = reg(); F = F[F.eligibility == 'FULLY_FEASIBLE']
    assert F.wing_ce_exact.all() and F.wing_pe_exact.all() and F.open_atm_exec.all() and (F.d1_windows_exec >= 15).all() and (F.validation_status == 'Complete').all()


def test_missing_and_special_sessions_are_unusable():
    R = reg(); assert (R[R.validation_status == 'Missing'].eligibility == 'UNUSABLE').all(); assert (R[R.special_d1 == True].eligibility == 'UNUSABLE').all()


def test_tiers_never_call_inspected_data_out_of_sample():
    R = reg(); assert not any('OOS' in t.upper() for t in R.tier.unique())
    assert (R[R.d0 <= '2025-11-17'].tier == 'T3_in_sample_of_prior_programmes').all()
    assert (R[(R.d0 >= '2026-06-22') & (R.d0 <= '2026-10-22')].tier == 'T4_live_window_reverse_engineering').all()
    assert (R[R.d0 > '2026-10-22'].tier == 'T1_never_evaluated').all()


def test_criteria_file_has_no_performance_terms():
    txt = open(f'{ROOT}/config/eligibility_criteria.yaml').read().lower()
    assert not any(w in txt for w in ('sharpe', 'p&l', 'profit factor')) or 'never on p&l' in txt


def test_sensex_before_first_session_is_unusable():
    R = reg(); S = R[(R.und == 'SENSEX') & (R.d0 < '2024-05-30')]; assert len(S) > 0 and (S.eligibility == 'UNUSABLE').all()
