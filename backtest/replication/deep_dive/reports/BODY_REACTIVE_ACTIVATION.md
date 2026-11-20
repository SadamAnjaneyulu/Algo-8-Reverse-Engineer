# Algo 8 — reactive pairs: the dynamic reference and what activates a pair

*Investigation only. In-sample, observational (D-1, 363 reactive pairs, 10,890 random control seconds inside 10:30–15:15). Plan written before the tests: `BODY_REACTIVE_ACTIVATION_PLAN.md`; the moving-average-gap analysis (§2) was added **after** a single-feature diagnostic pointed to it and is labelled post-hoc. Numbers are read from `outputs/bl_act_*` and `bl_summary_act*.json`. Figure: `figures/bl_act_logic.png`.*

## 0. Answers

| Question | Answer | Evidence level |
|---|---|---|
| Is it a "look-back" or something dynamic? | **Dynamic, yes: the live spot compared with a trailing price level** — either the spot 10–60 minutes ago or a moving average of the last 5–60 minutes. All of these give the same strike side (89.3%–90.6% hit rate on the live-spot proxy); none beats the others by more than 0.9 points. **Anchors tied to the book or the day** fit clearly worse: short-book centre 80%, last timetable-pair strike 74%, day mid-range 67%, opening ATM 63%, last sold strike 46%, last reactive strike 30%. So the reference is **recent price level, not the position or a clock anchor**; which exact smoothing (5–60 min, average or earlier price) is not identifiable. | Observed (family); exact form Not identifiable |
| **When does a reactive pair activate?** | Three facts, none a complete rule: **(1) time gate** 10:30–15:15 (earlier study). **(2) Not when the spot sits on its own average:** with |spot − 60-min average| < 0.1 strike step the rate is **4.0 per 1000 cycle-minutes**, with the gap at 0.1–0.5 step **27**, and ≥ 0.5 step **41** (only 2.6% of pairs occur with a gap < 0.1 step although it covers 18% of minutes); the same in both halves and both underlyings. The sign of the gap is the direction of the strike. **(3) Clustering with other orders:** 61% of pairs come within 5 minutes of another body sell (random seconds: 41%), 36% within 60 s of a hedge/stop/lump-module order (random: 12%), 13% within 60 s of a body buy-back (random: 4%). | Observed; rule **Unresolved** |
| So is the gap the trigger? | **Part of it — a necessary-looking condition, not a sufficient one.** "No clear direction (spot ≈ its average) → almost no pair" fits a rule that needs a defined side; but beyond ≈ 0.3 step the rate **saturates** (≈ 37–47 per 1000 for gaps of 0.3–1.5 steps) instead of rising, so it does not fire at a threshold crossing and still does not say *when* within the active periods. Causal models (completed bars only) separate pair seconds from random seconds with AUC **0.85** (clock alone 0.57, + order-activity ages 0.74, + spot-position block 0.87); adding the *current minute's* move (look-ahead) lifts it to 0.90 and the live-spot proxy to 0.91, i.e. part of the activation is a **movement inside the minute that minute bars cannot see**. | Observed (predictive); trigger **Unresolved** |
| How often is it calculated? | **Still not testable.** The strike and the activation are both consistent with a live-spot comparison made at the order moment; continuous evaluation vs evaluation at firing cannot be separated. | Not testable |

