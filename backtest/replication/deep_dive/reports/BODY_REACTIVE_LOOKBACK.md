# Algo 8 — is "ATM + 1 step toward the 15-minute move" correct, and how is the look-back taken?

*Investigation only. In-sample, observational (D-1, 363 reactive pairs with a complete 15-minute look-back). Plan written before the tests: `BODY_REACTIVE_LOOKBACK_PLAN.md`. Numbers are read from `outputs/bl_lb_*` and `bl_summary_lb*.json`. Figure: `figures/bl_lb_logic.png`.*

## 0. Verdict on your explanation

| Your statement | Verdict | Evidence |
|---|---|---|
| Direction = spot now vs spot 15 minutes earlier (up / down / ~unchanged) | **Correct in substance, with two refinements:** (a) "spot now" is best read as the **live spot at the order second** (rule on the last completed minute close 80.2%; on a live-spot proxy **90.4%**); (b) **15 minutes is not special** — any look-back from 10 to 60 minutes fits equally (§3). | Observed |
| Strike = previous-minute ATM + 1 strike interval toward the move (24,100 → 24,150 up / 24,050 down) | **Correct for 80% of pairs on the stated rule** (82% NIFTY, 79% SENSEX); **90%** with the live-spot proxy. The rest: +2 steps (14%; 6% live), the ATM itself (3%), the opposite side (4%). Your worked example holds in 8 of 10 pre-selected pairs (§1). | Observed |
| The 15-minute move decides WHERE, not WHETHER, a pair is sold | **Mostly correct.** The pair rate is **2.4×** higher when the 15-minute move is non-flat (CI 1.7–3.5), but it does **not** depend on the direction (up 33 vs down 31 per 1000) or on the size of the move, and flat markets still produce pairs (13.5 per 1000). So the move is **not** what fires a pair. | Observed |
| "We have not established that it checks every minute from open" | **Correct, and it stays that way.** The strike is consistent with a **rolling** window that ends at the order moment — not anchored to a 15-minute grid, the previous block, the open, or the last sell — but minute data cannot tell whether the algorithm computes it every minute or only when it places a pair; both give identical strikes (§3). | Observed (rolling); frequency **not testable** |

