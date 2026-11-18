import os
import numpy as np, pandas as pd, pytest
from conftest import need_data, c
from test_hypotheses import holm, BinHazard


@need_data
def test_counts_and_quantities_reconcile_with_tp01():
    R = pd.read_csv(os.path.join(c.DATA, 'mechanism_reconciliation.csv')); assert (R['difference'] == 0).all() and len(R) >= 20
    assert int(R[R.check == 'closed units'].tp02.iloc[0]) == 1377065 and int(R[R.check == 'closing fills'].tp02.iloc[0]) == 17760


@need_data
def test_every_closing_fill_has_exactly_one_stop_class_and_one_mechanism(T):
    assert T.close_row.is_unique and T.candidate_mechanism.notna().all() and T.confidence.notna().all()
    assert set(T.confidence) <= {'HIGH', 'MEDIUM', 'LOW', 'UNRESOLVED', 'UNEXPLAINED'}


@need_data
def test_pre_registered_definitions_are_unchanged():
    cfg = c.CFG; assert cfg['stop']['adverse_ratio'] == 1.25 and cfg['replacement']['window_seconds'] == 60 and cfg['wing']['link_window_seconds'] == 10 and cfg['basket']['window_seconds'] == 5
    assert cfg['basket']['used_in_unexplained_definition'] is False and cfg['verdict_rubric']['SUPPORTED'].startswith('effect in all three conventions')
    assert cfg['effect_thresholds']['ratio_effect_present'] == 1.5 and cfg['inference']['bootstrap_unit'] == 'expiry_cycle'


@need_data
def test_hypothesis_output_has_every_registered_test_and_holm_is_applied():
    H = pd.read_csv(os.path.join(c.ANALYSIS, 'hypothesis_tests.csv')); ids = set(H.test_id)
    assert {'H1-FIFO', 'H1-LIFO', 'H1-AVG', 'H4b-MTM', 'H2a-grid', 'H2b-timer-FIFO', 'H2b-timer-LIFO', 'H4a-basket', 'H3-readd', 'H6-replacement'} <= ids and sum(i.startswith('H5-') for i in ids) == 6
    assert (H.holm_p >= H.perm_p - 1e-12).all() and set(H.verdict) <= {'SUPPORTED', 'PARTIAL', 'NOT_SUPPORTED', 'INCONCLUSIVE'}


def test_holm_adjustment_matches_the_definition():
    p = np.array([0.01, 0.04, 0.03, 0.2]); assert np.allclose(holm(p), [0.04, 0.09, 0.09, 0.2])


def _panel(effect, seed=0, n=6000):
    rng = np.random.default_rng(seed); b = rng.integers(0, 20, n); gid = np.sort(rng.integers(0, 60, n)); strata = rng.integers(0, 4, n); cyc = gid % 6
    p = np.where(b == 7, 0.30 if effect else 0.10, 0.10); y = rng.random(n) < p
    return BinHazard(b, y, strata, cyc, 20), gid


def test_binned_hazard_detects_a_planted_bin_and_not_a_null():
    for effect in (True, False):
        bh, gid = _panel(effect); r = bh.run(0, 20, 50, 100, None, gid)
        if effect: assert r['best_bin'] == 7 and r['max_ratio'] > 1.8 and r['perm_p'] < 0.05
        else: assert r['perm_p'] > 0.05
