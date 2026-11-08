"""Option-derived causal features per (und, m) for the expiry traded that day: ATM IV (CE & PE, Black-Scholes, prev-minute closes),
IV changes, ATM straddle premium & changes, skew (IV of ~1.5%-OTM put minus ~1.5%-OTM call, nearest traded strikes), PCR of OI (NIFTY).
python3 analysis/indicators_options.py -> _cache/indicators_options.pkl"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from math import log, sqrt, erf
from scipy.optimize import brentq
from load import load_tagged
C = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_cache')
N = lambda x: 0.5 * (1 + erf(x / sqrt(2)))
def bs(cp, S, K, T, v):
    d1 = (log(S / K) + 0.5 * v * v * T) / (v * sqrt(T)); d2 = d1 - v * sqrt(T)
    return S * N(d1) - K * N(d2) if cp == 'CE' else K * N(-d2) - S * N(-d1)
def iv(cp, S, K, T, p):
    intr = max(0.0, S - K) if cp == 'CE' else max(0.0, K - S)
    if not (np.isfinite(p) and np.isfinite(S)) or p <= intr + 0.05 or T <= 0: return np.nan
    try: return brentq(lambda v: bs(cp, S, K, T, v) - p, 1e-3, 6.0)
    except Exception: return np.nan
d = load_tagged()
sess = d.groupby('date').agg(und=('und', 'first'), expiry=('expiry', 'first')).reset_index()
ix = pd.read_pickle(os.path.join(C, 'idx_candles.pkl'))
op = pd.read_pickle(os.path.join(C, 'opt_candles.pkl'))
rows = []
for r in sess.itertuples():
    step = 50 if r.und == 'NIFTY' else 100
    s = ix[(ix.und == r.und) & (ix.ts.dt.normalize() == r.date)].set_index('ts').close
    o = op[(op.und == r.und) & (op.expiry == r.expiry) & (op.ts.dt.normalize() == r.date)]
    if len(s) < 50 or o.empty: continue
    C_ = o.pivot_table(index='ts', columns=['cp', 'strike'], values='c', aggfunc='last').sort_index().ffill()
    OI = o.pivot_table(index='ts', columns='cp', values='oi', aggfunc='sum').sort_index()
    strikes = sorted(o.strike.unique())
    for m in pd.date_range(r.date + pd.Timedelta('09:16:00'), r.date + pd.Timedelta('15:29:00'), freq='min'):
        prev = m - pd.Timedelta(minutes=1)
        if prev not in s.index or prev not in C_.index: continue
        S = s[prev]; K0 = round(S / step) * step
        T = max(((r.expiry + pd.Timedelta('15:30:00')) - m).total_seconds(), 600) / (365 * 86400)
        row = C_.loc[prev]
        pc, pp = row.get(('CE', K0), np.nan), row.get(('PE', K0), np.nan)
        ivc, ivp = iv('CE', S, K0, T, pc), iv('PE', S, K0, T, pp)
        kc = min(strikes, key=lambda k: abs(k - S * 1.015)); kp = min(strikes, key=lambda k: abs(k - S * 0.985))
        sk = iv('PE', S, kp, T, row.get(('PE', kp), np.nan)) - iv('CE', S, kc, T, row.get(('CE', kc), np.nan))
        oi = OI.loc[prev] if prev in OI.index else None
        pcr = (oi.get('PE', np.nan) / oi.get('CE', np.nan)) if oi is not None and oi.get('CE', 0) > 0 else np.nan
        rows.append(dict(und=r.und, m=m, atm_iv=np.nanmean([ivc, ivp]) if np.isfinite(ivc) or np.isfinite(ivp) else np.nan, iv_ce_minus_pe=ivc - ivp,
                         straddle_bp=(pc + pp) / S * 1e4, skew_15=sk, pcr_oi=pcr))
X = pd.DataFrame(rows).sort_values(['und', 'm'])
g = X.groupby([X.und, X.m.dt.normalize()])
for L in [5, 15, 30]:
    X[f'atm_iv_chg{L}'] = g.atm_iv.diff(L); X[f'straddle_chg{L}'] = g.straddle_bp.diff(L) / X.straddle_bp.shift(L)
X['atm_iv_vs_open'] = X.atm_iv - g.atm_iv.transform('first'); X['pcr_chg15'] = g.pcr_oi.diff(15)
X.to_pickle(os.path.join(C, 'indicators_options.pkl'))
print(X.shape); print(X.describe().T[['count', 'mean', 'std']].round(4).to_string())
