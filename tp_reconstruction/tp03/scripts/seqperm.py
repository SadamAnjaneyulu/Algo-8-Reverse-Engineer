"""Sequential Monte-Carlo permutation p-value (Besag and Clifford 1991) with the pre-registered extension.
Rule (config inference.permutations): draw until h exceedances (statistic >= observed) at draw L or N draws.
  stopped at the h-th exceedance: p = h / L          not stopped: p = (m + 1) / (N + 1)
  if the N draws end with m <= extend_if_at_most exceedances the SAME stream is continued to N_ext draws (decision by the exceedance count only).
Every call returns a full record (seed entropy, draws made, exceedances, stopping reason, extension flag, p) for the permutation log."""
import zlib
import numpy as np


def test_rng(base_seed, test_id):
    """independent, reproducible stream per test; returns (Generator, entropy list)"""
    entropy = [int(base_seed), zlib.crc32(str(test_id).encode()) & 0xFFFFFFFF]
    return np.random.default_rng(np.random.SeedSequence(entropy)), entropy


def sequential_permutation_p(observed, draw, rng, h_stop=100, n_max=10000, extend_if_at_most=10, n_max_extended=100000):
    """draw(rng) -> one permutation statistic. Larger statistic = more extreme (one-sided, >=; ties count as exceedances, which is conservative)."""
    n = 0; m = 0; reason = None; extended = False; limit = n_max
    while True:
        s = draw(rng); n += 1
        if s >= observed: m += 1
        if m == h_stop: reason = 'h_exceedances'; p = h_stop / n; break
        if n == limit:
            if limit == n_max and m <= extend_if_at_most and n_max_extended > n_max: limit = n_max_extended; extended = True; continue
            reason = 'n_max_extended' if extended else 'n_max'; p = (m + 1) / (n + 1); break
    return dict(p=p, draws=n, exceedances=m, stopped_by=reason, extended=extended, h_stop=h_stop, n_max=n_max, n_max_extended=n_max_extended)


def run_test(test_id, observed, draw, base_seed, params):
    """convenience wrapper used by the entry / exit programs: seeds per test and returns the log record"""
    rng, entropy = test_rng(base_seed, test_id)
    r = sequential_permutation_p(observed, draw, rng, h_stop=params['h_stop'], n_max=params['n_max'], extend_if_at_most=params['extend_if_exceedances_at_most'], n_max_extended=params['n_max_extended'])
    r.update(test_id=test_id, seed_entropy='-'.join(str(e) for e in entropy), observed=float(observed)); return r
