"""Late D-1 sale trigger: stratified-AUC tests, BH-FDR, cycle bootstrap, underlying comparison, nested leave-one-cycle-out logistic
(plan: reports/D0_CLEAR_AND_LATE_TRIGGER_PLAN.md). Output outputs/trig/auc_<era>.csv, combo.json, summary.json."""
import sys, os, json, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from scipy.stats import rankdata
from sklearn.linear_model import LogisticRegression
OUT = os.path.join(os.path.dirname(os.path.abspath('.')), 'outputs'); TR = f'{OUT}/trig'; BP, BB = 2000, 1000; RNG = np.random.default_rng(2024)
def family(cols, era):
    fam = {}
    for c in cols:
        for U in ('FEED', 'FUT', 'OPT'):
            if c.startswith(U) and not c.startswith(U + 'L'): fam[c] = ('U:' + c[len(U):].rstrip('0123456789').strip('_'), U)
    for c in ('prem_ratio', 'imb', 'clock', 'mins_since_sale'): fam[c] = (c, '-')
    return fam
def prep(D):
    D = D.copy(); D['block'] = D.und + '|' + D.expiry + '|' + D.side; D['cyc'] = D.und + '|' + D.expiry
    D['clock'] = np.nan
    for era, g in D.groupby('era'):
        ev = g[g.y == 1]; cycs = g.cyc.unique(); n = len(cycs)
        cnt = ev.groupby(['j', 'side', 'cyc']).size().groupby(['j', 'side']).size()
        own = ev.groupby(['j', 'side', 'cyc']).size().rename('own').reset_index(); own['own'] = 1
        for ix, r in g.iterrows():
            tot = cnt.get((r.j, r.side), 0); mine = int(((own.j == r.j) & (own.side == r.side) & (own.cyc == r.cyc)).any()); D.loc[ix, 'clock'] = (tot - mine) / (n - 1)
    return D
def blocks(D, cols):
    """per-block average ranks (NaN -> block median), returns R (rows x feats), y, block id array, cycle id array"""
    y = D.y.values; bl = D.block.values; R = np.zeros((len(D), len(cols))); X = D[cols].values.astype(float)
    for b in np.unique(bl):
        ix = np.where(bl == b)[0]
        for k in range(len(cols)):
            v = X[ix, k].copy(); m = np.nanmedian(v) if np.isfinite(v).any() else 0.0; v = np.where(np.isfinite(v), v, m); R[ix, k] = rankdata(v)
    return R, y, bl
def strat(R, y, bl, w=None):
    """stratified AUC per feature; w = dict block->weight for bootstrap"""
    U = np.zeros(R.shape[1]); den = 0.0
    for b in np.unique(bl):
        ix = np.where(bl == b)[0]; yy = y[ix]; n1 = yy.sum(); n0 = len(yy) - n1
        if n1 == 0 or n0 == 0: continue
        wt = 1.0 if w is None else w[b]
        if wt == 0: continue
        U += wt * (R[ix][yy == 1].sum(0) - n1 * (n1 + 1) / 2); den += wt * n1 * n0
    return U / den if den else np.full(R.shape[1], np.nan)
def analyse(D, cols, fam, label):
    R, y, bl = blocks(D, cols); obs = strat(R, y, bl); ub = np.unique(bl); cyc_of = {b: b.rsplit('|', 1)[0] for b in ub}; cycs = sorted(set(cyc_of.values()))
    # permutation null within block (ranks fixed, y permuted within block)
    idx = {b: np.where(bl == b)[0] for b in ub}; null = np.zeros((BP, len(cols)))
    for t in range(BP):
        yp = y.copy()
        for b in ub:
            ix = idx[b]; yp[ix] = y[ix][RNG.permutation(len(ix))]
        null[t] = strat(R, yp, bl)
    p = (1 + (np.abs(null - 0.5) >= np.abs(obs - 0.5)[None, :] - 1e-12).sum(0)) / (BP + 1)
    order = np.argsort(p); m = len(p); adj = np.empty(m); run = 1.0
    for rnk, i in enumerate(order[::-1]):
        k = m - rnk; run = min(run, p[i] * m / k); adj[i] = run
    boot = np.zeros((BB, len(cols)))
    for t in range(BB):
        draw = RNG.integers(0, len(cycs), len(cycs)); cnt = pd.Series(draw).map(lambda i: cycs[i]).value_counts(); boot[t] = strat(R, y, bl, {b: cnt.get(cyc_of[b], 0) for b in ub})
    lo, hi = np.nanquantile(boot, [.025, .975], axis=0)
    T = pd.DataFrame(dict(feature=cols, family=[fam[c][0] for c in cols], underlying=[fam[c][1] for c in cols], auc=obs, lo=lo, hi=hi, p=p, p_bh=adj)); T['sig_bh10'] = T.p_bh < 0.10
    T.sort_values('p').to_csv(f'{TR}/auc_{label}.csv', index=False); return T, (R, y, bl, boot, cols)
