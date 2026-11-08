"""B2b: univariate indicator-by-decision tests with time-of-day stratification, date-derangement null (B=30) and BH-FDR.
Adds crossover-event features (EMA9/20 cross, Supertrend flip, MACD-hist sign change, RSI 30/70 crossings, BB band touch, first ORB break)
within the last 3 / 10 minutes.   python3 analysis/b2_univariate.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from scipy.stats import norm
from sklearn.metrics import roc_auc_score
import b2_indicator_tests as B
C = B.C
I = B.IND.sort_values(['und', 'm']).copy()
day = I.m.dt.normalize()
ev = {}
for tf in ['1m', '5m', '15m']:
    g = I.groupby(['und', day])
    s = np.sign(I[f'{tf}_ema9_20']); ev[f'{tf}_ema_cross'] = (s != g[f'{tf}_ema9_20'].shift(1).pipe(np.sign)) & s.ne(0)
    ev[f'{tf}_st_flip'] = I[f'{tf}_supertrend'] != g[f'{tf}_supertrend'].shift(1)
    mh = np.sign(I[f'{tf}_macd_hist']); ev[f'{tf}_macd_flip'] = mh != g[f'{tf}_macd_hist'].shift(1).pipe(np.sign)
    r = I[f'{tf}_rsi14']; rp = g[f'{tf}_rsi14'].shift(1)
    ev[f'{tf}_rsi_x70'] = ((r >= 70) & (rp < 70)) | ((r < 70) & (rp >= 70)); ev[f'{tf}_rsi_x30'] = ((r <= 30) & (rp > 30)) | ((r > 30) & (rp <= 30))
    ev[f'{tf}_bb_touch'] = (I[f'{tf}_bb_pctb'] > 1) | (I[f'{tf}_bb_pctb'] < 0)
ev['orb_first_break'] = (I.orb_state != 0) & (I.groupby(['und', day]).orb_state.shift(1).fillna(0) == 0)
E = pd.DataFrame(ev).astype(float)
for w in [3, 10]:
    for c in list(ev):
        I[f'ev_{c}_{w}m'] = E[c].groupby([I.und, day]).transform(lambda x: x.rolling(w, min_periods=1).max())
EV_COLS = [c for c in I.columns if c.startswith('ev_')]
B.IND = I; B.IND_COLS = B.IND_COLS + EV_COLS

def strat_auc(x, y, strata):
    num = den = 0.0
    for s in np.unique(strata):
        m = strata == s; ys = y[m]; xs = x[m]; ok = np.isfinite(xs)
        if ok.sum() < 30 or ys[ok].min() == ys[ok].max(): continue
        a = roc_auc_score(ys[ok], xs[ok]); w = ok.sum(); num += a * w; den += w
    return num / den if den else np.nan

if __name__ == '__main__':
    rng = np.random.default_rng(11); maps = [B.derangement_map(rng) for _ in range(30)]
    res = []
    for name, (df, base, price, side) in B.datasets().items():
        df = df.dropna(subset=['label']).reset_index(drop=True)
        if len(df) > 40000: df = df.sample(40000, random_state=1).reset_index(drop=True)
        y = df.label.astype(int).values
        strata = (df.get('d0', pd.Series(0, index=df.index)).astype(int).astype(str) + '_' + (df.m.dt.hour * 2 + (df.m.dt.minute >= 30)).astype(str)).values
        real = B.attach(df, side); nulls = [B.attach(df, side, mp) for mp in maps]
        for c in B.IND_COLS:
            a = strat_auc(real[c].values.astype(float), y, strata)
            if not np.isfinite(a): continue
            na = np.array([strat_auc(n[c].values.astype(float), y, strata) for n in nulls]); na = na[np.isfinite(na)]
            z = (a - na.mean()) / (na.std(ddof=1) + 1e-9)
            res.append(dict(decision=name, indicator=c, auc=round(a, 3), null_mean=round(na.mean(), 3), null_sd=round(na.std(ddof=1), 4), z=round(z, 2), p=2 * norm.sf(abs(z))))
        print(name, 'done', flush=True)
    R = pd.DataFrame(res)
    R = R.sort_values('p'); m = len(R); R['bh_q'] = (R.p * m / np.arange(1, m + 1))[::-1].cummin()[::-1].clip(upper=1)
    R.to_csv(os.path.join(C, 'b2_univariate.csv'), index=False)
    pd.set_option('display.width', 250); pd.set_option('display.max_rows', 100)
    print('tests', m, '| significant at BH q<0.05:', int((R.bh_q < 0.05).sum()))
    print(R[R.bh_q < 0.05].head(60).to_string(index=False))
