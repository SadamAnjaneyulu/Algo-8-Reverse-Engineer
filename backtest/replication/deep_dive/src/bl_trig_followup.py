"""Post-hoc follow-up to bl_trig_test.py (all tests below are ADDED beyond the pre-registered family and counted in the report):
(a) paired underlying comparison of directional scores (FUT-FEED, OPT-FEED, FUT-OPT) for mv1/3/5/10, ext5/15/30/60, exc  -> 27 comparisons, BH 10%;
(b) side split of the best directional scores; (c) directional-only nested-LOCO logistic with the clock forced in (no side-neutral |move| features) vs clock-only;
(d) the same restricted to 15:15-15:29 (j<=374) to remove the 15:30+ time-of-day confound. Output outputs/trig/followup.json."""
import sys, os, json, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from bl_trig_test import prep, blocks, strat, TR, BB
RNG = np.random.default_rng(77)
DIR = ['mv1', 'mv3', 'mv5', 'mv10', 'ext5', 'ext15', 'ext30', 'ext60', 'exc']
def boot_ci(R, y, bl, col_idx_pairs):
    ub = np.unique(bl); cyc_of = {b: b.rsplit('|', 1)[0] for b in ub}; cs = sorted(set(cyc_of.values())); out = []
    for t in range(BB):
        draw = RNG.integers(0, len(cs), len(cs)); cnt = pd.Series(draw).map(lambda i: cs[i]).value_counts(); a = strat(R, y, bl, {b: cnt.get(cyc_of[b], 0) for b in ub}); out.append(a)
    return np.array(out)
def bh(p):
    p = np.asarray(p); o = np.argsort(p); m = len(p); adj = np.empty(m); run = 1.0
    for rnk, i in enumerate(o[::-1]): run = min(run, p[i] * m / (m - rnk)); adj[i] = run
    return adj
def model(D, U, k=2, force=('clock',), pool_extra=('imb', 'prem_ratio')):
    pool = [f'{U}_{d}' for d in DIR] + list(pool_extra); cycs = sorted(D.cyc.unique()); oof = np.full(len(D), np.nan); chosen = []
    for held in cycs:
        tr = D[D.cyc != held]; te = D[D.cyc == held]; R, y, bl = blocks(tr, pool); a = strat(R, y, bl); sc = pd.DataFrame(dict(c=pool, dev=np.abs(a - 0.5), fam=[c.split('_')[-1].rstrip('0123456789') if c.startswith(U) else c for c in pool])).dropna()
        top = sc.sort_values('dev', ascending=False).drop_duplicates('fam').head(k).c.tolist() + list(force); chosen.append(top)
        med = tr[top].median(); Xtr = tr[top].fillna(med).values; Xte = te[top].fillna(med).values; mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-9
        lr = LogisticRegression(C=0.5, max_iter=500).fit((Xtr - mu) / sd, tr.y.values); oof[[D.index.get_loc(i) for i in te.index]] = lr.decision_function((Xte - mu) / sd)
    D2 = D.assign(oof=oof); R, y, bl = blocks(D2, ['oof', 'clock']); a = strat(R, y, bl); B = boot_ci(R, y, bl, None); d = B[:, 0] - B[:, 1]
    return dict(U=U, oof_auc=float(a[0]), oof_ci=[float(x) for x in np.nanquantile(B[:, 0], [.025, .975])], clock_auc=float(a[1]), diff=float(a[0] - a[1]), diff_ci=[float(x) for x in np.nanquantile(d, [.025, .975])],
                chosen=pd.Series([c for ch in chosen for c in ch]).value_counts().head(6).to_dict())
if __name__ == '__main__':
    D0 = pd.read_csv(f'{TR}/event_table.csv.gz'); out = {}
    A = prep(D0[(D0.era == 'after') & (D0.outlier == 0)].reset_index(drop=True))
    # (a) paired underlying comparison
    cols = [f'{U}_{d}' for U in ('FEED', 'FUT', 'OPT') for d in DIR]; R, y, bl = blocks(A, cols); obs = strat(R, y, bl); B = boot_ci(R, y, bl, None); ci = {c: i for i, c in enumerate(cols)}; rows = []
    for d in DIR:
        for a_, b_ in (('FUT', 'FEED'), ('OPT', 'FEED'), ('FUT', 'OPT')):
            i, j = ci[f'{a_}_{d}'], ci[f'{b_}_{d}']; diff = B[:, i] - B[:, j]; dd = obs[i] - obs[j]; p = 2 * min((diff <= 0).mean(), (diff >= 0).mean()); rows.append(dict(score=d, pair=f'{a_}-{b_}', auc_a=obs[i], auc_b=obs[j], diff=dd, lo=np.quantile(diff, .025), hi=np.quantile(diff, .975), p=max(p, 1 / BB)))
    P = pd.DataFrame(rows); P['p_bh'] = bh(P.p.values); P.to_csv(f'{TR}/underlying_compare.csv', index=False); out['compare'] = {pr: dict(mean_diff=float(g['diff'].mean()), n_sig_bh10=int((g.p_bh < .1).sum()), n=len(g)) for pr, g in P.groupby('pair')}
    print(P.round(3).to_string(index=False))
    # (b) side split
    out['side'] = {}
    for U in ('FEED', 'FUT', 'OPT'):
        for s in ('CE', 'PE'):
            S = A[A.side == s]; R2, y2, bl2 = blocks(S, [f'{U}_mv1', f'{U}_mv3', f'{U}_ext5', f'{U}_exc']); out['side'][f'{U}_{s}'] = dict(zip(['mv1', 'mv3', 'ext5', 'exc'], [round(float(x), 3) for x in strat(R2, y2, bl2)]))
    print(json.dumps(out['side']))
    # (c) directional-only + clock forced; (d) window 15:15-15:29 only
    out['dir_model_full'] = [model(A, U) for U in ('FEED', 'FUT', 'OPT')]; A2 = prep(D0[(D0.era == 'after') & (D0.outlier == 0) & (D0.j <= 374)].reset_index(drop=True))
    out['dir_model_1529'] = [model(A2, U) for U in ('FEED', 'FUT', 'OPT')]; out['events'] = dict(full=int(A.y.sum()), w1529=int(A2.y.sum()), cycles=int(A.cyc.nunique()))
    for k in ('dir_model_full', 'dir_model_1529'):
        for m in out[k]: print(k, m['U'], 'oof', round(m['oof_auc'], 3), [round(x, 3) for x in m['oof_ci']], 'clock', round(m['clock_auc'], 3), 'diff', round(m['diff'], 3), [round(x, 3) for x in m['diff_ci']], m['chosen'])
    json.dump(out, open(f'{TR}/followup.json', 'w'), indent=1, default=float)