def loco_combo(D, cols, fam, U, label):
    """nested leave-one-cycle-out: pick top-3 families (one feature each, in-fold |AUC-0.5|), logistic L2 on them, out-of-fold scores -> stratified AUC"""
    use = [c for c in cols if fam[c][1] in (U, '-')]; cycs = sorted(D.cyc.unique()); oof = np.full(len(D), np.nan); chosen = []
    for held in cycs:
        tr = D[D.cyc != held]; te = D[D.cyc == held]; R, y, bl = blocks(tr, use); a = strat(R, y, bl); sc = pd.DataFrame(dict(c=use, dev=np.abs(a - 0.5), fam=[fam[c][0].split(':')[-1] if fam[c][0].startswith('U:') else fam[c][0] for c in use])).dropna()
        top = sc.sort_values('dev', ascending=False).drop_duplicates('fam').head(3).c.tolist(); chosen.append(top)
        Xtr = tr[top].fillna(tr[top].median()).values; Xte = te[top].fillna(tr[top].median()).values; mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-9
        lr = LogisticRegression(C=0.5, max_iter=500).fit((Xtr - mu) / sd, tr.y.values); oof[te.index.map(lambda i: D.index.get_loc(i))] = lr.decision_function((Xte - mu) / sd)
    D2 = D.assign(oof=oof); R, y, bl = blocks(D2, ['oof', 'clock']); a = strat(R, y, bl); ub = np.unique(bl); cyc_of = {b: b.rsplit('|', 1)[0] for b in ub}; cs = sorted(set(cyc_of.values())); bt = []
    for t in range(BB):
        draw = RNG.integers(0, len(cs), len(cs)); cnt = pd.Series(draw).map(lambda i: cs[i]).value_counts(); bt.append(strat(R, y, bl, {b: cnt.get(cyc_of[b], 0) for b in ub}))
    bt = np.array(bt); diff = bt[:, 0] - bt[:, 1]; from collections import Counter
    return dict(underlying=U, oof_auc=float(a[0]), oof_ci=[float(x) for x in np.nanquantile(bt[:, 0], [.025, .975])], clock_auc=float(a[1]), clock_ci=[float(x) for x in np.nanquantile(bt[:, 1], [.025, .975])],
                diff_vs_clock=float(a[0] - a[1]), diff_ci=[float(x) for x in np.nanquantile(diff, [.025, .975])], features_chosen=Counter(c for ch in chosen for c in ch).most_common(6))
if __name__ == '__main__':
    D0 = pd.read_csv(f'{TR}/event_table.csv.gz'); summ = {}
    for era in ('after', 'before'):
        for excl in (True, False):
            D = D0[(D0.era == era) & ((D0.outlier == 0) if excl else True)].reset_index(drop=True); D = prep(D); label = f"{era}{'' if excl else '_with_outlier'}"
            cols = [c for c in D.columns if c.startswith(('FEED', 'FUT', 'OPT')) and not c.startswith(tuple(U + 'L' for U in ('FEED', 'FUT', 'OPT')))] + ['prem_ratio', 'imb', 'clock', 'mins_since_sale']
            fam = family(cols, era); cols = [c for c in cols if c in fam]; T, _ = analyse(D, cols, fam, label)
            s = dict(rows=int(len(D)), events=int(D.y.sum()), cycles=int(D.cyc.nunique()), scores=len(cols), n_sig_bh10=int(T.sig_bh10.sum()), best=T.sort_values('p').head(8)[['feature', 'auc', 'lo', 'hi', 'p', 'p_bh']].round(4).to_dict('records'))
            if excl:
                s['combo'] = [loco_combo(D, cols, fam, U, label) for U in (('FEED', 'FUT', 'OPT') if era == 'after' else ('FEED',))]
                # lag-1 robustness (not part of acceptance): same features through j-1
                lag = [c for c in D0.columns if c.startswith(('FEEDL', 'FUTL', 'OPTL'))]; D2 = D.copy()
                for c in lag: D2[c.replace('L_', '_', 1)] = D0.loc[D0.index.isin([]), c] if False else np.nan
                Rl = D0[(D0.era == era) & (D0.outlier == 0)].reset_index(drop=True); D2 = prep(Rl)
                for c in [x for x in lag if x.startswith(('FEEDL', 'FUTL', 'OPTL'))]: D2[c.replace(c[:c.index('L_')+1], c[:c.index('L_')])] = D2[c]
                Tl, _ = analyse(D2, [c for c in cols if c in D2.columns and c.startswith(('FEED', 'FUT', 'OPT'))], fam, label + '_lag1'); s['lag1_n_sig'] = int(Tl.sig_bh10.sum()); s['lag1_best'] = Tl.sort_values('p').head(3)[['feature', 'auc', 'p_bh']].round(4).to_dict('records')
            summ[label] = s; print(label, json.dumps({k: v for k, v in s.items() if k != 'best'}, default=lambda z: round(float(z), 3))[:900]); print(T.sort_values('p').head(8).round(4).to_string(index=False))
    json.dump(summ, open(f'{TR}/summary.json', 'w'), indent=1, default=float)
