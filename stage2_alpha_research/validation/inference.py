"""Inference tools (Milestone 2).  The unit of resampling is always the session date; rows are never resampled or shuffled individually.

  cluster bootstrap   : draw session dates with replacement (block_len = 1), or moving blocks of consecutive dates (block_len > 1, sensitivity to
                        dependence across neighbouring dates); recompute the statistic on all rows of the drawn dates; percentile interval.
  date permutation    : null of "no relation between predictor and target, given the intraday pattern": the target of every (index, date) session is
                        reassigned to another date with ONE permutation of dates shared by both indices; two-sided p = (1 + #|s*| >= |s|) / (1 + B).
  multiple testing    : Holm (family-wise) and Benjamini-Hochberg (false discovery) adjusted p-values across all registered tests."""
import numpy as np, pandas as pd


def _groups(dates):
    codes, uniq = pd.factorize(pd.Series(dates).values, sort=True)
    order = np.argsort(codes, kind='stable'); bounds = np.searchsorted(codes[order], np.arange(len(uniq) + 1))
    return [order[bounds[i]:bounds[i + 1]] for i in range(len(uniq))]


def cluster_bootstrap(stat, dates, arrays, reps=2000, seed=0, block_len=1, ci=0.95):
    """stat(*arrays_subset) -> float.  Returns (point, lo, hi, n_dates)."""
    G = _groups(dates); n = len(G); rng = np.random.default_rng(seed); point = stat(*arrays); out = np.empty(reps)
    for b in range(reps):
        if block_len == 1: pick = rng.integers(0, n, n)
        else:
            starts = rng.integers(0, n, int(np.ceil(n / block_len))); pick = (starts[:, None] + np.arange(block_len)[None, :]).ravel()[:n] % n
        idx = np.concatenate([G[i] for i in pick]); out[b] = stat(*[a[idx] for a in arrays])
    a = (1 - ci) / 2
    return float(point), float(np.nanquantile(out, a)), float(np.nanquantile(out, 1 - a)), n


def date_permutation_p(stat, X, Y, reps=2000, seed=0):
    """X, Y: dicts {index name: array (n_dates, n_grid)} on a common date axis.  Rows of every Y are permuted with one shared permutation."""
    rng = np.random.default_rng(seed); names = list(X); n = next(iter(X.values())).shape[0]
    f = lambda P: stat(np.concatenate([X[k].ravel() for k in names]), np.concatenate([Y[k][P].ravel() for k in names]))
    s = f(np.arange(n)); null = np.array([f(rng.permutation(n)) for _ in range(reps)])
    return float(s), float((1 + np.sum(np.abs(null) >= abs(s))) / (1 + reps)), float(np.nanstd(null))


def holm(p):
    p = np.asarray(p, float); m = len(p); o = np.argsort(p); adj = np.empty(m); run = 0.0
    for i, j in enumerate(o): run = max(run, (m - i) * p[j]); adj[j] = min(run, 1.0)
    return adj


def bh(p):
    p = np.asarray(p, float); m = len(p); o = np.argsort(p)[::-1]; adj = np.empty(m); run = 1.0
    for i, j in enumerate(o): run = min(run, p[j] * m / (m - i)); adj[j] = run
    return adj


# ---- statistics on plain arrays (NaN rows removed inside) -------------------------------------------------------------------------
def _ok(*a):
    m = np.ones(len(a[0]), bool)
    for x in a: m &= np.isfinite(x)
    return [x[m] for x in a]

def pearson(x, y):
    x, y = _ok(x, y)
    return float(np.corrcoef(x, y)[0, 1]) if len(x) > 2 and x.std() > 0 and y.std() > 0 else np.nan

def spearman(x, y):
    x, y = _ok(x, y)
    if len(x) < 3: return np.nan
    return pearson(pd.Series(x).rank().values, pd.Series(y).rank().values)

def hit_rate(x, y):
    x, y = _ok(x, y); m = (x != 0) & (y != 0)
    return float(np.mean(np.sign(x[m]) == np.sign(y[m]))) if m.any() else np.nan

def mean_signed(x, y):
    x, y = _ok(x, y)
    return float(np.mean(np.sign(x) * y)) if len(x) else np.nan

def mse(f, y):
    f, y = _ok(f, y)
    return float(np.mean((y - f) ** 2)) if len(y) else np.nan

def mae(f, y):
    f, y = _ok(f, y)
    return float(np.mean(np.abs(y - f))) if len(y) else np.nan

def skill(f, ref, y):
    """1 - MSE(f) / MSE(ref): positive = f is better than the reference forecast"""
    f, ref, y = _ok(f, ref, y); d = np.mean((y - ref) ** 2)
    return float(1 - np.mean((y - f) ** 2) / d) if len(y) and d > 0 else np.nan
