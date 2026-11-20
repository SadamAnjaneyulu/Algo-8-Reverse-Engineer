# Algo 8 — reactive pairs: which indicator best reproduces the behaviour?

*Investigation only. In-sample, observational (D-1, 363 reactive pairs, 10,890 random control seconds inside 10:30–15:15). Plan written before the tests: `BODY_REACTIVE_INDICATOR_PLAN.md`; the range-/MAD-/RSI-based relatives and the breakout reading (§4–§5) were added **after** the first search and are labelled post-hoc. Numbers are read from `outputs/bl_ind_*` and `bl_summary_ind*.json`. Figure: `figures/bl_ind_logic.png`. Everything below is about what *explains* the behaviour; **it does not show that Algo 8 uses this (or any named) indicator.***

## 0. Answers

| Question | Answer | Evidence level |
|---|---|---|
| **Which indicator best reproduces it?** | **The position of the live spot inside its own trailing high–low range of the last ~45–65 minutes** (a Donchian-channel / stochastic-type position: v = (spot − low)/(high − low) − 0.5, the high and low taken over the previous N completed one-minute closes). Its side (above or below the middle of the range) gives the strike direction, and its distance from the middle gives the activation: **79% of pairs fall in the top decile of abs(v) (spot at or beyond the edge of the range) against 10% of random seconds**; only 3.3% of pairs occur with the spot in the inner half of the range (43% of random seconds). Activation AUC **0.910** (parameter chosen on the other half of the cycles) vs 0.882 for the best moving-average-type indicator (EMA z) and **0.764 for the plain SMA gap**. | Observed (best-fitting indicator); not a statement about Algo 8's code |
| Is the SMA / trend-with-neutral-zone idea right? | **Partly.** For the **direction** every level-type indicator (SMA/EMA/WMA gap, momentum, Bollinger z, Donchian position, MACD) gives the same 89%–90% hit rate, so direction **cannot** distinguish them; SMA cross-overs, regression slopes and RSI/efficiency ratio are somewhat worse. For the **neutral zone** the standard SMA gap is a poor description (AUC 0.77); normalising the distance by volatility helps (z-score 0.86) and normalising by the **range** helps most (0.91). So the neutral zone is **relative**, not a fixed distance from an average. | Observed |
| Which window? | **About 45–65 minutes, most likely 60** (AUC plateau 0.910–0.914; CIs of 45–65 vs 60 include 0; ≤ 35 and ≥ 75 minutes are worse). A 60-minute window is a natural choice but 45–65 are statistically equal. | Observed (plateau); exact N Not identifiable |
| Is it a breakout? | **Yes in the sense that matters:** 65% of pairs are placed while the live spot is **beyond the previous 60-minute high or low** (random seconds 6.5%); with completed bars only, a close beyond the previous 60 closes lifts the pair rate 4.8× (91 vs 19 per 1000 minutes) and the rate is highest in the first minute after it (114 per 1000). **But a breakout does not fire a pair every time:** only 17% of the 532 completed-bar breakout episodes contain a pair minute, and 60% of pair minutes have no completed-bar breakout (the breakout is happening inside the minute). | Observed; trigger **Unresolved** |
| Anything that adds to it? | **No.** Adding the SMA gap, Bollinger/EMA z, gap/ATR, momentum, SMA cross, MACD, regression drift, RSI or a second (15-minute) range position to the 60-minute range position changes leave-one-cycle-out AUC by at most +0.0052 (alone: 0.913): the range position subsumes the other indicator-like variables. | Observed |

## 1. What was tested
Families and parameter grids were fixed in the plan (SMA/EMA/WMA gap, momentum, regression drift and line, SMA cross-over, MACD-like, Donchian mid-gap, Bollinger z, gap/ATR; N or span 3–120 minutes). **Post-hoc additions** after Bollinger z led: CCI-like gap/MAD, momentum/σ, Donchian **position**, RSI minus 50, efficiency ratio, EMA z. Indicators use completed one-minute closes of the spot (no spot high/low or volume exists in the data, so Supertrend, SAR, ATR from ranges and VWAP are not testable); the live spot is the linear interpolation between the two bracketing closes at the order second (diagnostic proxy). **Direction metric** = share of pairs whose strike equals nearest(live spot) + one step × sign(indicator). **Activation metric** = AUC of |indicator| for pair seconds vs random seconds. **Selection:** the parameter of each family is chosen on one half of the cycles and scored on the other half, both ways.

