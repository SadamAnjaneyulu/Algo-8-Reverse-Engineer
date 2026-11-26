"""Phase A G3 (plan: reports/PHASE_A_G1_G6_PLAN.md): is the low exact-strike agreement of the engine's premium-matched rule in the last 25 minutes a data-lag artefact?
decision price d = limit / 0.85 (sell); chosen contract's previous-minute close c; drift = |d/c - 1|; adjacent gap g = smaller relative difference between c and the previous-minute close of the two neighbouring strikes; low-lag: drift < g/2.
Output outputs/phaseA/g3.json, g3_orders.csv"""
import sys, os, json, warnings; sys.path.insert(0, '.'); sys.path.insert(0, '../..'); sys.path.insert(0, '../../..'); sys.path.insert(0, '../../../../d1_strategy'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
import bl_bt3_sim as S, bl_d0x_diag as DG
from d1_algo.shadow import solo_strike
OUT = S.OUT; PA = f'{OUT}/phaseA'; RNG = np.random.default_rng(20261202); CAS = '2026-08-03'; OUTLIER = ('NIFTY', '2026-10-16'); W0 = 54900
def run():
    O = DG.real_orders(); O = O.assign(jj=(O.t_first // 60 - 555).astype(int)); Tc = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv'); Tc = Tc[Tc.ok]; Bk = pd.read_csv(f'{OUT}/d0x/book_compare.csv'); keep = set(zip(Bk.und, Bk.expiry)); rows = []
    for r in Tc.itertuples():
        if (r.und, r.expiry) not in keep or (r.und, r.d1) == OUTLIER: continue
        post = r.d0 >= CAS; g = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 0) & (O.role == 'open_short')].sort_values(['t_first', 'row']); step = 50.0 if r.und == 'NIFTY' else 100.0
        cx = pd.read_pickle(f'{OUT}/bt3x/{r.und}_{r.expiry}.pkl.gz'); K = cx['opt1']['K'].astype(float); ki = {int(k): i for i, k in enumerate(K)}; ref = (pd.read_pickle(f'{OUT}/bt3s/{r.und}_{r.expiry}.pkl.gz')['spot1'] if post else cx['spot1']).close.values.astype(float); nmin = cx['opt1'][('CE', 'close')].shape[1]
        for q in g[(g.t_first >= W0)].itertuples():
            j = int(q.jj); prior = g[(g.cp == q.cp) & (g.t_first < q.t_first)]; lastp = float(prior.px_avg.iloc[-1]) if len(prior) else None
            if j - 1 >= nmin or j < 1: continue
            P = cx['opt1'][(q.cp, 'close')]; prem = lambda k, cp=q.cp, j=j: float(P[ki[int(k)], j - 1]) if int(k) in ki else float('nan')
            prop = solo_strike(K, float(K[np.argmin(np.abs(K - ref[j - 1]))]), prem, lastp, step, 4); c = prem(q.strike); d = float(q.lim_px) / 0.85
            nb = [prem(q.strike - step), prem(q.strike + step)]; gaps = [abs(x - c) / c for x in nb if x == x and c == c and c > 0]
            ok = c == c and c > 0 and len(gaps) > 0; rows.append(dict(cyc=f'{r.und}|{r.d1}', post=post, j=j, cp=q.cp, strike=float(q.strike), prop=prop, exact=bool(prop == q.strike), c=c, d=d, drift=abs(d / c - 1) if ok else np.nan, gap=min(gaps) if ok else np.nan, usable=bool(ok), held=bool((prior.strike == q.strike).any()), first_sale=bool(len(prior) == 0)))
    D = pd.DataFrame(rows); D.to_csv(f'{PA}/g3_orders.csv', index=False); U = D[D.usable].copy(); U['low_lag'] = U.drift < U.gap / 2; res = {}
    def summarise(x, label):
        a, b = x[x.low_lag], x[~x.low_lag]; cy = sorted(x.cyc.unique()); bs = []
        for _ in range(4000):
            s = RNG.integers(0, len(cy), len(cy)); xx = pd.concat([x[x.cyc == cy[i]] for i in s]); l_, h_ = xx[xx.low_lag], xx[~xx.low_lag]
            if len(l_) and len(h_): bs.append(float(l_.exact.mean() - h_.exact.mean()))
        bs = np.array(bs); return dict(label=label, orders=int(len(x)), low_lag_share=float(x.low_lag.mean()), exact_all=float(x.exact.mean()), exact_low_lag=float(a.exact.mean()) if len(a) else None, exact_high_lag=float(b.exact.mean()) if len(b) else None, n_low=int(len(a)), n_high=int(len(b)),
                                       difference=float(a.exact.mean() - b.exact.mean()) if len(a) and len(b) else None, diff_ci95=[float(np.quantile(bs, .025)), float(np.quantile(bs, .975))] if len(bs) else None, median_drift=float(x.drift.median()), median_gap=float(x.gap.median()))
    res['all_eras'] = summarise(U, 'both eras'); res['post_auction'] = summarise(U[U.post], 'post-auction'); res['not_usable_orders'] = int((~D.usable).sum()); res['total_orders'] = int(len(D))
    for k in ('all_eras', 'post_auction'):
        s = res[k]; lo = s['exact_low_lag']; df = s['difference']; ci = s['diff_ci95']
        s['verdict'] = 'data-limited' if (lo is not None and lo >= 0.55 and df is not None and df >= 0.15 and ci and ci[0] > 0) else ('rule incomplete' if (lo is not None and lo < 0.45) else 'inconclusive')
    json.dump(res, open(f'{PA}/g3.json', 'w'), indent=1, default=float); print(json.dumps(res, indent=1, default=lambda z: round(float(z), 3)))
if __name__ == '__main__': run()
