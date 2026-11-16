"""PHASE 1 - compact causal OHLCV feature library (about 45 features in six groups; see OHLCV_FEATURE_CATALOG.md for every formula).

CAUSALITY CONTRACT (enforced by tests/test_features.py):
  * Every row is keyed by a DECISION MINUTE m (minute start, IST).  The row at m is computed ONLY from bars that COMPLETED before m, i.e. bars whose start is <= m - 1 min.
    The candle that starts at m (still forming when a minute-stamped order is decided) is never used: not its open, high, low, close or volume.
  * Higher-timeframe (5-minute) bars are released only at their END; a 5-minute bar is used at m only if its end <= m.
  * Session-anchored quantities (returns, rolling windows, opening range, session range, VWAP, volume windows) never cross a session boundary.
  * Option features never mix contracts: one (underlying, expiry, strike, right, session) at a time.  The straddle uses the CE and PE of ONE strike of ONE expiry.
  * No statistic is fitted on the whole sample (no global scaler, no full-sample quantile): every normalisation is a trailing window, so nothing crosses a chronological split.
  * Index volume is invalid (all zero) -> no index volume / VWAP feature exists.  Open interest is never loaded.
Sessions are re-indexed to the full 375-minute grid (09:15 ... 15:29); a missing bar is NOT interpolated: closes are carried forward at most 5 minutes for return
calculations, volume is 0, and `bar_age` reports how old the last real bar is."""
import numpy as np, pandas as pd

OPEN = pd.Timedelta('09:15:00'); N = 375; FF = 5
RET_H = (1, 5, 15, 30, 60)
INDEX_FEATURES = ['ret_1m_bp', 'ret_5m_bp', 'ret_15m_bp', 'ret_30m_bp', 'ret_60m_bp', 'ema_slope_5m', 'rsi14_5m', 'macd_hist_5m_bp', 'adx14_5m',          # momentum
                  'z60_1m', 'bb_pctb_5m', 'ema_dist_5m',                                                                                                   # mean reversion
                  'atr14_5m_bp', 'rv30_bp', 'hlvol30_bp', 'range_exp', 'bb_width_5m_bp',                                                                   # volatility
                  'ret_open_bp', 'or_pos', 'or_break', 'dist_prev_high_bp', 'dist_prev_low_bp', 'gap_bp', 'sess_range_bp', 'sess_pos']                      # market structure
OPTION_FEATURES = ['prem_ret_1m_pct', 'prem_ret_5m_pct', 'prem_ret_15m_pct', 'prem_spot_bp', 'prem_range5_pct', 'opt_vwap_dist_pct',                         # option OHLC
                   'rel_vol5', 'vol_z60', 'obv_imb15', 'cmf20', 'bar_age_min']                                                                              # option volume
STRADDLE_FEATURES = ['atm_strike', 'straddle_bp', 'straddle_ret_5m_pct', 'straddle_ret_15m_pct', 'cepe_log_ratio', 'atm_rel_vol5']
CALENDAR_FEATURES = ['tod_min', 'dte_days', 'tte_session_min', 'dow']

# ---------------------------------------------------------------- primitives (as of the close of each bar) ----------------------------------------------
def ema(x, n): return x.ewm(span=n, adjust=False).mean()
def wilder(x, n): return x.ewm(alpha=1.0 / n, adjust=False).mean()
def rsi(c, n=14):
    d = c.diff(); up = wilder(d.clip(lower=0), n); dn = wilder((-d).clip(lower=0), n)
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))
def true_range(h, l, c): return pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
def atr(h, l, c, n=14): return wilder(true_range(h, l, c), n)
def adx(h, l, c, n=14):
    up = h.diff(); dn = -l.diff()
    pdm = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=h.index); ndm = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=h.index)
    a = atr(h, l, c, n); pdi = 100 * wilder(pdm, n) / a; ndi = 100 * wilder(ndm, n) / a
    return wilder(100 * (pdi - ndi).abs() / (pdi + ndi).replace(0, np.nan), n)
def macd_hist(c, fast=12, slow=26, sig=9):
    m = ema(c, fast) - ema(c, slow); return m - ema(m, sig)
def bollinger(c, n=20, k=2.0):
    mid = c.rolling(n, min_periods=n).mean(); sd = c.rolling(n, min_periods=n).std(ddof=0)
    return (c - (mid - k * sd)) / (2 * k * sd).replace(0, np.nan), 2 * k * sd / mid          # %B, width

