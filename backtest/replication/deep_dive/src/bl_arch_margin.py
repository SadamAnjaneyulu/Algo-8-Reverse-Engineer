"""Question B of reports/PREMIUM_AND_ARCHITECTURE_PLAN.md: approximate SPAN-like margin, overnight gap stress and return on margin for the ablation variants.
Margin: worst of 16 scenarios (index x (1 + k*PSR/3), k=-3..3, implied vol +/- VSR; extreme +/-2*PSR weighted 35%) + exposure margin 2% of short notional (+2% on D0 from 20 Nov 2024).
Black r = 0, each contract's own implied total standard deviation; volatility shift on the trading-minute clock. Constant lot (NIFTY 65, SENSEX 20).
Output outputs/arch/arch_cycles.csv (one row per cycle x variant x PSR x VSR) and arch_gap.csv. Run: OMP_NUM_THREADS=1 python bl_arch_margin.py"""
import sys, os, json, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from scipy.special import ndtr
from multiprocessing import Pool
import bl_thesis_tests as TT
OUT = TT.OUT; BT3 = TT.BT3; RES = f'{OUT}/bt3_results'; AR = f'{OUT}/arch'; os.makedirs(AR, exist_ok=True); REFU = {'NIFTY': 65.0, 'SENSEX': 20.0}
VARIANTS = ['full', 'd1_no_wings', 'd1_no_lump', 'd0_no_hedge', 'd1_no_stops', 'd0_no_stop_tp', 'no_cycle_stop']; PSRS = [0.04, 0.06, 0.093]; VSRS = [0.0, 0.04, 0.08]
GAPS = [-0.05, -0.03, -0.02, -0.01, 0.01, 0.02, 0.03, 0.05]
def black(S, K, s, call):
    s = np.maximum(s, 1e-6); d1 = (np.log(S / K) + 0.5 * s * s) / s; d2 = d1 - s
    return np.where(call, S * ndtr(d1) - K * ndtr(d2), K * ndtr(-d2) - S * ndtr(-d1))
def book_state(o, S, keys, pos):
    K = np.array([k for _, k in keys], float); call = np.array([cp == 'CE' for cp, _ in keys]); s = np.zeros(len(keys)); p0 = np.zeros(len(keys))
    for n, (cp, k) in enumerate(keys):
        i = int(np.searchsorted(o['K'], k)); pr = TT.px(o, cp, 'close', i, o['_j']) if i < len(o['K']) and o['K'][i] == k else np.nan
        intr = max(S - k, 0) if cp == 'CE' else max(k - S, 0); pr = intr + 0.05 if not np.isfinite(pr) else pr; sd = TT.total_std(pr, S, k, cp == 'CE')
        s[n] = sd if np.isfinite(sd) else 1e-4; p0[n] = black(S, k, s[n], cp == 'CE')
    return K, call, s, p0
def scen_loss(S, K, call, s, p0, q, T, psr, vsr):
    sig = s / np.sqrt(T); worst = 0.0
    for k in range(-3, 4):
        for dv in ((-vsr, vsr) if vsr > 0 else (0.0,)):
            s2 = np.maximum(sig + dv, 1e-4) * np.sqrt(T); worst = max(worst, -float(np.sum(q * (black(S * (1 + k * psr / 3), K, s2, call) - p0))))
    for x in (-2 * psr, 2 * psr): worst = max(worst, -0.35 * float(np.sum(q * (black(S * (1 + x), K, s, call) - p0))))
    return worst
def one(a):
    und, expiry, d0date, variant, F = a; c = pd.read_pickle(f'{BT3}/{und}_{expiry}.pkl.gz'); U = REFU[und]; post = d0date >= '2024-11-20'
    t = F.day.values * 375 + F.j.values; keys = sorted({(r.cp, int(r.strike)) for r in F.itertuples()}); ki = {k: n for n, k in enumerate(keys)}
    dq = np.zeros((len(keys), 750)); np.add.at(dq, ([ki[(cp, int(k))] for cp, k in zip(F.cp, F.strike)], t), F.side.values * F.lots.values); pos = np.cumsum(dq, axis=1) * U
    samples = [(0, j) for j in list(range(1, 362, 15)) + [374]] + [(1, j) for j in list(range(1, 347, 15)) + [358]]
    out = {(p, v): dict(peak_margin=0.0, peak_span=0.0, margin_d1_close=np.nan, peak_short_units=0.0) for p in PSRS for v in VSRS}; gap = []
    for day, j in samples:
        tt = day * 375 + j; q = pos[:, tt]; nz = q != 0
        if not nz.any(): continue
        o = c['opt1'] if day == 0 else c['opt0']; o['_j'] = j; S = float((c['spot1'] if day == 0 else c['spot0']).close.iloc[j]); kk = [keys[n] for n in np.where(nz)[0]]; qq = q[nz]
        K, call, s, p0 = book_state(o, S, kk, qq); T = max(750 - tt, 1) / 93750.0; short_units = float(-qq[qq < 0].sum()); elm = (0.02 + (0.02 if (day == 1 and post) else 0.0)) * S * short_units
        for p in PSRS:
            for v in VSRS:
                span = scen_loss(S, K, call, s, p0, qq, T, p, v); m = span + elm; r = out[(p, v)]; r['peak_margin'] = max(r['peak_margin'], m); r['peak_span'] = max(r['peak_span'], span); r['peak_short_units'] = max(r['peak_short_units'], short_units)
                if day == 0 and j == 374: r['margin_d1_close'] = m
        if day == 0 and j == 374:                                                           # overnight gap stress of the carried book (time value kept = conservative)
            for x in GAPS:
                for vm in (1.0, 1.25): gap.append(dict(und=und, expiry=expiry, variant=variant, gap=x, vol_mult=vm, loss=-float(np.sum(qq * (black(S * (1 + x), K, s * vm, call) - p0))), short_units=short_units, long_units=float(qq[qq > 0].sum())))
    rows = [dict(und=und, expiry=expiry, variant=variant, psr=p, vsr=v, **r) for (p, v), r in out.items()]; return rows, gap
if __name__ == '__main__':
    T0 = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv'); T0 = T0[T0.split3.isin(['IS', 'OOS', 'LIVE_FITTED']) & T0.ok].set_index(['und', 'expiry']); jobs = []
    for v in VARIANTS:
        F = pd.read_csv(f'{RES}/ablate_{v}_fills.csv.gz')
        for (u, e), g in F.groupby(['und', 'expiry']):
            if (u, e) in T0.index: jobs.append((u, e, T0.loc[(u, e), 'd0'], v, g))
    with Pool(4) as p: res = p.map(one, jobs, chunksize=4)
    A = pd.DataFrame([r for rs, _ in res for r in rs]); G = pd.DataFrame([r for _, gs in res for r in gs]); A.to_csv(f'{AR}/arch_cycles.csv', index=False); G.to_csv(f'{AR}/arch_gap.csv', index=False)
    print(len(jobs), 'cycle-variants'); print(A[A.vsr == 0.04].groupby(['psr', 'variant'])[['peak_margin', 'margin_d1_close', 'peak_span']].median().round(-3).to_string())
    print(G[G.vol_mult == 1.25].groupby(['gap', 'variant']).loss.quantile(.95).unstack().round(-3).to_string())