## 1. Which reference does the live spot get compared with?
Hit rate of the strike rule "nearest strike to the live spot + 1 step × sign(live spot − X)" for each pre-registered X (live-spot proxy = linear interpolation between the bracketing minute closes at the order second; diagnostic, uses the current minute's close):
| reference X (direction = sign of live spot − X) | pairs | hit rate | first half | second half | NIFTY | SENSEX | Δ vs spot 15 min ago | 95% CI of Δ |
|---|---|---|---|---|---|---|---|---|
| SMA 60 | 363 | 90.6% | 90.3% | 90.9% | 89.4% | 91.8% | +0.3 pts | +0.0 … +0.9 |
| spot 30 min ago | 363 | 90.4% | 90.3% | 90.4% | 88.8% | 91.8% | +0.0 pts | -0.8 … +0.9 |
| spot 15 min ago | 363 | 90.4% | 90.3% | 90.4% | 89.4% | 91.3% | +0.0 pts | +0.0 … +0.0 |
| SMA 30 | 363 | 90.4% | 90.3% | 90.4% | 89.4% | 91.3% | +0.0 pts | +0.0 … +0.0 |
| spot 10 min ago | 363 | 90.1% | 89.8% | 90.4% | 89.4% | 90.8% | -0.3 pts | -0.9 … +0.0 |
| spot 60 min ago | 363 | 90.1% | 89.2% | 90.9% | 88.3% | 91.8% | -0.3 pts | -1.7 … +0.8 |
| SMA 10 | 363 | 89.5% | 90.3% | 88.8% | 87.7% | 91.3% | -0.8 pts | -2.5 … +0.0 |
| SMA 15 | 363 | 89.5% | 90.3% | 88.8% | 87.7% | 91.3% | -0.8 pts | -2.5 … +0.0 |
| SMA 5 | 363 | 89.3% | 90.3% | 88.2% | 87.2% | 91.3% | -1.1 pts | -2.7 … +0.0 |
| short-book centre | 363 | 79.9% | 80.1% | 79.7% | 77.6% | 82.1% | -10.5 pts | -14.0 … -7.3 |
| last timetable pair strike | 363 | 74.4% | 77.8% | 71.1% | 65.9% | 82.6% | -16.0 pts | -20.4 … -11.8 |
| day mid-range | 363 | 67.2% | 64.2% | 70.0% | 67.0% | 67.4% | -23.1 pts | -29.6 … -17.9 |
| opening ATM | 363 | 62.5% | 60.8% | 64.2% | 64.8% | 60.3% | -27.8 pts | -33.2 … -22.3 |
| last body sell strike | 363 | 46.0% | 52.8% | 39.6% | 42.5% | 49.5% | -44.4 pts | -50.8 … -38.8 |
| last reactive pair strike | 329 | 30.4% | 30.1% | 30.6% | 27.4% | 33.3% | -60.0 pts | -65.4 … -53.8 |

* Trend-type references (red in the figure) are within a point of each other and hold in both halves and both underlyings; book-based and day-based references lose 10–60 points. **Decision rule:** no candidate beats "spot 15 minutes ago" by ≥ 3 points, so no more specific dynamic reference is supported; the family "live spot vs a trailing price" is.
* Why the book anchors fail (inference): the strike side follows the *market*, not the position — a reactive pair is placed toward where the price has been going, even when that is away from the strikes already held.

## 2. Activation: the gap between the spot and its moving average (post-hoc)
A single-feature diagnostic (leave-one-cycle-out gain over clock + order-activity ages, causal features) ranked the spot's distance from its moving averages first:
| feature added to clock + ages (causal) | AUC gain |
|---|---|
| c_d_sma60 | 0.069 |
| c_d_sma30 | 0.048 |
| c_d_sma10 | 0.029 |
| c_d_lo | 0.026 |
| c_d_hi | 0.018 |
| abs_c_m15 | 0.013 |

Greedy forward selection adds only `c_d_sma60`, `c_d_sma10`, `c_d_lo`, `age_lo` in turn (AUC 0.809, 0.847, 0.856, 0.870); the SMA gap carries almost all of the spot-position gain. Events versus random seconds, by control-quintile of the 60-minute gap: the middle quintile (spot within about ±0.1 step of its average) holds 2.8% of events against 20% of controls (ratio 0.14), the two outer quintiles 1.6× and 1.5×.
Minute-level, causal (completed bars, 10:30–15:15, no timetable wave; N = averaging window):
| N (minutes) | AUC of |spot − N-min moving average| | CI low | CI high | half 1 | half 2 | AUC of |spot − spot N min ago| (comparison) |
|---|---|---|---|---|---|---|
| 3 | 0.588 | 0.557 | 0.62 | 0.587 | 0.589 | 0.578 |
| 5 | 0.614 | 0.585 | 0.649 | 0.606 | 0.622 | 0.58 |
| 10 | 0.643 | 0.612 | 0.676 | 0.646 | 0.639 | 0.592 |
| 15 | 0.652 | 0.626 | 0.684 | 0.659 | 0.646 | 0.595 |
| 20 | 0.656 | 0.632 | 0.683 | 0.666 | 0.645 | 0.569 |
| 30 | 0.651 | 0.628 | 0.669 | 0.66 | 0.641 | 0.554 |
| 45 | 0.65 | 0.623 | 0.667 | 0.656 | 0.645 | 0.556 |
| 60 | 0.639 | 0.611 | 0.655 | 0.645 | 0.635 | 0.536 |
| 90 | 0.598 | 0.576 | 0.621 | 0.601 | 0.597 | 0.465 |
| 120 | 0.544 | 0.524 | 0.564 | 0.556 | 0.535 | 0.426 |

* |spot − moving average| separates better than the plain move |spot − spot N min ago| at every N from 10 to 90, and peaks on a plateau at N = 15–45 (AUC about 0.65); N = 3–5 and N ≥ 90 are worse. **The averaging length is not sharply identified** (10–60 fits).
Reactive-pair hazard by |spot − 60-minute average|:
| |spot − 60-min average| (strike steps) | cycle-minutes | reactive-pair minutes | per 1000 |
|---|---|---|---|
| (0.0, 0.05] | 755 | 2 | 2.6 |
| (0.05, 0.1] | 752 | 4 | 5.3 |
| (0.1, 0.2] | 1325 | 20 | 15.1 |
| (0.2, 0.3] | 1140 | 32 | 28.1 |
| (0.3, 0.5] | 1499 | 56 | 37.4 |
| (0.5, 0.75] | 1111 | 51 | 45.9 |
| (0.75, 1.0] | 669 | 26 | 38.9 |
| (1.0, 1.5] | 579 | 27 | 46.6 |
| (1.5, 10.0] | 415 | 10 | 24.1 |

| subset | |gap| < 0.1 step | 0.1 – 0.5 step | ≥ 0.5 step |
|---|---|---|---|
| all | 4.0 | 27.2 | 41.1 |
| first half | 2.6 | 27.0 | 43.4 |
| second half | 5.4 | 27.5 | 38.9 |
| NIFTY | 5.4 | 34.8 | 43.6 |
| SENSEX | 1.7 | 18.0 | 40.2 |

* **Dead zone, then saturation:** the first adjacent step ≥ 2.8× is at 0.1–0.2 step; from 0.3 step on the rate is flat (≈ 37–47 per 1000) and falls only beyond 1.5 steps (few minutes). My pre-registered line for a *threshold* (≥ 3× between adjacent bins) is just missed (2.85×), so I call this a **dead zone around the average**, not a threshold. In points: 0.1 step is about 5 points on NIFTY and 10 on SENSEX (≈ 0.02% of the index, the same "flat" level as the earlier moving-vs-flat result).

## 3. Clustering with other order activity (Observed)
Time since the previous event of each kind, for pair seconds vs random seconds inside the active window:
| time since the last … | events | within 60 s (events) | random seconds | within 300 s (events) | random seconds  | within 900 s (events) | random seconds   |
|---|---|---|---|---|---|---|---|
| previous reactive pair | 329 | 12% | 0% | 24% | 12% | 42% | 38% |
| any body sell | 363 | 34% | 9% | 61% | 41% | 92% | 86% |
| timetable wave | 363 | 6% | 6% | 30% | 25% | 70% | 72% |
| body buy-back | 315 | 13% | 4% | 21% | 15% | 29% | 33% |
| hedge / stop / lump module order | 363 | 36% | 12% | 63% | 46% | 92% | 89% |

* Reactive pairs sit in **bursts of order activity** (other sells, hedge/stop/lump-module orders, buy-backs, a previous reactive pair), not in quiet periods. The hedge-module link is expected: that module reacts to body fills. Whether a common decision loop produces all of these or one causes the other cannot be told apart here.

## 4. Causal vs live-spot
| model (reactive-pair second vs random second, leave-one-cycle-out AUC) | AUC |
|---|---|
| clock only | 0.570 |
| clock + ages | 0.738 |
| CAUSAL (completed bars only): clock + ages + spot_position | 0.865 |
| CAUSAL (completed bars only): clock + ages + atm_dynamics | 0.729 |
| CAUSAL (completed bars only): clock + ages + move | 0.753 |
| CAUSAL: all blocks | 0.854 |
| CAUSAL: all blocks + current-minute move (look-ahead) | 0.896 |
| LIVE-PROXY clock + ages + spot_position | 0.910 |
| LIVE-PROXY clock + ages + atm_dynamics | 0.734 |
| LIVE-PROXY clock + ages + move | 0.855 |
| LIVE-PROXY all blocks | 0.905 |
| LIVE-PROXY all blocks, ages shuffled | 0.882 |
| LIVE-PROXY all blocks, spot_position shuffled | 0.840 |
| LIVE-PROXY all blocks, atm_dynamics shuffled | 0.905 |
| LIVE-PROXY all blocks, move shuffled | 0.908 |

* The big jump comes from the spot-position block even with completed bars only (0.87 vs 0.74); the extra from the current-minute move (+0.04) and the live proxy shows the decision reacting to the spot **within** the minute, consistent with the strike result (live proxy 90% vs completed bar 80%).
* Block shuffles on the live-proxy model: spot position −0.065, order-activity ages −0.023, ATM dynamics and the move block ≈ 0 once the others are in.

## 5. Evidence register
| Claim | Label | Basis |
|---|---|---|
| The reference is the live spot vs a trailing price level (spot N min ago or a 5–60 min moving average); book/day anchors fit worse | **Observed** | 15 pre-registered references, halves, underlyings |
| The exact reference / averaging length (5–60 min) | **Not identifiable** | plateau |
| Almost no reactive pairs when the spot sits on its moving average (rate ≈ 4 vs 27–41 per 1000) | **Observed** (post-hoc discovery) | both halves, both underlyings |
| The gap fires a pair at a threshold | **Not supported** | saturating, biggest adjacent step 2.85× |
| Pairs cluster with other order activity | **Observed** | events vs random seconds |
| Part of the activation is intra-minute movement | **Inferred** | look-ahead / live-proxy gain |
| What exactly activates a pair | **Unresolved** | no complete rule |
| Whether direction/gap is computed every minute | **Not testable** | — |

## 6. Limits and how this could be wrong
* **Post-hoc discovery:** the SMA-gap finding followed a search over ~27 candidate features; it replicates in both halves and both underlyings and in a separate minute-level panel, but it was found, not pre-registered, and the candidate AUCs are not multiplicity-corrected.
* **Live-spot proxy** uses the current minute's close (linear path); the look-ahead part of the activation result should be read as "there is intra-minute information", not as a causal rule.
* **Controls** are random seconds in the active window (30 per event); a different control scheme (e.g. matched to other-sell times) would change the order-activity result.
* **Collinearity:** moving-average gaps, spot-N-minutes-ago and the day's position move together; the plateau means I cannot name one.
* In-sample; D-1 only; 32 cycles; predictive not causal; no source code or tick data.

## 7. Files
`src/bl_act_build.py` (events, controls, features, direction references) → `bl_act_tests.py` (AUC, blocks, lags) → `bl_act_tests2.py` (single-feature diagnostic) → `bl_act_tests3.py` (SMA gap, minute level) → `bl_act_fig.py` → `make_act_report.py`. Outputs `outputs/bl_act_*`, `bl_summary_act*.json`. Tests `tests/test_bl.py` (`test_act_*`).
