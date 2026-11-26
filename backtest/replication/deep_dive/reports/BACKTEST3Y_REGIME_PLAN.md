# Is the edge seasonal, or does it only work in some periods? — plan

*Written before the tests below, after the combined backtest of `BACKTEST3Y_RESULT.md`. The slices, tests and the correction for multiple testing are fixed here.*

## Status of this investigation (stated first)
* **Exploratory, not confirmatory.** The out-of-sample cycles were already used once for the headline result, and every cycle (IS 175, OOS 64, rule-fitted live window 36) is used here. **There is no untouched data left for this question.** Whatever is found is a hypothesis; the only clean test is new cycles from now on (forward / paper trading) against a rule written down in advance.
* **The data cannot prove seasonality.** About 3 years: each calendar month occurs 2–3 times, a quarter 2–3 times, and two correlated indices share each week. The tests below say whether the observed pattern is larger than what shuffling the labels produces, not why.

## Unit and metric (locked)
* **Weekly unit.** NIFTY and SENSEX cycles that expire in the same ISO week are not independent, so the unit of analysis is the **week**: the mean net P&L per cycle of the cycles that expired that week (the indices present). About 160 weeks.
* **Primary metric:** net P&L per cycle of the **B/V2 point line**, restated at a **constant lot size** (NIFTY 65, SENSEX 20, the 2026 units) so that exchange lot-size changes (NIFTY 50 → 25 → 75 → 65; SENSEX 10 → 20) cannot create a "period effect". Gross and the A/V1 band are reported next to it for the main tests.
* Cycles from the rule-fitted live window are included and marked (they are in-sample for the rules).

## Part 1 — is the edge stable in time? (stationarity)
* **1a Rolling 26-week mean** of the weekly series with a week-bootstrap band.
* **1b Variability test:** the standard deviation of the rolling 26-week means against its distribution when the weeks are **randomly reordered** (5,000 permutations). A small p-value means the good and bad weeks cluster in time more than chance (regimes); a large p-value means the series behaves like independent weeks.
* **1c Change-point scan:** the largest |t| between an earlier and a later segment over all splits with at least 30 weeks on each side; p-value from the same permutations.
* **1d First half vs second half** (chronological), difference of means with a week-bootstrap interval.
* **1e Autocorrelation** of the weekly series at lags 1–4 against ±2/√n.
* **1f By module:** the same 1b–1d for the **D-1 book managed alone** and for **what the D0 module adds** (the diagnostic `hold` runs), to see which part is stable.

## Part 2 — calendar slices
Families (each is tested as a whole and cell by cell): **month of year (12)**, **quarter (4)**, **calendar year (4)**, **half-year (7)**, **weekday of D0 (5)** (the expiry weekday regime: Thursday, Tuesday, Friday), **week of month of D0 (5)**, **monthly-expiry week (2)**, **index (2)**, **timetable regime before / after June 2026 (2)**.
* **Family test:** the between-group sum of squares of the weekly series against the distribution when the group labels are permuted across weeks (5,000 permutations). One p-value per family.
* **Cell test:** mean, week-bootstrap 95% interval and a two-sided bootstrap p-value.
* **Multiple testing:** all cells of all families (≈ 48) are corrected together with the **Benjamini–Hochberg false-discovery rate at 10%**; the families (9) with a Holm correction on their permutation p-values.

## Part 3 — market-regime slices (terciles of the weekly series by a feature, by index then averaged)
* **Known at the D-1 open (tradeable as a filter):** the **implied move** (ATM straddle at 09:15 ÷ spot), the **D-1 morning range** (09:15–10:15 high–low ÷ spot).
* **Known at the D0 open:** the **opening gap** (D0 open vs D-1 close, absolute).
* **Ex post (explains, cannot be traded):** the **realised move** (|D0 close − D-1 open| ÷ spot), the **realised ÷ implied ratio**, the **intraday excursion**.
* Same family and cell tests as Part 2 (5 families × 3 terciles = 15 more cells; the total of ≈ 63 cells enters one FDR correction).
* **Mechanism check:** the edge of a short-premium book should be the implied-minus-realised spread, and should fail when the realised ÷ implied ratio is high. The correlation of the weekly net with that ratio is reported, with its permutation p-value.

## Reading rules
* A calendar or regime effect is called **"supported"** only if (a) its **family** permutation p < 0.05 after Holm, **and** (b) at least one of its cells has FDR q < 0.10, **and** (c) the sign agrees in the A/V1 band and in the gross series. Otherwise it is **"not supported"**, and the cell is only a description.
* A regime-dependence finding does not make a filter: a filter is a new rule that needs new data (see the status above).
* **Not testable here:** causes (events, flows, liquidity), cycles longer than the sample, anything about years before November 2023.
