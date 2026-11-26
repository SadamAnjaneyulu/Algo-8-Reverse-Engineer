# Algo 8 — reactive pairs in depth (D-1): the 10:30–15:15 gate, the strike rule, and a census of every sell

*Investigation only. In-sample, observational (32 D-1 cycles). Plan written before the tests: `BODY_REACTIVE_MECHANISM_PLAN.md`. Numbers are read from `outputs/bl_mech_*`, `bl_react_*` and `bl_summary_mech*.json`. Figure: `figures/bl_mech_logic.png`.*

## 0. Answers

| Question | Answer | Evidence level |
|---|---|---|
| **Why only after 11:00?** | **It is not 11:00 — it is a hard time gate at 10:30.** Maximum-likelihood start of the active window **10:30** (bootstrap 5–95%: 10:30–10:30), stop **15:15** (15:09–15:15). Inside the window the reactive-pair hazard is **27.7** per 1000 cycle-minutes, outside **3.8** (only 4 reactive-pair minutes before 10:30 and 5 after 15:15, against 228 inside). Same in NIFTY and SENSEX and in both halves of the sample. The first reactive pair of a cycle comes at a median **10:40** (10–90%: 9:38–11:32) because the hazard is ≈ 2.8% per minute after the gate opens; the earlier "11:00" came from averaging by clock hour. | Observed |
| Is it **London open / volume**? | **Not supported.** Option volume peaks at the open and again 14:15–15:00 and is lowest around 11:00–12:00, but the reactive hazard is flat (≈ 20–35 per 1000) across all of that; the gate opens at 10:30 while volume is **falling**. No step at the London open (12:30 IST while the UK is on summer time): hazard 31 vs 20 per 1000 in the block before; volume ×0.92. Spot excursion from the opening strike does not explain the onset either (Spearman 0.12–0.24, permutation p 0.19–0.47). | Observed (not supported) |
| So what *is* the gate? | **The clock — or something deterministic in time.** "Waves done so far", "short lots held" and the clock are not separable: a model with those progress variables but **no clock** reaches AUC 0.633, the clock alone 0.624; all proxies without the clock 0.672, adding the clock 0.690. Why 10:30 is a configuration choice that fills cannot reveal. | Observed; reason **Unresolved** |
| **How do they happen inside the window?** | At a roughly **constant rate of ≈ 2.8% per cycle-minute** (≈ one pair-minute every 36 min; mean 23.5 min between successive reactive pairs), **burstier than a Poisson clock** (CV 1.21; hazard 52 per 1000 in the minute right after a previous pair vs ≈ 17–34 later). **Not** according to spot move %: the hazard is 21–30 per 1000 for 15-min moves of 0–0.3% and almost zero above 0.3% — unlike solo sells, which keep rising. Each firing is usually one pair (77%). | Observed |
| **Which strike?** | **ATM of the previous minute + 1 step in the direction of the recent (15-minute) move: 79.1%** of reactive pairs (first half 79.5%, second half 78.6%; NIFTY 79.8%, SENSEX 78.4%) vs 11.0% for timetable pairs; another 13% are +2 steps. The offset does **not** grow with the size of the move. This is just under my pre-registered 80% line, so I call it **nearly supported**; every other rule (lagged ATM, momentum projection, floor/ceil, synthetic ATM, previous reactive strike) is ≤ 45%. | Observed (near-supported) |
| When does it **stop**? | At the end of the window, **≈ 15:15** (hazard 12 per 1000 in the 15:15–15:30 block vs 27 before); the last reactive pair of a cycle has median 15:01. Between 15:15 and 15:25 there are **0** reactive pairs; then **16 pairs in 9 cycles in the final minutes 15:25–15:30** (15 of them at 15:28 or later) — a closing-time effect outside the gate, not part of the hazard fit (the panel ends at 15:28). | Observed |
| **Any other selling** besides timetable pairs, reactive pairs and solo sells? | **Yes — and no unexplained remainder.** Counting every D-1 sell order of every module (**6,072 lots in 32 cycles**): **hedge-module sells that close long wings = 19.6%** (largest "other" type), **batches of ≥ 3 lots** 9.1% (a sub-type of solo), end-of-day solo sells (≥ 15:00) 3.6%, body sells closing wings 2.7%, near-pairs 0.8% and stop-module wing sales 0.8% (§5). | Observed |

