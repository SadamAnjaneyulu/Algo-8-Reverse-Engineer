# OHLCV feature catalog (Phase 1)

Library: [`features.py`](features.py). Tests: [`tests/test_features.py`](tests/test_features.py) (25 tests, all passing). Coverage and
redundancy: [`results/feature_coverage.csv`](results/feature_coverage.csv), [`results/feature_redundancy.csv`](results/feature_redundancy.csv).
**42 market features in six groups, plus 4 clock / calendar fields.** No target or outcome variable was used to build or select any of them.

## 1. Causality contract

| Rule | Implementation |
|---|---|
| A row is keyed by a **decision minute *m*** (minute start, IST) and uses only bars that **completed before *m*** (bar start ≤ *m* − 1 min). | Features are computed as of each bar's close and re-keyed to *m* = bar start + 1 min. Rows exist for 09:16 … 15:30. There is no 09:15 row: no candle of the day has completed. |
| The candle forming at *m* is never used (not its open, high, low, close or volume). | Same re-keying. For a minute-stamped body order, *m* is the order minute; for a tagged order with an exact time, *m* is the start of the minute containing it. |
| Higher-timeframe bars are released only at their end. | 5-minute bars aligned to 09:15 carry `avail` = bar end and join backward on `avail` ≤ *m*. |
| Session-anchored features never cross a session. | Each session is re-indexed to its own 375-minute grid; rolling windows, returns, opening range, session range, VWAP and volume windows are computed inside it. |
| Instruments, contracts and expiries never mix. | Index features per underlying; option features per (underlying, expiry, strike, right, session); the straddle uses the CE and PE of one strike of one expiry. |
| Nothing is fitted on the whole sample. | No global scaler or quantile; every normalisation is a trailing window. Features on DEV are identical whether or not later data exist (tested). |
| Missing bars are not interpolated. | Closes are carried at most 5 minutes for return calculations; volume of a missing bar is 0; `bar_age_min` reports staleness. Post-close bars (15:30–15:39) are dropped. |

Continuous indicators (the 5-minute EMA / RSI / MACD / ADX / ATR / Bollinger set) run across sessions per underlying, as on a normal chart.
In the first minutes of a session they still reflect the previous session's bars.

## 2. Features and formulas

Notation: *c*, *h*, *l*, *o*, *v* are close, high, low, open, volume of completed bars; *t* is the last completed 1-minute bar
(*t* = *m* − 1 min); `EMA_n` uses α = 2 / (n + 1); `W_n` is Wilder smoothing, α = 1 / n. "5m" means 5-minute bars.

### Group 1 — Momentum (index)

| Feature | Formula |
|---|---|
| `ret_1m_bp`, `ret_5m_bp`, `ret_15m_bp`, `ret_30m_bp`, `ret_60m_bp` | 10⁴ · ln(*c*ₜ / *c*ₜ₋ₕ), same session only |
| `ema_slope_5m` | (EMA₂₀ − EMA₂₀ three 5m bars earlier) / ATR₁₄ |
| `rsi14_5m` | 100 − 100 / (1 + W₁₄(up) / W₁₄(down)); undefined (NaN) when there is no down move |
| `macd_hist_5m_bp` | 10⁴ · [(EMA₁₂ − EMA₂₆) − EMA₉(EMA₁₂ − EMA₂₆)] / *c* |
| `adx14_5m` | W₁₄ of 100 · |+DI − −DI| / (+DI + −DI), with ±DI = 100 · W₁₄(±DM) / ATR₁₄ |

### Group 2 — Mean reversion (index)

| Feature | Formula |
|---|---|
| `z60_1m` | (*c*ₜ − mean₆₀) / sd₆₀ over the last 60 one-minute closes of the session (min 30) |
| `bb_pctb_5m` | (*c* − (SMA₂₀ − 2 sd₂₀)) / (4 sd₂₀) on 5m bars |
| `ema_dist_5m` | (*c* − EMA₂₀) / ATR₁₄ on 5m bars |
| VWAP distance (index) | **Not available**: index volume is zero. The option version is `opt_vwap_dist_pct`. |

### Group 3 — Volatility (index)

| Feature | Formula |
|---|---|
| `atr14_5m_bp` | 10⁴ · W₁₄(true range) / *c* on 5m bars |
| `rv30_bp` | 10⁴ · √(Σ of squared 1-minute log returns over 30 min) |
| `hlvol30_bp` | 10⁴ · √(Σ ln(*h* / *l*)² over 30 min / (4 ln 2)) (Parkinson) |
| `range_exp` | last 5-minute range ÷ mean of the six preceding non-overlapping 5-minute ranges |
| `bb_width_5m_bp` | 10⁴ · 4 sd₂₀ / SMA₂₀ on 5m bars |

### Group 4 — Volume (options only; index volume is invalid)

| Feature | Formula |
|---|---|
| `rel_vol5` | volume of the last 5 minutes ÷ average 5-minute volume of the 30 minutes before them |
| `vol_z60` | (*v*ₜ − mean₆₀) / sd₆₀ of 1-minute volume (min 30) |
| `obv_imb15` | Σ sign(Δ*c*) · *v* over 15 min ÷ Σ *v* over 15 min (bounded OBV change, −1 … 1) |
| `cmf20` | Σ [((*c* − *l*) − (*h* − *c*)) / (*h* − *l*)] · *v* over 20 min ÷ Σ *v* (Chaikin money flow; flat bars contribute 0) |
| `bar_age_min` | minutes since the contract's last real bar (0 = fresh) |

### Group 5 — Market structure (index) and clock

