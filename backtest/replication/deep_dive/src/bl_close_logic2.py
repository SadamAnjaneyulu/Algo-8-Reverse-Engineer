"""Buy-back study, step 3 (plan test C): single-leg vs combined trigger on the strike-level contract-minute panel (rows = CE leg of a strike while BOTH rights have body shorts open at that strike, minute j >= 5).
unit target: CE bought back / PE bought back / both in the same minute / CE only / PE only. Variables (decision-time, minute j-1 close): r_ce, r_pe (price / average open body entry), max, min, straddle ratio.
Cluster bootstrap over cycles; leave-one-cycle-out logistic incremental value; permutation null (shuffle within cycle). D-1 primary, D0 secondary. Output outputs/bl_close_C_*.csv, bl_summary_close2.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
P = pd.read_csv(f'{OUT}/bl_close_panel2.csv.gz'); rng = np.random.default_rng(1); R = {}
def auc(x, y): m = ~np.isnan(x); x, y = x[m], y[m]; n1 = y.sum(); n0 = len(y) - n1; r = stats.rankdata(x); return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0) if n1 and n0 else np.nan
def loco(X, y, g):
    o = np.zeros(len(y))
    for c in np.unique(g):
        tr = g != c; m = LogisticRegression(C=1.0, max_iter=300).fit(X[tr], y[tr]); o[~tr] = m.predict_proba(X[~tr])[:, 1]
    return o
def boot(f, g, n=200):
    ucy = np.unique(g); idx = {c: np.where(g == c)[0] for c in ucy}; out = []
    for _ in range(n): ii = np.concatenate([idx[c] for c in rng.choice(ucy, len(ucy))]); out.append(f(ii))
    return np.nanquantile(out, [.025, .975])
rows = []; HZ = []
for day in ('D-1', 'D0'):
    Q = P[(P.day == day) & (P.cp == 'CE') & (P.o_n_open > 0) & P.o_r_avg.notna()].reset_index(drop=True)
    Q['r_ce'] = Q.r_avg; Q['r_pe'] = Q.o_r_avg; Q['r_max'] = Q[['r_ce', 'r_pe']].max(axis=1); Q['r_min'] = Q[['r_ce', 'r_pe']].min(axis=1)
    Q['ce'] = (Q.bb_lots > 0).astype(int); Q['pe'] = (Q.o_bb_lots > 0).astype(int); Q['both'] = Q.ce * Q.pe; Q['ce_only'] = Q.ce * (1 - Q.pe); Q['pe_only'] = Q.pe * (1 - Q.ce); Q['any'] = ((Q.ce + Q.pe) > 0).astype(int)
    g = (Q.und + Q.expiry).values; print(f'\n===== {day}: strike-minutes with both legs short: {len(Q):,}; CE bought back {Q.ce.sum()}, PE {Q.pe.sum()}, both {Q.both.sum()}, CE-only {Q.ce_only.sum()}, PE-only {Q.pe_only.sum()}')
    R[f'{day}_rows'] = len(Q); R[f'{day}_counts'] = {k: int(Q[k].sum()) for k in ('ce', 'pe', 'both', 'ce_only', 'pe_only', 'any')}
    # share of both-leg events among any-leg events
    R[f'{day}_both_share_of_any'] = float(Q.both.sum() / max(Q['any'].sum(), 1)); print(f'  both-in-the-same-minute share of all strike-minutes with any buy-back: {R[day + "_both_share_of_any"]:.3f}')
    R[f'{day}_both_ge12_rows'] = float(((Q.r_ce >= 1.2) & (Q.r_pe >= 1.2)).mean()); print(f'  share of strike-minutes where both legs >=1.2x: {R[day + "_both_ge12_rows"]:.4f}')
    for tgt, vs in (('ce', ['r_ce', 'r_pe', 'r_max', 'r_min', 'straddle_r']), ('pe', ['r_pe', 'r_ce', 'r_max', 'r_min', 'straddle_r']), ('both', ['r_max', 'r_min', 'straddle_r', 'r_ce', 'r_pe']), ('ce_only', ['r_ce', 'r_pe', 'r_max', 'straddle_r']), ('pe_only', ['r_pe', 'r_ce', 'r_max', 'straddle_r'])):
        y = Q[tgt].values
        if y.sum() < 10: continue
        for v in vs:
            x = Q[v].values.astype(float); a = auc(x, y); lo, hi = boot(lambda ii: auc(x[ii], y[ii]), g, 120)
            nul = [auc(pd.Series(x).groupby(g).transform(lambda s: rng.permutation(s.values)).values, y) for _ in range(20)]
            rows.append((day, tgt, v, int(y.sum()), a, lo, hi, np.nanmedian(nul), np.nanmax(nul)))
        print(f'  target {tgt} (n={int(y.sum())}):', {r[2]: round(r[4], 3) for r in rows if r[0] == day and r[1] == tgt})
    # which leg is bought when only one is?  higher-ratio leg share
    S = Q[(Q.ce_only + Q.pe_only) == 1]; hl = np.where(S.ce_only == 1, S.r_ce > S.r_pe, S.r_pe > S.r_ce).astype(float); k = len(S)
    gs = (S.und + S.expiry).values; lo, hi = boot(lambda ii: hl[ii].mean(), gs, 300); R[f'{day}_single_higher_leg'] = [k, float(hl.mean()), float(lo), float(hi)]
    print(f'  single-leg events (n={k}): bought leg is the higher-ratio leg {hl.mean():.3f} (CI {lo:.3f}-{hi:.3f}); 0.5 = indifferent')
    # LOCO incremental: own-ratio only vs own + other-leg ratio
    for tgt, own, oth in (('ce', 'r_ce', 'r_pe'), ('pe', 'r_pe', 'r_ce')):
        y = Q[tgt].values; X1 = Q[[own]].values; X2 = Q[[own, oth]].values; X3 = Q[[own, oth, 'straddle_r']].values; X1 = np.c_[X1, np.log(X1)]; Z = lambda X: (X - X.mean(0)) / X.std(0)
        p1 = loco(Z(Q[[own]].values), y, g); p2 = loco(Z(Q[[own, oth]].values), y, g); a1 = roc_auc_score(y, p1); a2 = roc_auc_score(y, p2); nul = []
        for _ in range(5): Qp = Q.copy(); Qp[oth] = Qp.groupby(g)[oth].transform(lambda s: rng.permutation(s.values)); nul.append(roc_auc_score(y, loco(Z(Qp[[own, oth]].values), y, g)) - a1)
        R[f'{day}_loco_{tgt}'] = dict(own=float(a1), own_plus_other=float(a2), gain=float(a2 - a1), null_median=float(np.median(nul)), null_max=float(max(nul))); print(f'  LOCO {tgt}: own ratio AUC {a1:.3f} -> + other leg {a2:.3f} (gain {a2 - a1:+.4f}; permuted-other gain median {np.median(nul):+.4f}, max {max(nul):+.4f})')
    # hazard of CE buy-back by own ratio x other-leg ratio class
    Q['own_b'] = pd.cut(Q.r_ce, [0, .8, 1.0, 1.2, 1.4, 1.55, 1.7, 99]); Q['oth_b'] = pd.cut(Q.r_pe, [0, .8, 1.2, 99], labels=['PE<0.8', 'PE 0.8-1.2', 'PE>=1.2'])
    for rr in ((Q, 'CE', 'ce', 'r_ce', 'r_pe'), (Q.assign(r_ce=Q.r_pe, r_pe=Q.r_ce, ce=Q.pe), 'PE', 'pe', 'r_ce', 'r_pe')):
        D, nm = rr[0].copy(), rr[1]; D['own_b'] = pd.cut(D.r_ce, [0, .8, 1.0, 1.2, 1.4, 1.55, 1.7, 99]); D['oth_b'] = pd.cut(D.r_pe, [0, .8, 1.2, 99], labels=['other<0.8', 'other 0.8-1.2', 'other>=1.2'])
        t = D.groupby(['own_b', 'oth_b'], observed=True).ce.agg(['size', 'sum']); t['per1000'] = (t['sum'] / t['size'] * 1000).round(1); t = t.reset_index(); t.insert(0, 'leg', nm); t.insert(0, 'day', day); HZ.append(t)
        if day == 'D-1': print(f'\n  {nm} buy-back per 1000 strike-minutes by own ratio x other-leg ratio'); print(t.pivot(index='own_b', columns='oth_b', values='per1000').to_string()); print(t.pivot(index='own_b', columns='oth_b', values='size').to_string())
pd.DataFrame(rows, columns=['day', 'target', 'variable', 'n_events', 'AUC', 'lo', 'hi', 'null_median', 'null_max']).round(4).to_csv(f'{OUT}/bl_close_C_auc.csv', index=False)
pd.concat(HZ).assign(own_b=lambda d: d.own_b.astype(str), oth_b=lambda d: d.oth_b.astype(str)).to_csv(f'{OUT}/bl_close_C_hazard.csv', index=False); rec('close2', R)