## 2. Family ranking
| indicator family | direction hit (cross-validated) | direction: difference vs the best direction family (95% CI) | activation AUC (cross-validated) | activation: paired bootstrap difference vs the best (95% CI) | best N / parameter for activation | parameters within 0.01 AUC of best |
|---|---|---|---|---|---|---|
| Donchian position | 89.3% | -2.9 … +0.0 pts | 0.91 | +0.000 … +0.000 | 60 | 2 |
| EMA z | 89.5% | -2.5 … +0.0 pts | 0.882 | -0.044 … -0.015 | 30 | 3 |
| Bollinger z | 89.3% | -2.9 … +0.0 pts | 0.854 | -0.073 … -0.042 | 30 | 3 |
| CCI-like gap/MAD | 89.3% | -2.9 … +0.0 pts | 0.846 | -0.083 … -0.050 | 45 | 3 |
| gap/ATR | 89.3% | -2.9 … +0.0 pts | 0.82 | -0.111 … -0.072 | 15 | 4 |
| EMA gap | 89.5% | -2.5 … +0.0 pts | 0.789 | -0.144 … -0.091 | 10 | 5 |
| WMA gap | 89.3% | -2.9 … +0.0 pts | 0.777 | -0.157 … -0.104 | 15 | 5 |
| SMA gap | 89.3% | -2.9 … +0.0 pts | 0.764 | -0.174 … -0.117 | 8 | 5 |
| Donchian mid gap | 89.5% | -2.5 … +0.0 pts | 0.76 | -0.169 … -0.126 | 15 | 2 |
| momentum/sigma | 90.4% | +0.0 … +0.0 pts | 0.719 | -0.220 … -0.164 | 10 | 2 |
| momentum | 90.4% | +0.0 … +0.0 pts | 0.705 | -0.234 … -0.176 | 10 | 2 |
| MACD | 90.1% | -0.8 … +0.0 pts | 0.671 | -0.268 … -0.209 | 5-15 | 1 |
| RSI minus 50 | 87.6% | -4.8 … -1.1 pts | 0.67 | -0.273 … -0.209 | 10 | 2 |
| efficiency ratio | 87.6% | -4.8 … -1.1 pts | 0.67 | -0.273 … -0.209 | 10 | 2 |
| SMA cross | 86.5% | -6.3 … -1.5 pts | 0.632 | -0.314 … -0.243 | 3-15 | 1 |
| regression line gap | 81.8% | -11.9 … -5.9 pts | 0.627 | -0.323 … -0.247 | 60 | 3 |
| regression drift | 85.7% | -7.0 … -2.6 pts | 0.579 | -0.366 … -0.295 | 10 | 1 |


* **Direction:** the level-type families are within about 1.5 points of each other and indistinguishable (paired CIs reach 0 for Donchian position, EMA z, Bollinger z, CCI-like gap/MAD, gap/ATR, EMA gap, WMA gap); **SMA cross-over (87%), regression line gap (82%), regression drift (86%) and RSI/efficiency ratio (88%) are clearly worse**.
* **Activation:** **Donchian position beats every other family** (paired bootstrap differences all negative with CIs excluding 0; the closest, EMA z, is -0.044 … -0.015 below). **Pre-registered rule:** "identified" only if the family wins both metrics; it wins activation decisively but the direction metric cannot discriminate, so strictly the answer is **identified on activation, undecidable on direction**.
* **Normalising helps:** at the same N the volatility-scaled distances beat the absolute gap in steps (Bollinger z − absolute gap: +0.059 AUC, CI +0.035 … +0.082; gap/ATR: +0.052, CI +0.035 … +0.069; N = 10):

