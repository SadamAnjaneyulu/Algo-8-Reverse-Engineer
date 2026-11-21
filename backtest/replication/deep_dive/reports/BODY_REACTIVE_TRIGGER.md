# Algo 8 — reactive pairs: window, indicator and trigger

*Investigation only. In-sample (D-1 of 32 cycles with reactive pairs, 354 reactive pairs in 266 pair-minutes inside 10:30–15:15 of 9,152 cycle-minutes; not a holdout). Plan written before the tests: `BODY_REACTIVE_TRIGGER_PLAN.md`. Steps added after the first results are labelled **post-hoc**. Numbers are read from `outputs/bl_trg_*` and `bl_summary_trg1…5.json`. Figure: `figures/bl_trg_logic.png`.*

## 0. Answers

| Question | Answer | Evidence level |
|---|---|---|
| **Is a Donchian channel the real indicator?** | **Cannot be proved from behaviour, and I did not prove it.** What the data does is rule alternatives out: a range that expands from the open (AUC 0.61 vs 0.91), every moving-average-gap family (0.76–0.88, previous study), and channels shorter than ~40 or longer than ~70 minutes. It cannot separate "position in the trailing N-minute range", "N-minute high/low breakout" and "stochastic %K": they are the same signal in this data. | Observed (alternatives rejected); identity **Not established** |
| **Which window: 60 or another?** | **A rolling window of about 40–70 minutes; 60 has the highest point estimate (AUC 0.914) but 40, 45, 50, 55, 65 and 70 are statistically indistinguishable from it** (paired CIs include 0). Upper-edge and lower-edge events agree (best N 55 and 45; both on the plateau). I cannot narrow it further with minute closes. | Observed (plateau); exact N **Not identifiable** |
| **What does the strike do at the edge?** | Among pairs placed beyond the 60-minute band, **94.5%** sit one step on the broken side of ATM; among pairs not beyond the band 81.1% (n = 236 and 127). | Observed |
| **What fires a pair?** | **Not cracked.** The range edge is close to *necessary*: **79% of pair-minutes have the current minute's close beyond the previous 60 closes** (look-ahead variant; 41% with completed bars only). It is far from *sufficient*: only **19%** of those minutes (look-ahead; 10% completed-bar) contain a pair. | Observed; trigger **Unresolved** |
| **What explains which breakouts fire?** | Only **elapsed time since the previous reactive pair** (within breakout minutes: AUC 0.69, same in both halves). Breakouts within 20 minutes of the last pair fire at 53–144 per 1000 minutes; after 20 minutes at 281–347. It is **time, not the spot or ATM move** since that pair. Book state, option premium/volume, market speed and clock add nothing measurable. | Observed (predictive); mechanism **Unresolved** |
| **Is there a simple rule?** | **No.** The best leave-one-cycle-out tree has precision 19% and recall 32%; pre-registered success needed ≥ 50% on both. | Observed |

## 1. Block A — band definition and window (363 pairs vs 10,890 random seconds)
| window | AUC | AUC upper edge | AUC lower edge | AUC even / odd cycles | share of pairs beyond the band | random seconds | difference vs N = 60 (95% CI) |
|---|---|---|---|---|---|---|---|
| N = 20 | 0.877 | 0.877 | 0.876 | 0.903 / 0.851 | 72.2% | 14.7% | -0.050 … -0.026 |
| N = 30 | 0.897 | 0.888 | 0.904 | 0.922 / 0.873 | 70.8% | 10.8% | -0.025 … -0.009 |
| N = 40 | 0.907 | 0.896 | 0.916 | 0.929 / 0.886 | 69.2% | 9.0% | -0.013 … +0.001 |
| N = 45 | 0.91 | 0.898 | 0.921 | 0.935 / 0.887 | 68.0% | 8.1% | -0.009 … +0.002 |
| N = 50 | 0.911 | 0.905 | 0.915 | 0.934 / 0.888 | 66.1% | 7.5% | -0.007 … +0.001 |
| N = 55 | 0.914 | 0.91 | 0.916 | 0.935 / 0.892 | 65.8% | 6.9% | -0.004 … +0.003 |
| N = 60 | 0.914 | 0.908 | 0.919 | 0.933 / 0.896 | 65.0% | 6.5% | +0.000 … +0.000 |
| N = 65 | 0.914 | 0.908 | 0.918 | 0.933 / 0.896 | 64.2% | 6.2% | -0.004 … +0.003 |
| N = 70 | 0.909 | 0.903 | 0.912 | 0.932 / 0.887 | 62.0% | 5.8% | -0.012 … +0.001 |
| N = 80 | 0.885 | 0.875 | 0.892 | 0.911 / 0.861 | 58.4% | 5.3% | -0.046 … -0.014 |
| N = 90 | 0.86 | 0.842 | 0.875 | 0.886 / 0.837 | 54.0% | 5.0% | -0.073 … -0.036 |
| N = 120 | 0.775 | 0.79 | 0.761 | 0.808 / 0.745 | 42.1% | 4.5% | -0.164 … -0.118 |
| expanding since the open | 0.613 | 0.576 | 0.65 | 0.620 / 0.610 | 26.5% | 3.4% | -0.346 … -0.255 |