## 1. Definitions (locked in the plan)
Same pair / timetable / reactive definitions as `BODY_REACTIVE_PAIRS.md`. Panel = D-1 cycle-minutes (5–373) without a timetable wave (10,645 rows, 237 reactive-pair minutes). Option volume = CE+PE minute volume of the ATM ±3 strikes; realised volatility = sum of |1-minute returns|; excursion = |spot − opening ATM| in strike steps. Gate = piecewise-constant hazard (low outside, constant inside) fitted by maximum likelihood over start 09:35–11:40 and stop 13:55–15:25 (5-minute grid), cluster bootstrap over cycles (60 draws).

## 2. When it starts and stops (Observed)
Hazard by 15-minute block, with option volume and volatility for comparison:
| block start | reactive pairs per 1000 cycle-min | solo sells per 1000 | buy-backs per 1000 | median option volume (millions / 15 min) | median realised volatility (% / 15 min) |
|---|---|---|---|---|---|
| 9:30 | 9.6 | 62.5 | 12.0 | 163.0 | 0.3 |
| 9:45 | 0.0 | 62.5 | 28.8 | 169.0 | 0.3 |
| 10:00 | 0.0 | 43.3 | 26.4 | 144.0 | 0.3 |
| 10:15 | 7.4 | 84.0 | 61.7 | 149.0 | 0.3 |
| 10:30 | 22.3 | 29.0 | 20.1 | 136.0 | 0.3 |
| 10:45 | 22.8 | 53.2 | 32.9 | 119.0 | 0.2 |
| 11:00 | 24.0 | 55.3 | 36.1 | 115.0 | 0.2 |
| 11:15 | 19.8 | 29.6 | 19.8 | 113.0 | 0.2 |
| 11:30 | 25.8 | 37.5 | 32.8 | 124.0 | 0.2 |
| 11:45 | 55.3 | 67.3 | 52.9 | 116.0 | 0.2 |
| 12:00 | 31.2 | 49.1 | 60.3 | 124.0 | 0.2 |
| 12:15 | 20.1 | 53.6 | 38.0 | 124.0 | 0.2 |
| 12:30 | 31.2 | 44.6 | 73.7 | 137.0 | 0.2 |
| 12:45 | 20.8 | 62.5 | 54.2 | 127.0 | 0.2 |
| 13:00 | 34.9 | 63.2 | 50.1 | 165.0 | 0.2 |
| 13:15 | 17.2 | 27.1 | 29.6 | 121.0 | 0.2 |
| 13:30 | 39.5 | 44.4 | 29.6 | 135.0 | 0.2 |
| 13:45 | 19.2 | 67.3 | 43.3 | 152.0 | 0.2 |
| 14:00 | 31.2 | 33.6 | 38.5 | 147.0 | 0.2 |
| 14:15 | 26.4 | 64.9 | 26.4 | 201.0 | 0.2 |
| 14:30 | 29.1 | 53.7 | 42.5 | 197.0 | 0.2 |
| 14:45 | 20.8 | 85.4 | 14.6 | 189.0 | 0.3 |
| 15:00 | 27.1 | 141.7 | 27.1 | 201.0 | 0.2 |
| 15:15 | 12.0 | 101.0 | 16.8 | 156.0 | 0.3 |

* The step is at **10:30** (block start 10:30: 22 per 1000 vs 0–10 before) and the rate then stays 17–55 per 1000 until 15:15 (the 11:45 block is high, 55). Maximum-likelihood window and bootstrap:
| subset | cycle-minutes | window start | window stop | hazard inside (per 1000) | hazard outside (per 1000) |
|---|---|---|---|---|---|
| NIFTY | 4990 | 10:30 | 15:15 | 29.5 | 2.67 |
| SENSEX | 5655 | 10:30 | 15:15 | 26.03 | 4.71 |
| first half | 5328 | 10:30 | 15:15 | 27.86 | 1.67 |
| second half | 5317 | 10:30 | 15:15 | 27.45 | 5.83 |
| V1 | 6993 | 10:30 | 15:15 | 27.5 | 1.9 |
| V2 | 3652 | 11:00 | 14:30 | 32.06 | 11.52 |

  (The V2 subset has only 11 cycles and a noisier estimate, 11:00–14:30 with a high outside rate; V1 and every other subset give 10:30–15:15.)
