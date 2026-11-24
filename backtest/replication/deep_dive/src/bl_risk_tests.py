"""Pre-registered tests H1-H6 of reports/LATE_SALE_RISK_PLAN.md on the reconstructed book risk (outputs/risk). EXPLORATORY; development cycles only.
Order level (H1-H3): observed share of sales whose SIDE improves the book metric vs the share expected if the side were drawn independently of the book at the cycle's own CE/PE mix; cycle-cluster bootstrap.
Hazard (H4): stratified AUC within (cycle, side) blocks over the 25 window minutes, curveball null. Cycle level (H5, H6): sign tests. BH over the 15 primary tests.
Output outputs/risk/tests.json, cycle_diagnosis.csv, hazard_auc.csv"""
import sys, os, json, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from scipy.stats import rankdata, binomtest
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'outputs'); RK = f'{OUT}/risk'; RNG = np.random.default_rng(20261125); NPERM = int(os.environ.get('NPERM', 1000)); BOOT = 4000
FEATS = ['delta_pressure', 'abs_delta', 'short_gamma', 'vega', 'theta', 'gap_worst', 'asym_pressure', 'lighter_side', 'uncovered_same', 'vwap_dev_trend', 'cum_premium']
def bh(p):
    p = np.asarray(p, float); o = np.argsort(p); m = len(p); adj = np.empty(m); run = 1.0
    for rnk, i in enumerate(o[::-1]): run = min(run, p[i] * m / (m - rnk)); adj[i] = run
    return adj
# ---------------------------------------------------------------- order level (H1-H3)
def order_tests(O, label):
    O = O.copy(); O['cyc'] = O.und + '|' + O.d1; own = O.groupby('cyc').cp.transform(lambda s: s.map(s.value_counts(normalize=True)))          # share of the cycle's late orders on this order's own side
    for nm, a, m, b in (('h1', 'delta_rs_pct_a', 'delta_rs_pct_m', 'delta_rs_pct_b'), ('h2', 'asym_a', 'asym_m', 'asym_b')):
        O[f'{nm}_a'] = (O[a].abs() < O[b].abs()).astype(float); O[f'{nm}_m'] = (O[m].abs() < O[b].abs()).astype(float)
    bd = O.SC - O.SP; sgn = np.where(O.cp == 'CE', 1.0, -1.0); O['h7_a'] = ((bd + sgn * O.lots).abs() < bd.abs()).astype(float); O['h7_m'] = ((bd - sgn * O.lots).abs() < bd.abs()).astype(float)      # H7 (post hoc): short-lot COUNT balancing
    O['dg_a'] = O.gap_worst_a - O.gap_worst_b; O['dg_m'] = O.gap_worst_m - O.gap_worst_b; O['h3_a'] = (O.dg_a > O.dg_m).astype(float); O['h3_m'] = 1 - O.h3_a
    res = {}; cycles = sorted(O.cyc.unique())
    def stat(df, nm):
        if nm == 'h3b': return float((df.dg_a - (df.own * df.dg_a + (1 - df.own) * df.dg_m)).mean())
        return float((df[f'{nm}_a'] - (df.own * df[f'{nm}_a'] + (1 - df.own) * df[f'{nm}_m'])).mean())
    O['own'] = own
    for nm in ('h1', 'h2', 'h3', 'h3b', 'h7'):
        key = 'h3' if nm == 'h3b' else nm; obs = stat(O, nm); rate = float(O[f'{key}_a'].mean()) if nm != 'h3b' else float(O.dg_a.mean()); exp = rate - obs
        bs = []
        for _ in range(BOOT):
            d = RNG.integers(0, len(cycles), len(cycles)); df = pd.concat([O[O.cyc == cycles[i]] for i in d]); bs.append(stat(df, nm))
        bs = np.array(bs); p = 2 * min((bs <= 0).mean(), (bs >= 0).mean()); p = max(p, 1 / BOOT); per = {c: stat(O[O.cyc == c], nm) for c in cycles if (O.cyc == c).sum() >= 3}
        pos = sum(v > 0 for v in per.values()); res[nm] = dict(n_orders=int(len(O)), n_cycles=len(cycles), observed=rate, expected_under_independent_side=exp, excess=obs, ci=[float(np.quantile(bs, .025)), float(np.quantile(bs, .975))], p=float(p), cycles_with_ge3=len(per), cycles_positive=int(pos))
    return O, res
# ---------------------------------------------------------------- hazard (H4)
def curveball(M, trades=600):
    M = M.copy(); nr = M.shape[0]
    for _ in range(trades):
        a, b = RNG.choice(nr, 2, replace=False); ra, rb = M[a], M[b]; oa = np.where((ra == 1) & (rb == 0))[0]; ob = np.where((rb == 1) & (ra == 0))[0]
        if len(oa) == 0 or len(ob) == 0: continue
        pool = np.concatenate([oa, ob]); RNG.shuffle(pool); k = len(oa); M[a, oa] = 0; M[b, ob] = 0; M[a, pool[:k]] = 1; M[b, pool[k:]] = 1
    return M