| N (minutes) | AUC of abs(spot − SMA) in steps | AUC of abs(Bollinger z) | AUC of abs(spot − SMA) / ATR | direction hit of SMA gap |
|---|---|---|---|---|
| 5 | 0.7577 | 0.7799 | 0.7963 | 0.8926 |
| 10 | 0.7662 | 0.8265 | 0.8195 | 0.8953 |
| 15 | 0.7633 | 0.8414 | 0.8234 | 0.8953 |
| 20 | 0.7572 | 0.8457 | 0.8233 | 0.8953 |
| 30 | 0.7472 | 0.8587 | 0.8077 | 0.9036 |
| 45 | 0.7326 | 0.8568 | 0.7822 | 0.9036 |
| 60 | 0.7134 | 0.8563 | 0.76 | 0.9063 |
| 90 | 0.6617 | 0.8197 | 0.6951 | 0.9036 |


  A neutral band fixed in index points or strike steps is therefore not the right description; one scaled by recent volatility or by the recent range is.

## 3. Channel length (Donchian position, fine grid)
| channel length N (min) | activation AUC | 95% CI | difference vs N = 60 (95% CI) | direction hit |
|---|---|---|---|---|
| 30 | 0.897 | 0.875–0.921 | -0.025 … -0.009 | 89.5% |
| 35 | 0.902 | 0.880–0.925 | -0.020 … -0.005 | 89.5% |
| 40 | 0.907 | 0.886–0.930 | -0.014 … -0.000 | 89.5% |
| 45 | 0.91 | 0.889–0.933 | -0.008 … +0.002 | 89.5% |
| 50 | 0.911 | 0.888–0.933 | -0.007 … +0.001 | 89.8% |
| 55 | 0.914 | 0.891–0.936 | -0.003 … +0.003 | 89.8% |
| 60 | 0.914 | 0.892–0.935 | +0.000 … +0.000 | 89.8% |
| 65 | 0.914 | 0.892–0.934 | -0.004 … +0.003 | 89.8% |
| 70 | 0.909 | 0.884–0.930 | -0.013 … +0.000 | 89.8% |
| 75 | 0.899 | 0.871–0.924 | -0.027 … -0.004 | 89.5% |
| 80 | 0.885 | 0.856–0.912 | -0.045 … -0.015 | 89.5% |
| 90 | 0.86 | 0.832–0.888 | -0.071 … -0.033 | 89.0% |


* Plateau 45–65 minutes. CIs of 45, 50, 55 and 65 vs 60 include 0; 40 and 70 touch 0; ≤ 35 and ≥ 75 are clearly worse. The direction hit is flat (89%–90%) across N.

## 4. Robustness and the neutral zone
| subset | pairs | activation AUC (N = 60) | direction hit |
|---|---|---|---|
| all | 363 | 0.914 | 89.8% |
| first half | 176 | 0.923 | 90.3% |
| second half | 187 | 0.906 | 89.3% |
| NIFTY | 179 | 0.892 | 87.7% |
| SENSEX | 184 | 0.935 | 91.8% |
| V1 | 237 | 0.922 | 91.1% |
| V2 | 126 | 0.899 | 87.3% |


* Holds in both halves, both underlyings and both schedule versions. Neutral zone in range units (deciles of the absolute distance of the position from the middle, defined on random seconds): the lowest five deciles hold 3.9% of pairs; the top decile holds 79% (the implied pair rate is ≈ 219 per 1000 minutes at the edge vs ≈ 2 in the lower deciles). **The neutral zone is "the inside of the range", not a band around an average.**

| state of the live spot vs the previous 60 completed closes | share of pairs | share of random seconds | ratio | implied pair rate per 1000 min |
|---|---|---|---|---|
| beyond the 60-min high or low (abs position > 0.5) | 65.0% | 6.5% | 10.0 | 277.0 |
| within 5% of the band (abs position >= 0.45) | 87.9% | 16.9% | 5.2 | 144.0 |
| within 10% (abs position >= 0.40) | 93.1% | 27.3% | 3.4 | 95.0 |
| inner half of the range (abs position < 0.25) | 3.3% | 43.2% | 0.1 | 2.0 |



## 5. Breakout reading (post-hoc; completed bars only, no live proxy)
| N (min) | share of minutes in the state | pair rate in the state (per 1000) | outside | ratio | share of pair-minutes in the state |
|---|---|---|---|---|---|
| 20 | 22.3% | 68.5 | 15.9 | 4.3 | 55.3% |
| 30 | 17.7% | 78.2 | 16.8 | 4.7 | 50.0% |
| 45 | 13.9% | 88.1 | 17.9 | 4.9 | 44.3% |
| 60 | 12.2% | 90.8 | 18.9 | 4.8 | 39.9% |
| 90 | 9.5% | 83.2 | 21.8 | 3.8 | 28.5% |

