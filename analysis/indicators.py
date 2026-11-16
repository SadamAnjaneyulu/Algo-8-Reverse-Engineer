"""Causal indicator library on Breeze index 1-min bars (bar_label = start).  Value at minute m uses only bars that COMPLETED before m.
Timeframes: 1m, 5m, 15m (resampled bars are released at bar end). Plus prior-day levels, opening range, option-derived ATM IV/skew.
python3 analysis/indicators.py  -> _cache/indicators.pkl indexed by (und, m)"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from math import log, sqrt, erf
from scipy.optimize import brentq
C = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_cache')

def ema(x, n): return x.ewm(span=n, adjust=False).mean()
def rsi(c, n=14):
    d = c.diff(); up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean(); dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))
def atr(h, l, c, n=14):
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()
def adx(h, l, c, n=14):
    up = h.diff(); dn = -l.diff()
    pdm = np.where((up > dn) & (up > 0), up, 0.0); ndm = np.where((dn > up) & (dn > 0), dn, 0.0)
    a = atr(h, l, c, n)
    pdi = 100 * pd.Series(pdm, index=h.index).ewm(alpha=1 / n, adjust=False).mean() / a
    ndi = 100 * pd.Series(ndm, index=h.index).ewm(alpha=1 / n, adjust=False).mean() / a
    dx = 100 * (pdi - ndi).abs() / (pdi + ndi).replace(0, np.nan)
    return dx.ewm(alpha=1 / n, adjust=False).mean(), pdi, ndi
def supertrend(h, l, c, n=10, mult=3.0):
    a = atr(h, l, c, n); hl2 = (h + l) / 2; ub = hl2 + mult * a; lb = hl2 - mult * a
    fu, fl, dirn = ub.copy(), lb.copy(), pd.Series(1, index=c.index)
    for i in range(1, len(c)):
        fu.iat[i] = ub.iat[i] if (ub.iat[i] < fu.iat[i - 1]) or (c.iat[i - 1] > fu.iat[i - 1]) else fu.iat[i - 1]
        fl.iat[i] = lb.iat[i] if (lb.iat[i] > fl.iat[i - 1]) or (c.iat[i - 1] < fl.iat[i - 1]) else fl.iat[i - 1]
        dirn.iat[i] = 1 if c.iat[i] > fu.iat[i - 1] else (-1 if c.iat[i] < fl.iat[i - 1] else dirn.iat[i - 1])
    return dirn
def block(df, tf):
    """compute indicator block on OHLC bars of timeframe tf (bars indexed by bar START); returns frame indexed by AVAILABILITY time."""
    o, h, l, c = df.open, df.high, df.low, df.close
    bp = lambda x: x / c * 1e4
    out = pd.DataFrame(index=df.index)
    for n in [5, 9, 20, 50]: out[f'ema{n}_dist'] = bp(c - ema(c, n))
    out['ema9_20'] = bp(ema(c, 9) - ema(c, 20)); out['ema20_slope'] = bp(ema(c, 20).diff(3))
    out['sma20_dist'] = bp(c - c.rolling(20).mean())
    m12, m26 = ema(c, 12), ema(c, 26); macd = m12 - m26; out['macd_hist'] = bp(macd - ema(macd, 9)); out['macd'] = bp(macd)
    for n in [7, 14]: out[f'rsi{n}'] = rsi(c, n)
    ll, hh = l.rolling(14).min(), h.rolling(14).max(); out['stoch_k'] = 100 * (c - ll) / (hh - ll).replace(0, np.nan)
    tp = (h + l + c) / 3; out['cci20'] = (tp - tp.rolling(20).mean()) / (0.015 * tp.rolling(20).apply(lambda x: np.mean(np.abs(x - x.mean())), raw=True))
    out['roc10'] = bp(c - c.shift(10))
    out['atr14_bp'] = bp(atr(h, l, c, 14))
    mid = c.rolling(20).mean(); sd = c.rolling(20).std(); out['bb_pctb'] = (c - (mid - 2 * sd)) / (4 * sd).replace(0, np.nan); out['bb_width'] = bp(4 * sd)
    a, pdi, ndi = adx(h, l, c, 14); out['adx14'] = a; out['di_diff'] = pdi - ndi
    out['supertrend'] = supertrend(h, l, c, 10, 3.0)
    out['rv20_bp'] = (np.log(c).diff().rolling(20).std()) * 1e4
    out.columns = [f'{tf}_{x}' for x in out.columns]
    step = {'1m': 1, '5m': 5, '15m': 15}[tf]
    out.index = out.index + pd.Timedelta(minutes=step)          # available once the bar has completed
    return out

if __name__ == '__main__':
    ix = pd.read_pickle(os.path.join(C, 'idx_candles.pkl'))
    allf = []
    for und, g in ix.groupby('und'):
        g = g.set_index('ts').sort_index()[['open', 'high', 'low', 'close']]
        g['date'] = g.index.normalize()
        parts = [block(g, '1m')]
        for tf, rule in [('5m', '5min'), ('15m', '15min')]:
            r = g.groupby('date', group_keys=False).apply(lambda x: x[['open', 'high', 'low', 'close']].resample(rule, origin='start_day', offset='9h15min').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}).dropna())
            parts.append(block(r, tf))
        minutes = pd.DatetimeIndex(sorted(set(g.index) | set(g.index + pd.Timedelta(minutes=1))))
        F = pd.concat([p.reindex(minutes, method='ffill') for p in parts], axis=1)
        # day levels (prior-day H/L/C, pivots, open, opening range 09:15-09:30, day H/L so far) -- causal
        dly = g.groupby('date').agg(dh=('high', 'max'), dl=('low', 'min'), dc=('close', 'last'), do=('open', 'first'))
        prev = dly.shift(1)
        F['date'] = F.index.normalize()
        P = prev.reindex(F.date).set_axis(F.index)
        last_close = g.close.reindex(minutes - pd.Timedelta(minutes=1)).set_axis(minutes).ffill()   # close of bar m-1
        piv = (P.dh + P.dl + P.dc) / 3
        bp = lambda x: x / last_close * 1e4
        F['gap_bp'] = bp(dly.do.reindex(F.date).values - P.dc)
        F['dist_prev_close'] = bp(last_close - P.dc); F['dist_prev_high'] = bp(last_close - P.dh); F['dist_prev_low'] = bp(last_close - P.dl)
        F['dist_pivot'] = bp(last_close - piv); F['dist_R1'] = bp(last_close - (2 * piv - P.dl)); F['dist_S1'] = bp(last_close - (2 * piv - P.dh))
        F['dist_day_open'] = bp(last_close - dly.do.reindex(F.date).values)
        hi_sofar = g.high.groupby(g.date).cummax().reindex(minutes - pd.Timedelta(minutes=1)).set_axis(minutes).ffill()
        lo_sofar = g.low.groupby(g.date).cummin().reindex(minutes - pd.Timedelta(minutes=1)).set_axis(minutes).ffill()
        F['dist_day_high'] = bp(last_close - hi_sofar); F['dist_day_low'] = bp(last_close - lo_sofar); F['day_range_bp'] = bp(hi_sofar - lo_sofar)
        orr = g[(g.index.time >= pd.Timestamp('09:15').time()) & (g.index.time < pd.Timestamp('09:30').time())].groupby('date').agg(orh=('high', 'max'), orl=('low', 'min'))
        OR = orr.reindex(F.date).set_axis(F.index); after = F.index.time >= pd.Timestamp('09:30').time()
        F['orb_state'] = np.where(after, np.sign(last_close - OR.orh).clip(lower=0) - np.sign(OR.orl - last_close).clip(lower=0), 0)
        F['und'] = und
        allf.append(F.drop(columns=['date']))
    IND = pd.concat(allf).reset_index().rename(columns={'index': 'm'})
    IND = IND[IND.m.dt.time >= pd.Timestamp('09:16').time()]
    IND.to_pickle(os.path.join(C, 'indicators_index.pkl'))
    print('index indicators', IND.shape, 'columns', len([c for c in IND.columns if c not in ('und', 'm')]))
    print(IND.describe().T[['mean', 'std', 'min', 'max']].round(2).head(60).to_string())