| Feature | Formula |
|---|---|
| `ret_open_bp` | 10⁴ · ln(*c*ₜ / session open) |
| `or_pos`, `or_break` | position of *c*ₜ in the 09:15–09:29 range; +1 above its high, −1 below its low, 0 inside. Defined from *m* = 09:30. |
| `dist_prev_high_bp`, `dist_prev_low_bp` | 10⁴ · (*c*ₜ − previous session's high or low) / *c*ₜ |
| `gap_bp` | 10⁴ · (session open − previous session's last close) / previous close; available from 09:16 |
| `sess_range_bp`, `sess_pos` | running session range ÷ open; position of *c*ₜ in the running range |
| `tod_min`, `dow`, `dte_days`, `tte_session_min` (clock, not market) | minutes since 09:15; weekday; calendar days to expiry; **session** minutes to the expiry day's 15:30 |

### Group 6 — Option OHLCV

| Feature | Formula |
|---|---|
| `prem_ret_1m_pct`, `prem_ret_5m_pct`, `prem_ret_15m_pct` | 100 · ln(premium now / premium *h* minutes earlier), same contract and session |
| `prem_spot_bp` | 10⁴ · premium / index close of the same bar |
| `prem_range5_pct` | 100 · (5-minute high − low) / premium |
| `opt_vwap_dist_pct` | 100 · (premium / session VWAP − 1), VWAP = Σ ((*h* + *l* + *c*) / 3 · *v*) / Σ *v* |
| `atm_strike` | strike nearest the last completed index close |
| `straddle_bp` | 10⁴ · (CE + PE of `atm_strike`) / index close. Both legs required (each carried ≤ 5 min), else NaN. |
| `straddle_ret_5m_pct`, `straddle_ret_15m_pct` | 100 · ln(straddle now / straddle *h* minutes earlier) **for the same strike** |
| `cepe_log_ratio` | ln(CE / PE) at `atm_strike` |
| `atm_rel_vol5` | `rel_vol5` computed on CE + PE volume of `atm_strike` |

`straddle_bp` is an observed premium, **not** implied volatility.

## 3. Availability

| Table | Rows | Typical availability | At Algo 8 decision minutes |
|---|---:|---|---|
| Index (underlying, *m*) | 63,750 | 84 % (60-minute return) to 100 % | 79 % to 96 % |
| Option contract (contract, *m*) | 1,216,125 | 91 % to 100 % | 83 % to 96 % |
| ATM straddle (underlying, expiry, *m*) | 25,125 | 85 % to 93 % | 82 % to 95 % |

The ceiling of ≈ 96 % at Algo 8 decisions has one cause: 3.3 % of orders (1,316) are decided in the 09:15 minute, before any candle of the
day completes, and a few contracts have no earlier bar that day. Long windows are undefined early in the session by construction.

Heavy tails: `prem_range5_pct` and the premium returns explode for sub-rupee premiums near expiry (99th percentile 150 %). The library does
not clip; any winsorising in later phases must use DEV-only limits.

## 4. Redundancy (identifiability limit)

Spearman correlation between features, computed without any outcome:

| Cluster | Members | |ρ| |
|---|---|---|
| 5-minute trend / oscillator | `rsi14_5m`, `ema_dist_5m`, `ema_slope_5m`, `bb_pctb_5m` | 0.86–0.98 |
| Session location | `or_pos`, `or_break`, `ret_open_bp`, `sess_pos` | 0.85–0.94 |
| Realised volatility | `rv30_bp`, `hlvol30_bp` | 0.94 |
| Medium-horizon return / z-score | `ret_30m_bp`, `z60_1m` | 0.86 |

8 pairs exceed 0.9 and 16 exceed 0.8. These features were requested by name and are kept, but **they cannot be told apart statistically**:
a result for "RSI" is equally a result for "distance from the EMA". Phase 2 therefore tests **families**, with one representative per
cluster for any single-feature statement.

## 5. Leakage and integrity tests

| Test | What it proves |
|---|---|
| Primitives vs independent loop implementations | EMA, Wilder RSI, ATR, Bollinger %B and width, MACD on a constant, ADX on a pure trend. |
| Row at *m* equals hand calculation from bars before *m* | The 10:00 row uses the 09:59 and 09:58 bars, not 10:00. No 09:15 row exists. |
| **Truncation invariance** (synthetic and real data) | Features at *m* computed from all data equal features computed from data cut off before *m*, for index, option and straddle tables. |
| Split boundary (real data) | Every DEV row is identical with and without VAL / TEST data. |
| Future and current-candle perturbation | Scaling every bar from *m* onward, or only the candle forming at *m*, changes no feature at or before *m*; changing the last completed bar does. |
| 5-minute release timing | A 5-minute bar still forming at 10:04 does not affect the 10:04 row and does affect 10:05. |
| Session boundaries | Day-2 session features are unchanged when day-1's intraday path is reshuffled; gap and previous-day levels match hand values; the first session has none. |
| Contract, expiry and instrument isolation | Changing another contract, another expiry of the same strike, or the other index changes nothing. |
| Post-close bars | 15:30–15:39 bars never enter any timeframe. |
| Straddle | Both legs of one strike required; the return keeps the strike fixed when ATM moves. |
| Staleness | A 10-minute gap gives `bar_age_min` = 10 and no return; a 3-minute gap is carried. |
| Loaders | `open_interest` and index `provider_volume` are never read. |

**Mutation check.** Twelve deliberate leaks were injected into a copy of the library (row keyed by the bar start, 5-minute bar released at
its start, centred window, full-session high / low, opening range before 09:30, cross-strike straddle return, post-close bars kept,
forward-shifted volume window, global z-score, unlimited carry, same-day "previous" level, decision minute rounded up). **All 12 are caught**
([`results/mutation_test_report.txt`](results/mutation_test_report.txt)). The first run caught 10; two tests were added for the two that
escaped.
