"""Phase A G1 (plan: reports/PHASE_A_G1_G6_PLAN.md, written before this ran). Are the CE+PE bursts at/after 15:15 fires of the unchanged two-candle breakout rule with its gate end extended?
V0 = engine rule (gate end 15:15); V1 = same rule, gate end = last minute of data (pre-auction index to 15:29, post-auction clean futures to 15:39). Output outputs/phaseA/g1.json, g1_bursts.csv, g1_orders.csv"""
import sys, os, json, warnings; sys.path.insert(0, '.'); sys.path.insert(0, '../..'); sys.path.insert(0, '../../..'); sys.path.insert(0, '../../../../d1_strategy'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
import bl_bt3_sim as S, bl_d0x_diag as DG, algo8_d1 as A
OUT = S.OUT; PA = f'{OUT}/phaseA'; os.makedirs(PA, exist_ok=True); RNG = np.random.default_rng(20261201); CAS = '2026-08-03'; OUTLIER = ('NIFTY', '2026-10-16'); W0 = 54900; NS = 5000; GAP = 10
def clusters(t):
    ev = []; cur = []
    for i in range(len(t)):
        if cur and t[i] - t[i - 1] > GAP: ev.append(cur); cur = []
        cur.append(i)
    if cur: ev.append(cur)
    return ev
def load():
    O = DG.real_orders(); O = O.assign(jj=(O.t_first // 60 - 555).astype(int)); Tc = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv'); Tc = Tc[Tc.ok]; Bk = pd.read_csv(f'{OUT}/d0x/book_compare.csv'); keep = set(zip(Bk.und, Bk.expiry)); bursts = []; orders = []; per = {}
    for r in Tc.itertuples():
        if (r.und, r.expiry) not in keep or (r.und, r.d1) == OUTLIER: continue
        post = r.d0 >= CAS; g = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 0)].sort_values(['t_first', 'row']).reset_index(drop=True)
        if not len(g): continue
        sells = g[g.role == 'open_short']; late = sells[sells.t_first >= W0].sort_values('t_first'); step = 50.0 if r.und == 'NIFTY' else 100.0
        x = pd.read_pickle(f'{OUT}/{"bt3u" if post else "bt3x"}/{r.und}_{r.expiry}.pkl.gz')['spot1']; h, l, c = (x[k].values.astype(float) for k in ('high', 'low', 'close')); n = len(c)
        cfg = A.Config(); cfg.strike_step = step; cfg.breakout_end_min = 360; v0 = A.breakout_fires(h, l, cfg); cfg.breakout_end_min = n - 1; v1 = A.breakout_fires(h, l, cfg)
        cfgl = A.Config(); cfgl.ladder_gate_min = 5; cfgl.strike_step = step; ev = {cp: sorted(set(sells[sells.cp == cp].jj.tolist())) for cp in ('CE', 'PE')}; lad = {(j, cp) for j, cps in A.ladder_fires(c, h, l, ev, cfgl).items() for cp in cps}
        cyc = f'{r.und}|{r.d1}'; per[cyc] = dict(post=post, n=n, v0=v0, v1=v1, lad=lad)
        if len(late):
            for e in clusters(late.t_first.values):
                z = late.iloc[e]; cps = sorted(set(z.cp)); bursts.append(dict(cyc=cyc, post=post, t0=float(z.t_first.min()), j0=int(z.jj.min()), n=len(z), legs='+'.join(cps), pair=int(len(cps) == 2), off_ce=float(z[z.cp == 'CE'].off_prev.median()) if 'CE' in cps else np.nan, off_pe=float(z[z.cp == 'PE'].off_prev.median()) if 'PE' in cps else np.nan))
            for q in late.itertuples(): orders.append(dict(cyc=cyc, post=post, j=int(q.jj), cp=q.cp, t=float(q.t_first)))
    return per, pd.DataFrame(bursts), pd.DataFrame(orders)
def run():
    per, B, lo0 = load(); P = B[B.pair == 1].reset_index(drop=True); res = {}; orders = lo0.to_dict('records')
    fires_after = lambda f: [(j, s, d) for j, s, d in f if j >= 361]
    def matched(row, fires):
        return any(abs(j - row.j0) <= 1 for j, s, d in fires)
    P['v1_match'] = [matched(r, per[r.cyc]['v1']) for r in P.itertuples()]; P['v0_match'] = [matched(r, per[r.cyc]['v0']) for r in P.itertuples()]; obs = int(P.v1_match.sum()); nn = []
    for _ in range(NS):
        m = 0
        for r in P.itertuples():
            nj = per[r.cyc]['n']; L = nj - 361; jj = 361 + (r.j0 - 361 + int(RNG.integers(0, L))) % L; m += any(abs(j - jj) <= 1 for j, s, d in per[r.cyc]['v1'])
        nn.append(m)
    nn = np.array(nn); res['G1'] = dict(pair_bursts=int(len(P)), post=int(P.post.sum()), pre=int((~P.post).sum()), v1_matched=obs, v0_matched=int(P.v0_match.sum()), null_mean=float(nn.mean()), p_one_sided=float((1 + (nn >= obs).sum()) / (NS + 1)), success_rule='matched >= 5 of 8 and p <= 0.05', supported=bool(obs >= 5 and (1 + (nn >= obs).sum()) / (NS + 1) <= 0.05))
    # descriptives: fires after 15:15 and their precision; order-level recall by rule; side / strike of matched bursts
    V1a = {c: fires_after(v['v1']) for c, v in per.items()}; lo = pd.DataFrame(orders); tot_f = sum(len(v) for v in V1a.values()); hit_f = 0
    for c, fl in V1a.items():
        js = lo[lo.cyc == c].j.values
        hit_f += sum(any(abs(j - x) <= 1 for x in js) for j, s, d in fl)
    lo['ladder'] = [((r.j + d, r.cp) in per[r.cyc]['lad']) for r in lo.itertuples() for d in (0,)]; lo['ladder'] = [any((r.j + d, r.cp) in per[r.cyc]['lad'] for d in (-1, 0, 1)) for r in lo.itertuples()]; lo['v0'] = [any(abs(j - r.j) <= 1 for j, s, d in per[r.cyc]['v0']) for r in lo.itertuples()]; lo['v1'] = [any(abs(j - r.j) <= 1 for j, s, d in per[r.cyc]['v1']) for r in lo.itertuples()]
    lo['either'] = lo.ladder | lo.v1; lo['burst_pair'] = False
    for r in P.itertuples(): lo.loc[(lo.cyc == r.cyc) & (lo.t >= r.t0) & (lo.t <= r.t0 + 15), 'burst_pair'] = True
    res['descriptive'] = dict(v1_fires_after_1515=int(tot_f), v1_fires_within_1min_of_any_real_late_sale=int(hit_f), v1_precision_vs_any_late_sale=hit_f / tot_f if tot_f else None, cycles=len(per), late_orders=int(len(lo)),
                              order_recall={k: float(lo[k].mean()) for k in ('v0', 'v1', 'ladder', 'either')}, order_recall_post={k: float(lo[lo.post][k].mean()) for k in ('v0', 'v1', 'ladder', 'either')}, order_recall_pair_burst_orders={k: float(lo[lo.burst_pair][k].mean()) for k in ('v0', 'v1', 'ladder', 'either')}, pair_burst_orders=int(lo.burst_pair.sum()),
                              same_strike_bursts=int(((P.off_ce - P.off_pe).abs() < 1e-9).sum()), v1_extra_fires_per_cycle=float(tot_f / len(per)))
    P.to_csv(f'{PA}/g1_bursts.csv', index=False); lo.to_csv(f'{PA}/g1_orders.csv', index=False); json.dump(res, open(f'{PA}/g1.json', 'w'), indent=1, default=float); print(json.dumps(res, indent=1, default=lambda z: round(float(z), 4))); print(P.drop(columns=[]).round(2).to_string(index=False))
if __name__ == '__main__': run()
