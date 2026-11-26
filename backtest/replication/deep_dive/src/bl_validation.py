"""Validation core for the forward test (audit of 2026-11-24; reports/OVERFITTING_AUDIT.md). Pure functions, no trading logic, no fitted parameters.

The FROZEN endpoint is unchanged: delta AUC = AUC(frozen score) - AUC(frozen clock baseline), stratified within (cycle, side) blocks (Mann-Whitney with average ties),
inference clustered by cycle. What this module adds is the inference that was missing or inconsistent in bl_fwd_eval.py (v1, kept unchanged for the record):
  * per-cycle U / denominator components, so any resampling is a cheap re-weighting of cycles;
  * paired cluster bootstrap AND a linearised (sandwich) cluster-robust interval with t critical values;
  * the Pocock constant computed independently by numerical integration, and the nominal level used at EACH look (v1 used 95% at every look);
  * explicit cycle roles (development / burn-in / confirmatory / regime-A forward) so burn-in can never enter the confirmatory sample;
  * order de-duplication, missing-minute accounting, and chronological ordering checks.
"""
import json, hashlib
import numpy as np, pandas as pd
from scipy.stats import rankdata, t as tdist, norm, multivariate_normal


# ----------------------------------------------------------------------------- stratified AUC components
def components(T, cols, cyc='cyc', side='side', y='y'):
    """Per-cycle sums over (cycle, side) blocks that have both classes: d = sum n1*n0 and U_<col> = sum of Mann-Whitney U (average ties). NaN scores are replaced by the
    block median of that column (same treatment for every column, so model and baseline see identical observations)."""
    out = {}
    for (c, s), g in T.groupby([cyc, side], sort=False):
        yy = g[y].values.astype(int); n1 = int(yy.sum()); n0 = len(yy) - n1
        rec = out.setdefault(c, dict(d=0.0, **{f'U_{k}': 0.0 for k in cols}))
        if n1 == 0 or n0 == 0: continue
        rec['d'] += n1 * n0
        for k in cols:
            v = g[k].values.astype(float); m = np.nanmedian(v) if np.isfinite(v).any() else 0.0; v = np.where(np.isfinite(v), v, m)
            r = rankdata(v); rec[f'U_{k}'] += r[yy == 1].sum() - n1 * (n1 + 1) / 2.0
    return pd.DataFrame(out).T


def auc_from(C, col, w=None):
    w = np.ones(len(C)) if w is None else np.asarray(w, float); den = (w * C['d'].values).sum()
    return float((w * C[f'U_{col}'].values).sum() / den) if den > 0 else float('nan')


def delta_from(C, a, b, w=None):
    """paired delta AUC = AUC(a) - AUC(b) on exactly the same blocks"""
    w = np.ones(len(C)) if w is None else np.asarray(w, float); den = (w * C['d'].values).sum()
    return float((w * (C[f'U_{a}'].values - C[f'U_{b}'].values)).sum() / den) if den > 0 else float('nan')


def effective_cycles(C):
    """Kish effective number of independent cycles for the ratio estimator (weights = block pair counts d_k)"""
    d = C['d'].values; return float(d.sum() ** 2 / (d ** 2).sum()) if (d ** 2).sum() > 0 else 0.0


# ----------------------------------------------------------------------------- inference
def boot_deltas(C, a, b, B=2000, rng=None):
    rng = rng or np.random.default_rng(0); m = len(C); W = rng.multinomial(m, np.ones(m) / m, size=B).astype(float)
    num = W @ (C[f'U_{a}'].values - C[f'U_{b}'].values); den = W @ C['d'].values; return num / np.where(den > 0, den, np.nan)


def boot_ci(C, a, b, level, B=2000, rng=None):
    x = boot_deltas(C, a, b, B, rng); q = (1 - level) / 2; return float(np.nanquantile(x, q)), float(np.nanquantile(x, 1 - q))


def lin_ci(C, a, b, level):
    """linearised cluster-robust interval: delta = sum(a_k) / sum(d_k); residual r_k = a_k - delta d_k; V = m/(m-1) sum r_k^2 / (sum d)^2; t(m-1) critical value"""
    m = len(C); ak = C[f'U_{a}'].values - C[f'U_{b}'].values; dk = C['d'].values; D = dk.sum()
    if D <= 0 or m < 2: return float('nan'), float('nan'), float('nan')
    est = ak.sum() / D; r = ak - est * dk; se = np.sqrt(m / (m - 1.0) * (r ** 2).sum()) / D; crit = tdist.ppf(1 - (1 - level) / 2, m - 1); return float(est - crit * se), float(est + crit * se), float(se)


def leave_one_cycle_out(C, a, b):
    """delta AUC with each cycle removed in turn (sensitivity to single cycles)"""
    return {k: delta_from(C.drop(index=k), a, b) for k in C.index}


