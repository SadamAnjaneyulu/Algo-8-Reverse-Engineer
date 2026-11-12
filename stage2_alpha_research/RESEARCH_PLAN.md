# Stage 2 research plan

Objective: test whether repeatable, statistically defensible, economically meaningful predictive information exists.
The five families below are hypotheses to test, not assumed signals. Everything marked **PROPOSED** is a draft for
review and is not locked.

## 1. Milestones

| # | Content | Status |
|---|---|---|
| 1 | Repository inspection, input validation, data and leakage audit | **Complete** ([`DATA_AUDIT.md`](DATA_AUDIT.md)) |
| 2 | Lock prediction targets and horizons; build the five baselines | **Complete** ([`MILESTONE2_REPORT.md`](MILESTONE2_REPORT.md)); awaiting review |
| 3 | Test the five families one at a time, each registered before it is run | Not started |
| 4 | Statistical validation and robustness | Not started |
| 5 | Economic feasibility for promising candidates | Not started |

## 2. Requirement lock (completed at Milestone 2; decisions D1–D6 authorised on 12 Nov 2026)

| Item | Value |
|---|---|
| Assets | NIFTY and SENSEX index (signals); ATM index options on D-1 / D0 sessions (family E, and any execution test) |
| Data | Raw Breeze 1-minute bars, 22 Jun – 22 Oct 2026: 85 index dates, 67 option session dates |
| Native resolution | 1 minute; decisions use completed bars only |
| Features | PR #6 library, unchanged (42 market features, 4 calendar fields). A new feature needs its own register row, definition and causality test |
| Targets and horizons | **LOCKED**: 15, 30, 60 min (5 min sensitivity only); entry = open of the decision bar; section 3 |
| Validation | **LOCKED**: folds 43 / 22 / 20 dates, four-block stability, purged non-overlapping grid; section 5 |
| Costs | **LOCKED**: the four scenarios already registered in `alpha_freeze` (`analysis/engine.py::COSTS`: zero, moderate, conservative, adverse); no bid/ask exists |
| Metrics | Predictive: IC, rank IC, conditional means with cluster confidence intervals. Strategy (Milestone 5 only): trades, win rate, profit factor, Sharpe, return, maximum drawdown, trades per day |
| Explicit exclusions | Algo 8's ledger and all provisional inputs; universe-derived option quantities; deep learning; hyper-parameter search; accuracy targets |

## 3. Prediction targets (LOCKED at Milestone 2; exact indexing in `MILESTONE2_REPORT.md` §3)

Notation: decision minute *m* (features use bars starting ≤ *m*−1); *O*ₘ = open of the bar starting at *m*;
*C*ₖ, *H*ₖ, *L*ₖ = close, high, low of bar *k*; horizon *h* minutes; label bars = [*m*, *m*+*h*−1], same session.

