"""Stage 2 prediction targets (LOCKED at Milestone 2; RESEARCH_PLAN.md section 3).

Indexing.  Session bars are numbered k = 0 ... 374 (bar k starts at 09:15 + k min).  A decision at minute m has index kd = minutes(m - 09:15).
  features at kd  : bars 0 ... kd-1 only (completed before m)
  entry reference : O[kd], the open of the bar that starts at m (first price after the decision)          (decision D2)
  label bars      : kd ... kd+h-1, valid only if kd + h <= 375 (never crosses the session end)

  r(kd,h)   = 1e4 * ln( C[kd+h-1] / O[kd] )                                               directional return, bp
  RV(kd,h)  = 1e4 * sqrt( ln(C[kd]/O[kd])^2 + sum_{k=kd+1}^{kd+h-1} ln(C[k]/C[k-1])^2 )   realised volatility, bp
              (the first increment starts at the entry reference O[kd], not at C[kd-1]: no price move before the entry enters the target)
  RG(kd,h)  = 1e4 * ( max_{k in label} H[k] - min_{k in label} L[k] ) / O[kd]             range, bp
  REX(kd,h) = ( max H - min L over the label bars ) / ( max H - min L over bars kd-h ... kd-1 )   range expansion; needs kd >= h
  reversal  = 1 if sign(r(kd,h)) != sign(trailing return), defined in baselines (needs the trailing return); dead band not locked

Missing-bar rule: if any bar of the label window is missing, every target of that decision is NaN (nothing is interpolated).
"""
import numpy as np, pandas as pd
from numpy.lib.stride_tricks import sliding_window_view as swv

N = 375
OPEN = pd.Timedelta('09:15:00')