## 1. The stated rule and your worked example
Rule: strike = nearest strike to the previous-minute close + step × sign(close[j−1] − close[j−16]); step 50 NIFTY / 100 SENSEX.
* Hit rate **80.2%** (79.5% first half, 80.7% second half). (The earlier report's 79.1% used 368 pairs including 5 before 09:35 whose look-back is clipped at the open; this study uses 363.)
* Offset of the sold strike from the ATM, in the move direction: -2: 1.1%, -1: 2.5%, 0: 2.8%, 1: 80.2%, 2: 13.5%. No 15-minute move was exactly zero.
* **Ten pre-selected pairs** (the first reactive pair of the first ten D-1 cycles by date), written out like your example:
| D-1 date | underlying | order time | previous-minute ATM | spot 15 min earlier | spot now (prev-minute close) | 15-min move (points) | predicted strike | actual strike | match |
|---|---|---|---|---|---|---|---|---|---|
| 2026-06-24 | SENSEX | 11:02:57 | 76800 | 76729.8 | 76772.8 | 43.0 | 76900 | 76900 | yes |
| 2026-06-29 | NIFTY | 11:32:34 | 24050 | 24080.3 | 24056.2 | -24.0 | 24000 | 24000 | yes |
| 2026-07-01 | SENSEX | 11:15:05 | 77000 | 76826.8 | 76979.3 | 152.5 | 77100 | 77100 | yes |
| 2026-07-06 | NIFTY | 10:48:08 | 24400 | 24411.0 | 24411.0 | -0.1 | 24350 | 24450 | no |
| 2026-07-08 | SENSEX | 10:37:31 | 77700 | 77681.6 | 77741.9 | 60.3 | 77800 | 77900 | no |
| 2026-07-13 | NIFTY | 11:12:00 | 24150 | 24122.4 | 24158.0 | 35.5 | 24200 | 24200 | yes |
| 2026-07-15 | SENSEX | 11:32:52 | 77600 | 77521.2 | 77592.0 | 70.8 | 77700 | 77700 | yes |
| 2026-07-20 | NIFTY | 10:30:38 | 24250 | 24210.0 | 24230.2 | 20.3 | 24300 | 24300 | yes |
| 2026-07-22 | SENSEX | 11:30:03 | 76900 | 76826.6 | 76914.6 | 88.1 | 77000 | 77000 | yes |
| 2026-07-27 | NIFTY | 10:32:41 | 23900 | 23928.4 | 23913.5 | -14.9 | 23850 | 23850 | yes |

* The two misses are informative: **2026-07-06** has a 15-minute move of −0.1 point (effectively flat, so the sign is arbitrary) and **2026-07-08** is a +2-step case.

## 2. Direction means a rolling trend, not a 15-minute block
Hit rate of the rule with different direction definitions (all causal; "rolling L" = close[j−1] vs close[j−1−L]):
| direction definition | n | hit rate | 95% CI | minutes 0–4 of the block | 5–9 | 10–14 |
|---|---|---|---|---|---|---|
| rolling 30 | 363 | 81.8% | 77–86% | 78% | 82% | 85% |
| rolling 10 | 363 | 80.2% | 76–85% | 75% | 81% | 85% |
| rolling 15 | 363 | 80.2% | 75–85% | 75% | 83% | 83% |
| rolling 20 | 363 | 79.9% | 75–85% | 74% | 82% | 84% |
| rolling 60 | 363 | 79.6% | 74–84% | 77% | 78% | 83% |
| since previous timetable wave | 363 | 74.9% | 70–80% | 68% | 81% | 77% |
| since previous reactive pair | 329 | 69.3% | 64–75% | 66% | 70% | 72% |
| current block so far | 363 | 68.9% | 64–74% | 51% | 80% | 79% |
| previous 15-min block (open to close) | 363 | 61.4% | 55–68% | 74% | 54% | 54% |
| since previous sell (any) | 363 | 59.5% | 54–65% | 56% | 64% | 60% |
| since the open | 363 | 56.2% | 51–62% | 62% | 52% | 54% |
| direction of latest day extreme | 363 | 49.0% | 43–56% | 51% | 47% | 49% |

* **Anchored definitions fail:** the previous completed 15-minute block gives 61% overall and **5.2%** where it disagrees with the rolling direction (97 pairs; the rolling direction is right in 75% of them). "Current block so far" is only 51% in the first five minutes of a block (little history) and reaches ~79% later — a window that restarts at block boundaries would behave like that; a rolling one does not. Since-open, since-last-sell and latest-extreme are worse; the best anchored one (since the previous timetable wave, 75%) is still below every rolling window.
* **The rolling windows are indistinguishable from each other** (10, 15, 20, 30, 60 minutes: 80%–82%).

## 3. Is 15 minutes special? Is it computed every minute?
Hit rate of the rule for look-back L:
| look-back L (min) | last completed close | live-spot proxy |
|---|---|---|
| 3 | 73.6% | 88.4% |
| 5 | 76.9% | 88.7% |
| 10 | 80.2% | 90.1% |
| 15 | 80.2% | 90.4% |
| 20 | 79.9% | 90.1% |
| 30 | 81.8% | 90.4% |
| 45 | 78.8% | 90.6% |
| 60 | 79.6% | 90.1% |
| 90 | 72.2% | 83.5% |

* **No.** The curve is a broad plateau from 10 to 60 minutes (about 80% on the last completed close, about 90% on the live-spot proxy); on the live proxy L = 15 is at most 1.6 points better than any L in 10…60 and the paired cluster-bootstrap CIs reach 0; on the last-completed-close version L = 30 is the highest (81.8% vs 80.2% at L = 15). L ≤ 7 and L = 90 are worse. **The data say "recent trend over roughly 10–60 minutes", not "15 minutes".** The 15 in your example (and in my earlier wording) is a convenient choice, not an identified parameter.
* **Constant every-minute look-back?** What I can test is what information the strike is consistent with. It is consistent with the spot at the order second and the spot L minutes before **that second** — a window that *ends when the order is placed*. It is not consistent with a direction frozen at a clock time (previous block, open, extreme, last sell). Whether Algo 8 recomputes that comparison every minute (or every second) and a pair fires on some other condition, or computes it only when a pair is placed, **cannot be separated**: both produce the same strike. The firing times themselves are spread uniformly over the seconds of the minute (earlier study), so the firing is not tied to a bar close.

## 4. Live spot, not the last completed bar
Hit rate by the second of the minute at which the order is placed (rule on the last completed minute close vs on a live-spot proxy = linear interpolation between the previous and the current minute close at that second):
| second of the minute | pairs | rule on the last completed minute close | rule on the live-spot proxy |
|---|---|---|---|
| 0–9 | 73 | 89% | 90% |
| 10–19 | 55 | 82% | 91% |
| 20–29 | 64 | 77% | 86% |
| 30–39 | 61 | 88% | 93% |
| 40–49 | 45 | 78% | 98% |
| 50–59 | 65 | 66% | 86% |

* The rule on the last completed close **falls late in the minute** (Spearman with the second: -0.14; 71% for seconds ≥ 40, n = 110) as the live spot drifts away from it; the live proxy is flat (0.00) and 91% late in the minute. Overall 80% → 90% (difference CI +6 to +15 points). **Inference:** the strike is chosen from the live spot at the moment of the order. *Caveat:* the proxy uses the current minute's close (not available at decision time) and a straight-line path; it is a diagnostic of what the decision-time spot looked like, not a causal rule.

## 5. Size of the move and ties
| |15-min move| in strike steps | pairs | hit rate | mean strike offset in the move direction (steps) |
|---|---|---|---|
| (1e-09, 0.1] | 34 | 73.5% | 0.59 |
| (0.1, 0.25] | 64 | 82.8% | 0.88 |
| (0.25, 0.5] | 109 | 78.9% | 1.11 |
| (0.5, 1.0] | 106 | 81.1% | 1.11 |
| (1.0, 2.0] | 45 | 84.4% | 1.11 |
| (2.0, 10.0] | 5 | 60.0% | 1.4 |

* The sign decides the side; the **size does not**: moves from 0.1 to 2 steps all give about +1 step and 79–84% hits. For essentially flat moves (< 0.1 step, n = 34) the side is a coin flip-ish (74% hits) — the case of the 2026-07-06 example. There is no visible dead-band: tiny moves still shift the strike by one step.

## 6. The move and the trigger (your distinction) — hazard of a reactive pair, 10:30–15:15
| 15-min move before the minute | cycle-minutes | reactive-pair minutes | per 1000 |
|---|---|---|---|
| down > 0.1% | 956 | 40 | 41.8 |
| down 0.02-0.1% | 2442 | 65 | 26.6 |
| flat (< 0.02%) | 1919 | 26 | 13.5 |
| up 0.02-0.1% | 2215 | 72 | 32.5 |
| up > 0.1% | 713 | 25 | 35.1 |

* Pairs are **2.4×** more likely in a moving than in a flat 15-minute window (the flat group is 23% of minutes), but direction and size beyond that do not matter, and a direction flip in the last 5 minutes does not raise the rate (24 vs 29 per 1000). Together with the weak predictive tilt found earlier this supports your distinction: **direction → strike; the cause of firing remains unknown.**

## 7. Evidence register
| Claim | Label | Basis |
|---|---|---|
| Strike = ATM + 1 step toward the recent move: 80% (bar) / 90% (live proxy) | **Observed** | 363 pairs, halves, underlyings |
| Look-back length 10–60 minutes fits equally; 15 not special | **Observed** | scan with paired bootstrap |
| Direction is a rolling window ending at the order moment, not anchored to a block / open / event | **Observed** | 5.2% vs 75% on 97 disagreements |
| The decision-time spot is the live spot at the order second | **Inferred** | live proxy vs completed bar, by second |
| Whether Algo 8 recomputes the direction every minute | **Not testable** | same strike either way |
| The move itself fires the pair | **Not supported** | rate ×2.4 moving vs flat, none with direction or size |
| What fires a pair | **Unresolved** | earlier studies |

## 8. Limits and how this could be wrong
* **Live-spot proxy** is an interpolation using the current minute's close; if the true intraminute path is far from a straight line the true hit rate could differ. The qualitative result (the bar-based rule degrades late in the minute, the proxy does not) is robust to that.
* **Look-back identification** is limited by 363 pairs and by strongly overlapping windows; "10–60 minutes" is a plateau of statistically equal rules, not a measured parameter.
* **Reactive-pair labels** use the ±3 s pairing and the timetable cells; mislabelled pairs would lower hit rates.
* **Frequency of evaluation** is not testable with these data; sub-second fills or logs would be needed.
* In-sample; D-1 only; no source code.

## 9. Files
`src/bl_lb_tests.py` (rule, definitions, scan, magnitude, seconds, hazard) → `bl_lb_tests2.py` (live proxy, hazard ratio) → `bl_lb_tests3.py` (live scan) → `bl_lb_fig.py` → `make_lb_report.py`. Outputs `outputs/bl_lb_*`, `bl_summary_lb*.json`. Tests `tests/test_bl.py` (`test_lb_*`).