# ----------------------------------------------------------------------------- sequential design
def pocock_constant(K, alpha=0.05):
    """Critical |z| of Pocock's design with K equally spaced looks and overall two-sided level alpha, by numerical integration of the K-variate normal with
    Corr(Z_i, Z_j) = sqrt(min(i, j) / max(i, j)). Independent of any table."""
    if K == 1: return float(norm.ppf(1 - alpha / 2))
    S = np.array([[np.sqrt(min(i, j) / max(i, j)) for j in range(1, K + 1)] for i in range(1, K + 1)])
    def tail(c): return 1.0 - multivariate_normal(mean=np.zeros(K), cov=S, allow_singular=False, maxpts=200000 * K, abseps=1e-7, releps=1e-7).cdf(np.full(K, c), lower_limit=np.full(K, -c))
    lo, hi = 1.5, 4.0
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        if tail(mid) > alpha: lo = mid
        else: hi = mid
    return 0.5 * (lo + hi)


def pocock_nominal(K, alpha=0.05):
    c = pocock_constant(K, alpha); return float(2 * (1 - norm.cdf(c)))


def sequential_decision(look, K, est, lo, futility_at_first=True):
    """Pre-registered rules: confirm if the lower bound (computed at the Pocock-adjusted level of this look) is > 0; futility only at look 1 and only on the primary point estimate <= 0."""
    if lo > 0: return 'confirmed'
    if look == 1 and futility_at_first and est <= 0: return 'futility'
    return 'continue' if look < K else 'not_confirmed'


# ----------------------------------------------------------------------------- cycle roles and data hygiene
def assign_roles(cycles, cfg):
    """cycles: DataFrame with columns cyc, d1 (ISO date). Returns role per cycle. Regime of a cycle is decided by its D-1 date. Order is strictly chronological within regime.
    development = D-1 before the freeze date; regime A forward = freeze..cutover (exploratory only); regime B: first burn_in cycles = burn_in, next sum(looks) = confirmatory (look index recorded)."""
    c = cycles.drop_duplicates('cyc').sort_values(['d1', 'cyc']).reset_index(drop=True); roles = []; b_count = 0; looks = cfg['confirmatory']['looks_cumulative']; burn = cfg['burn_in_cycles']
    for r in c.itertuples():
        if r.d1 < cfg['freeze_date']: roles.append(('development', 0))
        elif r.d1 < cfg['regime_B_start']: roles.append(('regime_A_forward_exploratory', 0))
        else:
            b_count += 1
            if b_count <= burn: roles.append(('burn_in', 0))
            elif b_count - burn <= looks[-1]: roles.append(('confirmatory', int(next(i + 1 for i, L in enumerate(looks) if b_count - burn <= L))))
            else: roles.append(('beyond_protocol', 0))
    c['role'] = [x[0] for x in roles]; c['look'] = [x[1] for x in roles]; return c


def assert_chronological_disjoint(roles):
    """cycles never straddle roles, development precedes forward, burn-in precedes confirmatory"""
    order = {'development': 0, 'regime_A_forward_exploratory': 1, 'burn_in': 2, 'confirmatory': 3, 'beyond_protocol': 4}; r = roles.sort_values('d1'); lv = r.role.map(order).values
    assert (np.diff(lv) >= 0).all(), 'roles are not chronological'; assert roles.cyc.is_unique, 'a cycle appears twice'; return True


def dedupe_orders(orders):
    """one row per real order: by order_id when present, otherwise by (ts, right, strike, lots, side, price). Returns (deduped, n_removed)."""
    o = orders.copy()
    if 'order_id' in o.columns and o['order_id'].astype(str).str.len().gt(0).all(): key = ['cyc', 'order_id']
    else: key = [c for c in ('cyc', 'ts', 'cp', 'strike', 'lots', 'px') if c in o.columns]
    d = o.drop_duplicates(key); return d, len(o) - len(d)


def missing_minutes(T, window, cyc='cyc', side='side', j='j'):
    """expected rows per cycle = 2 sides x window minutes; returns per-cycle missing counts (rows silently dropped by a gap in the bar log are visible here)"""
    n = (window[1] - window[0] + 1) * 2; g = T.groupby(cyc).size(); return (n - g).clip(lower=0)


def sha256_json(obj):
    return hashlib.sha256(json.dumps(obj, indent=1, sort_keys=True).encode()).hexdigest()


def pair_events(orders, cyc='cyc', j='j', side='cp'):
    """CE+PE pair bursts: (cycle, minute) cells in which BOTH sides have a real sale. Returns (n_pair_minutes, n_orders_in_pairs). Used only for secondary reporting."""
    if len(orders) == 0: return 0, 0
    g = orders.groupby([cyc, j])[side].agg(lambda s: set(s)); pm = g[g.map(lambda s: len(s) == 2)]; n_orders = int(orders.set_index([cyc, j]).loc[pm.index].shape[0]) if len(pm) else 0; return int(len(pm)), n_orders