* **Volume** is highest at 9:15 (163 million per 15 min in the first listed block) and in 14:15–15:00 (≈ 200), lowest 11:00–12:00 (≈ 115); the hazard does not follow it. Within each clock hour the hazard shows no consistent ordering across the low, mid and high option-volume terciles:
| clock hour | low option volume | mid | high |
|---|---|---|---|
| 9 | 4.5 | 5.3 | 1.9 |
| 10 | 12.7 | 9.9 | 11.2 |
| 11 | 27.1 | 32.6 | 31.3 |
| 12 | 29.1 | 24.4 | 24.3 |
| 13 | 31.3 | 30.5 | 28.6 |
| 14 | 34.5 | 25.0 | 20.1 |
| 15 | 0.0 | 24.4 | 23.4 |

* **Spot excursion from the opening strike:** the first reactive pair is not tied to when the spot first leaves the opening ATM:
| spot excursion from opening ATM | cycles | Spearman with first reactive pair | permutation p | median time reached | share of cycles reaching it AFTER the first reactive pair |
|---|---|---|---|---|---|
| ≥ 1 step | 32 | 0.239 | 0.196 | 9:30 | 0.219 |
| ≥ 1.5 steps | 30 | 0.125 | 0.466 | 10:01 | 0.433 |
| ≥ 2 steps | 29 | 0.166 | 0.406 | 10:18 | 0.552 |
| ≥ 3 steps | 21 | -0.248 | 0.284 | 11:35 | 0.667 |
| day range ≥ 0.2% | 32 | 0.306 | 0.092 | 9:30 | 0.062 |
| day range ≥ 0.3% | 32 | 0.267 | 0.108 | 9:54 | 0.344 |

* **Clock vs proxies** (leave-one-cycle-out gradient boosting; `no clock` = hour/minute removed; ids = underlying and version):
| model (reactive-pair minute, leave-one-cycle-out AUC) | AUC |
|---|---|
| clock only (j) | 0.624 |
| no clock, ids only | 0.482 |
| no clock + volume | 0.600 |
| clock + volume | 0.690 |
| no clock + realised_vol | 0.572 |
| clock + realised_vol | 0.628 |
| no clock + range_open | 0.529 |
| clock + range_open | 0.636 |
| no clock + progress | 0.633 |
| clock + progress | 0.643 |
| all proxies, no clock | 0.672 |
| all proxies + clock | 0.690 |
| all proxies + clock, clock shuffled within cycle | 0.670 |

  Excursion from the open does not help (AUC 0.53); option volume helps only together with the clock (0.69); the "progress" variables (waves done, short lots held, minutes since the last sell) carry the clock's information (0.63) — they are all time-driven, so a calendar gate and a progress gate cannot be told apart with this data.

## 3. How a reactive pair happens inside the window (Observed)
* **Rate:** about 28 per 1000 cycle-minutes, constant through the window; mean 23.5 min between pairs (quartiles 0.2 / 13.1 / 33.9); CV 1.21 > 1 means clustering:
| minutes since previous reactive pair | cycle-minutes in window | reactive-pair minutes | per 1000 |
|---|---|---|---|
| (0, 1] | 213 | 11 | 51.6 |
| (1, 2] | 229 | 4 | 17.5 |
| (2, 3] | 230 | 4 | 17.4 |
| (3, 5] | 440 | 10 | 22.7 |
| (5, 10] | 984 | 18 | 18.3 |
| (10, 20] | 1565 | 33 | 21.1 |
| (20, 40] | 2044 | 69 | 33.8 |
| (40, 400] | 1923 | 54 | 28.1 |