* Plateau, not a peak: 40–70 minutes are inside the 95% paired-bootstrap CI of N = 60; ≤ 35 and ≥ 75 minutes are excluded. Excluded windows: N10, N15, N20, N25, N30, N35, N75, N80, N90, N100, N120.
* **Expanding range since the open is rejected** (AUC 0.613, difference to N = 60 -0.35 … -0.26): the band is a *rolling* range, not the day high/low.
* **No crossing signature in the margin**: events beyond the band sit a median 0.054 strike-steps beyond it, random seconds beyond the band 0.031; ≥ 98% of both are within half a step. With minute closes only I cannot see the exact crossing second, so the boundary cannot be located more precisely.

## 2. Block C/D — what separates firing from non-firing breakouts
Populations (all features completed-bar/causal at the minute start; the look-ahead population is defined by the current minute's close and is flagged):
* **1131 causal breakout minutes** (completed bar closed beyond its previous 60 closes), 110 with a pair;
* **1127 look-ahead breakout minutes**, 210 with a pair.

**Look-ahead breakout minutes** — AUC gain of each block over the edge-only model (edge-only AUC logistic 0.611, boosting 0.626):

| block added to the edge features | logistic AUC | logistic gain (95% CI) | boosting AUC | boosting gain (95% CI) |
|---|---|---|---|---|
| clock | 0.607 | -0.004 (-0.029 … +0.015) | 0.634 | +0.008 (-0.009 … +0.025) |
| activity | 0.705 | +0.095 (+0.056 … +0.129) | 0.72 | +0.094 (+0.043 … +0.143) |
| book | 0.623 | +0.012 (-0.023 … +0.042) | 0.6 | -0.027 (-0.056 … +0.001) |
| option | 0.612 | +0.002 (-0.017 … +0.021) | 0.641 | +0.014 (-0.011 … +0.040) |
| market | 0.612 | +0.002 (-0.015 … +0.019) | 0.627 | +0.001 (-0.020 … +0.025) |
| all blocks | 0.704 | +0.093 (+0.051 … +0.131) | 0.725 | +0.099 (+0.049 … +0.144) |

**Causal breakout minutes** (edge-only AUC 0.587 / 0.582):

| block added to the edge features | logistic AUC | logistic gain (95% CI) | boosting AUC | boosting gain (95% CI) |
|---|---|---|---|---|
| clock | 0.565 | -0.022 (-0.043 … -0.004) | 0.567 | -0.014 (-0.035 … +0.009) |
| activity | 0.639 | +0.052 (-0.013 … +0.130) | 0.633 | +0.052 (-0.019 … +0.135) |
| book | 0.594 | +0.007 (-0.038 … +0.049) | 0.596 | +0.015 (-0.025 … +0.057) |
| option | 0.588 | +0.001 (-0.041 … +0.040) | 0.618 | +0.037 (-0.007 … +0.076) |
| market | 0.591 | +0.004 (-0.021 … +0.032) | 0.608 | +0.026 (-0.017 … +0.066) |
| all blocks | 0.695 | +0.108 (+0.044 … +0.183) | 0.652 | +0.070 (-0.005 … +0.157) |

**Episode starts** (causal breakout, pair within 3 minutes; 571 episodes, 121 with a pair; edge-only AUC 0.544 / 0.534):

| block added to the edge features | logistic AUC | logistic gain (95% CI) | boosting AUC | boosting gain (95% CI) |
|---|---|---|---|---|
| clock | 0.52 | -0.024 (-0.043 … -0.009) | 0.536 | +0.002 (-0.030 … +0.034) |
| activity | 0.65 | +0.106 (+0.027 … +0.172) | 0.586 | +0.052 (-0.027 … +0.130) |
| book | 0.564 | +0.020 (-0.020 … +0.056) | 0.558 | +0.024 (-0.022 … +0.075) |
| option | 0.544 | -0.000 (-0.047 … +0.043) | 0.515 | -0.019 (-0.075 … +0.039) |
| market | 0.536 | -0.008 (-0.032 … +0.018) | 0.546 | +0.012 (-0.040 … +0.062) |
| all blocks | 0.65 | +0.106 (+0.047 … +0.170) | 0.635 | +0.102 (+0.018 … +0.176) |

**All cycle-minutes** (edge-only AUC 0.821 / 0.831; the edge features already carry most of it):

| block added to the edge features | logistic AUC | logistic gain (95% CI) | boosting AUC | boosting gain (95% CI) |
|---|---|---|---|---|
| clock | 0.821 | -0.000 (-0.006 … +0.006) | 0.831 | +0.001 (-0.003 … +0.004) |
| activity | 0.818 | -0.003 (-0.024 … +0.016) | 0.856 | +0.025 (+0.015 … +0.039) |
| book | 0.816 | -0.005 (-0.018 … +0.007) | 0.836 | +0.005 (-0.001 … +0.012) |
| option | 0.819 | -0.001 (-0.013 … +0.008) | 0.843 | +0.012 (+0.005 … +0.019) |
| market | 0.812 | -0.008 (-0.015 … -0.001) | 0.834 | +0.004 (-0.003 … +0.010) |
| all blocks | 0.826 | +0.005 (-0.015 … +0.025) | 0.854 | +0.024 (+0.013 … +0.037) |

* Rule used: a block "explains non-firing" if it adds ≥ 0.03 AUC with a CI excluding 0 in both halves. **Only the order-activity block does** (look-ahead minutes: +0.09 logistic and +0.09 boosting with CIs excluding 0; causal minutes and episodes: +0.05 to +0.11, CIs sometimes include 0). **Clock, book state, option state and market-speed blocks do not** (one small exception: option premium/volume adds +0.012, CI 0.005–0.019, in the all-minutes boosting model, below the 0.03 threshold and absent inside breakout minutes).
* Even the full model reaches only AUC 0.65–0.73 inside breakout minutes: most of the non-firing is unexplained.

## 3. Block E — what inside order activity matters: time since the last pair (**post-hoc drill-down**)
Single features, look-ahead breakout minutes:

| feature (look-ahead breakout minutes) | AUC (pairs vs no pair) | even cycles | odd cycles |
|---|---|---|---|
| age_react | 0.688 | 0.708 | 0.669 |
| age_bb | 0.614 | 0.641 | 0.584 |
| age_oth | 0.595 | 0.61 | 0.58 |
| last_react_same_side | 0.414 | 0.412 | 0.417 |
| width60 | 0.417 | 0.389 | 0.443 |
| age_sell | 0.583 | 0.61 | 0.553 |
| n_react_sofar | 0.419 | 0.452 | 0.379 |
| n_bb_sofar | 0.428 | 0.425 | 0.433 |
| run60 | 0.433 | 0.428 | 0.439 |
| n_sell_sofar | 0.439 | 0.464 | 0.409 |

| minutes since the last reactive pair | breakout minutes | with a pair | pairs per 1000 minutes |
|---|---|---|---|
| no pair yet | 67 | 21 | 313.43 |
| <2 min | 175 | 13 | 74.29 |
| 2-5 | 150 | 16 | 106.67 |
| 5-10 | 161 | 16 | 99.38 |
| 10-20 | 208 | 30 | 144.23 |
| 20-40 | 199 | 56 | 281.41 |
| 40+ | 167 | 58 | 347.31 |

Finer bins:

| minutes since the last pair | breakout minutes | with a pair | per 1000 |
|---|---|---|---|
| (0, 1] | 99 | 9 | 91.0 |
| (1, 2] | 76 | 4 | 53.0 |
| (2, 3] | 54 | 4 | 74.0 |
| (3, 5] | 96 | 12 | 125.0 |
| (5, 8] | 109 | 11 | 101.0 |
| (8, 12] | 107 | 13 | 121.0 |
| (12, 20] | 153 | 22 | 144.0 |
| (20, 40] | 199 | 56 | 281.0 |
| (40, 1000] | 167 | 58 | 347.0 |

* The relationship is a **ramp, not a cool-down threshold** (no clean step at any age). Overall (not conditional on a breakout) the pair rate does **not** depend on time since the last pair (ratio 1.03, CI 0.69–1.49):

| minutes since the last reactive pair | all minutes | with a pair | pairs per 1000 minutes |
|---|---|---|---|
| no pair yet | 721 | 27 | 37.45 |
| <2 min | 498 | 17 | 34.14 |
| 2-5 | 706 | 18 | 25.5 |
| 5-10 | 1063 | 20 | 18.81 |
| 10-20 | 1769 | 41 | 23.18 |
| 20-40 | 2251 | 78 | 34.65 |
| 40+ | 2144 | 65 | 30.32 |

* **Within breakout minutes** the rate within 5 minutes of the last pair is 0.41× the rate later (CI 0.29–0.55; causal breakouts 0.49×, CI 0.31–0.74).
* Side matters too (same side as the last pair is suppressed about 2×), and so does repeating the same strike:

| population | last pair vs current breakout side | minutes | with a pair | per 1000 |
|---|---|---|---|---|
| all minutes | opposite side | 2245 | 82 | 36.53 |
| all minutes | same side | 6186 | 157 | 25.38 |
| causal breakout minutes | opposite side | 153 | 32 | 209.15 |
| causal breakout minutes | same side | 928 | 66 | 71.12 |
| LOOK-AHEAD breakout minutes | opposite side | 214 | 65 | 303.74 |
| LOOK-AHEAD breakout minutes | same side | 846 | 124 | 146.57 |
| inside range (no LA breakout) | opposite side | 2031 | 17 | 8.37 |
| inside range (no LA breakout) | same side | 5340 | 33 | 6.18 |

| look-ahead breakout minutes | minutes | with a pair | per 1000 |
|---|---|---|---|
| target strike differs from the last pair strike | 438 | 101 | 230.6 |
| target strike = last pair strike | 622 | 88 | 141.5 |

* **Time or move?** (post-hoc):

| feature (look-ahead breakout minutes) | AUC | even cycles | odd cycles |
|---|---|---|---|
| age_react | 0.688 | 0.708 | 0.669 |
| move_since_pair | 0.556 | 0.558 | 0.557 |
| abs_move_since_pair | 0.562 | 0.555 | 0.571 |
| atm_move_since_pair | 0.538 | 0.549 | 0.527 |

| comparison (leave-one-cycle-out logistic) | AUC first | AUC second | difference (95% CI) |
|---|---|---|---|
| time + move vs time only | 0.665 | 0.68 | -0.015 (-0.043 … +0.012) |
| time + move vs move only | 0.665 | 0.408 | +0.256 (+0.209 … +0.309) |
| move only vs time only | 0.408 | 0.68 | -0.271 (-0.327 … -0.211) |

  Adding the spot move or ATM move since the last pair to elapsed time does not help (difference −0.015, CI includes 0); the move alone has no signal. The pacing is **by time**.
* **One pair per leg?** (post-hoc). A leg = consecutive minutes beyond the band on the same side; the null places each cycle's pair-minutes at random among its leg minutes (2,000 draws):

| leg definition | legs | leg minutes | pair minutes in legs | legs with a pair | legs with 2+ pair minutes | null mean legs with a pair | null mean legs with 2+ | P(null <= observed 2+) | null 2.5% | null 97.5% |
|---|---|---|---|---|---|---|---|---|---|---|
| look-ahead legs | 569 | 1127 | 210 | 192 | 18 | 178.732 | 26.84 | 0.009 | 20.0 | 34.0 |
| causal legs | 571 | 1131 | 110 | 105 | 5 | 99.232 | 9.59 | 0.042 | 5.0 | 14.0 |

  Legs with two or more pair-minutes are fewer than chance (look-ahead legs: 18 vs 26.8, one-sided p = 0.009), a modest spacing, not a one-per-leg rule: 192 of 569 look-ahead legs have a pair.
* Gaps between consecutive reactive pairs: median 24 min, 25th percentile 7.2 min, 10th percentile 68 s; 9.7% are under 60 s (bursts of pairs placed together exist); 56% of pairs repeat the previous reactive strike.

## 4. Block F — simplest rule
| rule | minutes predicted | precision | recall of the pair minutes |
|---|---|---|---|
| depth<=3 tree, all causal features | 442 | 19.0% | 31.6% |
| depth<=3 tree, edge features only | 1700 | 8.9% | 56.8% |
| completed-bar breakout (N=60) (no learning) | 1131 | 9.7% | 41.3% |
| LOOK-AHEAD breakout (current close beyond prior 60 closes) (no learning) | 1127 | 18.6% | 79.0% |

* No rule reaches 50% precision and 50% recall. The look-ahead breakout alone recalls 79% of pair-minutes but with 19% precision; learning from all causal features lifts precision to 19% but cuts recall to 32%.

## 5. What this means
* **Where / when (supported):** a reactive pair is a **range-edge event**: roughly when the live spot has just pushed beyond its trailing ~hour range, on that side (strike one step toward it); this happens mostly inside the minute, so completed-bar data see only 41% of them.
* **Which edge events fire (partly supported):** more likely the longer since the previous reactive pair (a time-based ramp), less likely when the previous pair was on the same side/strike. Whether this is a cool-down timer, a rate limit, a per-leg budget, or something else is **not identifiable** here.
* **Unexplained:** about 81% of look-ahead breakout minutes have no pair and the best model explains little of it. The missing variable may be one the data do not contain: the true intraday high/low, ticks or a second-level crossing time, bid/ask, quantity budget/margin state, or a stochastic element.

## 6. Evidence register
| Claim | Label | Basis |
|---|---|---|
| The band is a rolling range of about 40–70 minutes (60 best point estimate), not an expanding range or an MA-gap | **Observed** | AUC plateau with paired CIs; expanding 0.61 |
| Strike direction follows the broken side (94.5% beyond the band) | **Observed** | 236 pairs beyond the band |
| Algo 8 is a Donchian channel / any named indicator | **Not established** | equivalent formulations are indistinguishable |
| The exact window (60 vs 40–70) | **Not identifiable** | plateau; minute closes only |
| An edge pair is more likely the longer since the previous reactive pair | **Observed (predictive)** | AUC 0.69, both halves; ratio 0.41× (CI 0.29–0.55); post-hoc drill-down |
| The pacing is by elapsed time, not by the spot/ATM move since the last pair | **Observed (predictive)** | post-hoc; time + move vs time only CI includes 0 |
| Book state, option premium/volume, market speed, clock explain non-firing | **Not supported** | gains ≤ +0.03, CIs include 0 |
| What exactly fires each pair | **Unresolved** | no rule with precision and recall ≥ 50%; ~81% of look-ahead breakout minutes unexplained |
| Intra-minute crossing time, calculation frequency | **Not testable** | minute data only |

## 7. Limits and how this could be wrong
* **Post-hoc steps:** the time-since-last-pair drill-down, time-vs-move and per-leg tests were added after the pre-registered block C showed activity as the only useful block; they are labelled, replicate in both cycle halves, but are not multiplicity-corrected. Many candidate features (≈ 30) and windows (19) were examined.
* **Look-ahead variant:** it defines the population by the current minute's close; it shows how much of the gap is intra-minute, it is not a causal rule.
* **Closes only:** no spot high/low. The true channel may use highs/lows, which could change which windows fit.
* **Pair minutes, not seconds:** the minute panel cannot see the crossing second; 9 pairs outside 10:30–15:15 and cycles without reactive pairs are excluded; some minutes contain several pairs (counted once).
* In-sample; D-1 only; 266 pair-minutes; predictive not causal; no source code.

## 8. Files
`src/bl_trg_band.py` (block A, B) → `bl_trg_panel.py` (minute panel) → `bl_trg_tests.py` (blocks C–F) → `bl_trg_drill.py` → `bl_trg_move.py` → `bl_trg_leg.py` → `bl_trg_fig.py` → `make_trg_report.py`. Outputs `outputs/bl_trg_*`, `bl_summary_trg1…5.json`. Tests `tests/test_bl.py` (`test_trg_*`).
