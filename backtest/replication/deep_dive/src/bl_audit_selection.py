"""Selection-bias audit (reports/OVERFITTING_AUDIT.md): re-runs the REPORTED selection pipeline (3 candidate underlyings x nested leave-one-cycle-out choice of the top-2 directional
feature families, clock forced in, L2 logistic; as bl_trig_followup.model) on label-permuted data. Vectorised: within-block ranks of every feature are fixed, only y is permuted.
N3 (primary) = curveball swaps preserving each cycle-side event count AND each minute's frequency; N1 = permute y within (cycle, side) blocks (destroys clock and features); N2 = permute y across cycles within each (minute, side) cell (keeps the clock structure, breaks any
feature-label link given the cell) = the right null for 'does the directional score add to the clock'. The statistic is max over the 3 underlyings of delta AUC (best-of-3, as chosen).
Output outputs/audit/selection_null.json"""
import sys, os, json, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from scipy.stats import rankdata
from sklearn.linear_model import LogisticRegression
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'outputs'); AU = f'{OUT}/audit'; RNG = np.random.default_rng(4242)
DIR = ['mv1', 'mv3', 'mv5', 'mv10', 'ext5', 'ext15', 'ext30', 'ext60', 'exc']; P_PERM = int(os.environ.get('P_PERM', 300))
D = pd.read_csv(f'{OUT}/trig/event_table.csv.gz'); D = D[(D.era == 'after') & (D.outlier == 0)].copy(); D['cyc'] = D.und + '|' + D.expiry; cycs = sorted(D.cyc.unique()); J = sorted(D.j.unique()); nC, nJ = len(cycs), len(J)
def cube(col): return np.stack([np.stack([D[(D.cyc == c) & (D.side == s)].sort_values('j')[col].values for s in ('CE', 'PE')]) for c in cycs]).astype(float)   # (cyc, side, j)
Y0 = cube('y').astype(int); FE = {U: np.stack([cube(f'{U}_{d}') for d in DIR] + [cube('imb'), cube('prem_ratio')], -1) for U in ('FEED', 'FUT', 'OPT')}   # (cyc, side, j, F)
NAMES = DIR + ['imb', 'prem_ratio']; FAM = [n.rstrip('0123456789') for n in NAMES]
def block_ranks(F):
    nb = F.shape[0] * F.shape[1]; X = F.reshape(nb, nJ, -1).copy(); R = np.zeros_like(X)
    for b in range(nb):
        for k in range(X.shape[2]):
            v = X[b, :, k]; m = np.nanmedian(v) if np.isfinite(v).any() else 0.0; v = np.where(np.isfinite(v), v, m); X[b, :, k] = v; R[b, :, k] = rankdata(v)
    return X.reshape(F.shape), R.reshape(nb, nJ, -1)
BR = {U: block_ranks(F) for U, F in FE.items()}
def clock_loco(Y):
    E = (Y.sum(2) > 0)[..., None] * 0 + (Y > 0); cnt = E.sum(0); return (cnt[None] - E) / (nC - 1)   # (cyc, side, j) share of OTHER cycles with an event in that cell
def strat_u(R, Y):   # R (nb, nJ, F) ranks; Y (nb, nJ) -> per-block U (nb, F), d (nb,)
    n1 = Y.sum(1); n0 = nJ - n1; U = np.einsum('bjf,bj->bf', R, Y) - (n1 * (n1 + 1) / 2)[:, None]; return U, (n1 * n0).astype(float)
