"""Re-centring hypothesis (plan: reports/LATE_SALE_RECENTER_PLAN.md, written before this ran). EXPLORATORY.
D(side, j) = OTM steps of the nearest net-short strike held on that side at the start of minute j (price = close of j-1). Tests R1, R1-held-out, R2, R2-held-out, R3; descriptives R4-R6.
Output outputs/trig4/recenter.json, family.csv, state_{after,before}.csv, new_strikes.csv"""
import sys, os, json, warnings; sys.path.insert(0, '.'); sys.path.insert(0, '../..'); sys.path.insert(0, '../../..'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from scipy.stats import norm
from sklearn.linear_model import LogisticRegression
import bl_bt3_sim as S, bl_d0x_diag as DG, bl_validation as V, bl_risk_tests as RT, bl_trig3_focused as T
OUT = S.OUT; T4 = f'{OUT}/trig4'; T3 = f'{OUT}/trig3'; os.makedirs(T4, exist_ok=True); CAS = '2026-08-03'; OUTLIER = ('NIFTY', '2026-10-16'); RNG = np.random.default_rng(20261129); T.RT.RNG = RNG; RT.RNG = RNG
def build(era):
    O = DG.real_orders(); Tc = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv'); Tc = Tc[Tc.ok]; Bk = pd.read_csv(f'{OUT}/d0x/book_compare.csv'); keep = set(zip(Bk.und, Bk.expiry)); rows = []; new = []
    for r in Tc.itertuples():
        post = r.d0 >= CAS
        if (r.und, r.expiry) not in keep or (era == 'after') != post or (r.und, r.d1) == OUTLIER: continue
        g = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 0)].sort_values(['t_first', 'row']).reset_index(drop=True)
        if not len(g): continue
        cx = pd.read_pickle(f'{OUT}/bt3x/{r.und}_{r.expiry}.pkl.gz'); Kc = cx['opt1']['K'].astype(float); kidx = {int(k): i for i, k in enumerate(Kc)}
        pr = pd.read_pickle(f'{OUT}/bt3u/{r.und}_{r.expiry}.pkl.gz')['spot1'].close.values.astype(float) if post else cx['spot1'].close.values.astype(float); nmin = len(pr); step = 50.0 if r.und == 'NIFTY' else 100.0
        cyc = f'{r.und}|{r.d1}'; t = g.t_first.values.astype(float); k = np.array([kidx.get(int(s), -1) for s in g.strike]); c = (g.cp == 'PE').astype(int).values; q = (g.sg * g.lots).values.astype(float); role = g.role.values
        def book_at(ts):
            pos = np.zeros((len(Kc), 2))
            for ti, ki, ci, qi in zip(t, k, c, q):
                if ti >= ts: break
                if ki >= 0: pos[ki, ci] += qi
            return pos
        def dist(pos, ci, P):
            ks = np.where(pos[:, ci] < 0)[0]
            if not len(ks): return np.nan
            d = (Kc[ks] - P) / step if ci == 0 else (P - Kc[ks]) / step; return float(d.min())
        jj = (t // 60 - 555).astype(int)
        for j in range(360, nmin):
            ts = (555 + j) * 60.0; pos = book_at(ts); P = pr[j - 1]; y = {cp: int(((role == 'open_short') & (g.cp.values == cp) & (jj == j)).any()) for cp in ('CE', 'PE')}
            for cp, ci in (('CE', 0), ('PE', 1)): rows.append(dict(cyc=cyc, und=r.und, d1=r.d1, expiry=r.expiry, j=j, side=cp, y=y[cp], D=dist(pos, ci, P)))
        for i in np.where((role == 'open_short') & (t >= 54900))[0]:
            ts = t[i]; pos = book_at(ts); j = int(ts // 60 - 555); P = pr[j - 1]; ci = int(c[i]); dn = (g.strike[i] - P) / step if ci == 0 else (P - g.strike[i]) / step; dold = dist(pos, ci, P); new.append(dict(cyc=cyc, era=era, t=ts, cp=g.cp[i], D_new=float(dn), D_before=dold))
        print(era, cyc, flush=True)
    M = pd.DataFrame(rows); M.to_csv(f'{T4}/state_{era}.csv', index=False); N = pd.DataFrame(new); N.to_csv(f'{T4}/new_strikes_{era}.csv', index=False); return M, N
def side_share(M, label):
    P = M.pivot_table(index=['cyc', 'j'], columns='side', values=['y', 'D']); one = P[(P[('y', 'CE')] + P[('y', 'PE')]) == 1].copy(); both = one[('D', 'CE')].notna() & one[('D', 'PE')].notna(); no_same = int((~both).sum()); one = one[both]
    sold_ce = one[('y', 'CE')] == 1; ds = np.where(sold_ce, one[('D', 'CE')], one[('D', 'PE')]); do = np.where(sold_ce, one[('D', 'PE')], one[('D', 'CE')]); keepm = ds != do; larger = (ds > do)[keepm].astype(float); cyc = one.index.get_level_values(0).values[keepm]; ucy = sorted(set(cyc)); bs = []
    for _ in range(4000): d = RNG.integers(0, len(ucy), len(ucy)); bs.append(np.concatenate([larger[cyc == ucy[i]] for i in d]).mean())
    bs = np.array(bs); return dict(label=label, single_side_minutes_with_both_D=int(len(larger)), minutes_dropped_no_short_on_a_side=no_same, share_sold_side_has_larger_D=float(larger.mean()), ci95=[float(np.quantile(bs, .025)), float(np.quantile(bs, .975))], p_one_sided=float((1 + (bs <= 0.5).sum()) / 4001), cycles=len(ucy))
def run():
    NP = int(os.environ.get('NPERM', 1000)); res = {}; fam = []
    Ma, Na = build('after'); Mb, Nb = build('before'); S3a = pd.read_csv(f'{T3}/state_after.csv'); S3b = pd.read_csv(f'{T3}/state_before.csv')
    Ma = Ma.merge(S3a[['cyc', 'j', 'side', 'STR15', 'FUT5L']], on=['cyc', 'j', 'side']); Mb = Mb.merge(S3b[['cyc', 'j', 'side', 'STR15', 'FUT5L']], on=['cyc', 'j', 'side'])
    # R1 hazards
    for nm, M, j1, one_sided in (('R1', Ma, 384, False), ('R1_held_out', Mb, 374, True)):
        cy, nj, X = T.cubes(M, ['D', 'y'], 360, j1); Y = X['y'].astype(int); Rk = T.ranks(X['D']); a = T.auc(Rk, Y, nj); nl = T.null_curveball(Rk, Y, nj, NP); d = T.cyc_dir(Rk, Y, nj)
        p = float((1 + (nl >= a - 1e-12).sum()) / (NP + 1)) if one_sided else float((1 + (np.abs(nl - 0.5) >= abs(a - 0.5) - 1e-12).sum()) / (NP + 1))
        res[nm] = dict(cycles=len(cy), sale_minutes=int(Y.sum()), auc=a, null_mean=float(nl.mean()), p=p, cycles_same_direction=f'{int((d > 0.5).sum())}/{len(d)}', share_blocks_with_no_short=float(np.isnan(X['D']).mean())); fam.append((nm, f'hazard AUC of D ({"held-out" if one_sided else "post"})', f'AUC {a:.3f} vs {nl.mean():.3f}', p))
    # R2 side
    res['R2'] = side_share(Ma, 'post-auction'); res['R2_held_out'] = side_share(Mb, 'pre-auction (held-out)')
    for nm in ('R2', 'R2_held_out'): fam.append((nm, f'sold side has the larger D ({res[nm]["label"]})', f'share {res[nm]["share_sold_side_has_larger_D"]:.3f}', res[nm]['p_one_sided']))
    # R3 incremental
    D3 = pd.read_csv(f'{OUT}/trig/event_table.csv.gz'); D3 = D3[(D3.era == 'after') & (D3.outlier == 0)].reset_index(drop=True); D3['cyc0'] = D3.und + '|' + D3.expiry; ev = D3[D3.y == 1]; n = D3.cyc0.nunique(); cnt = ev.groupby(['j', 'side']).cyc0.nunique(); own = ev.groupby(['j', 'side', 'cyc0']).size().reset_index()[['j', 'side', 'cyc0']].assign(m=1)
    D3 = D3.merge(own, on=['j', 'side', 'cyc0'], how='left'); D3['m'] = D3.m.fillna(0); D3['clock'] = [(cnt.get((j, s), 0) - m) / (n - 1) for j, s, m in zip(D3.j, D3.side, D3.m)]
    Tt = Ma.merge(D3[['und', 'expiry', 'j', 'side', 'clock']], on=['und', 'expiry', 'j', 'side'], how='left'); cyl = sorted(Tt.cyc.unique())
    for nm, F in {'T': ['clock', 'STR15'], 'R': ['clock', 'STR15', 'D'], 'C': ['clock'], 'RD': ['clock', 'D']}.items():
        o = np.full(len(Tt), np.nan)
        for h in cyl:
            tr = Tt[Tt.cyc != h]; te = (Tt.cyc == h).values; med = tr[F].median(); X = tr[F].fillna(med).values; mu, sd = X.mean(0), X.std(0) + 1e-9; lr = LogisticRegression(C=0.5, max_iter=500).fit((X - mu) / sd, tr.y.values); o[te] = lr.decision_function((Tt.loc[te, F].fillna(med).values - mu) / sd)
        Tt[f'm_{nm}'] = o
    C = V.components(Tt, ['m_T', 'm_R', 'm_C', 'm_RD']); blk = lambda a, b: (lambda lo, hi, se: dict(auc_a=V.auc_from(C, a), auc_b=V.auc_from(C, b), delta=V.delta_from(C, a, b), boot95=list(V.boot_ci(C, a, b, 0.95, 4000, RNG)), lin95=[lo, hi], p=float(2 * (1 - norm.cdf(abs(V.delta_from(C, a, b) / se)))) if se > 0 else np.nan))(*V.lin_ci(C, a, b, 0.95))
    res['R3'] = dict(R_vs_T=blk('m_R', 'm_T'), RD_vs_clock=blk('m_RD', 'm_C'), T_vs_clock=blk('m_T', 'm_C')); fam.append(('R3', 'D adds to clock + straddle change (LOCO)', f"dAUC {res['R3']['R_vs_T']['delta']:+.3f}", res['R3']['R_vs_T']['p']))
    # descriptives R4 R5 R6
    N = pd.concat([Na, Nb]); r4 = {}
    for era, x in (('after', Na), ('before', Nb)):
        has = x.D_before.notna(); dd = (x.D_before - x.D_new)[has]; r4[era] = dict(late_sales=int(len(x)), with_same_side_short=int(has.sum()), no_same_side_short=int((~has).sum()), new_strike_closer_to_money=float((dd > 0).mean()) if has.any() else None, same_strike=float((dd == 0).mean()) if has.any() else None, farther=float((dd < 0).mean()) if has.any() else None, median_D_new=float(x.D_new.median()), median_D_before=float(x.D_before.median()), median_improvement_steps=float(dd.median()) if has.any() else None)
    res['R4'] = r4; sale = Ma[Ma.y == 1].D.dropna(); non = Ma[Ma.y == 0].D.dropna(); res['R5'] = dict(D_at_sale=dict(n=int(len(sale)), median=float(sale.median()), p25=float(sale.quantile(.25)), p75=float(sale.quantile(.75))), D_other_minutes=dict(n=int(len(non)), median=float(non.median()), p25=float(non.quantile(.25)), p75=float(non.quantile(.75))), share_sale_minutes_without_same_side_short=float(Ma[Ma.y == 1].D.isna().mean()))
    best = None
    for thr in np.arange(-2, 12.01, 0.5):
        m_ = Ma.D.notna(); pred = (Ma.D >= thr) & m_; tp = int((pred & (Ma.y == 1)).sum()); fp = int((pred & (Ma.y == 0)).sum()); fn = int(((~pred) & (Ma.y == 1)).sum()); prec = tp / (tp + fp) if tp + fp else 0; rec = tp / (tp + fn) if tp + fn else 0; f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0
        if best is None or f1 > best['f1']: best = dict(threshold_steps=float(thr), precision=prec, recall=rec, f1=f1, base_rate=float(Ma.y.mean()))
    res['R5']['best_single_threshold_post_hoc'] = best; res['R6'] = dict(R2_share_D=res['R2']['share_sold_side_has_larger_D'], F2a_share_futures_direction=json.load(open(f'{T3}/focused.json'))['F2a']['contrarian_share'])
    F = pd.DataFrame(fam, columns=['id', 'test', 'statistic', 'p']); F['p_bh_10'] = RT.bh(F.p.values); F['bh_significant_10'] = F.p_bh_10 <= 0.10; F.to_csv(f'{T4}/family.csv', index=False); json.dump(res, open(f'{T4}/recenter.json', 'w'), indent=1, default=float); print(json.dumps(res, indent=1, default=lambda z: round(float(z), 4))); print(F.round(4).to_string(index=False))
if __name__ == '__main__': run()
