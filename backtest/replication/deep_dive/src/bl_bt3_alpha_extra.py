"""Independent checks for the alpha question (plan reports/ALPHA_SOURCE_PLAN.md): (1) implied volatility (trading-minute clock) and realised volatility by session; (2) naive benchmark: one ATM straddle sold at the D-1 09:16 open and held to the D0 15:14 close, without and with the strategy's wing rule.
Output outputs/bt3_results/alpha_iv_cycles.csv, alpha_naive_cycles.csv, alpha_extra_summary.json"""
import sys, os, json, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from multiprocessing import Pool
import bl_bt3_greeks as G
OUT = G.OUT; RES = G.RES; BT3 = G.BT3; REFU = {'NIFTY': 65.0, 'SENSEX': 20.0}; STEP = {'NIFTY': 50.0, 'SENSEX': 100.0}
def atm_iv(o, spot, j, T):
    K = o['K']; a = int(np.argmin(np.abs(K - spot))); ivs = []
    for cp in ('CE', 'PE'):
        p = o[(cp, 'close')][a, j]; ivs.append(G.implied_vol(np.array([p]), np.array([spot]), np.array([K[a]]), np.array([T]), np.array([cp == 'CE']))[0] if p > 0.2 else np.nan)
    return float(np.nanmean(ivs))
def one(a):
    und, expiry, d1, d0, unit, split = a; c = pd.read_pickle(f'{BT3}/{und}_{expiry}.pkl.gz'); s1, s0 = c['spot1'], c['spot0']; o1, o0 = c['opt1'], c['opt0']; Tt = lambda t: (750 - t) / 93750.0; row = dict(und=und, expiry=expiry, split=split)
    for nm, (o, s, j, t) in {'iv_D1_open': (o1, s1, 2, 2), 'iv_D1_mid': (o1, s1, 240, 240), 'iv_D1_close': (o1, s1, 372, 372), 'iv_D0_open': (o0, s0, 2, 377), 'iv_D0_mid': (o0, s0, 120, 495), 'iv_D0_late': (o0, s0, 355, 730)}.items(): row[nm] = atm_iv(o, float(s.close.iloc[j]), j, Tt(t))
    for nm, s in (('rv_D1', s1), ('rv_D0', s0)): r = np.diff(np.log(s.close.values.astype(float))); row[nm] = float(np.sqrt(93750 * np.mean(r ** 2)))
    ov = np.log(s0.open.iloc[0] / s1.close.iloc[374]); row['overnight_move_pct'] = float(100 * ov)
    # naive straddle: sell ATM CE+PE at D-1 j=1 open, buy back at D0 j=359 close; one lot each leg, constant lot size
    K1 = o1['K']; a1 = int(np.argmin(np.abs(K1 - s1.close.iloc[0]))); k = K1[a1]; i0 = int(np.searchsorted(o0['K'], k)); u = REFU[und]; pnl = 0.0; prem = 0.0; wing = 0.0; ok = i0 < len(o0['K']) and o0['K'][i0] == k
    if ok:
        for cp in ('CE', 'PE'):
            e = o1[(cp, 'open')][a1, 1]; x = o0[(cp, 'close')][i0, 359]; pnl += (e - x) * u; prem += e * u
        row.update(naive_pnl=pnl, naive_premium=prem)
        for cp, sg in (('CE', 1), ('PE', -1)):
            tgt = 0.025 * o1[(cp, 'close')][a1, 0]; off = (K1 - s1.close.iloc[0]) * sg; okk = (off > 0) & np.isfinite(o1[(cp, 'close')][:, 0]) & (o1[(cp, 'close')][:, 0] > 0)
            if okk.any():
                kk = K1[okk][np.argmin(np.abs(np.log(o1[(cp, 'close')][okk, 1] / tgt)))]; ii0 = int(np.searchsorted(o0['K'], kk)); ii1 = int(np.searchsorted(K1, kk))
                if ii0 < len(o0['K']) and o0['K'][ii0] == kk: wing += (o0[(cp, 'close')][ii0, 359] - o1[(cp, 'close')][ii1, 1]) * u
        row['naive_wings_pnl'] = pnl + wing
    return row
if __name__ == '__main__':
    T0 = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv'); T0 = T0[T0.split3.isin(['IS', 'OOS', 'LIVE_FITTED']) & T0.ok]
    with Pool(4) as p: res = p.map(one, [(r.und, r.expiry, r.d1, r.d0, float(r.unit), r.split3) for r in T0.itertuples()], chunksize=4)
    D = pd.DataFrame(res); D.to_csv(f'{RES}/alpha_iv_cycles.csv', index=False); pd.set_option('display.width', 250)
    print(D.groupby('und')[['iv_D1_open', 'iv_D1_mid', 'iv_D1_close', 'iv_D0_open', 'iv_D0_mid', 'iv_D0_late', 'rv_D1', 'rv_D0']].mean().round(3).to_string()); print('naive straddle per cycle (Rs, const lot): mean', round(D.naive_pnl.mean()), 'win', round((D.naive_pnl > 0).mean(), 2), 'with wings mean', round(D.naive_wings_pnl.mean()), 'worst', round(D.naive_pnl.min()), 'premium mean', round(D.naive_premium.mean()))
