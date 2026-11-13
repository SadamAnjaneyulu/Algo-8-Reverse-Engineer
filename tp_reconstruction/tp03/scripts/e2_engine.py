"""TP-03 Phase 1: E2 statistic and cycle-block / within-window permutation machinery (operational spec: tp03/PHASE1_TEST_SPEC.md section 2).
Arrays are [cycle, window]; NaN marks a missing / not-applicable cell. One pooled statistic per test = sum over the underlyings and windows of the per-window standardised statistic / sqrt(#windows used)."""
import numpy as np

MIN_CELLS = 8; MIN_CLASS = 2


def _window_stats_binary(X, Y):
    """Y in {0,1,NaN}; per window pooled-variance t of X between Y==1 and Y==0; returns (t[window], ok[window])"""
    m = np.isfinite(X) & np.isfinite(Y); y1 = (Y == 1) & m; y0 = (Y == 0) & m; n1 = y1.sum(0); n0 = y0.sum(0); Xz = np.where(m, X, 0.0)
    s1 = (Xz * y1).sum(0); s0 = (Xz * y0).sum(0); q1 = (Xz ** 2 * y1).sum(0); q0 = (Xz ** 2 * y0).sum(0)
    with np.errstate(all='ignore'):
        m1 = s1 / n1; m0 = s0 / n0; ss = (q1 - n1 * m1 ** 2) + (q0 - n0 * m0 ** 2); sp2 = ss / (n1 + n0 - 2); se = np.sqrt(sp2 * (1.0 / n1 + 1.0 / n0)); t = (m1 - m0) / se
    ok = (n1 >= MIN_CLASS) & (n0 >= MIN_CLASS) & (n1 + n0 >= MIN_CELLS) & np.isfinite(t) & (se > 0)
    return np.where(ok, t, 0.0), ok


def _window_stats_rank(RX, RY):
    """RX, RY: within-window ranks computed once (NaN where missing); Pearson r of the ranks over the cells valid in both, Fisher-z * sqrt(n-3)"""
    m = np.isfinite(RX) & np.isfinite(RY); n = m.sum(0); x = np.where(m, RX, 0.0); y = np.where(m, RY, 0.0)
    with np.errstate(all='ignore'):
        mx = x.sum(0) / n; my = y.sum(0) / n; cxy = (x * y).sum(0) - n * mx * my; vx = (x * x).sum(0) - n * mx ** 2; vy = (y * y).sum(0) - n * my ** 2; r = cxy / np.sqrt(vx * vy)
        z = np.arctanh(np.clip(r, -0.999999, 0.999999)) * np.sqrt(n - 3)
    ok = (n >= MIN_CELLS) & np.isfinite(z) & (vx > 0) & (vy > 0)
    return np.where(ok, z, 0.0), ok


def rank_columns(A):
    """average ranks within each column over the finite cells; NaN stays NaN"""
    from scipy.stats import rankdata
    R = np.full_like(A, np.nan, dtype=float)
    for j in range(A.shape[1]):
        m = np.isfinite(A[:, j])
        if m.sum(): R[m, j] = rankdata(A[m, j])
    return R


class Design:
    """one test design: per-underlying (feature, outcome) [cycle, window] arrays; kind 'binary' (outcome 0/1/NaN) or 'quantity' (rank-association)"""
    def __init__(self, parts, kind):
        self.kind = kind; self.parts = []
        for X, Y in parts:
            self.parts.append((rank_columns(X), rank_columns(Y)) if kind == 'quantity' else (X, Y))

    def _one(self, A, B):
        return _window_stats_rank(A, B) if self.kind == 'quantity' else _window_stats_binary(A, B)

    def _stat(self, As):
        """pooled statistic: sum of per-window standardised statistics over underlyings / sqrt(windows used)"""
        tot = 0.0; used = 0
        for (_, B), A in zip(self.parts, As):
            s, ok = self._one(A, B); tot += s.sum(); used += int(ok.sum())
        return (tot / np.sqrt(used) if used else 0.0), used

    def observed(self):
        return self._stat([p[0] for p in self.parts])

    def per_underlying(self):
        out = []
        for A, B in self.parts:
            s, ok = self._one(A, B); out.append(float(s.sum() / np.sqrt(ok.sum())) if ok.sum() else 0.0)
        return out

    def draw_block(self, rng):
        """cycle-block permutation: rows of the feature array permuted among the cycles of each underlying; |S|"""
        return abs(self._stat([p[0][rng.permutation(p[0].shape[0])] for p in self.parts])[0])

    def draw_within(self, rng):
        """within-window shuffle: every window column permuted independently among cycles; |S|"""
        As = []
        for A, _ in self.parts: perm = np.argsort(rng.random(A.shape), axis=0); As.append(np.take_along_axis(A, perm, 0))
        return abs(self._stat(As)[0])