def session_matrices(I):
    """I: und, ts, open, high, low, close -> {und: (dates, O, H, L, C)} with arrays (n_dates, 375); missing bars are NaN"""
    d = I.copy(); d['date'] = d.ts.dt.normalize(); d['k'] = ((d.ts - d.date - OPEN).dt.total_seconds() // 60).astype(int)
    d = d[(d.k >= 0) & (d.k < N)]; out = {}
    for u, g in d.groupby('und'):
        W = {c: g.pivot(index='date', columns='k', values=c).reindex(columns=range(N)).sort_index() for c in ('open', 'high', 'low', 'close')}
        out[u] = (list(W['open'].index), W['open'].values.astype(float), W['high'].values.astype(float), W['low'].values.astype(float), W['close'].values.astype(float))
    return out


def targets_matrix(O, H, L, C, h):
    """arrays (n_dates, 375) -> dict of (n_dates, 375) target arrays for horizon h; entries with kd + h > 375 are NaN"""
    D = O.shape[0]; nan = np.full((D, N), np.nan); nv = N - h + 1                       # valid kd: 0 ... 375-h
    r = nan.copy(); rv = nan.copy(); rg = nan.copy(); rex = nan.copy()
    Cend = C[:, h - 1:]                                                                # C[kd+h-1] for kd = 0 ... 375-h
    r[:, :nv] = 1e4 * np.log(Cend / O[:, :nv])
    d2 = np.full((D, N), np.nan); d2[:, 1:] = np.log(C[:, 1:] / C[:, :-1]) ** 2        # close-to-close squared increments of bar k (k >= 1)
    first = np.log(C / O) ** 2                                                         # increment of the decision bar measured from its own open
    tail = swv(d2, h - 1, axis=1).sum(axis=2) if h > 1 else np.zeros((D, N + 1))       # tail[:, j] = sum d2[j ... j+h-2]
    rv[:, :nv] = 1e4 * np.sqrt(first[:, :nv] + (tail[:, 1:nv + 1] if h > 1 else 0.0))  # bars kd+1 ... kd+h-1
    hi = swv(H, h, axis=1).max(axis=2); lo = swv(L, h, axis=1).min(axis=2)             # window starting at kd
    rg[:, :nv] = 1e4 * (hi - lo) / O[:, :nv]
    rex[:, h:nv] = (hi - lo)[:, h:nv] / np.where((hi - lo)[:, :nv - h] > 0, (hi - lo)[:, :nv - h], np.nan)   # label range / range of bars kd-h ... kd-1
    miss = np.isnan(swv(C, h, axis=1)).any(axis=2) | np.isnan(swv(O, h, axis=1)).any(axis=2) | np.isnan(hi) | np.isnan(lo)
    for a in (r, rv, rg, rex): a[:, :nv][miss] = np.nan
    return dict(r_bp=r, rv_bp=rv, rg_bp=rg, rex=rex, entry=np.where(np.isnan(r), np.nan, O))


def index_targets(I, horizons):
    """long table: und, date, kd, m, h, entry, r_bp, rv_bp, rg_bp, rex (rows for every decision index with a complete label window)"""
    rows = []
    for u, (dates, O, H, L, C) in session_matrices(I).items():
        for h in horizons:
            T = targets_matrix(O, H, L, C, h); kd = np.arange(N)
            df = pd.DataFrame({k: v.ravel() for k, v in T.items()})
            df['und'] = u; df['date'] = np.repeat(pd.to_datetime(dates), N); df['kd'] = np.tile(kd, len(dates)); df['h'] = h
            rows.append(df[df.r_bp.notna() | (df.kd + h <= N)])
    out = pd.concat(rows, ignore_index=True); out = out[out.kd + out.h <= N]
    out['m'] = out.date + OPEN + pd.to_timedelta(out.kd, unit='min')
    return out[['und', 'date', 'kd', 'm', 'h', 'entry', 'r_bp', 'rv_bp', 'rg_bp', 'rex']]


def straddle_targets(Opt, Z, horizons, kds_by_h):
    """ATM straddle premium change for the strike fixed at the decision minute (options are kept in their own table).
    P_in = open(CE) + open(PE) of bar kd;  P_out = close(CE) + close(PE) of bar kd+h-1;  target = 100 * (P_out / P_in - 1).
    Z: PR #6 straddle feature rows (und, expiry, date, m, atm_strike); only the ATM strike chosen from bars completed before m is used.
    Both legs must have a bar at kd and at kd+h-1, otherwise the target is NaN."""
    o = Opt.copy(); o['date'] = o.ts.dt.normalize(); o['k'] = ((o.ts - o.date - OPEN).dt.total_seconds() // 60).astype(int); o = o[(o.k >= 0) & (o.k < N)]
    book = {}
    for (u, d, e, K, cp), g in o.groupby(['und', 'date', 'expiry', 'strike', 'cp']):
        a = np.full((2, N), np.nan); a[0, g.k.values] = g.open.values; a[1, g.k.values] = g.close.values; book[(u, d, e, float(K), cp)] = a
    z = Z.dropna(subset=['atm_strike']).copy(); z['kd'] = ((z.m - z.date - OPEN).dt.total_seconds() // 60).astype(int)
    rows = []
    for h in horizons:
        zz = z[z.kd.isin(kds_by_h[h])]
        for r in zz.itertuples():
            ce = book.get((r.und, r.date, r.expiry, float(r.atm_strike), 'CE')); pe = book.get((r.und, r.date, r.expiry, float(r.atm_strike), 'PE'))
            if ce is None or pe is None or r.kd + h > N: pin = pout = np.nan
            else: pin = ce[0, r.kd] + pe[0, r.kd]; pout = ce[1, r.kd + h - 1] + pe[1, r.kd + h - 1]
            rows.append((r.und, r.date, r.expiry, r.kd, h, r.atm_strike, pin, pout, 100 * (pout / pin - 1) if pin and pin > 0 else np.nan))
    out = pd.DataFrame(rows, columns=['und', 'date', 'expiry', 'kd', 'h', 'atm_strike', 'p_in', 'p_out', 'straddle_chg_pct'])
    out['day'] = np.where(out.date == out.expiry, 'D0', 'D-1')
    return out
