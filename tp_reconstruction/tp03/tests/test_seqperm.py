import os, sys, yaml
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); TP03 = os.path.dirname(HERE); sys.path.insert(0, os.path.join(TP03, 'scripts'))
import seqperm as sp
CFG = yaml.safe_load(open(os.path.join(TP03, 'config.yaml'))); PAR = CFG['inference']['permutations']['parameters']; SEED = CFG['inference']['seed']
unif = lambda rng: rng.random()


def test_parameters_in_the_config_match_the_registered_rule():
    assert PAR == {'h_stop': 100, 'n_max': 10000, 'extend_if_exceedances_at_most': 10, 'n_max_extended': 100000} and SEED == 20261114 and CFG['inference']['permutations']['final_inference'] == 10000


def test_same_seed_is_reproducible_and_different_tests_get_different_streams():
    a = sp.run_test('E2-x', 0.99, unif, SEED, PAR); b = sp.run_test('E2-x', 0.99, unif, SEED, PAR); c = sp.run_test('E2-y', 0.99, unif, SEED, PAR)
    assert a == b and a['seed_entropy'] == f'{SEED}-{sp.zlib.crc32(b"E2-x")}' and c['seed_entropy'] != a['seed_entropy'] and (c['draws'], c['exceedances']) != (a['draws'], a['exceedances'])


def test_stops_at_the_h_th_exceedance_with_p_equal_h_over_L():
    r = sp.run_test('stop', 0.9, unif, SEED, PAR)                       # true p = 0.1 -> about 1,000 draws for 100 exceedances
    assert r['stopped_by'] == 'h_exceedances' and r['exceedances'] == 100 and not r['extended'] and abs(r['p'] - 100 / r['draws']) < 1e-12 and 700 < r['draws'] < 1500 and abs(r['p'] - 0.1) < 0.03


def test_unbiased_for_a_known_tail_probability():
    ps = [sp.run_test(f'k{i}', 0.9, unif, SEED, PAR)['p'] for i in range(200)]
    assert abs(np.mean(ps) - 0.1) < 0.005                                # mean of h/L is close to the true tail probability


def test_never_exceeded_statistic_extends_to_100000_and_gives_the_minimum_p():
    r = sp.run_test('ext', 2.0, unif, SEED, PAR)
    assert r['extended'] and r['stopped_by'] == 'n_max_extended' and r['draws'] == 100000 and r['exceedances'] == 0 and r['p'] == 1 / 100001


def test_extension_is_decided_by_the_exceedance_count_only():
    rare = sp.sequential_permutation_p(0.9992, unif, np.random.default_rng(1))        # ~8 exceedances in 10,000 -> extended
    common = sp.sequential_permutation_p(0.997, unif, np.random.default_rng(1))       # ~30 exceedances in 10,000 -> not extended, no h reached
    assert rare['extended'] and rare['draws'] > 10000 and common['stopped_by'] == 'n_max' and not common['extended'] and common['draws'] == 10000
    assert common['exceedances'] > 10 and common['p'] == (common['exceedances'] + 1) / 10001
    # the extension continues the same stream: the first 10,000 draws are identical with and without extension
    a = sp.sequential_permutation_p(0.9992, unif, np.random.default_rng(5), n_max_extended=10000); b = sp.sequential_permutation_p(0.9992, unif, np.random.default_rng(5))
    assert a['exceedances'] <= b['exceedances'] and a['draws'] == 10000 and not a['extended']


def test_recorded_counts_are_consistent_and_resolution_is_as_registered():
    for obs in (0.5, 0.9, 0.999, 1.5):
        r = sp.run_test(f'rec{obs}', obs, unif, SEED, PAR); assert 1 <= r['draws'] <= 100000 and 0 <= r['exceedances'] <= r['draws'] and r['p'] >= 1 / 100001
        if r['stopped_by'] == 'n_max': assert r['draws'] == 10000 and r['p'] == (r['exceedances'] + 1) / 10001


def test_validity_under_the_null_p_below_alpha_is_at_most_alpha():
    """observed and permutation statistics from the same distribution; scaled-down parameters keep the test fast"""
    rng = np.random.default_rng(123); ps = []
    for i in range(3000):
        obs = rng.random(); r = sp.sequential_permutation_p(obs, unif, rng, h_stop=20, n_max=300, extend_if_at_most=2, n_max_extended=1500); ps.append(r['p'])
    ps = np.array(ps)
    for a in (0.01, 0.05, 0.1, 0.25, 0.5): assert (ps <= a).mean() <= a + 0.02, (a, (ps <= a).mean())


def test_ties_are_counted_as_exceedances_and_stay_conservative():
    r = sp.sequential_permutation_p(1.0, lambda rng: 1.0, np.random.default_rng(0), h_stop=100, n_max=500, extend_if_at_most=10, n_max_extended=500)
    assert r['stopped_by'] == 'h_exceedances' and r['draws'] == 100 and r['p'] == 1.0
