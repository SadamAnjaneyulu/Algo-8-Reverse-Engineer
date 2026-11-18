"""Unit, leakage and boundary tests for the causal OHLCV feature library.   python -m pytest ohlcv_research/tests -q
Real-data tests run only when ALGO8_MARKET_DIR (or data/breeze/normalized) is present; the synthetic tests always run."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); PKG = os.path.dirname(HERE); sys.path.insert(0, PKG)
import numpy as np, pandas as pd, pytest
import features as F
import common as CM

STEP = {'AAA': 50, 'BBB': 100}
def sess(date, n=375, start=20000.0, seed=0, und='AAA'):
    rng = np.random.default_rng(seed); c = start * np.exp(np.cumsum(rng.normal(0, 3e-4, n))); o = np.r_[start, c[:-1]]
    h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 1e-4, n))); l = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 1e-4, n)))
    ts = pd.Timestamp(date) + F.OPEN + pd.to_timedelta(np.arange(n), unit='min')
    return pd.DataFrame(dict(und=und, ts=ts, open=o, high=h, low=l, close=c))
def index_data():
    return pd.concat([sess('2026-07-01', seed=1), sess('2026-07-02', seed=2, start=20100), sess('2026-07-03', seed=3, start=19950),
                      sess('2026-07-01', seed=4, und='BBB', start=80000), sess('2026-07-02', seed=5, und='BBB', start=80200), sess('2026-07-03', seed=6, und='BBB', start=79900)], ignore_index=True)
def option_data(I, und='AAA', expiry='2026-07-02', dates=('2026-07-01', '2026-07-02'), seed=0):
    rng = np.random.default_rng(seed); rows = []
    for d in dates:
        s = I[(I.und == und) & (I.ts.dt.normalize() == pd.Timestamp(d))]
        for k in np.arange(19800, 20401, STEP[und]):
            for cp in ('CE', 'PE'):
                intr = np.maximum(s.close.values - k, 0) if cp == 'CE' else np.maximum(k - s.close.values, 0)
                c = np.round((intr + 40 * np.exp(-np.abs(s.close.values - k) / 150) + rng.uniform(0, 1, len(s))) * 20) / 20 + 0.05
                o = np.r_[c[0], c[:-1]]; x = pd.DataFrame(dict(und=und, expiry=pd.Timestamp(expiry), strike=k, cp=cp, ts=s.ts.values, open=o, high=np.maximum(o, c) + 0.05, low=np.maximum(np.minimum(o, c) - 0.05, 0.05),
                                                               close=c, volume=rng.integers(0, 50, len(s)) * 65.0))
                rows.append(x.sample(frac=0.97, random_state=int(rng.integers(1e6))).sort_values('ts'))        # 3 % of minutes have no bar
    return pd.concat(rows, ignore_index=True)

I0 = index_data(); O0 = option_data(I0)
def same(a, b, cols):
    a = a.reset_index(drop=True); b = b.reset_index(drop=True); assert len(a) == len(b) and len(a) > 0
    for c in cols: assert np.allclose(a[c].astype(float).values, b[c].astype(float).values, equal_nan=True, rtol=1e-9, atol=1e-9), c

# ------------------------------------------------------------------ formulas ---------------------------------------------------------------------------------
def test_primitives_against_independent_loops():
    rng = np.random.default_rng(7); c = pd.Series(100 + np.cumsum(rng.normal(0, 1, 200))); h = c + rng.uniform(0, 1, 200); l = c - rng.uniform(0, 1, 200); n = 14
    e = [c[0]]; a = 2 / (20 + 1)
    for x in c[1:]: e.append(a * x + (1 - a) * e[-1])
    assert np.allclose(F.ema(c, 20), e)
    up = dn = 0.0; out = [np.nan]
    for i in range(1, len(c)):
        d = c[i] - c[i - 1]; u, w = max(d, 0), max(-d, 0)
        up = u if i == 1 else up + (u - up) / n; dn = w if i == 1 else dn + (w - dn) / n          # Wilder smoothing seeded with the first change
        out.append(100 - 100 / (1 + up / dn) if dn > 0 else np.nan)
    assert np.allclose(F.rsi(c, n)[20:], out[20:], equal_nan=True)
    tr = [h[0] - l[0]] + [max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])) for i in range(1, len(c))]; at = [tr[0]]
    for x in tr[1:]: at.append(at[-1] + (x - at[-1]) / n)
    assert np.allclose(F.atr(h, l, c, n), at)
    pb, bw = F.bollinger(c, 20, 2.0); w = c[30:50].values
    assert np.isclose(pb[49], (w[-1] - (w.mean() - 2 * w.std())) / (4 * w.std())) and np.isclose(bw[49], 4 * w.std() / w.mean())
    assert np.allclose(F.macd_hist(pd.Series(np.full(100, 5.0))), 0)
    up_ = pd.Series(np.arange(1.0, 101.0)); assert F.adx(up_ + 1, up_ - 1, up_, 14).iloc[-1] > 99        # a pure up-trend has DX = 100
    assert F.rsi(up_, 14).isna().all()                                                                      # no down move: RS undefined -> NaN, not 100 by fiat

def test_row_at_decision_minute_uses_only_bars_completed_before_it():
    X = F.index_features(I0); a = I0[(I0.und == 'AAA')].set_index('ts').close
    m = pd.Timestamp('2026-07-01 10:00:00'); r = X[(X.und == 'AAA') & (X.m == m)].iloc[0]
    assert np.isclose(r.ret_1m_bp, 1e4 * np.log(a[m - pd.Timedelta(minutes=1)] / a[m - pd.Timedelta(minutes=2)]))        # bars 09:59 and 09:58, not 10:00
    assert np.isclose(r.ret_15m_bp, 1e4 * np.log(a[m - pd.Timedelta(minutes=1)] / a[m - pd.Timedelta(minutes=16)]))
    s = I0[(I0.und == 'AAA') & (I0.ts.dt.normalize() == '2026-07-01') & (I0.ts < m)]
    assert np.isclose(r.sess_pos, (s.close.iloc[-1] - s.low.min()) / (s.high.max() - s.low.min())) and np.isclose(r.ret_open_bp, 1e4 * np.log(s.close.iloc[-1] / s.open.iloc[0]))
    orb = s[s.ts < pd.Timestamp('2026-07-01 09:30')]; assert np.isclose(r.or_pos, (s.close.iloc[-1] - orb.low.min()) / (orb.high.max() - orb.low.min()))
    assert X.m.dt.strftime('%H:%M').min() == '09:16' and X.m.dt.strftime('%H:%M').max() == '15:30'        # the row keyed 09:15 would need the forming candle: it does not exist

# ------------------------------------------------------------------ leakage ----------------------------------------------------------------------------------
MS = [pd.Timestamp(x) for x in ('2026-07-01 09:31', '2026-07-01 12:07', '2026-07-02 09:16', '2026-07-02 09:20', '2026-07-02 13:45', '2026-07-03 15:30')]
@pytest.mark.parametrize('m', MS)
def test_truncation_invariance_index(m):
    full = F.index_features(I0); tr = F.index_features(I0[I0.ts < m])
    same(full[full.m == m], tr[tr.m == m], F.INDEX_FEATURES)

@pytest.mark.parametrize('m', MS[:5])
def test_truncation_invariance_options_and_straddle(m):
    full = F.option_features(O0, I0); tr = F.option_features(O0[O0.ts < m], I0[I0.ts < m]); k = ['und', 'expiry', 'strike', 'cp']
    a = full[full.m == m].sort_values(k); b = tr[tr.m == m].sort_values(k); b = b.merge(a[k], on=k); a = a.merge(b[k], on=k)
    same(a.sort_values(k), b.sort_values(k), F.OPTION_FEATURES)
    sf = F.straddle_features(O0, I0, STEP); st = F.straddle_features(O0[O0.ts < m], I0[I0.ts < m], STEP)
    same(sf[sf.m == m], st[st.m == m], F.STRADDLE_FEATURES)

def test_future_and_current_candle_perturbation_changes_nothing():
    m = pd.Timestamp('2026-07-02 11:00'); base = F.index_features(I0); ob = F.option_features(O0, I0); sb = F.straddle_features(O0, I0, STEP)
    for mask_i, mask_o in ((I0.ts >= m, O0.ts >= m), (I0.ts == m, O0.ts == m)):                              # everything from m on / only the candle forming at m
        I2 = I0.copy(); I2.loc[mask_i, ['open', 'high', 'low', 'close']] *= 1.07
        O2 = O0.copy(); O2.loc[mask_o, ['open', 'high', 'low', 'close']] *= 3.0; O2.loc[mask_o, 'volume'] *= 9
        same(base[base.m <= m], F.index_features(I2).query('m <= @m'), F.INDEX_FEATURES)
        same(ob[ob.m <= m], F.option_features(O2, I2).query('m <= @m'), F.OPTION_FEATURES)
        same(sb[sb.m <= m], F.straddle_features(O2, I2, STEP).query('m <= @m'), F.STRADDLE_FEATURES)
    I3 = I0.copy(); I3.loc[I3.ts == m - pd.Timedelta(minutes=1), 'close'] *= 1.01                              # sanity: the last COMPLETED bar does matter
    assert not np.isclose(F.index_features(I3).query('m == @m and und == "AAA"').ret_1m_bp.iloc[0], base.query('m == @m and und == "AAA"').ret_1m_bp.iloc[0])

def test_five_minute_bars_are_released_only_at_their_end():
    X = F.index_features(I0); a = X[(X.und == 'AAA')].set_index('m')
    assert np.isnan(a.at[pd.Timestamp('2026-07-01 09:19'), 'atr14_5m_bp']) and np.isfinite(a.at[pd.Timestamp('2026-07-01 09:20'), 'atr14_5m_bp'])
    assert a.at[pd.Timestamp('2026-07-01 09:24'), 'atr14_5m_bp'] == a.at[pd.Timestamp('2026-07-01 09:20'), 'atr14_5m_bp']        # unchanged until 09:25
    I2 = I0.copy(); I2.loc[(I2.ts >= '2026-07-01 10:00') & (I2.ts < '2026-07-01 10:05'), ['high', 'close']] *= 1.02               # a 5-minute bar still forming at 10:04
    b = F.index_features(I2)[lambda x: x.und == 'AAA'].set_index('m'); t = pd.Timestamp('2026-07-01 10:04')
    assert a.at[t, 'rsi14_5m'] == b.at[t, 'rsi14_5m'] and a.at[t + pd.Timedelta(minutes=1), 'rsi14_5m'] != b.at[t + pd.Timedelta(minutes=1), 'rsi14_5m']

# ------------------------------------------------------------------ boundaries -------------------------------------------------------------------------------
def test_session_boundaries_and_previous_day_levels():
    X = F.index_features(I0); a = X[X.und == 'AAA'].set_index('m'); d1 = I0[(I0.und == 'AAA') & (I0.ts.dt.normalize() == '2026-07-01')]; d2 = I0[(I0.und == 'AAA') & (I0.ts.dt.normalize() == '2026-07-02')]
    t = pd.Timestamp('2026-07-02 09:17')
    assert np.isnan(a.at[t, 'ret_5m_bp']) and np.isnan(a.at[t, 'rv30_bp']) and np.isnan(a.at[t, 'z60_1m']) and np.isnan(a.at[t, 'or_pos'])     # nothing carried from the previous session
    assert np.isclose(a.at[t, 'gap_bp'], 1e4 * (d2.open.iloc[0] - d1.close.iloc[-1]) / d1.close.iloc[-1])
    assert np.isclose(a.at[t, 'dist_prev_high_bp'], 1e4 * (d2.close.iloc[1] - d1.high.max()) / d2.close.iloc[1])
    assert a[a.index.normalize() == '2026-07-01'].gap_bp.isna().all() and a[a.index.normalize() == '2026-07-01'].dist_prev_low_bp.isna().all()   # first session has no previous day
    I2 = I0.copy(); mid = (I2.und == 'AAA') & (I2.ts > '2026-07-01 11:00') & (I2.ts < '2026-07-01 12:00'); I2.loc[mid, ['open', 'close']] = I2.loc[mid, ['open', 'close']].values[::-1]
    b = F.index_features(I2)[lambda x: x.und == 'AAA'].set_index('m'); sess_cols = ['ret_1m_bp', 'ret_60m_bp', 'z60_1m', 'rv30_bp', 'hlvol30_bp', 'range_exp', 'ret_open_bp', 'or_pos', 'or_break', 'sess_range_bp', 'sess_pos', 'gap_bp', 'dist_prev_high_bp', 'dist_prev_low_bp']
    day2 = a.index.normalize() == '2026-07-02'; same(a[day2], b[day2], sess_cols)                             # reshuffling day-1's intraday path (same H / L / close) leaves day 2 unchanged
    other = X[X.und == 'BBB']; I3 = I0.copy(); I3.loc[I3.und == 'AAA', ['open', 'high', 'low', 'close']] *= 2; same(other, F.index_features(I3)[lambda x: x.und == 'BBB'], F.INDEX_FEATURES)   # instruments do not mix

def test_option_contract_and_expiry_isolation_and_post_close_bars():
    O2 = option_data(I0, expiry='2026-07-09', dates=('2026-07-01', '2026-07-02'), seed=9); both = pd.concat([O0, O2], ignore_index=True)
    a = F.option_features(O0, I0); b = F.option_features(both, I0); b = b[b.expiry == pd.Timestamp('2026-07-02')]
    same(a.sort_values(['strike', 'cp', 'm']), b.sort_values(['strike', 'cp', 'm']), F.OPTION_FEATURES)        # another expiry of the same strikes changes nothing
    O3 = O0.copy(); hit = (O3.strike == 20000) & (O3.cp == 'CE'); O3.loc[hit, ['high', 'low', 'close']] *= 5; c = F.option_features(O3, I0)
    k = (a.strike != 20000) | (a.cp != 'CE'); same(a[k], c[(c.strike != 20000) | (c.cp != 'CE')], F.OPTION_FEATURES)                                 # contracts do not mix
    pc = O0[O0.ts.dt.strftime('%H:%M') == '15:29'].copy(); pc['ts'] += pd.Timedelta(minutes=5); pc[['high', 'low', 'close']] *= 50; pc['volume'] = 1e9
    same(a, F.option_features(pd.concat([O0, pc], ignore_index=True), I0), F.OPTION_FEATURES)                    # 15:30-15:39 bars are ignored
    d2 = a[a.m == pd.Timestamp('2026-07-02 09:17')]; assert d2.prem_ret_5m_pct.isna().all() and d2.rel_vol5.isna().all() and d2.cmf20.isna().all()   # no carry across sessions

def test_straddle_needs_both_legs_of_one_strike():
    S = F.straddle_features(O0, I0, STEP); m = pd.Timestamp('2026-07-01 11:00'); r = S[S.m == m].iloc[0]; s = I0[(I0.und == 'AAA') & (I0.ts == m - pd.Timedelta(minutes=1))].close.iloc[0]
    k = round(s / 50) * 50; assert r.atm_strike == k
    px = lambda cp, t, kk: O0[(O0.strike == kk) & (O0.cp == cp) & (O0.ts <= t) & (O0.ts > t - pd.Timedelta(minutes=6)) & (O0.ts.dt.normalize() == '2026-07-01')].sort_values('ts').close.iloc[-1]
    t1 = m - pd.Timedelta(minutes=1); t6 = m - pd.Timedelta(minutes=6)
    assert np.isclose(r.straddle_bp, 1e4 * (px('CE', t1, k) + px('PE', t1, k)) / s)
    assert np.isclose(r.straddle_ret_5m_pct, 100 * np.log((px('CE', t1, k) + px('PE', t1, k)) / (px('CE', t6, k) + px('PE', t6, k))))             # same strike at both times
    noPE = O0[~((O0.cp == 'PE') & (O0.strike == k))]; r2 = F.straddle_features(noPE, I0, STEP); assert np.isnan(r2[r2.m == m].straddle_bp.iloc[0]) and np.isnan(r2[r2.m == m].atm_strike.iloc[0])

def test_straddle_return_keeps_the_strike_fixed_when_atm_moves():
    S = F.straddle_features(O0, I0, STEP).set_index('m'); a = I0[(I0.und == 'AAA') & (I0.ts.dt.normalize() == '2026-07-01')].set_index('ts').close; atm = (np.round(a / 50) * 50)
    moved = [t for t in atm.index[20:300] if atm[t] != atm[t - pd.Timedelta(minutes=5)]]; assert moved, 'synthetic path never changes ATM strike'
    hits = 0
    for t in moved[:25]:                                                             # bar t is the last completed bar of decision minute t + 1
        m = t + pd.Timedelta(minutes=1); k = atm[t]; r = S.loc[m]
        leg = lambda cp, tt: O0[(O0.strike == k) & (O0.cp == cp) & (O0.ts <= tt) & (O0.ts > tt - pd.Timedelta(minutes=6)) & (O0.ts.dt.normalize() == '2026-07-01')].sort_values('ts').close
        now = [leg(cp, t) for cp in ('CE', 'PE')]; old = [leg(cp, t - pd.Timedelta(minutes=5)) for cp in ('CE', 'PE')]
        if any(len(x) == 0 for x in now + old): continue
        assert np.isclose(r.straddle_ret_5m_pct, 100 * np.log((now[0].iloc[-1] + now[1].iloc[-1]) / (old[0].iloc[-1] + old[1].iloc[-1]))); hits += 1
    assert hits >= 5

def test_post_close_index_bars_never_enter_any_timeframe():
    pc = I0[I0.ts.dt.strftime('%H:%M') >= '15:20'].copy(); pc['ts'] += pd.Timedelta(minutes=10); pc = pc[pc.ts.dt.strftime('%H:%M') >= '15:30']; pc[['open', 'high', 'low', 'close']] *= 1.5
    same(F.index_features(I0), F.index_features(pd.concat([I0, pc], ignore_index=True)), F.INDEX_FEATURES)        # incl. the continuous 5-minute indicators of the next day

def test_volume_features_exist_only_for_options_and_bar_age_reports_gaps():
    assert not any('vol' in c.replace('hlvol', '') and c not in ('rv30_bp',) for c in F.INDEX_FEATURES if 'vwap' in c or 'obv' in c or 'cmf' in c or c.startswith('rel_vol') or c.startswith('vol_'))
    assert not [c for c in F.INDEX_FEATURES if any(x in c for x in ('vwap', 'obv', 'cmf', 'rel_vol', 'vol_z'))]
    O2 = O0[~((O0.strike == 20000) & (O0.cp == 'CE') & (O0.ts >= '2026-07-01 10:00') & (O0.ts < '2026-07-01 10:10'))]
    a = F.option_features(O2, I0); x = a[(a.strike == 20000) & (a.cp == 'CE')].set_index('m')
    assert x.at[pd.Timestamp('2026-07-01 10:10'), 'bar_age_min'] == 10 and np.isnan(x.at[pd.Timestamp('2026-07-01 10:10'), 'prem_ret_1m_pct'])      # stale > 5 min -> no return, age reported
    assert x.at[pd.Timestamp('2026-07-01 10:03'), 'bar_age_min'] == 3 and np.isfinite(x.at[pd.Timestamp('2026-07-01 10:03'), 'prem_spot_bp'])        # carried at most 5 minutes

def test_calendar_and_decision_minute():
    sess_ = pd.to_datetime(['2026-07-01', '2026-07-02', '2026-07-03', '2026-07-06'])
    c = F.calendar_features(pd.Series(pd.to_datetime(['2026-07-02 09:15', '2026-07-03 15:00', '2026-07-03 15:00'])), pd.Series(pd.to_datetime(['2026-07-02', '2026-07-03', '2026-07-06'])), sess_)
    assert c.tod_min.tolist() == [0, 345, 345] and c.dte_days.tolist() == [0, 0, 3] and c.tte_session_min.tolist() == [375, 30, 30 + 375]            # the weekend adds no session minutes
    o = pd.DataFrame(dict(tp=['num', 'h_'], t_dec_lo=pd.to_datetime(['2026-07-01 10:16:00', '2026-07-01 10:16:07']), t_dec=pd.to_datetime(['2026-07-01 10:16:41', '2026-07-01 10:16:07'])))
    assert F.decision_minute(o).tolist() == [pd.Timestamp('2026-07-01 10:16'), pd.Timestamp('2026-07-01 10:16')]

def test_loaders_never_read_open_interest_or_index_volume(tmp_path, monkeypatch):
    (tmp_path / 'indices' / 'AAA').mkdir(parents=True); (tmp_path / 'options' / 'AAA' / '2026-07-02' / '20000CE').mkdir(parents=True)
    (tmp_path / 'indices' / 'AAA' / '2026-07-01.x.csv').write_text('timestamp_ist,underlying,open,high,low,close,provider_volume\n2026-07-01T09:15:00+05:30,AAA,1,2,1,2,777\n')
    (tmp_path / 'options' / 'AAA' / '2026-07-02' / '20000CE' / '2026-07-01.x.csv').write_text('timestamp_ist,underlying,expiry_date,strike,option_type,open,high,low,close,volume,open_interest\n2026-07-01T09:15:00+05:30,AAA,2026-07-02,20000,CE,1,2,1,2,65,999\n')
    monkeypatch.setattr(CM, 'MARKET', str(tmp_path)); monkeypatch.setattr(CM, 'CACHE', str(tmp_path))
    i = CM.load_index(); o = CM.load_options()
    assert list(i.columns) == ['und', 'ts', 'open', 'high', 'low', 'close'] and list(o.columns) == ['und', 'expiry', 'strike', 'cp', 'ts', 'open', 'high', 'low', 'close', 'volume']
    assert i.ts.iloc[0] == pd.Timestamp('2026-07-01 09:15:00')

# ------------------------------------------------------------------ real data (skipped without the market files) ------------------------------------------------
REAL = os.path.isdir(os.path.join(CM.MARKET, 'indices'))
@pytest.mark.skipif(not REAL, reason='market data not present')
def test_real_data_truncation_at_the_split_boundary_and_random_minutes():
    I = CM.load_index(); full = F.index_features(I); cut = CM.DEV_END + pd.Timedelta(days=1)
    dev = F.index_features(I[I.ts < cut]); same(full[full.m <= cut], dev[dev.m <= cut], F.INDEX_FEATURES)        # DEV features do not depend on any later bar
    rng = np.random.default_rng(0); ms = full.m.sample(8, random_state=1).tolist()
    for m in ms:
        tr = F.index_features(I[I.ts < m]); same(full[full.m == m], tr[tr.m == m], F.INDEX_FEATURES)

@pytest.mark.skipif(not REAL, reason='market data not present')
def test_real_data_option_truncation():
    I = CM.load_index(); O = CM.load_options(); e = O[O.und == 'NIFTY'].expiry.unique()[3]; O = O[(O.und == 'NIFTY') & (O.expiry == e)]; I = I[(I.und == 'NIFTY')]
    full = F.option_features(O, I); sf = F.straddle_features(O, I, CM.STEP); k = ['und', 'expiry', 'strike', 'cp']
    for m in full.m.sample(4, random_state=2).tolist():
        tr = F.option_features(O[O.ts < m], I[I.ts < m]); a = full[full.m == m].merge(tr[tr.m == m][k], on=k).sort_values(k); b = tr[tr.m == m].merge(a[k], on=k).sort_values(k)
        same(a, b, F.OPTION_FEATURES); st = F.straddle_features(O[O.ts < m], I[I.ts < m], CM.STEP); same(sf[sf.m == m], st[st.m == m], F.STRADDLE_FEATURES)
