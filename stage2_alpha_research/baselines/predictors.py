"""Baseline predictors (Milestone 2).  Every predictor at decision index kd uses bars 0 ... kd-1 of the same session only.

  trailing return  tr(kd,h)  = 1e4 * ln( C[kd-1] / C[kd-1-h] )             = PR #6 feature `ret_{h}m_bp` at decision minute m (reused, not recomputed)
  trailing RV      trv(kd,h) = 1e4 * sqrt( sum_{k=kd-h}^{kd-1} d[k]^2 ),   d[k] = ln(C[k]/C[k-1]) for k >= 1, d[0] = ln(C[0]/O[0]);  needs kd >= h
  trailing range   trg(kd,h) = 1e4 * ( max H - min L over bars kd-h ... kd-1 ) / C[kd-1];                                               needs kd >= h
Any missing bar in the trailing window gives NaN.  These are baseline forecasts ("the next h minutes look like the last h"), not alpha features."""
import numpy as np, pandas as pd
from numpy.lib.stride_tricks import sliding_window_view as swv
N = 375


def trailing_matrix(O, H, L, C, h):
    D = O.shape[0]; trv = np.full((D, N), np.nan); trg = np.full((D, N), np.nan)
    d2 = np.log(C / np.concatenate([O[:, :1], C[:, :-1]], axis=1)) ** 2            # d[0] from the session open, d[k] close-to-close
    s = swv(d2, h, axis=1).sum(axis=2)                                            # s[:, j] = sum d2[j ... j+h-1]
    hi = swv(H, h, axis=1).max(axis=2); lo = swv(L, h, axis=1).min(axis=2)
    trv[:, h:] = 1e4 * np.sqrt(s[:, :N - h])                                      # decision kd uses window starting at kd-h
    trg[:, h:] = 1e4 * (hi - lo)[:, :N - h] / C[:, h - 1:N - 1]                   # divided by C[kd-1]
    return dict(trv_bp=trv, trg_bp=trg)


def trailing_table(mats, horizons):
    rows = []
    for u, (dates, O, H, L, C) in mats.items():
        for h in horizons:
            T = trailing_matrix(O, H, L, C, h)
            df = pd.DataFrame({k: v.ravel() for k, v in T.items()}); df['und'] = u; df['date'] = np.repeat(pd.to_datetime(dates), N); df['kd'] = np.tile(np.arange(N), len(dates)); df['h'] = h
            rows.append(df)
    return pd.concat(rows, ignore_index=True)


def tod_bucket(kd, width):
    """clock bucket of the decision minute: bucket b covers decision indices [b*width, (b+1)*width)"""
    return (np.asarray(kd) // width).astype(int)