* **Not by spot move %:** reactive pairs vs solo sells by the absolute 15-minute spot move:
| |15-min spot move| (%) | cycle-minutes | reactive-pair minutes | reactive per 1000 | solo sell per 1000 |
|---|---|---|---|---|
| (0.0, 0.1] | 8021 | 168 | 21.0 | 46.8 |
| (0.1, 0.2] | 1959 | 58 | 29.6 | 82.7 |
| (0.2, 0.3] | 441 | 10 | 22.7 | 176.9 |
| (0.3, 5.0] | 218 | 1 | 4.6 | 142.2 |

  Reactive pairs do not follow the solo-sell logic (1-minute breakout / favourable move, `BODY_SOLO_VARIABLE_SEARCH.md`): their rate is nearly flat in the size of the move and vanishes in large moves. The earlier report found only a small tilt from market-move and event-history features; none of that changes.
* **Strike:** pre-registered rules ranked by hit rate on reactive pairs:
| strike rule | reactive pairs (n = 368) | timetable pairs | first half | second half | NIFTY | SENSEX |
|---|---|---|---|---|---|---|
| ATM + 1 step toward 15-min move | 79.1% | 11.0% | 79.5% | 78.6% | 79.8% | 78.4% |
| ATM + 1 step toward 5-min move | 75.8% | 10.9% | 75.0% | 76.6% | 77.6% | 74.1% |
| ATM + 1 step toward 3-min move | 72.6% | 10.9% | 72.2% | 72.9% | 71.6% | 73.5% |
| strike of previous reactive pair | 44.7% | 10.0% | 46.8% | 42.9% | 48.2% | 41.2% |
| nearest(spot + 3x 5-min move) | 39.1% | 45.8% | 39.8% | 38.5% | 38.8% | 39.5% |
| nearest(spot + 2x 5-min move) | 33.7% | 56.7% | 36.4% | 31.2% | 26.8% | 40.5% |
| floor/ceil of spot toward 15-min move | 29.3% | 54.9% | 32.4% | 26.6% | 31.7% | 27.0% |
| floor/ceil of spot toward 5-min move | 28.5% | 53.3% | 30.7% | 26.6% | 31.1% | 25.9% |

  ("ATM" = nearest strike to the previous-minute spot close; the "toward the move" side is the sign of the spot change over 15 / 5 / 3 minutes.) The sold strike lies about 1.1 steps beyond the spot in the direction of the move (quartiles 0.9–1.4), whatever the size of the move.
* **Quantity:** one pair in 77% of firings, at most 3; the number of pairs per firing is not related to lots just bought back (Spearman 0.10) or to the strike drift (-0.02), and only weakly to the 5-minute move (0.27).

## 4. Why not London open? (summary of the evidence)
1. The gate opens at 10:30 IST, two hours before the London open (12:30 IST during UK summer time; UK clocks changed on 2026-10-25, after the last D-1 date used).
2. The hazard shows no step at 12:30 (block 12:30: 31 per 1000; previous block 20); volume rises only ×0.92 and volatility ×0.98.
3. Within each clock hour the rate has no consistent ordering across the low/mid/high option-volume terciles (table above).
4. Caveat: option volume and calendar time are strongly collinear in an intraday panel; what I can say is that volume does not add anything once the clock is in, not that the algorithm ignores volume.

## 5. Census of every D-1 sell (Observed)
All sell orders of all modules on D-1, in the fixed priority of the plan:
| class (D-1 sell orders, all modules) | orders | lots | lots per cycle | share of D-1 sold lots | median clock time | cycles with it |
|---|---|---|---|---|---|---|
| scheduled cell | 2143 | 2143 | 67.0 | 35.3% | 11:01 | 32 |
| hedge-module sell closing a long wing | 600 | 1192 | 37.2 | 19.6% | 12:43 | 31 |
| reactive pair (outside timetable) | 954 | 954 | 29.8 | 15.7% | 13:10 | 32 |
| single solo | 751 | 751 | 23.5 | 12.4% | 12:13 | 32 |
| batch (>= 3 lots, one strike/right, within 3 s) | 321 | 555 | 17.3 | 9.1% | 13:08 | 25 |
| end-of-day solo (>= 15:00) | 220 | 220 | 6.9 | 3.6% | 15:07 | 31 |
| body sell closing a long wing | 134 | 163 | 5.1 | 2.7% | 11:12 | 30 |
| near-pair (CE and PE within 3 s, different strikes) | 19 | 48 | 1.5 | 0.8% | 13:15 | 4 |
| stop-module sell closing a long wing | 10 | 46 | 1.4 | 0.8% | 14:46 | 1 |

