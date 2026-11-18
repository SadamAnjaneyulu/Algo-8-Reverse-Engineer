# C. Data quality report
Pinned commit `eb4097308d47ccc75078ab73ba76d33bb1c7030b`. Every figure is recomputed from the committed files (`reports/tables/`).

| Check | NIFTY | SENSEX |
|---|---|---|
| Option rows scanned | 18,978,233 | 12,928,723 |
| Duplicate (datetime, strike, right) rows | 0 | 0 |
| Missing / NaN OHLC | 0 | 0 |
| Invalid OHLC (high < low/open/close, low > open/close, price <= 0, off the 0.05 tick) | 0 | 0 |
| Volume outside [0, 2^31) (int32 wrap-around) | 20 (10 negative, 10 positive) | 3 (negative, with bad prices) |
| Missing or negative open interest | 0 | 0 (but all values are 0, see below) |
| Open interest equal to 0 | 9.7% of rows; 3,482 contract-sessions | 100% of rows |
| Timestamp unparseable / weekend / other date | 0 / 11,190 (Muhurat Sunday) / 0 | 0 / 0 / 0 |
| Out-of-order or repeated timestamps within a contract | 0 | 0 |
| Expiry field mismatch with file name; right not CE/PE; strike off the step grid; rows outside the plan | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 |
| Cross-contract identical price series (>= 20 bars, non-constant) | 0 | 0 |
| Contract-sessions with data | 52,134 | 36,404 |
| Contract-sessions with a full 375/385-minute grid | 38,773 (74.4%) | 24,703 (67.9%) |
| Contract-sessions with < 50% of the grid | 1,095 | 1,717 |
| Contract-sessions with a gap > 30 minutes | 622 | 431 |
| Flat zero-volume (carried-price) bars | 6,312,819 (33.3%) | 2,579,706 (19.9%) |
| Isolated price spikes (>5x vs both neighbours) | 0 | 6 |
| Volume > 0 bars priced below intrinsic value by > 0.5% of spot | 1,378 of 12.6M (1,278 after 2026-08-03) | 903 of 10.3M (733 after 2026-08-03) |
| Bars after the last regular minute | 23,793 (6,757 with volume) | 29,395 (5,918 with volume) |
| Option minutes with no spot bar in the session | 17,374 | 33,235 |
| Spot sessions with missing regular minutes | 10 (342 min) | 13 (310 min) |

## Put-call parity (CE/PE labels and spot alignment)
At 11:00 and 14:00, strikes within 2 steps of spot with volume > 0: median |C - P - (S - K)| is 0.038% of spot (NIFTY) and 0.035% (SENSEX); no session exceeds 0.3% (max 0.27%). Two NIFTY sessions have no testable strikes (the Muhurat session and the incomplete 2024-06-26). This supports correct CE/PE labelling and option/spot minute alignment; it is a plausibility test (carry and early-exercise-free European parity), not a price verification.

## Missing candles are not all "missing"
The vendor repeats the previous price (volume 0) for no-trade minutes of contracts that have traded, so a missing minute is rarer than a no-trade minute. A contract-minute with no row at all can be a true gap or a minute before the first trade; the data cannot distinguish them. Treat volume 0 as no trade and an absent row as unknown.

## Raw versus normalized
| | NIFTY | SENSEX |
|---|---|---|
| Option sessions compared | 316 | 248 |
| Raw rows / normalized rows | 18,978,233 / 18,978,233 | 12,928,723 / 12,928,723 |
| Rows only in raw / only in normalized / value mismatches | 0 / 0 / 0 | 0 / 0 / 0 |
| Underlying files (spot + futures): raw-only / norm-only / mismatching values | 0 / 0 / 0 | 0 / 0 / 0 |

Normalization does not change any OHLC, volume or OI value. Caveat: this proves the normalizer is faithful, not that the raw files are the original API responses (defect D10).

## Index versus an independent vendor (Yahoo daily)
| index | period | sessions | day_open_median_abs_pts | day_open_p95_abs_pts | day_open_sessions_gt_0.3pct | day_high_median_abs_pts | day_high_p95_abs_pts | day_high_sessions_gt_0.3pct | day_low_median_abs_pts | day_low_p95_abs_pts | day_low_sessions_gt_0.3pct | day_close_median_abs_pts | day_close_p95_abs_pts | day_close_sessions_gt_0.3pct |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| NIFTY | pre_CAS | 286 | 4.7 | 26.6 | 0 | 0.6 | 7.0 | 0 | 0.6 | 4.5 | 0 | 11.4 | 47.7 | 3 |
| NIFTY | post_CAS | 29 | 2.8 | 15.7 | 0 | 46.7 | 353.3 | 12 | 0.4 | 268.0 | 7 | 0.0 | 0.0 | 0 |
| SENSEX | pre_CAS | 218 | 42.1 | 181.7 | 9 | 1.3 | 48.7 | 0 | 1.7 | 55.5 | 2 | 34.8 | 158.1 | 2 |
| SENSEX | post_CAS | 30 | 24.7 | 205.2 | 1 | 2.8 | 697.4 | 5 | 15.1 | 1512.7 | 6 | 0.0 | 0.0 | 0 |

Pre-auction-era closes differ by a median of 11 (NIFTY) / 35 (SENSEX) points because the vendor close is the 15:29 print and Yahoo carries the official close; highs/lows agree within a few points. After 2026-08-03 the NIFTY day high/low differ in 12/7 sessions because of the 15:20 artefact (D05).

## Cross-check with the earlier exact-contract files (same vendor, different pipeline and time)
3,243 contract-days / 1,222,729 overlapping minutes: **0** mismatches in open, high, low, close, volume and open interest; 72 index days with **0** mismatching OHLC values. The broad data hold 1,290 extra minutes (post-close 15:30+ rows the earlier pipeline dropped) and omit 20 legacy contract-days, all of them strikes outside the +-45 window. This shows both pipelines treat the vendor data identically; it is **not** independent proof that the vendor data are correct.

## Anomaly list
Negative-volume rows: `reports/tables/negative_volume_rows.csv`. Spikes and intrinsic-value breaches: `reports/tables/deep_scan_examples.csv`. Planned contracts without rows: `reports/tables/planned_contracts_without_rows.csv`. Session-level scan: `reports/tables/option_session_scan.json`, `deep_scan_sessions.csv`, `underlying_scan.json`.