def pipeline(Y, U):
    """returns delta AUC of the nested model vs the LOCO clock for underlying U, on labels Y"""
    X, R = BR[U]; nb = nC * 2; Yb = Y.reshape(nb, nJ); cl = clock_loco(Y); clb = cl.reshape(nb, nJ); cyc_of = np.repeat(np.arange(nC), 2); Ub, db = strat_u(R, Yb); oof = np.zeros((nb, nJ)); Xr = X.reshape(nb, nJ, -1)
    for h in range(nC):
        tr = cyc_of != h; auc = Ub[tr].sum(0) / max(db[tr].sum(), 1); dev = np.abs(auc - 0.5); best = {}
        for k, f in enumerate(FAM):
            if f not in best or dev[k] > dev[best[f]]: best[f] = k
        top = sorted(best.values(), key=lambda k: -dev[k])[:2]; Xtr = np.concatenate([Xr[tr][:, :, top].reshape(-1, 2), clb[tr].reshape(-1, 1)], 1); ytr = Yb[tr].reshape(-1)
        med = np.median(Xtr, 0); mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-9
        if ytr.sum() == 0: oof[~tr] = 0; continue
        lr = LogisticRegression(C=0.5, max_iter=300).fit((Xtr - mu) / sd, ytr); te = ~tr; Xte = np.concatenate([Xr[te][:, :, top].reshape(-1, 2), clb[te].reshape(-1, 1)], 1); oof[te] = lr.decision_function((Xte - mu) / sd).reshape(-1, nJ)
    S = np.stack([oof, clb], -1); RS = np.zeros_like(S)
    for b in range(nb):
        for k in range(2): RS[b, :, k] = rankdata(S[b, :, k])
    Us, dd = strat_u(RS, Yb); a = Us.sum(0) / dd.sum(); return float(a[0] - a[1])
def curveball(M, trades=600):
    """swap null for a binary matrix: preserves every row sum (cycle activity) AND every column sum (minute frequency)"""
    M = M.copy(); nr = M.shape[0]
    for _ in range(trades):
        a, b = RNG.choice(nr, 2, replace=False); ra, rb = M[a], M[b]; oa = np.where((ra == 1) & (rb == 0))[0]; ob = np.where((rb == 1) & (ra == 0))[0]
        if len(oa) == 0 or len(ob) == 0: continue
        pool = np.concatenate([oa, ob]); RNG.shuffle(pool); k = len(oa); M[a, oa] = 0; M[b, ob] = 0; M[a, pool[:k]] = 1; M[b, pool[k:]] = 1
    return M
def null_y(kind):
    if kind == 'N3':
        Y = Y0.copy()
        for s in range(2): Y[:, s, :] = curveball(Y0[:, s, :])
        return Y
    if kind == 'N1':
        Y = Y0.copy()
        for c in range(nC):
            for s in range(2): Y[c, s] = RNG.permutation(Y0[c, s])
        return Y
    Y = Y0.copy()
    for s in range(2):
        for j in range(nJ): Y[:, s, j] = RNG.permutation(Y0[:, s, j])
    return Y
if __name__ == '__main__':
    obs = {U: pipeline(Y0, U) for U in ('FEED', 'FUT', 'OPT')}; print('observed (vectorised re-implementation):', {k: round(v, 3) for k, v in obs.items()}, '| reported in bl_trig_followup: FEED -0.023, FUT +0.088, OPT -0.043')
    res = dict(observed=obs, observed_best=max(obs.values()), observed_best_underlying=max(obs, key=obs.get), P=P_PERM)
    for kind in ('N3', 'N2', 'N1'):
        mx = []; per = {U: [] for U in obs}
        for _ in range(P_PERM):
            Y = null_y(kind); v = {U: pipeline(Y, U) for U in obs}; mx.append(max(v.values()))
            for U in obs: per[U].append(v[U])
        mx = np.array(mx); res[kind] = dict(null_best_mean=float(mx.mean()), null_best_sd=float(mx.std()), null_best_p95=float(np.quantile(mx, .95)), null_best_p99=float(np.quantile(mx, .99)), p_value_best_of_3=float((1 + (mx >= res['observed_best']).sum()) / (P_PERM + 1)),
                                           null_single_mean={U: float(np.mean(v)) for U, v in per.items()}, p_value_FUT_only=float((1 + (np.array(per['FUT']) >= obs['FUT']).sum()) / (P_PERM + 1)))
        print(kind, json.dumps(res[kind], default=lambda z: round(float(z), 4)))
    res['bias_corrected_best_N3'] = res['observed_best'] - res['N3']['null_best_mean']; json.dump(res, open(f'{AU}/selection_null.json', 'w'), indent=1, default=float); print('observed best', round(res['observed_best'], 3), 'minus N3 mean of best-of-3 =', round(res['bias_corrected_best_N3'], 3))
