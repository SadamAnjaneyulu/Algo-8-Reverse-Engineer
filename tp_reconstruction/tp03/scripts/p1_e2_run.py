"""TP-03 Phase 1: E2 (state-gated addition) over 25 features x {action, quantity} x {pre-expiry, expiry day}, with the registered sequential permutation test.
Primary = view V2 (submission-attributed incl. ambiguous), common snapshot, cycle-block permutation. Sensitivities (all logged): V3 (excl. ambiguous), S1 snapshot, within-window shuffle.
All results are EXPLORATORY (config entry.testability_gates.evidence_ceiling). Run: python3 tp_reconstruction/tp03/scripts/p1_e2_run.py"""
import os, sys, json, itertools
import numpy as np, pandas as pd
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tp03_common as tc, entry_common as ec, e2_engine as eng, seqperm
from scipy.stats import mannwhitneyu
tc.assert_frozen(); CFG = tc.CFG; PARAMS = CFG['inference']['permutations']['parameters']; SEED = CFG['inference']['seed']
W = pd.read_parquet(os.path.join(tc.DATA, 'p1_window_dataset.parquet')); FEATS = ec.FEATURES
WINS = {k: sorted(W[W.kind == k].window.unique()) for k in ('PRE', 'D0')}


def arrays(kind, outcome, view, feat, snap):
    """per-underlying [cycle, window] arrays (X, Y), outcome Y: action -> 1 / 0 / NaN, quantity -> Q of acting windows / NaN"""
    col = f'view{view}_class'; fc = feat + ('__S1' if snap == 'S1' else ''); parts = []; meta = []
    for und in ('NIFTY', 'SENSEX'):
        g = W[(W.kind == kind) & (W.und == und)]; cyc = sorted(g.cycle.unique()); idx = {c: i for i, c in enumerate(cyc)}; wi = {w: j for j, w in enumerate(WINS[kind])}
        X = np.full((len(cyc), len(wi)), np.nan); Y = np.full_like(X, np.nan)
        for r in g.itertuples(index=False):
            i = idx[r.cycle]; j = wi[r.window]; cl = getattr(r, col); v = getattr(r, fc)
            if outcome == 'action':
                if cl == 'ACTION': Y[i, j] = 1.0
                elif cl == 'NO_ACTION_ACTIVE': Y[i, j] = 0.0
            else:
                if cl == 'ACTION': Y[i, j] = getattr(r, f'Q_v{view}')
            X[i, j] = v if (v is not None and np.isfinite(v)) else np.nan
        parts.append((X, Y)); meta.append(cyc)
    return parts, meta


def effect_sizes(parts, kind):
    """pooled effect size on within-window z-scored features: AUC (action) or top/bottom-tercile ratio of Q (quantity); sign share of cycles agreeing with the pooled sign"""
    zs = []; ys = []; contrib = []
    for X, Y in parts:
        Z = np.full_like(X, np.nan); ZY = np.full_like(Y, np.nan)
        for j in range(X.shape[1]):
            m = np.isfinite(X[:, j]) & np.isfinite(Y[:, j])
            if m.sum() >= eng.MIN_CELLS and np.nanstd(X[m, j]) > 0 and np.nanstd(Y[m, j]) > 0: Z[m, j] = (X[m, j] - X[m, j].mean()) / X[m, j].std(); ZY[m, j] = (Y[m, j] - Y[m, j].mean()) / Y[m, j].std()
        zs.append(Z); ys.append(Y); contrib.append(np.nansum(Z * ZY, axis=1))
    z = np.concatenate([a.ravel() for a in zs]); y = np.concatenate([a.ravel() for a in ys]); m = np.isfinite(z) & np.isfinite(y); z, y = z[m], y[m]; c = np.concatenate(contrib)
    out = dict(n_cells=int(m.sum()), auc=np.nan, tercile_ratio=np.nan)
    if kind == 'binary' and (y == 1).sum() > 1 and (y == 0).sum() > 1: out['auc'] = float(mannwhitneyu(z[y == 1], z[y == 0]).statistic / ((y == 1).sum() * (y == 0).sum()))
    if kind == 'quantity' and len(z) >= 30:
        lo, hi = np.quantile(z, [1 / 3, 2 / 3]); a = y[z <= lo].mean(); b = y[z >= hi].mean(); out['tercile_ratio'] = float(b / a) if a > 0 else np.nan
    return out, c


def one_test(args):
    kind, outcome, view, feat, snap, scheme = args
    test_id = f'E2|{kind}|{outcome}|{feat}|V{view}|{snap}|{scheme}'; parts, meta = arrays(kind, outcome, view, feat, snap); bkind = 'binary' if outcome == 'action' else 'quantity'
    d = eng.Design(parts, bkind); obs, used = d.observed(); per = d.per_underlying(); rec = dict(test_id=test_id, design=kind, outcome=outcome, feature=feat, view=f'V{view}', snapshot=snap, scheme=scheme, windows_used=used)
    ncells = int(sum(np.isfinite(Y).sum() for _, Y in parts))
    if used == 0:
        rec.update(status='NOT_TESTABLE_CONSTANT_OR_UNAVAILABLE', observed_S=0.0, p=np.nan); return rec
    draw = d.draw_block if scheme == 'block' else d.draw_within
    r = seqperm.run_test(test_id, abs(obs), draw, SEED, PARAMS); es, contrib = effect_sizes(parts, bkind)
    sgn = np.sign(obs) if obs != 0 else 1; share = float(np.mean(np.sign(contrib[contrib != 0]) == sgn)) if (contrib != 0).any() else np.nan
    rec.update(status='RUN', observed_S=float(obs), S_NIFTY=per[0], S_SENSEX=per[1], same_sign_both_und=bool(np.sign(per[0]) == np.sign(per[1]) and per[0] != 0), cycle_share_agreeing=share, **es, **{k: r[k] for k in ('p', 'draws', 'exceedances', 'stopped_by', 'extended', 'seed_entropy')})
    return rec


if __name__ == '__main__':
    combos = [(k, o, v, f, s, sc) for k in ('PRE', 'D0') for o in ('action', 'quantity') for f in FEATS for (v, s, sc) in (('2', 'primary', 'block'), ('3', 'primary', 'block'), ('2', 'S1', 'block'), ('2', 'primary', 'within'))]
    combos = [(k, o, int(v), f, s, sc) for (k, o, v, f, s, sc) in combos]
    with Pool(4) as pool: res = pool.map(one_test, combos, chunksize=4)
    R = pd.DataFrame(res).sort_values('test_id').reset_index(drop=True); R.to_csv(os.path.join(tc.ANALYSIS, 'p1_e2_results.csv'), index=False)
    log = R[R.status == 'RUN'][['test_id', 'seed_entropy', 'observed_S', 'draws', 'exceedances', 'stopped_by', 'extended', 'p']]; log.to_csv(os.path.join(tc.ANALYSIS, 'p1_permutation_log_e2.csv'), index=False)
    print(R.status.value_counts().to_string()); print(R[(R.status == 'RUN') & (R.view == 'V2') & (R.snapshot == 'primary') & (R.scheme == 'block')].sort_values('p').head(15)[['test_id', 'observed_S', 'p', 'draws', 'exceedances', 'stopped_by', 'extended']].to_string())
