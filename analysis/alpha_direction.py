"""ALPHA-3: how much of cycle P&L is directional? Regress cycle P&L on the index move over the cycle (D-1 09:16 -> expiry close), and
measure the book's net delta tilt (BS delta, own IV, lot-weighted) through D-1.  python3 analysis/alpha_direction.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from math import log, sqrt, erf
from scipy.optimize import brentq
from scipy import stats
from load import load_tagged
C = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_cache')
R = pd.read_pickle(os.path.join(C, 'alpha_split.pkl'))
ix = pd.read_pickle(os.path.join(C, 'idx_candles.pkl')); ixc = ix.set_index(['und', 'ts']).close.sort_index()
d = load_tagged()
N = lambda x: 0.5 * (1 + erf(x / sqrt(2)))
def bs(cp, S, K, T, v):
    d1 = (log(S / K) + 0.5 * v * v * T) / (v * sqrt(T)); d2 = d1 - v * sqrt(T)
    return S * N(d1) - K * N(d2) if cp == 'CE' else K * N(-d2) - S * N(-d1)
def delta(cp, S, K, T, p):
    intr = max(0, S - K) if cp == 'CE' else max(0, K - S)
    if p <= intr + 0.05: return (1.0 if S > K else 0.0) if cp == 'CE' else (-1.0 if S < K else 0.0)
    try: v = brentq(lambda v: bs(cp, S, K, T, v) - p, 1e-3, 6)
    except Exception: return np.nan
    d1 = (log(S / K) + 0.5 * v * v * T) / (v * sqrt(T)); return N(d1) if cp == 'CE' else N(d1) - 1
rows = []
for r in R.itertuples():
    e = pd.Timestamp(r.expiry); c = d[(d.und == r.und) & (d.expiry == e)]
    d1 = c[c.dte >= 1].date.min()
    S0 = ixc.get((r.und, d1 + pd.Timedelta('09:15:00')), np.nan); S_d1c = ix[(ix.und == r.und) & (ix.ts.dt.normalize() == d1)].close.iloc[-1]
    ST = ix[(ix.und == r.und) & (ix.ts.dt.normalize() == e)].close.iloc[-1]
    # net delta of the book at D-1 close (every fill before 15:30 D-1), BS delta from each sale's own fill price at sale time (approximation)
    pre = c[c.date == d1]
    T = ((e + pd.Timedelta('15:30:00')) - (d1 + pd.Timedelta('15:00:00'))).total_seconds() / (365 * 86400)
    pos = pre.groupby(['cp', 'strike']).sl.sum(); pos = pos[pos.abs() > 1e-9]
    last = pre.sort_values('t').groupby(['cp', 'strike']).px_fill.last()
    nd = sum(q * (delta(cp, S_d1c, K, T, last[(cp, K)]) or 0) for (cp, K), q in pos.items())
    lot = c.lot.iloc[0]
    rows.append(dict(und=r.und, expiry=r.expiry, ret_cycle_bp=(ST - S0) / S0 * 1e4, ret_overnight_bp=(ST - S_d1c) / S_d1c * 1e4,
                     net_delta_lots_D1close=nd, net_delta_rupee_per_1pct=nd * lot * S_d1c * 0.01,
                     total=r.total_actual, short_hold=r.short_hold, stop=r.stop))
X = pd.DataFrame(rows)
pd.set_option('display.width', 220)
print(X.round(1).to_string(index=False))
for ycol in ['total', 'short_hold']:
    for xcol in ['ret_cycle_bp', 'ret_overnight_bp']:
        sl, ic, rv, p, se = stats.linregress(X[xcol], X[ycol])
        print(f'{ycol:10s} ~ {xcol:16s}: slope Rs {sl:,.0f} per bp, intercept Rs {ic:,.0f}, R2 {rv**2:.2f}, p {p:.3f}')
print('\nnet delta at D-1 close (lots, + = long market): mean', round(X.net_delta_lots_D1close.mean(), 1), 'median', round(X.net_delta_lots_D1close.median(), 1),
      ' share of cycles net SHORT delta:', round((X.net_delta_lots_D1close < 0).mean(), 2))
print('index move over the 30 cycles: mean cycle return', round(X.ret_cycle_bp.mean(), 1), 'bp; cycles down', int((X.ret_cycle_bp < 0).sum()), '/', len(X))
X.to_pickle(os.path.join(C, 'alpha_direction.pkl'))