| Target | Definition | Used for |
|---|---|---|
| Directional return | *r*(m,h) = 10⁴ · ln(*C*ₘ₊ₕ₋₁ / *O*ₘ) | families B, C, D |
| Realised volatility | *RV*(m,h) = 10⁴ · √( ln(*C*ₘ/*O*ₘ)² + Σₖ₌ₘ₊₁..ₘ₊ₕ₋₁ (ln *C*ₖ/*C*ₖ₋₁)² ). **Clarified at lock:** the first increment starts from the entry open *O*ₘ, so no gap to *C*ₘ₋₁ enters | family A |
| Range | *RG*(m,h) = 10⁴ · (max *H*ₖ − min *L*ₖ) / *O*ₘ | families A, D |
| Range expansion | *RG*(m,h) divided by the trailing range of the previous *h* completed bars | family A |
| Reversal | sign(*r*(m,h)) ≠ sign(trailing *h*-minute return), with a dead band to be fixed at registration | family C |
| Straddle premium change | 10² · (*P*ₘ₊ₕ₋₁ / *P*ₘ − 1) for the ATM strike fixed at *m* (D-1 sessions; D0 flagged) | family E |

Candidate horizons: 5, 15, 30, 60 minutes. Locked (D1): 15, 30, 60; 5 min is a sensitivity only. Non-overlapping observations per session on the locked grid (a full trailing window is required): 73 (5 min), 23, 11, 5. With one-minute
bars and no bid/ask, the 5-minute horizon is the most exposed to costs and to stale prices; that argues for fewer,
longer horizons, but the choice is yours (section 7).

## 4. Baselines (Milestone 2)

1. No signal: unconditional mean of each target (and zero for direction).
2. Time of day: target mean by clock bucket.
3. Simple momentum: sign of the trailing *h*-minute return.
4. Simple mean reversion: minus that sign.
5. Volatility only: trailing realised volatility as the predictor of future volatility and range.

A candidate must beat the relevant baseline; a model that does not is not extended.

## 5. Validation design (LOCKED; implementation in `validation/`)

* **Unit of independence:** the session date (NIFTY and SENSEX on one date are one cluster). Sample: 85 dates.
* **Chronological only:** expanding-window walk-forward by date; no shuffling. Within a session, overlapping labels are
  purged within the horizon. Folds: TRAIN the first 43 dates (22 Jun–20 Aug), VAL the next 22 (21 Aug–22 Sep), TEST the last 20 (23 Sep–22 Oct);
  plus a stability check on 4 contiguous blocks (22/21/21/21 dates) with expanding fit and 3 test steps.
* **Uncertainty:** cluster (by date) block bootstrap; confidence intervals reported with the number of dates and events.
* **Multiple testing:** every registered experiment counts. Holm and Benjamini–Hochberg across the register, plus a
  max-statistic permutation null (date-level sign or block shuffles) for the best result of each family.
* **Stability:** by index, by month, by D-1 / D0 / other sessions, and leave-one-date-out for any positive result.
* **No untouched data:** every verdict is in-sample; the best possible verdict is PROMISING pending new data.

## 6. Family plans (each becomes registered experiments in Milestone 3)

| Family | Rationale to be tested | Features | Main constraint |
|---|---|---|---|
| A volatility | Volatility clusters, so recent volatility should predict near-future volatility and range; premium may or may not compensate | 5 volatility features; `straddle_bp` vs later realised move | Predicting volatility is not a trade by itself; the premium comparison exists only on D-1 / D0 |
| B momentum | Short-term continuation after directional moves or opening-range breaks | 9 momentum features, `or_break` | Costs at short horizons; index not tradable |
| C mean reversion | Reversal after short-term dislocations | `z60_1m`, `bb_pctb_5m`, `ema_dist_5m`, range position | Same; momentum and reversal are opposite claims on the same data, so both are counted in multiple testing |
| D market structure | Opening range, range position and time of day condition later behaviour | 8 structure features, calendar fields | Time-of-day effects are also a baseline |
| E options / premium | Premium changes carry information about later movement or premium | ATM straddle features | No true IV, no full chain; universe selected by Algo 8 (rules in `DATA_AUDIT.md` §5); 32 D-1 dates with clean coverage |

## 7. Decisions D1–D6 (all authorised as option A on 12 Nov 2026; open items from Milestone 2 are in `MILESTONE2_REPORT.md` §12)

| # | Decision | Options |
|---|---|---|
| D1 | Horizons | **A)** 15, 30, 60 min (5 min reported as a sensitivity only) · B) all four · C) other |
| D2 | Entry reference for returns | **A)** open of the decision bar (first price after the signal) · B) close of the last completed bar (not executable) |
| D3 | Walk-forward folds | **A)** 43 / 22 / 20 dates plus the 4-block stability variant · B) other |
| D4 | D0 option samples (biased against large moves) | **A)** report separately, never sufficient for a verdict above INCONCLUSIVE · B) exclude entirely |
| D5 | Cost scenarios | **A)** the four registered `alpha_freeze` scenarios · B) rates you supply |
| D6 | Tradable instrument for index signals | **A)** evaluate predictive value on the index now and treat execution as unresolved until futures data exist · B) pause directional families until futures data are supplied · C) use ATM options on D-1 / D0 only |

## 8. Milestone 2 addenda

* **Grid and purging.** Decisions kd = h + 1 + phase + j·h; label windows are disjoint inside a session; no cross-session label. Counts per horizon, per fold and purged totals are in `results/m2_sample_counts.csv`.
* **Bootstrap.** Resample whole session dates (2,000 resamples, 95 % percentile CI; both indices of a date move together); sensitivity with blocks of 5 consecutive dates.
* **Multiple testing.** Date-permutation null (2,000 permutations; smallest attainable p = 1/2001); Holm and Benjamini–Hochberg over every registered test. Milestone 3 must add each family test to the same register-wide family.
* **Data defect found after Milestone 1.** Frozen index bars at about 15:15–15:19 on 96 sessions (3 Aug – 9 Oct) and missing bars on 16 (12–22 Oct): register DAT-15, `DATA_AUDIT.md` addendum, `MILESTONE2_REPORT.md` §9. Locked definitions unchanged; the treatment in Milestone 3 is an open decision.
