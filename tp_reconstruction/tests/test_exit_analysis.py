import numpy as np, pandas as pd, pytest
from conftest import tc
import analyze_exits as ax


def test_cluster_rule_flags_a_planted_spike_and_ignores_a_flat_profile():
    flat = pd.Series([200] * 20, index=np.arange(0, 100, 5)); assert not ax.clusters(flat, 100, 3.0, 3).is_cluster.any()
    spike = flat.copy(); spike.loc[50] = 900; c = ax.clusters(spike, 100, 3.0, 3); assert c[c.key == 50].is_cluster.iloc[0] and c.is_cluster.sum() == 1


def test_cluster_rule_needs_the_minimum_count_and_uses_neighbours_without_the_bin_itself():
    low = pd.Series([10] * 20, index=np.arange(0, 100, 5)); low.loc[50] = 60; assert not ax.clusters(low, 100, 3.0, 3).is_cluster.any()          # ratio 6 but only 60 fills
    edge = pd.Series([100, 400, 100, 100], index=[0, 5, 10, 15]); c = ax.clusters(edge, 100, 3.0, 3).set_index('key'); assert c.loc[5, 'neighbour_median'] == 100 and c.loc[5, 'is_cluster']


def test_declared_candidate_rule_is_fixed_in_the_config():
    r = tc.CFG['candidate_rules']; assert r['decay_bin_width_pct'] == 5 and r['cluster_excess_ratio'] == 3.0 and r['cluster_min_count'] == 100 and r['max_candidates'] == 3


def test_controlled_hazard_ratio_removes_a_pure_time_effect():
    rng = np.random.default_rng(0); n = 4000
    P = pd.DataFrame({'d0': rng.random(n) < .5, 'tod_hour': rng.integers(0, 6, n)}); P['p'] = np.where(P.d0, .3, .05); P['y'] = rng.random(n) < P.p
    cond = pd.Series(P.d0.values & (rng.random(n) < .8))                       # the "condition" lives only on expiry days
    inb = P[cond.values]; nb = P[~cond.values]
    raw = inb.y.mean() / nb.y.mean(); ctl = ax.std_ratio(inb, nb, 'y', ('d0', 'tod_hour'))
    assert raw > 2 and abs(ctl - 1) < 0.25


def test_auc_rank():
    assert ax.auc_rank([3, 4], [1, 2]) == 1.0 and ax.auc_rank([1, 2], [3, 4]) == 0.0 and ax.auc_rank([1, 1], [1, 1]) == 0.5