def hazard(Mn, j0, j1, label):
    D = Mn[(Mn.j >= j0) & (Mn.j <= j1)].copy(); cyc = sorted(D.cyc.unique()); nj = j1 - j0 + 1
    def cube(col): return np.stack([np.stack([D[(D.cyc == c) & (D.side == s)].sort_values('j')[col].values for s in ('CE', 'PE')]) for c in cyc]).astype(float)
    full = D.groupby('cyc').size() == 2 * nj; D = D[D.cyc.isin(full[full].index)]; cyc = sorted(D.cyc.unique())
    if len(cyc) < 3: return None
    Y = cube('y').astype(int); R = {}
    for f in FEATS:
        X = cube(f); Rf = np.zeros_like(X)
        for c in range(X.shape[0]):
            for s in range(2):
                v = X[c, s]; m = np.nanmedian(v) if np.isfinite(v).any() else 0.0; Rf[c, s] = rankdata(np.where(np.isfinite(v), v, m))
        R[f] = Rf
    def aucs(Yc):
        n1 = Yc.sum(2); n0 = nj - n1; valid = (n1 > 0) & (n0 > 0); d = (n1 * n0 * valid).sum(); out = {}
        for f in FEATS: U = (R[f] * Yc).sum(2) - n1 * (n1 + 1) / 2; out[f] = float((U * valid).sum() / d) if d > 0 else np.nan
        return out
    obs = aucs(Y); null = {f: [] for f in FEATS}
    for _ in range(NPERM):
        Yn = Y.copy()
        for s in range(2): Yn[:, s, :] = curveball(Y[:, s, :])
        a = aucs(Yn)
        for f in FEATS: null[f].append(a[f])
    rows = []
    for f in FEATS:
        nu = np.array(null[f]); p = (1 + (np.abs(nu - 0.5) >= abs(obs[f] - 0.5) - 1e-12).sum()) / (NPERM + 1); rows.append(dict(window=label, feature=f, auc=obs[f], null_mean=float(nu.mean()), p=float(p)))
    # per-cycle direction: AUC of the cycle's own two blocks (CE and PE together), compared with the pooled sign
    n1 = Y.sum(2); n0 = nj - n1; valid = (n1 > 0) & (n0 > 0)
    for r_ in rows:
        f = r_['feature']; U = (R[f] * Y).sum(2) - n1 * (n1 + 1) / 2; dc = (n1 * n0 * valid).sum(1); ac = np.where(dc > 0, (U * valid).sum(1) / np.where(dc > 0, dc, 1), np.nan); ok = np.isfinite(ac) & (dc > 0)
        sgn = np.sign(r_['auc'] - 0.5); r_['cycles_same_direction'] = f'{int((np.sign(ac[ok] - 0.5) == sgn).sum())}/{int(ok.sum())}'
    return pd.DataFrame(rows), dict(cycles=len(cyc), events=int(Y.sum()))
