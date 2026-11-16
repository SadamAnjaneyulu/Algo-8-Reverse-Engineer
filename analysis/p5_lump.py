"""P5: overnight lump (v_) sizing. At the first v_ buy on each D-1: book greeks from Black-Scholes IVs inverted from Breeze bars.
Candidate rules for lots; scored by median absolute % error and leave-one-out regression.   python3 analysis/p5_lump.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from math import log, sqrt, exp, erf, pi
from scipy.optimize import brentq
from load import load_tagged
C = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_cache')
N = lambda x: 0.5 * (1 + erf(x / sqrt(2))); n = lambda x: exp(-x * x / 2) / sqrt(2 * pi)
def bs(cp, S, K, T, v):
    if T <= 0 or v <= 0: return max(0, (S - K) if cp == 'CE' else (K - S))
    d1 = (log(S / K) + 0.5 * v * v * T) / (v * sqrt(T)); d2 = d1 - v * sqrt(T)
    return S * N(d1) - K * N(d2) if cp == 'CE' else K * N(-d2) - S * N(-d1)
def iv(cp, S, K, T, p):
    try: return brentq(lambda v: bs(cp, S, K, T, v) - p, 1e-3, 5.0)
    except Exception: return np.nan
def greeks(cp, S, K, T, v):
    d1 = (log(S / K) + 0.5 * v * v * T) / (v * sqrt(T))
    delta = N(d1) if cp == 'CE' else N(d1) - 1
    return delta, n(d1) / (S * v * sqrt(T)), S * n(d1) * sqrt(T) / 100
d = load_tagged().sort_values(['t', 'row'])
ix = pd.read_pickle(os.path.join(C, 'idx_candles.pkl')).set_index(['und', 'ts']).close.sort_index()
op = pd.read_pickle(os.path.join(C, 'opt_candles.pkl')).set_index(['und', 'expiry', 'cp', 'strike', 'ts']).c.sort_index()
rows = []
for date, g in d[(d.dte >= 1)].groupby('date'):
    v = g[(g.tp == 'v_') & (g.side == 'Buy')]
    if v.empty: continue
    t0 = v.t.min(); und = g.und.iloc[0]; exp_ = g.expiry.iloc[0]; lot = g.lot.iloc[0]; step = 50 if und == 'NIFTY' else 100
    lump_cp = v.cp.mode()[0]; lump_K = v.strike.mode()[0]; lump_lots = v[(v.cp == lump_cp) & (v.strike == lump_K)].lots.sum()
    m = t0.floor('min') - pd.Timedelta(minutes=1)
    S = ix.get((und, m), np.nan)
    T = ((exp_ + pd.Timedelta('15:30:00')) - t0).total_seconds() / (365 * 86400)
    pre = d[(d.und == und) & (d.expiry == exp_) & (d.t < t0)]
    pos = pre.groupby(['cp', 'strike']).sl.sum(); pos = pos[pos.abs() > 1e-9]
    D = G = V = 0.0; heavyD = 0.0; prem_short = 0.0
    sCE = -pos[(pos < 0) & (pos.index.get_level_values(0) == 'CE')].sum(); sPE = -pos[(pos < 0) & (pos.index.get_level_values(0) == 'PE')].sum()
    heavy = 'CE' if sCE > sPE else 'PE'
    for (cp, K), q in pos.items():
        p = op.get((und, exp_, cp, K, m), np.nan)
        if not np.isfinite(p) or p <= 0.05: continue
        vol = iv(cp, S, K, T, p)
        if not np.isfinite(vol): continue
        de, ga, ve = greeks(cp, S, K, T, vol)
        D += q * de; G += q * ga; V += q * ve
        if q < 0: prem_short += -q * p * lot
    pL = op.get((und, exp_, lump_cp, lump_K, m), np.nan); vL = iv(lump_cp, S, lump_K, T, pL) if np.isfinite(pL) else np.nan
    dL, gL, veL = greeks(lump_cp, S, lump_K, T, vL) if np.isfinite(vL) else (np.nan,) * 3
    credit = pre[pre.date == date].cash.sum()
    rows.append(dict(date=date.date(), und=und, side=lump_cp, heavy=heavy, lots=lump_lots, S=S, K=lump_K, otm_pct=abs(lump_K - S) / S * 100, pL=pL,
                     netD=D, netG=G, netV=V, dL=dL, gL=gL, vL=veL, imb=abs(sCE - sPE), short_tot=sCE + sPE, prem_short=prem_short, credit=credit, lot=lot))
R = pd.DataFrame(rows)
R['side_ok'] = R.side == R.heavy
cands = {
    'delta-neutralise: |netD|/|dL|': (R.netD.abs() / R.dL.abs()),
    'gamma-neutralise: |netG|/gL': (R.netG.abs() / R.gL),
    'vega-neutralise: |netV|/vL': (R.netV.abs() / R.vL),
    'imbalance lots': R.imb,
    'short lots total': R.short_tot,
    'budget 3% of day credit / cost': (0.03 * R.credit.abs() / (R.pL * R.lot)),
}
pd.set_option('display.width', 220)
print(R[['date', 'und', 'side', 'heavy', 'lots', 'otm_pct', 'pL', 'netD', 'dL', 'netG', 'gL', 'imb', 'short_tot']].round(3).to_string(index=False))
print('\nlump on heavier short side:', R.side_ok.mean().round(3))
print('\ncandidate formula -> lots (ratio actual/candidate: median, IQR; corr):')
for k, c in cands.items():
    r = R.lots / c
    print(f'  {k:34s} median ratio {r.median():.3f}  IQR [{r.quantile(.25):.2f},{r.quantile(.75):.2f}]  corr {np.corrcoef(R.lots, c.fillna(0))[0,1]:.2f}  MdAPE-at-median-scale {np.median(np.abs(R.lots - r.median()*c)/R.lots):.2f}')
R.to_pickle(os.path.join(C, 'p5_lumps.pkl'))
