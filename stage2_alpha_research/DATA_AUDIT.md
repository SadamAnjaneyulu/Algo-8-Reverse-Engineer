# Stage 2 data and leakage audit (Milestone 1)

Produced by [`audit/data_leakage_audit.py`](audit/data_leakage_audit.py) (executed, 91 s) and
[`tests/test_data_integrity.py`](tests/test_data_integrity.py) (16 tests pass; the 25 PR #6 feature tests also pass).
Outputs are in [`results/`](results/). No model was trained and no feature was related to a future return.

## 1. Result

**Milestone 1 passes: 21 checks, 15 PASS, 6 RISK, 0 FAIL.** No critical data-integrity defect remains. The six risks are
real limits of the data that the research design must respect (section 5):

| Risk | Consequence |
|---|---|
| **Option universe is selected by Algo 8's trading** (E2) | The set of strikes present on a day reveals that day's later path. Option data may be used only under the rules in section 5 |
| **ATM straddle coverage on expiry days** (E1) | 99.8 % on D-1 but 87.5 % on D0, and missing exactly when the index moves far |
| **Stale option prices** (C6) | 2.35 % of option bars are carried prices |
| **Missing index bars** (B5) | 72 minutes (15:16–15:19, 15:29) on the last 8 dates |
| **NIFTY and SENSEX are one observation per date** (I1) | 85 independent dates, not 170 |
| **No untouched data** (I2) | Every result will be in-sample; external validation needs new data |

## 2. Dataset manifest

Full manifest with hashes: [`results/dataset_manifest.csv`](results/dataset_manifest.csv).

| Dataset | Role | Size |
|---|---|---|
| Index 1-minute bars, raw Breeze files | **Authoritative input** | 170 files, 63,678 bars, 22 Jun – 22 Oct 2026 |
| Option 1-minute bars, raw Breeze files | **Authoritative input** (with section 5 rules) | 3,243 files, 1,230,065 bars |
| Broker fills `Trades_GKOHNP140.csv` | Authoritative; used only to verify the bar-label convention | 41,421 fills |
| PR #6 feature library `ohlcv_research/features.py` | Authoritative code, reused unchanged (hash recorded) | 42 market features + 4 calendar fields |
| PR #6 caches, PR #3 index cache | **Not used.** Compared only: identical to the rebuild from raw | — |
| PR #3 panels, lot caches, model store, robustness results | **Excluded** (provisional per `FINAL_DEPENDENCY_AUDIT.md`) | — |

Algo 8's ledger is not an input to any Stage 2 feature, so the provisional carried-position labels, stop constant and
stop-module findings do not enter Stage 2.

## 3. Data quality

| Check | Result |
|---|---|
| Timezone and granularity | Every index and option timestamp is `+05:30`, on a whole minute |
| Duplicates | 0 in the raw index files, 0 in the raw option files |
| Bar label = bar start | 97.3 % of 41,421 broker fills lie inside the bar labelled with the fill's own minute (next bar 61.3 %, previous 56.6 %) |
| Index sessions | 85 per index, identical dates; no session on 26 Jun, 14 Sep, 2 Oct, 20 Oct |
| Index OHLC sanity | 0 inconsistent rows; 0 bars outside 09:15–15:29 |
| Index missing bars | 72 minutes in 16 index-sessions (8 dates, 12–22 Oct): 15:16–15:19 and some 15:29. Never interpolated |
| Index volume | All zero in the source (PR #6): no index volume feature exists |
| Option OHLC sanity | 0 inconsistent rows; all closes on the ₹0.05 tick; all volumes multiples of the lot |
| Option post-close bars | 19,518 bars at 15:30–15:39 exist and are dropped by the feature library |
| Option completeness | 3,243 contract-days; 95.2 % have all 375 bars |
| Expiry alignment | Exactly one expiry per (underlying, session). Sessions to expiry: 35 at 0 (D0), 32 at 1 (D-1). One D-1 is 3 calendar days before expiry (Fri 16 Oct for Mon 19 Oct) |
| Earlier caches | PR #6 `index.pkl`, `options.pkl`, three feature caches and PR #3 `idx_candles.pkl` reproduce exactly from the raw files |

## 4. Feature availability

All 42 market features were rebuilt from the raw files with the PR #6 library
([`results/feature_availability.csv`](results/feature_availability.csv): share available overall, per index, per time-of-day
bucket, and the median first-available minute).

| Family | Features (PR #6 names) | Available (share of decision minutes) | Median first-available minute |
|---|---|---|---|
| A volatility | `atr14_5m_bp`, `rv30_bp`, `hlvol30_bp`, `range_exp`, `bb_width_5m_bp` | 0.906 – 1.000 | 09:16 – 09:50 |
| B momentum | `ret_{1,5,15,30,60}m_bp`, `ema_slope_5m`, `rsi14_5m`, `macd_hist_5m_bp`, `adx14_5m` | 0.840 (`ret_60m`) – 1.000 | 09:16 – 10:16 |
| C mean reversion | `z60_1m`, `bb_pctb_5m`, `ema_dist_5m` | 0.922 – 1.000 | 09:16 – 09:45 |
| D market structure | `ret_open_bp`, `or_pos`, `or_break`, `dist_prev_high_bp`, `dist_prev_low_bp`, `gap_bp`, `sess_range_bp`, `sess_pos` | 0.963 – 1.000 | 09:16 – 09:30 |
| E options / premium, ATM straddle | `straddle_bp`, `straddle_ret_{5,15}m_pct`, `cepe_log_ratio`, `atm_rel_vol5`, `atm_strike` | 0.848 – 0.934 of option-session minutes | 09:16 – 09:50 |
| E options / premium, per contract | 11 features (`prem_ret_*`, `prem_spot_bp`, `rel_vol5`, `vol_z60`, …) | 0.909 – 1.000 | 09:16 – 09:50 |

Missing by construction: previous-day features on the first session of the sample (22 Jun, both indices); longer windows
during warm-up; the straddle on one whole session (SENSEX 24 Sep, coverage 0).
**Not available at all:** index volume, bid/ask, order book, true implied volatility, a full option chain, open interest
(present in the files, never loaded), index futures, and any option data outside D-1 / D0 sessions.

## 5. Leakage audit

| Test | Result |
|---|---|
| Feature rows use only completed candles | **PASS.** Prefix invariance on real data: on 6 random sessions × 3 random cut minutes, deleting every bar from the decision minute onward changed none of 1,633,414 feature values. The PR #6 suite (25 tests, including injected-leak mutations) passes |
| Forming candle excluded | **PASS** (synthetic test: scaling the forming candle and all later bars by 7 % changes no earlier row, and does change later rows) |
| No full-sample statistic | **PASS** (implied by prefix invariance; every normalisation is a trailing window inside the session) |
| Labels start after the signal | **PASS.** A label for decision minute *m* and horizon *h* uses bars starting in [*m*, *m*+*h*−1]; features use bars starting ≤ *m*−1. Windows never cross the close. Unit-tested for 5, 15, 30, 60 minutes |
| Overlapping labels | Handled by design: two decisions closer than *h* minutes overlap, so purge radius = *h* within a session; sessions do not overlap |
| Session boundaries | **PASS**: rolling quantities reset each session; previous-day levels use the previous session only |

**The one material leakage risk: the option universe (E2).** The files contain a contract-day only if Algo 8 traded or
held that contract on that day or the neighbouring day, and then they contain its bars for the whole day. So *which
strikes exist* at 09:15 already depends on where Algo 8 traded later, and Algo 8 trades near the money.

| Across sessions (Spearman) | D-1 (n = 32) | D0 (n = 35) |
|---|---:|---:|
| Universe room above the open vs the later maximum rise | +0.69 | +0.54 |
| Universe room below the open vs the later maximum fall | +0.83 | +0.22 |
| Universe centre minus open vs the open-to-close move | **+0.88** | +0.38 |

ATM straddle coverage by the index move since the open
([`results/audit_straddle_coverage_by_move.csv`](results/audit_straddle_coverage_by_move.csv)): D-1 ≥ 0.98 in every bin;
D0 0.91 (0–25 bp), 0.94, 0.85, **0.52 (100–150 bp), 0.44 (> 150 bp)**. Of the 6 D0 sessions below 90 % coverage, 5 are
sessions where Algo 8's cycle stop fired and it stopped trading; the sixth (NIFTY 29 Sep) has no Algo 8 fills that day.

Rules that follow (binding for later milestones):

1. Nothing derived from the universe may be a feature or a filter: strike counts, strike range, coverage, "bar exists" flags.
2. Prices of a contract that exists are real market prices and may be used. Selecting observations by *availability* is
   allowed only where availability is near-complete: **D-1 ATM straddle (99.8 %)**.
3. **D0 option samples are biased against large moves.** Any D0 option result must be reported as conditional on that
   selection and cannot be used alone to support a verdict above INCONCLUSIVE.
4. Index-only research (families A–D) is unaffected: index bars exist for all 85 dates regardless of Algo 8.

## 6. Independent sample size

| Quantity | Value |
|---|---|
| Index session dates (independent units) | **85** (170 underlying-sessions; NIFTY–SENSEX open-to-close correlation 0.95, close-to-close 0.97) |
| Option session dates | **67** (33 NIFTY, 34 SENSEX; never both indices on one date): 32 D-1 and 35 D0, in 35 weekly cycles |
| By month | Jun 6, Jul 23, Aug 21, Sep 21, Oct 14 |
| By the earlier chronological cuts (≤ 20 Aug / ≤ 22 Sep / later) | Index 43 / 22 / 20 dates; option 34 / 15 / 18 |
| Non-overlapping label windows per session | 74 (5 min), 24 (15 min), 12 (30 min), 6 (60 min) |
| Untouched dates | **0** |

## 7. Prior looks at this sample (selection-bias ledger)

| Earlier work | What it examined | Relevance |
|---|---|---|
| `alpha_freeze/` (lineage Y) | 4,512 BTST short-straddle configurations on 30 cycles; White reality check p = 0.104; H1 frozen, out-of-sample not run | Option-strategy returns on the same D-1 / D0 sessions were searched |
| Lineage Y alpha anatomy | Market ATM straddle premium vs realised move: +3.9 bp, 95 % CI [−12.3, +19.3] (D-1) | A family A / E quantity has already been looked at once |
| Lineage Y "lean" tests | Sign of Algo 8's book delta vs the next 15 / 60-minute index move (correlation −0.007 / +0.025) | Short-horizon index returns were examined conditional on Algo 8's book |
| Indicator studies (both lineages), PR #1, PR #3 | Indicators and features vs Algo 8's *decisions* | Not return prediction, but the same dates were inspected |
| PR #6 | Feature library and coverage only | No outcome touched. The planned "Track B" screen was never run (its results folder is empty) |
| This audit | Session-level future range, only to measure the universe artefact | Not a signal test |

No earlier work tested index features against forward index returns. Even so, no date is untouched, so every Stage 2
result is exploratory until tested on new data.

## 8. Unresolved items (not blocking Milestone 2)

1. **No tradable instrument for index signals.** The index is not tradable and there is no futures data. Economic
   feasibility (Milestone 5) can be assessed only through options on D-1 / D0 sessions, or needs futures data.
2. **No bid/ask.** Costs can only be scenario-based.
3. **External validation needs new data.** None exists in the repository.
4. The raw market files live on branch `research/ml-decision-engine`, not on this branch.