# ---------------------------------------------------------------- main
if __name__ == '__main__':
    O = pd.read_csv(f'{RK}/orders_risk.csv'); Mn = pd.read_csv(f'{RK}/minute_risk.csv'); C = pd.read_csv(f'{RK}/cycle_risk.csv'); out = {}
    prim = O[(O.j >= 360) & (O.outlier == 0)]; post = prim[prim.era == 'after']; pre = prim[prim.era == 'before']
    Opost, out['orders_post_1515'] = order_tests(post, 'post'); _, out['orders_pre_1515'] = order_tests(pre, 'pre') if len(pre) >= 6 else (None, None)
    sec = O[(O.j >= 300) & (O.j < 360) & (O.outlier == 0) & (O.era == 'after')]; _, out['orders_post_1415_1514_secondary'] = order_tests(sec, 'sec')
    H, meta = hazard(Mn[(Mn.era == 'after') & (Mn.outlier == 0)], 360, 384, 'post 15:15-15:39'); H.to_csv(f'{RK}/hazard_auc.csv', index=False); out['hazard_meta'] = meta
    NPERM_SAVE = NPERM; NPERM = max(NPERM // 3, 200); H2, meta2 = hazard(Mn[(Mn.era == 'after') & (Mn.outlier == 0)], 300, 359, 'post 14:15-15:14 (secondary)'); H2.to_csv(f'{RK}/hazard_auc_secondary.csv', index=False); NPERM = NPERM_SAVE
    # BH over the 15 primary tests
    names = [f'H4:{f}' for f in H.feature] + ['H1', 'H2', 'H3a', 'H3b']; ps = list(H.p) + [out['orders_post_1515'][k]['p'] for k in ('h1', 'h2', 'h3', 'h3b')]; adj = bh(ps); out['bh'] = dict(zip(names, [dict(p=float(p), p_bh=float(a)) for p, a in zip(ps, adj)]))
    adj16 = bh(ps + [out['orders_post_1515']['h7']['p']]); out['bh_with_posthoc_H7'] = dict(zip(names + ['H7(post hoc)'], [float(x) for x in adj16]))
    # cycle-level H5, H6 (cycles without the outlier, with late orders for H5)
    Cc = C[C.outlier == 0]; h5 = Cc[Cc.late_orders > 0]; res5 = {}
    for nm, better in (('abs_delta', lambda d: d.delta_rs_pct_end.abs() < d.delta_rs_pct_nolate.abs()), ('abs_asym', lambda d: d.asym_end.abs() < d.asym_nolate.abs()), ('gap_worst', lambda d: d.gap_worst_end > d.gap_worst_nolate)):
        b = better(h5); res5[nm] = dict(cycles=int(len(h5)), improved=int(b.sum()), p_sign=float(binomtest(int(b.sum()), len(h5), 0.5).pvalue))
    out['H5'] = res5; b6 = Cc.delta_ratio_end < Cc.delta_ratio_1415; out['H6'] = dict(cycles=int(len(Cc)), ratio_lower_at_close=int(b6.sum()), p_sign=float(binomtest(int(b6.sum()), len(Cc), 0.5).pvalue), median_ratio_1415=float(Cc.delta_ratio_1415.median()), median_ratio_end=float(Cc.delta_ratio_end.median()), median_ratio_nolate=float((Cc.delta_nolate_c.abs() / Cc.gross_nolate).median()), ratio_end_lower_than_nolate=int((Cc.delta_ratio_end < (Cc.delta_nolate_c.abs() / Cc.gross_nolate)).sum()),
                                                                                  near_neutral_end=int((Cc.delta_ratio_end < 0.05).sum()), near_neutral_1415=int((Cc.delta_ratio_1415 < 0.05).sum()))
    # per-cycle diagnosis (primary window, cycles with >=3 late orders)
    rows = []
    for c, g in Opost.groupby('cyc'):
        if len(g) < 3: rows.append(dict(cycle=c, era='after', late_orders=len(g), label='too few late orders (<3)')); continue
        d = {}
        for nm in ('h1', 'h2', 'h3', 'h7'): d[nm] = (float(g[f'{nm}_a'].mean()), float((g[f'{nm}_a'] - (g.own * g[f'{nm}_a'] + (1 - g.own) * g[f'{nm}_m'])).mean()))
        ok = [nm for nm in d if d[nm][0] >= 0.70 and d[nm][1] >= 0.25]; lab = '+'.join(k.upper() for k in ok) if ok else 'unexplained by book or VWAP state'
        rows.append(dict(cycle=c, era='after', late_orders=len(g), h1_rate=d['h1'][0], h1_excess=d['h1'][1], h2_rate=d['h2'][0], h2_excess=d['h2'][1], h3_rate=d['h3'][0], h3_excess=d['h3'][1], h7_rate=d['h7'][0], h7_excess=d['h7'][1], delta_before_median=float(g.delta_rs_pct_b.median()), label=lab))
    pd.DataFrame(rows).to_csv(f'{RK}/cycle_diagnosis.csv', index=False); Opost.to_csv(f'{RK}/orders_post_primary.csv', index=False)
    json.dump(out, open(f'{RK}/tests.json', 'w'), indent=1, default=float)
    print('ORDER LEVEL post-auction j>=360:'); [print(' ', k, {a: (round(b, 3) if isinstance(b, float) else b) for a, b in v.items() if a not in ('ci',)}, 'ci', [round(x, 3) for x in v['ci']]) for k, v in out['orders_post_1515'].items()]
    print('PRE-auction:', None if out['orders_pre_1515'] is None else {k: (round(v['observed'], 3), round(v['excess'], 3)) for k, v in out['orders_pre_1515'].items()})
    print('H7 (post hoc) post:', {k: (round(out['orders_post_1515']['h7'][k], 3) if isinstance(out['orders_post_1515']['h7'][k], float) else out['orders_post_1515']['h7'][k]) for k in ('observed','expected_under_independent_side','excess','p','cycles_positive','cycles_with_ge3')}, 'ci', [round(x,3) for x in out['orders_post_1515']['h7']['ci']]); print('BH incl H7:', {k: round(v, 3) for k, v in out['bh_with_posthoc_H7'].items()}); print('SECONDARY 14:15-15:14:', {k: (round(v['observed'], 3), round(v['excess'], 3), round(v['p'], 4)) for k, v in out['orders_post_1415_1514_secondary'].items()})
    print('HAZARD 15:15-15:39 (cycles/events)', meta); print(H.round(3).to_string(index=False)); print('H5', out['H5']); print('H6', out['H6']); print('BH', {k: round(v['p_bh'], 3) for k, v in out['bh'].items()})