def _wide(df, keys, col):
    """pivot to (375 session minutes) x (keys + date); missing bars stay NaN."""
    return df.pivot(index='k', columns=keys + ['date'], values=col).reindex(range(N))

def _prep(df):
    d = df.copy(); d['date'] = d.ts.dt.normalize(); d['k'] = ((d.ts - d.date - OPEN).dt.total_seconds() // 60).astype(int)
    return d[(d.k >= 0) & (d.k < N)]                                              # drops post-close bars (15:30-15:39 exist in the option files)

def _long(feats, names):
    """wide feature frames (index k = bar minute) -> long rows keyed by DECISION minute m = bar start + 1 minute."""
    out = None
    for nme, W in feats.items():
        s = W.stack(list(range(W.columns.nlevels)), future_stack=True).rename(nme)
        out = s.to_frame() if out is None else out.join(s)
    out = out.reset_index(); out['m'] = out['date'] + OPEN + pd.to_timedelta(out['k'] + 1, unit='min')
    return out.drop(columns=['k'])

# ---------------------------------------------------------------- index features ---------------------------------------------------------------------------
def five_minute_bars(I):
    """5-minute bars aligned to 09:15, labelled by START, with `avail` = bar END (the first decision minute that may use them)."""
    d = _prep(I); d['b'] = d.k // 5
    g = d.sort_values('ts').groupby(['und', 'date', 'b'])
    B = g.agg(open=('open', 'first'), high=('high', 'max'), low=('low', 'min'), close=('close', 'last')).reset_index()
    B['ts'] = B.date + OPEN + pd.to_timedelta(B.b * 5, unit='min'); B['avail'] = B.ts + pd.Timedelta(minutes=5)
    return B.sort_values(['und', 'ts']).reset_index(drop=True)

def index_features(I):
    """I: und, ts (bar start), open, high, low, close.  Returns one row per (und, decision minute m) for m = 09:16 ... 15:30 of every session."""
    d = _prep(I); W = {c: _wide(d, ['und'], c) for c in ('open', 'high', 'low', 'close')}
    C = W['close']; Cf = C.ffill(limit=FF); H, L = W['high'], W['low']; f = {}
    for h in RET_H: f[f'ret_{h}m_bp'] = 1e4 * np.log(Cf / Cf.shift(h))
    r1 = np.log(Cf / Cf.shift(1))
    f['z60_1m'] = (Cf - Cf.rolling(60, min_periods=30).mean()) / Cf.rolling(60, min_periods=30).std(ddof=0).replace(0, np.nan)
    f['rv30_bp'] = 1e4 * np.sqrt((r1 ** 2).rolling(30, min_periods=15).sum())
    f['hlvol30_bp'] = 1e4 * np.sqrt((np.log(H / L) ** 2).rolling(30, min_periods=15).sum() / (4 * np.log(2)))
    R5 = H.rolling(5, min_periods=5).max() - L.rolling(5, min_periods=5).min()
    f['range_exp'] = R5 / (sum(R5.shift(5 * j) for j in range(1, 7)) / 6).replace(0, np.nan)
    O0 = W['open'].bfill().iloc[0]; seen = C.notna().cummax()                      # session open = first printed open; rows before the first bar stay NaN
    f['ret_open_bp'] = (1e4 * np.log(Cf / O0)).where(seen)
    hi, lo = H.cummax(), L.cummin(); rng = (hi - lo).replace(0, np.nan)
    f['sess_range_bp'] = 1e4 * (hi - lo) / O0; f['sess_pos'] = (Cf - lo) / rng
    orh, orl = H.iloc[:15].max(), L.iloc[:15].min(); late = pd.Series(np.arange(N) >= 14, index=C.index)         # opening range 09:15-09:29, usable from m = 09:30
    f['or_pos'] = ((Cf - orl) / (orh - orl).replace(0, np.nan)).where(late, axis=0)
    f['or_break'] = (np.sign(Cf - orh).clip(lower=0) - np.sign(orl - Cf).clip(lower=0)).where(late, axis=0).where(Cf.notna())
    # previous session of the same underlying (constants for the whole session, known before the open)
    ph = H.max().groupby(level='und').shift(1); pl = L.min().groupby(level='und').shift(1); pc = C.ffill().iloc[-1].groupby(level='und').shift(1)
    f['dist_prev_high_bp'] = 1e4 * (Cf - ph) / Cf; f['dist_prev_low_bp'] = 1e4 * (Cf - pl) / Cf
    f['gap_bp'] = (1e4 * (O0 - pc) / pc + 0 * Cf).where(seen)
    out = _long(f, list(f))
    # 5-minute indicators: continuous per underlying, released at the bar end
    B = five_minute_bars(I); parts = []
    for u, b in B.groupby('und'):
        b = b.sort_values('ts').copy(); a = atr(b.high, b.low, b.close, 14); e20 = ema(b.close, 20); pb, bw = bollinger(b.close, 20, 2.0)
        b['atr14_5m_bp'] = 1e4 * a / b.close; b['rsi14_5m'] = rsi(b.close, 14); b['macd_hist_5m_bp'] = 1e4 * macd_hist(b.close) / b.close; b['adx14_5m'] = adx(b.high, b.low, b.close, 14)
        b['ema_slope_5m'] = (e20 - e20.shift(3)) / a.replace(0, np.nan); b['ema_dist_5m'] = (b.close - e20) / a.replace(0, np.nan); b['bb_pctb_5m'] = pb; b['bb_width_5m_bp'] = 1e4 * bw
        parts.append(b)
    B = pd.concat(parts); c5 = ['atr14_5m_bp', 'rsi14_5m', 'macd_hist_5m_bp', 'adx14_5m', 'ema_slope_5m', 'ema_dist_5m', 'bb_pctb_5m', 'bb_width_5m_bp']
    out = pd.merge_asof(out.sort_values('m'), B[['und', 'avail'] + c5].sort_values('avail'), left_on='m', right_on='avail', by='und', direction='backward').drop(columns='avail')
    return out[['und', 'date', 'm'] + INDEX_FEATURES].sort_values(['und', 'm']).reset_index(drop=True)

# ---------------------------------------------------------------- option contract features ---------------------------------------------------------------
def option_features(O, I):
    """O: und, expiry, strike, cp, ts, open, high, low, close, volume.  I: index bars (for premium / spot).  One row per (contract, decision minute)."""
    d = _prep(O); keys = ['und', 'expiry', 'strike', 'cp']; W = {c: _wide(d, keys, c) for c in ('high', 'low', 'close', 'volume')}
    C, H, L = W['close'], W['high'], W['low']; Cf = C.ffill(limit=FF); V = W['volume'].fillna(0.0); has = C.notna(); f = {}
    for h in (1, 5, 15): f[f'prem_ret_{h}m_pct'] = 100 * np.log(Cf / Cf.shift(h))
    f['prem_range5_pct'] = 100 * (H.rolling(5, min_periods=1).max() - L.rolling(5, min_periods=1).min()) / Cf
    tp = ((H + L + C) / 3).fillna(0.0); cv = V.cumsum(); vwap = (tp * V).cumsum() / cv.replace(0, np.nan)
    f['opt_vwap_dist_pct'] = 100 * (Cf / vwap - 1)
    f['rel_vol5'] = V.rolling(5, min_periods=5).sum() / (V.rolling(30, min_periods=30).sum().shift(5) / 6).replace(0, np.nan)
    f['vol_z60'] = (V - V.rolling(60, min_periods=30).mean()) / V.rolling(60, min_periods=30).std(ddof=0).replace(0, np.nan)
    sv = np.sign(Cf.diff()).fillna(0.0) * V; f['obv_imb15'] = sv.rolling(15, min_periods=15).sum() / V.rolling(15, min_periods=15).sum().replace(0, np.nan)
    mfm = (((C - L) - (H - C)) / (H - L).replace(0, np.nan)).fillna(0.0); f['cmf20'] = (mfm * V).rolling(20, min_periods=20).sum() / V.rolling(20, min_periods=20).sum().replace(0, np.nan)
    idx = pd.DataFrame(np.arange(N)[:, None] * np.ones((1, C.shape[1])), index=C.index, columns=C.columns); last = idx.where(has).ffill()
    f['bar_age_min'] = idx - last                                                    # 0 = the bar just completed is real; NaN = no bar yet today
    # premium relative to spot of the same bar minute
    di = _prep(I); S = _wide(di, ['und'], 'close').ffill(limit=FF)
    Sx = pd.DataFrame({col: S[(col[0], col[-1])].values if (col[0], col[-1]) in S.columns else np.nan for col in C.columns}, index=C.index); Sx.columns = C.columns
    f['prem_spot_bp'] = 1e4 * Cf / Sx
    out = _long(f, list(f))
    return out[keys + ['date', 'm'] + OPTION_FEATURES].sort_values(keys + ['m']).reset_index(drop=True)

# ---------------------------------------------------------------- ATM straddle (CE + PE of one strike) ---------------------------------------------------
def straddle_features(O, I, step):
    """per (und, expiry, decision minute): ATM strike = strike nearest to the last completed index close; CE + PE of that ONE strike, both needed (carried <= 5 min)."""
    d = _prep(O); di = _prep(I); S = _wide(di, ['und'], 'close').ffill(limit=FF); rows = []
    for (u, e, dt), g in d.groupby(['und', 'expiry', 'date']):
        if (u, dt) not in S.columns: continue
        s = S[(u, dt)].values; ks = np.sort(g.strike.unique()); kpos = {k: i for i, k in enumerate(ks)}
        P = {}
        for cp in ('CE', 'PE'):
            x = g[g.cp == cp]
            P[cp] = (x.pivot(index='k', columns='strike', values='close').reindex(index=range(N), columns=ks).ffill(limit=FF).values,
                     x.pivot(index='k', columns='strike', values='volume').reindex(index=range(N), columns=ks).fillna(0.0).values)
        atm = np.round(s / step[u]) * step[u]; col = np.array([kpos.get(a, -1) for a in atm]); t = np.arange(N); ok = col >= 0
        def pick(M, lag=0):
            tt = t - lag; v = np.full(N, np.nan); m_ = ok & (tt >= 0); v[m_] = M[tt[m_], col[m_]]; return v
        ce, pe = pick(P['CE'][0]), pick(P['PE'][0]); st = ce + pe
        vol = pd.DataFrame(P['CE'][1] + P['PE'][1]); v5 = vol.rolling(5, min_periods=5).sum().values; v30 = (vol.rolling(30, min_periods=30).sum().shift(5) / 6).values
        rel = np.full(N, np.nan); rel[ok] = v5[t[ok], col[ok]] / np.where(v30[t[ok], col[ok]] > 0, v30[t[ok], col[ok]], np.nan)
        with np.errstate(invalid='ignore', divide='ignore'):
            r5 = 100 * np.log(st / (pick(P['CE'][0], 5) + pick(P['PE'][0], 5))); r15 = 100 * np.log(st / (pick(P['CE'][0], 15) + pick(P['PE'][0], 15)))   # SAME strike at both times
            rows.append(pd.DataFrame(dict(und=u, expiry=e, date=dt, m=dt + OPEN + pd.to_timedelta(t + 1, unit='min'), atm_strike=np.where(np.isfinite(st), atm, np.nan), straddle_bp=1e4 * st / s,
                                          straddle_ret_5m_pct=r5, straddle_ret_15m_pct=r15, cepe_log_ratio=np.log(ce / pe), atm_rel_vol5=np.where(np.isfinite(st), rel, np.nan))))
    return pd.concat(rows, ignore_index=True)

# ---------------------------------------------------------------- calendar / clock (not market data) ------------------------------------------------------
def calendar_features(m, expiry, sessions):
    """m: decision minutes (Series), expiry: Series of expiry dates, sessions: sorted array of all session dates of the underlying.
    tte_session_min = session minutes from m to the expiry day's 15:30, counting trading sessions only."""
    m = pd.to_datetime(pd.Series(m).reset_index(drop=True)); e = pd.to_datetime(pd.Series(expiry).reset_index(drop=True)); d = m.dt.normalize()
    sess = np.array(sorted(pd.to_datetime(pd.Series(list(sessions))).unique()), dtype='datetime64[ns]')
    tod = ((m - d - OPEN).dt.total_seconds() / 60).astype(float)
    later = np.searchsorted(sess, e.values.astype('datetime64[ns]'), 'right') - np.searchsorted(sess, d.values.astype('datetime64[ns]'), 'right')      # sessions after today, up to expiry
    return pd.DataFrame(dict(tod_min=tod, dte_days=(e - d).dt.days.astype(float), tte_session_min=(N - tod).clip(lower=0) + N * later, dow=d.dt.dayofweek.astype(float)))

def decision_minute(orders):
    """decision minute per order: body orders are stamped to the minute -> that minute's START (features then use bars completed before it);
    tagged orders carry an exact time -> the start of the minute that contains it (conservative: nothing from that minute is used)."""
    t = pd.to_datetime(orders.t_dec_lo).where(orders.tp == 'num', pd.to_datetime(orders.t_dec)); return t.dt.floor('min')