| minutes since the 60-min breakout began | cycle-minutes | pair minutes | per 1000 |
|---|---|---|---|
| not in breakout | 7243 | 137 | 18.9 |
| minute 1 | 518 | 59 | 113.9 |
| minute 2 | 240 | 17 | 70.8 |
| minute 3 | 112 | 5 | 44.6 |
| minutes 4–5 | 102 | 10 | 98.0 |
| minutes 6–10 | 30 | 0 | 0.0 |


* Breakout episodes (N = 60, runs of consecutive completed-bar breakout minutes): 532 episodes, median length 1 minute(s); **17% contain a pair minute**; median delay to the first pair 0 minutes; 40% of the 228 pair minutes fall inside an episode.
* Reading: reactive pairs are placed **when the live spot is at or beyond the edge of its trailing ~hour range, toward that edge**, but being at the edge is **not sufficient** (most breakouts have no pair) and not always visible on completed bars (60% of pair minutes). Whatever else is required (the time gate, a refractory/throttle, order-activity clustering found earlier) is still unknown.
* This links to the earlier solo-sell finding (solo sells follow fresh favourable extremes): the same kind of range-edge information appears to drive both order types, with different strike and size rules.

## 6. Evidence register
| Claim | Label | Basis |
|---|---|---|
| Best-fitting indicator: position of the live spot in its trailing 45–65-minute high–low range (activation AUC 0.91, cross-validated) | **Observed** | 17 families, parameter chosen out of fold, paired bootstrap |
| Direction cannot distinguish level-type indicators (SMA gap, EMA, momentum, Bollinger z, Donchian position, MACD) | **Observed** | 89.3%–90.4% cross-validated; paired CIs reach 0 |
| The neutral zone is relative (volatility- or range-scaled), not a fixed distance from an SMA | **Observed** | normalised vs absolute AUC differences |
| Pairs are placed at/beyond the range edge, toward the edge; not every breakout fires one | **Observed** | 65% beyond the band vs 6.5% of random seconds; 17% of episodes |
| Algo 8 uses a Donchian channel (or any named indicator) | **Not established** | best-fitting description only; custom calculation possible |
| The exact window (60 vs 45–65) | **Not identifiable** | plateau |
| What exactly fires a pair | **Unresolved** | breakout is necessary-looking, not sufficient |

## 7. Limits and how this could be wrong
* **Selection among many candidates:** 17 families × parameters; parameters were chosen out of fold and family differences use paired cluster bootstrap, but the range-/MAD-/RSI additions followed the first result (post-hoc) and no multiplicity correction is applied. The margin of Donchian position over EMA z is 0.015–0.044 AUC (paired CI excludes 0) but is modest, and the 0.91 value is the best of a post-hoc-extended search.
* **Closes only:** the "high" and "low" are highs and lows of one-minute **closes** (no intraday high/low data). Indicators that need true highs/lows (ATR, Supertrend, SAR) could not be tested and might fit as well.
* **Live-spot proxy** (uses the current minute's close); the completed-bar results in §5 are the proxy-free check and are weaker (40% of pair minutes vs 65% of events beyond the band) because many breakouts occur inside the minute.
* **Equivalent formulations:** "position in the N-minute range", "new N-minute high/low breakout" and "stochastic %K − 50" are the same signal here; I cannot tell which Algo 8 would call it.
* In-sample; D-1 only; 363 events; predictive, not causal; no source code.

## 8. Files
`src/bl_ind_build.py` (indicator values for events and controls) → `bl_ind_tests.py` (scores, cross-validated families, bootstrap, normalisation, zone, combinations) → `bl_ind_break.py` (robustness, bands, completed-bar breakout, episodes) → `bl_ind_fine.py` (channel length) → `bl_ind_fig.py` → `make_ind_report.py`. Outputs `outputs/bl_ind_*`, `bl_summary_ind*.json`. Tests `tests/test_bl.py` (`test_ind_*`).
