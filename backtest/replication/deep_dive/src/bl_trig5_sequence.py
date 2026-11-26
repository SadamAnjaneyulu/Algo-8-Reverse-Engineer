"""Order sequence around the late bursts (plan: reports/LATE_SALE_SEQUENCE_PLAN.md, written before this ran). EXPLORATORY.
W1 wing balance restored, W2 lag after a body order, W3 follows a same-right cover; descriptives: timelines, who-first, outermost-first.
Output outputs/trig5/sequence.json, clusters.csv, timelines.csv, family.csv"""
import sys, os, json, warnings; sys.path.insert(0, '.'); sys.path.insert(0, '../..'); sys.path.insert(0, '../../..'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
import bl_bt3_sim as S, bl_d0x_diag as DG, bl_risk_tests as RT
OUT = S.OUT; T5 = f'{OUT}/trig5'; os.makedirs(T5, exist_ok=True); RNG = np.random.default_rng(20261130); W0, W1 = 54900, 56400; CAS = '2026-08-03'; OUTLIER = ('NIFTY', '2026-10-16'); NS = 5000; GAP = 10
def book(g, cp, before_t, upto_inclusive=False):
    """short lots S and long lots L on a right from the orders strictly before before_t (or up to and including it)"""
    x = g[(g.t_first <= before_t) if upto_inclusive else (g.t_first < before_t)]; x = x[x.cp == cp]; net = (x.sg * x.lots).groupby(x.strike).sum(); return float(-net[net < 0].sum()), float(net[net > 0].sum()), net
def tol(S_): return max(1.0, 0.1 * S_)
def clusters(cl):
    out = []; cur = []
    for r in cl.itertuples():
        if cur and r.t_first - cur[-1].t_first > GAP: out.append(cur); cur = []
        cur.append(r)
    if cur: out.append(cur)
    return out
def run():
    O = DG.real_orders(); Tc = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv'); Tc = Tc[Tc.ok]; Bk = pd.read_csv(f'{OUT}/d0x/book_compare.csv'); keep = set(zip(Bk.und, Bk.expiry)); E = pd.read_csv(f'{OUT}/trig2/events.csv'); rows = []; tl = []; res = {}
    G = {}
    for r in Tc.itertuples():
        if (r.und, r.expiry) not in keep or (r.und, r.d1) == OUTLIER: continue
        g = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 0)].sort_values(['t_first', 'row']).reset_index(drop=True)
        if len(g): G[f'{r.und}|{r.d1}'] = (g, r.d0 >= CAS)
    for cyc, (g, post) in G.items():
        cl = g[(g.role == 'close_long') & (g.t_first >= W0) & (g.t_first < W1)]
        for cp in ('CE', 'PE'):
            for c in clusters(cl[cl.cp == cp].sort_values('t_first')):
                t0, t1 = c[0].t_first, c[-1].t_first; lots = float(sum(x.lots for x in c)); S0, L0, net0 = book(g, cp, t0); S1, L1, _ = book(g, cp, t1, True)
                body = g[(g.module == 'num') & (g.t_first < t0)]; lag_any = float(t0 - body.t_first.max()) if len(body) else np.nan; lag_same = float(t0 - body[body.cp == cp].t_first.max()) if len(body[body.cp == cp]) else np.nan
                cov = g[(g.role == 'cover_short') & (g.cp == cp) & (g.t_first < t0) & (g.t_first >= t0 - 60)]; cov_any = g[(g.role == 'cover_short') & (g.t_first < t0) & (g.t_first >= t0 - 60)]
                strikes = sorted(set(x.strike for x in c)); held = net0[net0 > 0].index.values; outer = (max(held) if cp == 'CE' else min(held)) if len(held) else np.nan; outermost = [(s == outer) for s in strikes]
                b = E[E.cyc == cyc] if post else E.iloc[0:0]; lead = None
                if len(b): d = b.t0.values - t0; i = int(np.argmin(np.abs(d))); lead = float(d[i])        # >0: burst starts after the cluster
                rows.append(dict(cyc=cyc, post=post, cp=cp, t0=float(t0), t1=float(t1), orders=len(c), lots_closed=lots, module=','.join(sorted(set(x.module for x in c))), S_before=S0, L_before=L0, S_after=S1, L_after=L1, lag_since_body_any=lag_any, lag_since_body_same_right=lag_same,
                                 cover_same_right_60s=int(len(cov) > 0), cover_any_60s=int(len(cov_any) > 0), outermost_held_long_sold=float(np.mean(outermost)) if outermost else np.nan, nearest_burst_start_minus_cluster=lead, exit_over_entry=np.nan))
    C = pd.DataFrame(rows); C.to_csv(f'{T5}/clusters.csv', index=False); P = C[C.post]; n = len(P)
    # ---- null machinery: random time u in the same cycle/right
    def cond_w1(g, cp, u, lots):
        S_, L_, _ = book(g, cp, u); return (L_ > S_ + tol(S_)) and abs((L_ - lots) - S_) <= tol(S_)
    def cond_w2(g, u): body = g[(g.module == 'num') & (g.t_first < u)]; lag = u - body.t_first.max() if len(body) else np.inf; return 2 <= lag <= 8
    def cond_w3(g, cp, u): return int(len(g[(g.role == 'cover_short') & (g.cp == cp) & (g.t_first < u) & (g.t_first >= u - 60)]) > 0)
    obs1 = int(((P.L_before > P.S_before + P.S_before.map(tol)) & ((P.L_after - P.S_after).abs() <= P.S_after.map(tol))).sum()); obs2 = int(P.lag_since_body_any.between(2, 8).sum()); obs3 = int(P.cover_same_right_60s.sum())
    n1 = np.zeros(NS); n2 = np.zeros(NS); n3 = np.zeros(NS); pre = []
    for r in P.itertuples(): g = G[r.cyc][0]; pre.append((g, r.cp, r.lots_closed))
    for b in range(NS):
        a1 = a2 = a3 = 0
        for g, cp, lots in pre:
            u = RNG.uniform(W0, W1); a1 += cond_w1(g, cp, u, lots); a2 += cond_w2(g, u); a3 += cond_w3(g, cp, u)
        n1[b], n2[b], n3[b] = a1, a2, a3
        if b == 499 and os.environ.get('QUICK'): break
    NSd = b + 1; n1, n2, n3 = n1[:NSd], n2[:NSd], n3[:NSd]
    fam = []
    for nm, obs, nl, desc in (('W1', obs1, n1, 'wing balance restored by the close'), ('W2', obs2, n2, 'close 2-8 s after a body order'), ('W3', obs3, n3, 'close follows a same-right cover within 60 s')):
        p = float((1 + (nl >= obs).sum()) / (NSd + 1)); res[nm] = dict(clusters=n, observed=obs, share=obs / n, null_mean_share=float(nl.mean() / n), excess=float(obs / n - nl.mean() / n), p_one_sided=p); fam.append((nm, desc, f'{obs}/{n} vs {nl.mean():.1f}', p))
    F = pd.DataFrame(fam, columns=['id', 'test', 'statistic', 'p']); F['p_bh_10'] = RT.bh(F.p.values); F['bh_significant_10'] = F.p_bh_10 <= 0.10; F.to_csv(f'{T5}/family.csv', index=False)
    res['descriptive'] = dict(clusters_post=n, clusters_pre=int((~C.post).sum()), orders_post=int(P.orders.sum()), lag_since_body_any=P.lag_since_body_any.describe().round(1).to_dict(), lag_since_body_same_right=P.lag_since_body_same_right.describe().round(1).to_dict(), module=P.module.value_counts().to_dict(),
                              cover_same_right_60s=int(P.cover_same_right_60s.sum()), cover_any_60s=int(P.cover_any_60s.sum()), S_fell_before=int((P.S_before < 1e9).sum()), L_before_gt_S_before=int((P.L_before > P.S_before).sum()), balanced_after=int(((P.L_after - P.S_after).abs() <= P.S_after.map(tol)).sum()),
                              outermost_first_share=float(P.outermost_held_long_sold.mean()), cluster_first=int((P.nearest_burst_start_minus_cluster > 0).sum()), burst_first=int((P.nearest_burst_start_minus_cluster < 0).sum()), burst_lag_median_s=float(P.nearest_burst_start_minus_cluster.abs().median()))
    # timelines for the cycles with a post-auction close_long
    for cyc in sorted(set(P.cyc)):
        g = G[cyc][0]; lo = P[P.cyc == cyc].t0.min() - 120; hi = P[P.cyc == cyc].t1.max() + 120; x = g[(g.t_first >= lo) & (g.t_first <= hi)]
        for r in x.itertuples(): tl.append(dict(cyc=cyc, time=f'{int(r.t_first) // 3600:02d}:{int(r.t_first) % 3600 // 60:02d}:{int(r.t_first) % 60:02d}', role=r.role, module=r.module, cp=r.cp, strike=r.strike, lots=r.lots, price=r.px_avg))
    pd.DataFrame(tl).to_csv(f'{T5}/timelines.csv', index=False); json.dump(res, open(f'{T5}/sequence.json', 'w'), indent=1, default=float); print(json.dumps(res, indent=1, default=lambda z: round(float(z), 3))); print(F.round(4).to_string(index=False)); print(C.round(1).to_string(index=False))
if __name__ == '__main__': run()