* **Total 6,072 lots over 32 cycles; no residual class.** The three types you know (timetable pairs 35.3%, reactive pairs 15.7%, solo = single + batch + end-of-day + near-pair 25.9%) add up to 76.9%; the other **23.1%** is wing-closing sells (hedge module, body, stop module).
* **Hedge-module sells closing long wings** (19.6%; median 12:43; in 31 of 32 cycles) are the unwinds of the wing longs that the hedge module bought (see `BODY_HEDGE_MODULE_DEEP_INVESTIGATION.md`: a balance controller of long wings against short lots). They sell options but reduce protection rather than add short premium.
* **Batches** (≥ 3 lots at one strike and right within 3 s; part of "solo" in the sizing study): 84 batches in 25 cycles, median 4 lots (90%: 6), 81% CE, most often in 15:xx, 10:xx, 12:xx; 7 batches of ≥ 10 lots hold 45% of all batch lots (a few outsized orders, up to 54 lots in one order at 15:15–15:31 in one NIFTY cycle).
* **Near-pairs** (CE and PE within 3 s at different strikes) are minor (19 orders in 4 cycles), and stop-module wing sales occur in one cycle.

## 6. Evidence register
| Claim | Label | Basis |
|---|---|---|
| Reactive pairs are gated to 10:30–15:15 (hazard 27.7 vs 3.8 per 1000) | **Observed** | ML window, bootstrap, subsets |
| The 10:30 start is not explained by volume, spot excursion or the London open | **Observed** (not supported) | volume strata, excursion correlation, 12:30 check |
| Calendar gate vs progress gate | **Not separable** | progress variables are deterministic in time |
| Inside the window: flat ≈ 2.8%/min, bursty, not move-triggered | **Observed** | inter-arrival, move hazard |
| Strike = previous-minute ATM + 1 step toward the 15-min move (79.1%) | **Observed** (near-supported, 80% line missed) | 368 pairs, halves, underlyings |
| What fires an individual pair | **Unresolved** | no feature gives a rule |
| Other sells: hedge wing unwinds 19.6%, batches 9.1%, EOD solo 3.6%, body wing sells 2.7%, minor others | **Observed** | census, no residual |
| Why 10:30 / 15:15 | **Unresolved** | configuration |

## 7. Limits and how this could be wrong
* **Minute data**: a trigger on ticks or the live ATM inside the minute would look like a flat hazard with a tilt. The strike rule is evaluated on previous-minute closes.
* **Gate estimation** assumes a two-level hazard; a gradual ramp would show as a less sharp profile, but the likelihood profile peaks sharply at 10:30 (figure B).
* **Time gate vs progress gate** cannot be separated (waves done is a function of time in this strategy).
* **±3 s pairing:** coincident solo sells at one strike would be called a pair; batches and near-pairs are defined on the same rule.
* **Census classes** use fixed priority; a sell that fits two types is counted in the first (order in the plan). Hedge-module classification comes from earlier contract-level roles.
* In-sample; D-1 only; 32 cycles; predictive not causal; no source code.

## 8. Files
`src/bl_mech_panel.py` → `bl_mech_tests1.py` (onset, volume, clock vs proxies) → `bl_mech_strike.py` → `bl_mech_tests2.py` (gate, inter-arrival) → `bl_mech_census.py` → `bl_mech_fig.py` → `make_mech_report.py`. Outputs `outputs/bl_mech_*`, `bl_summary_mech*.json`. Tests `tests/test_bl.py` (`test_mech_*`).
