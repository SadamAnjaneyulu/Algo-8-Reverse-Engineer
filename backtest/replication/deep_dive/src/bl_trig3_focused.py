"""Focused late-sale tests (plan: reports/LATE_SALE_FOCUSED_PLAN.md, written before this ran). EXPLORATORY.
F1 straddle decline on the held-out pre-auction cycles, F1p cross-cycle placebo, F2a side by futures direction (post and pre), F3 timing+side model, PB1 (descriptive) PB2 PB3 PB4 PB5 profit booking, F4 pair-window descriptives.
Output outputs/trig3/focused.json, family.csv, pair_cycles.csv, close_long.csv"""
import sys, os, json, warnings; sys.path.insert(0, '.'); sys.path.insert(0, '../..'); sys.path.insert(0, '../../..'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from scipy.stats import rankdata, norm
from sklearn.linear_model import LogisticRegression
import bl_bt3_sim as S, bl_d0x_diag as DG, bl_validation as V, bl_risk_tests as RT
OUT = S.OUT; T3 = f'{OUT}/trig3'; T2 = f'{OUT}/trig2'; RNG = np.random.default_rng(20261128); RT.RNG = RNG; W0, W1 = 54900, 56400; W = W1 - W0; CAS = '2026-08-03'; OUTLIER = ('NIFTY', '2026-10-16')
def cubes(M, cols, j0, j1):
    D = M[(M.j >= j0) & (M.j <= j1)]; nj = j1 - j0 + 1; full = D.groupby('cyc').size() == 2 * nj; D = D[D.cyc.isin(full[full].index)]; cyc = sorted(D.cyc.unique())
    cube = lambda col: np.stack([np.stack([D[(D.cyc == c) & (D.side == s)].sort_values('j')[col].values for s in ('CE', 'PE')]) for c in cyc]).astype(float)
    return cyc, nj, {c: cube(c) for c in cols}
def ranks(X):
    R = np.zeros_like(X)
    for c in range(X.shape[0]):
        for s in range(2):
            v = X[c, s]; m = np.nanmedian(v) if np.isfinite(v).any() else 0.0; R[c, s] = rankdata(np.where(np.isfinite(v), v, m))
    return R
def auc(R, Y, nj):
    n1 = Y.sum(2); n0 = nj - n1; valid = (n1 > 0) & (n0 > 0); d = (n1 * n0 * valid).sum(); U = (R * Y).sum(2) - n1 * (n1 + 1) / 2; return float((U * valid).sum() / d) if d > 0 else np.nan
def cyc_dir(R, Y, nj):
    n1 = Y.sum(2); n0 = nj - n1; valid = (n1 > 0) & (n0 > 0); U = (R * Y).sum(2) - n1 * (n1 + 1) / 2; dc = (n1 * n0 * valid).sum(1); ac = np.where(dc > 0, (U * valid).sum(1) / np.where(dc > 0, dc, 1), np.nan); return ac[np.isfinite(ac) & (dc > 0)]
def null_curveball(R, Y, nj, n):
    out = []
    for _ in range(n):
        Yn = Y.copy()
        for s in range(2): Yn[:, s, :] = RT.curveball(Y[:, s, :])
        out.append(auc(R, Yn, nj))
    return np.array(out)
def lagged_pair(A, B_, key=('cyc', 'j')): return A
def run():
    res = {}; fam = []; NP = int(os.environ.get('NPERM', 1000))
    Ma = pd.read_csv(f'{T3}/state_after.csv'); Mb = pd.read_csv(f'{T3}/state_before.csv')
    # ---------------------------------------------------------------- F1 held-out straddle
    cb, nj_b, Xb = cubes(Mb, ['STR15', 'y'], 360, 374); Yb = Xb['y'].astype(int); Rb = ranks(Xb['STR15']); a_b = auc(Rb, Yb, nj_b); nl = null_curveball(Rb, Yb, nj_b, NP); p1 = float((1 + (nl <= a_b + 1e-12).sum()) / (NP + 1)); dirs = cyc_dir(Rb, Yb, nj_b)
    ca, nj_a, Xa = cubes(Ma, ['STR15', 'PP', 'GB', 'y'], 360, 384); Ya = Xa['y'].astype(int); Ra = ranks(Xa['STR15']); a_a = auc(Ra, Ya, nj_a)
    # power: 7 random post cycles over minutes 360-374
    pw = []; idx = np.arange(len(ca)); Rpost = ranks(Xa['STR15'][:, :, :15]); Ypost = Ya[:, :, :15]
    for _ in range(60):
        s_ = RNG.choice(idx, 7, replace=False); Rs, Ys = Rpost[s_], Ypost[s_]; a_ = auc(Rs, Ys, 15)
        if not np.isfinite(a_): continue
        nn = null_curveball(Rs, Ys, 15, 120); pw.append(a_ <= 0.40 and (1 + (nn <= a_ + 1e-12).sum()) / 121 <= 0.05)
    res['F1'] = dict(cycles=len(cb), sale_minutes=int(Yb.sum()), auc=a_b, null_mean=float(nl.mean()), p_one_sided=p1, cycles_lower_is_sale=f'{int((dirs < 0.5).sum())}/{len(dirs)}', post_auc_same_minutes_360_374=auc(Rpost, Ypost, 15), power_estimate_7cycles_15min=float(np.mean(pw)), rule='AUC<=0.40 and p<=0.05 supported; AUC>=0.50 contradicted; else inconclusive')
    fam.append(('F1', 'held-out straddle (pre-auction)', f'AUC {a_b:.3f} vs {nl.mean():.3f}', p1))
    # ---------------------------------------------------------------- F1p placebo (post)
    pl = []
    for _ in range(1000):
        perm = RNG.permutation(len(ca)); pl.append(auc(ranks(Xa['STR15'][perm]), Ya, nj_a)) if False else None
    Rfix = ranks(Xa['STR15']); pl = []
    for _ in range(1000): perm = RNG.permutation(len(ca)); pl.append(auc(Rfix[perm], Ya, nj_a))
    pl = np.array(pl); pp_ = float((1 + (pl <= a_a + 1e-12).sum()) / 1001); res['F1p'] = dict(post_auc=a_a, placebo_mean=float(pl.mean()), placebo_p05=float(np.quantile(pl, .05)), p_one_sided=pp_); fam.append(('F1p', 'straddle placebo (cross-cycle permutation)', f'AUC {a_a:.3f} vs {pl.mean():.3f}', pp_))
    # ---------------------------------------------------------------- PB3 / PB4 hazard (post)
    for nm, col in (('PB3', 'PP'), ('PB4', 'GB')):
        R_ = ranks(Xa[col]); a_ = auc(R_, Ya, nj_a); nn = null_curveball(R_, Ya, nj_a, NP); p_ = float((1 + (np.abs(nn - 0.5) >= abs(a_ - 0.5) - 1e-12).sum()) / (NP + 1)); d_ = cyc_dir(R_, Ya, nj_a); same = int((d_ > 0.5).sum() if a_ > 0.5 else (d_ < 0.5).sum())
        res[nm] = dict(feature=col, auc=a_, null_mean=float(nn.mean()), p_two_sided=p_, cycles_same_direction=f'{same}/{len(d_)}'); fam.append((nm, f'hazard AUC of {col}', f'AUC {a_:.3f} vs {nn.mean():.3f}', p_))
    # ---------------------------------------------------------------- F2a / F2b side
    def side_test(M, label):
        P = M.pivot_table(index=['cyc', 'j'], columns='side', values=['y', 'FUT5L', 'OPT5']); one = P[(P[('y', 'CE')] + P[('y', 'PE')]) == 1].copy()
        sold_ce = one[('y', 'CE')] == 1; f = np.where(sold_ce, one[('FUT5L', 'CE')], one[('FUT5L', 'PE')]); keepm = f != 0; one = one[keepm]; f = f[keepm]; sold_ce = sold_ce[keepm]
        contr = (f > 0).astype(float); cyc = one.index.get_level_values(0).values; ucy = sorted(set(cyc)); share = float(contr.mean()); bs = []
        for _ in range(4000): d = RNG.integers(0, len(ucy), len(ucy)); x = np.concatenate([contr[cyc == ucy[i]] for i in d]); bs.append(x.mean())
        bs = np.array(bs); per = [(contr[cyc == c].mean(), (cyc == c).sum()) for c in ucy]; elig = [m for m, n in per if n >= 2]; lean = int(sum(m > 0.5 for m in elig))
        so = np.where(sold_ce, one[('OPT5', 'CE')], one[('OPT5', 'PE')]); ot = np.where(sold_ce, one[('OPT5', 'PE')], one[('OPT5', 'CE')]); cheaper = float((so < ot).mean())
        return dict(label=label, single_side_minutes=int(len(contr)), cycles=len(ucy), contrarian_share=share, ci95=[float(np.quantile(bs, .025)), float(np.quantile(bs, .975))], p_one_sided=float((1 + (bs <= 0.5).sum()) / 4001), cycles_leaning_contrarian=f'{lean}/{len(elig)} (cycles with >=2 such minutes)', side_has_larger_option_premium_fall_share_F2b=cheaper)
    res['F2a'] = side_test(Ma, 'post-auction (development)'); res['F2a_heldout'] = side_test(Mb, 'pre-auction (held-out)'); fam.append(('F2a', 'side by futures direction (post)', f"share {res['F2a']['contrarian_share']:.3f}", res['F2a']['p_one_sided'])); fam.append(('F2a_heldout', 'side by index direction (pre)', f"share {res['F2a_heldout']['contrarian_share']:.3f}", res['F2a_heldout']['p_one_sided']))
    # ---------------------------------------------------------------- F3 timing + side model (post), LOCO
    D = pd.read_csv(f'{OUT}/trig/event_table.csv.gz'); D = D[(D.era == 'after') & (D.outlier == 0)].reset_index(drop=True); D['cyc0'] = D.und + '|' + D.expiry; ev = D[D.y == 1]; n = D.cyc0.nunique(); cnt = ev.groupby(['j', 'side']).cyc0.nunique(); own = ev.groupby(['j', 'side', 'cyc0']).size().reset_index()[['j', 'side', 'cyc0']].assign(m=1)
    D = D.merge(own, on=['j', 'side', 'cyc0'], how='left'); D['m'] = D.m.fillna(0); D['clock'] = [(cnt.get((j, s), 0) - m) / (n - 1) for j, s, m in zip(D.j, D.side, D.m)]
    T = Ma.merge(D[['und', 'expiry', 'j', 'side', 'clock']], on=['und', 'expiry', 'j', 'side'], how='left'); cy = sorted(T.cyc.unique()); MOD = {'T': ['clock', 'STR15'], 'J': ['clock', 'STR15', 'FUT5L'], 'C': ['clock']}
    for nm, F in MOD.items():
        o = np.full(len(T), np.nan)
        for h in cy:
            tr = T[T.cyc != h]; te = (T.cyc == h).values; med = tr[F].median(); X = tr[F].fillna(med).values; mu, sd = X.mean(0), X.std(0) + 1e-9; lr = LogisticRegression(C=0.5, max_iter=500).fit((X - mu) / sd, tr.y.values); o[te] = lr.decision_function((T.loc[te, F].fillna(med).values - mu) / sd)
        T[f'm_{nm}'] = o
    C = V.components(T, ['m_T', 'm_J', 'm_C']); blk = lambda a, b: (lambda lo, hi, se: dict(auc_a=V.auc_from(C, a), auc_b=V.auc_from(C, b), delta=V.delta_from(C, a, b), boot95=V.boot_ci(C, a, b, 0.95, 4000, RNG), lin95=[lo, hi], p=float(2 * (1 - norm.cdf(abs(V.delta_from(C, a, b) / se)))) if se > 0 else np.nan))(*V.lin_ci(C, a, b, 0.95))
    res['F3'] = dict(J_vs_T=blk('m_J', 'm_T'), T_vs_clock=blk('m_T', 'm_C'), J_vs_clock=blk('m_J', 'm_C')); fam.append(('F3', 'side term adds to timing model (J vs T)', f"dAUC {res['F3']['J_vs_T']['delta']:+.3f}", res['F3']['J_vs_T']['p']))
    # ---------------------------------------------------------------- orders for PB1, PB2, PB5, F4
    O = DG.real_orders(); Tc = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv'); Tc = Tc[Tc.ok]; Bk = pd.read_csv(f'{OUT}/d0x/book_compare.csv'); keep = set(zip(Bk.und, Bk.expiry)); E = pd.read_csv(f'{T2}/events.csv'); cl_rows = []; per = {}
    for r in Tc.itertuples():
        if (r.und, r.expiry) not in keep or (r.und, r.d1) == OUTLIER: continue
        g = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 0)].sort_values(['t_first', 'row'])
        if not len(g): continue
        cyc = f'{r.und}|{r.d1}'; post = r.d0 >= CAS; unit = float(r.unit); lg = g[g.role == 'open_long']; used = {}
        for q in g[(g.role == 'close_long') & (g.t_first >= W0)].itertuples():
            buys = lg[(lg.cp == q.cp) & (lg.strike == q.strike) & (lg.t_first < q.t_first)]; need = q.lots; cost = 0.0; got = 0.0
            for b in buys.itertuples():
                av = b.lots - used.get(b.Index, 0)
                if av <= 0 or need <= 0: continue
                tk = min(av, need); used[b.Index] = used.get(b.Index, 0) + tk; cost += tk * b.px_avg; got += tk; need -= tk
            cl_rows.append(dict(cyc=cyc, era='after' if post else 'before', module=q.module, cp=q.cp, strike=q.strike, lots=q.lots, t=float(q.t_first), exit_px=q.px_avg, matched_lots=got, entry_px=cost / got if got else np.nan, ratio=q.px_avg / (cost / got) if got and cost > 0 else np.nan))
        per[cyc] = dict(post=post, late=g[(g.role == 'open_short') & (g.t_first >= W0) & (g.t_first < W1)], covers=g[g.role == 'cover_short'], cl=g[(g.role == 'close_long') & (g.t_first >= W0) & (g.t_first < W1)])
    CL = pd.DataFrame(cl_rows); CL.to_csv(f'{T3}/close_long.csv', index=False)
    res['PB1'] = {}
    for era in ('after', 'before'):
        x = CL[(CL.era == era)]; xm = x[x.ratio.notna()]; res['PB1'][era] = dict(orders=int(len(x)), matched=int(len(xm)), sold_above_entry=float((xm.ratio > 1).mean()) if len(xm) else None, median_ratio=float(xm.ratio.median()) if len(xm) else None, share_h_module=float((x.module == 'h_').mean()) if len(x) else None, lots_weighted_profit_share=float(xm[xm.ratio > 1].lots.sum() / xm.lots.sum()) if len(xm) else None)
    P = E[(E.era == 'after') & (E.outlier == 0)]; cycs = sorted(c for c, v in per.items() if v['post']); ev_t = {c: P[P.cyc == c].t0.values for c in cycs}; ev_t1 = {c: P[P.cyc == c].t1.values for c in cycs}
    def near(c, ts, u):
        a = ev_t[c]; b = ev_t1[c]
        if not len(a): return 0
        s0 = W0 + ((a - W0 + u) % W); d = (b - a); return int(sum(any((s0 - 60 <= t_) & (t_ <= s0 + d + 60)) for t_ in ts))
    clt = {c: per[c]['cl'].t_first.values.astype(float) for c in cycs}; ncl = sum(len(v) for v in clt.values()); k2 = sum(near(c, clt[c], 0.0) for c in cycs); n2 = np.array([sum(near(c, clt[c], RNG.uniform(0, W)) for c in cycs) for _ in range(2000)])
    res['PB2'] = dict(close_long_orders=ncl, within_60s_of_short_burst=int(k2), share=k2 / ncl if ncl else None, null_share_mean=float(n2.mean() / ncl) if ncl else None, p_one_sided=float((1 + (n2 >= k2).sum()) / 2001), excess=float(k2 / ncl - n2.mean() / ncl) if ncl else None); fam.append(('PB2', 'close_long sells near short bursts', f"{k2}/{ncl} vs {n2.mean() / ncl:.2f}", res['PB2']['p_one_sided']))
    day0, day1 = 9 * 3600 + 15 * 60, W1
    def pb5(c, u):
        pc = per[c]; ct = np.sort(day0 + ((pc['covers'].t_first.values.astype(float) - day0 + u) % (day1 - day0))); lt = pc['late'].t_first.values.astype(float); return int((np.searchsorted(ct, lt, side='left') - np.searchsorted(ct, lt - 600, side='left') > 0).sum())
    tot = sum(len(per[c]['late']) for c in cycs); h5 = sum(pb5(c, 0.0) for c in cycs); n5 = np.array([sum(pb5(c, RNG.uniform(0, day1 - day0)) for c in cycs) / tot for _ in range(2000)])
    res['PB5'] = dict(late_orders=tot, share=h5 / tot, null_mean=float(n5.mean()), excess=float(h5 / tot - n5.mean()), p_one_sided=float((1 + (n5 >= h5 / tot).sum()) / 2001)); fam.append(('PB5', 'any-side cover in previous 10 min', f"{h5 / tot:.3f} vs {n5.mean():.3f}", res['PB5']['p_one_sided']))
    # ---------------------------------------------------------------- F4 pair window (descriptive)
    pairs = E[(E.type == 'pair') & (E.outlier == 0)].copy(); hm = lambda s: f'{int(s) // 3600:02d}:{int(s) % 3600 // 60:02d}:{int(s) % 60:02d}'; pairs['time'] = pairs.t0.map(hm)
    s372 = Ma[(Ma.j == 372) & (Ma.side == 'CE')].set_index('cyc'); pc_rows = []
    for c in sorted(set(Ma.cyc)):
        hp = P[(P.cyc == c) & (P.type == 'pair')]; r_ = s372.loc[c]; pc_rows.append(dict(cyc=c, pair_burst=int(len(hp) > 0), pair_time=hm(hp.t0.iloc[0]) if len(hp) else '', late_bursts=int((P.cyc == c).sum()), sold_deficit_CE_row_1527=r_.sold_deficit, PP_1527=r_.PP, GB_1527=r_.GB, STR15_1527=r_.STR15, off_prev_median=float(hp.med_off.iloc[0]) if len(hp) else np.nan))
    PC = pd.DataFrame(pc_rows); PC.to_csv(f'{T3}/pair_cycles.csv', index=False); Ep = E[(E.era == 'before') & (E.outlier == 0)]
    res['F4'] = dict(pair_events=pairs[['cyc', 'time', 'n', 'ce_lots', 'pe_lots', 'same_strike', 'interleg_gap']].to_dict('records'), cycles_with_pair=int(PC.pair_burst.sum()), of=len(PC), pre_auction_events=int(len(Ep)), pre_auction_pairs=int((Ep.type == 'pair').sum()), pre_auction_event_times=[hm(t) for t in Ep.t0.values],
                     state_1527_mean_pair_vs_other={k: [float(PC[PC.pair_burst == 1][k].mean()), float(PC[PC.pair_burst == 0][k].mean())] for k in ('sold_deficit_CE_row_1527', 'PP_1527', 'GB_1527', 'STR15_1527')})
    # ---------------------------------------------------------------- BH family
    F = pd.DataFrame(fam, columns=['id', 'test', 'statistic', 'p']); F['p_bh_10'] = RT.bh(F.p.values); F['bh_significant_10'] = F.p_bh_10 <= 0.10; F.to_csv(f'{T3}/family.csv', index=False); json.dump(res, open(f'{T3}/focused.json', 'w'), indent=1, default=float)
    print(json.dumps(res, indent=1, default=lambda z: round(float(z), 4))[:9000]); print(F.round(4).to_string(index=False))
if __name__ == '__main__': run()
