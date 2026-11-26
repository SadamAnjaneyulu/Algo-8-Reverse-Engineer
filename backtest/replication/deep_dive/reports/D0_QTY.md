# Algo 8 — D0 quantity: lot sizes, order execution, position management

*Plan `D0_QTY_PLAN.md`, written before the tests. In-sample: D0 of the 33 live cycles with orders; Parts B and C use the 30 cycles that also have the minute data, 19 of them without a stop. Figure: `figures/bl_d0u_summary.png`. Lots are 65 contracts (NIFTY) / 20 (SENSEX); a lot is about ₹15.5 lakh of notional on both.*

## 0. Result

| question | answer | evidence |
|---|---|---|
| How big is an order? | **Body orders are single lots**: 91% of body sells and 91% of buy-backs are 1 lot. A "multi-lot sale" is several 1-lot orders sent in the same second (69% of gaps are 0 s). Hedge, lump and stop orders are sized orders (median 2 / 2 / 6 lots). | Observed |
| Are big orders split? | Yes. All 125 events above 27 lots (NIFTY) / 50 (SENSEX) are split into several orders. NIFTY order size tops out at **27 lots (1,755 contracts) June–September** (the cap binds: 53 orders sit exactly at 27 in September) and at **54 lots (3,510) in October**. SENSEX tops out at 50 lots (1,000), seen in August and September, once per month. | Observed (maxima); the exchange rule itself not read |
| What price do they send? | **Limit = LTP × (1 ± 0.15)**, i.e. a marketable limit 15% through the price (median 14.8% from the first fill; body sells 14.7%, tight, CV 0.20). Body orders are DAY, hedge and lump orders IOC. It is protection: the reference price (limit ÷ 1.15) is within 1.3% of the first fill (median). **My D-1 engine used 1%; corrected to 15% in this commit.** | Observed |
| At what price do they fill? | Fills come within 1 s. Against the minute bar of the option: sells fill at **0.30** of the low–high range, buys at **0.62** (both on the adverse side of the middle); 2.7% of fills are outside the bar. Median gap to the bar close 4.1%, signed bias vs close ≈ 0 (-0.2% sells, 0.6% buy-backs). Part is selection (the system trades price moves), not only spread. | Observed; cause not separable |
| Which quantities follow a rule? | Scheduled pair: every order 1 lot, CE and PE together (the 6-second bucket first used merged adjacent waves, see addendum). **Hedge wave = the gap S−L in 93.6%** of 5202 events (96.1% are ≤ gap). Wing release ≤ long excess in 97.0% (88.8% exactly equal). Lump order ≤ long excess in 94.2%. | Observed |
| Is the number of lots in a sale or buy-back predictable? | **Only weakly: not found by the rule I set (solo sells associated, buy-backs associated).** Solo sells: median 1 lot per cell (51% single); the model cuts the error 19% vs the best baseline but ρ is 0.46 and it hits the exact count less often than "always 1" (41% vs 51%). Buy-backs: median 2 lots per cell, error −14%, ρ 0.50. Ladder depth does not set the count (ρ 0.01). | Observed; rule threshold not met |
| Is it a fixed ratio or fixed premium? | No. Counter-sell lots ÷ same-minute buy-back lots: median 1.0, IQR 0.38–2.00, exactly equal in 22%. A buy-back takes a median 2.5% of the right's open lots per cell (IQR 1.4%–5.7%). Lots do not scale with premium or notional (ρ ≤ 0.14). | Observed |
| How big does the book get? | Peak shorts on one right: **NIFTY 140 lots** (IQR 120–167), **SENSEX 112** (71–164); about ₹22 / ₹16 crore of notional. Carry-in from D-1 ≈ 56 / 46 lots per right; peak around minute 278 / 236 after 09:15. At 15:08 (no-stop cycles) 128 lots short in total, all hedged 1:1. 92% of right-days end flat. | Observed |
| Is there a position cap? | **No ceiling observed.** The peak varies across cycles (CV 0.35; at most 50% of cycles within ±10% of the group median), and selling does not slow near the typical peak (rate 27% vs 23%). Not a proof of no cap: 4–8 cycles per group, and a margin or capital limit is not visible here. | Observed; low power |
| Does the book change selling? | **No inventory feedback.** Adding shorts, CE–PE imbalance and distance to the typical peak gives AUC +0.0005 (CI -0.0010 to 0.0018) on top of spot and book features. | Observed |
| Is the book balanced between CE and PE? | No. Solo sells go to the **lighter** right only 39% of the time (n=4915, p<0.001), i.e. to the heavier right 61%; median |CE−PE| gap 50 lots. Only opening solos are even (49%). | Observed |
| What does protection cost? | The hedge keeps long = short in 93% of active minutes (mean L/S 0.9999). Wings bought cost 2.2% of the premium sold, **0.7% net** of what is sold back (medians over cycles). | Observed |
| What happens at a stop? | Just before the stop: median 67 lots short (about ₹11 crore), hedged 1.00×. The stop module then sends 35 orders / 233 lots (shorts bought back and longs sold) in a median 40 s, 6 lots per order; partial fills on 36% of its orders. | Observed |

**What this means for the 3-year backtest** (table at the end): the *quantity* of the hedge, the scheduled pairs and the clearance is rule-exact; the quantity of solo sells and buy-backs is **not** reconstructable beyond a distribution, so a free-running backtest will get the count wrong event by event (it already shows lot F1 ≈ 0.4). The decision for you at the end is how to size those.

## 1. Order execution (Part A)

### A1 Size and splitting (D0)

| klass | orders | lots | lots_per_order_med | lots_per_order_p90 | lots_per_order_max | single_lot_orders | events | lots_per_event_med | lots_per_event_p90 | lots_per_event_max | orders_per_event_med |
|---|---|---|---|---|---|---|---|---|---|---|---|
| body buy-back | 9335 | 11498 | 1 | 1 | 42 | 0.91 | 4194 | 2 | 5 | 159 | 1 |
| body long buy | 1067 | 1216 | 1 | 2 | 15 | 0.89 | 475 | 1 | 5 | 66 | 1 |
| body long sell | 831 | 2496 | 1 | 6 | 54 | 0.71 | 594 | 1 | 3 | 159 | 1 |
| body sell | 8955 | 10190 | 1 | 1 | 54 | 0.91 | 5907 | 1 | 3 | 121 | 1 |
| hedge other | 153 | 787 | 2 | 12.8 | 27 | 0.37 | 118 | 2 | 10.6 | 240 | 1 |
| lump salvage | 312 | 952 | 2 | 6 | 37 | 0.44 | 312 | 2 | 6 | 37 | 1 |
| other | 7 | 32 | 3 | 8.8 | 16 | 0.14 | 7 | 3 | 8.8 | 16 | 1 |
| stop module | 387 | 3515 | 6 | 24.8 | 37 | 0.15 | 108 | 24 | 72.3 | 262 | 3 |
| wing buy | 5242 | 9370 | 1 | 3 | 27 | 0.67 | 5202 | 1 | 3 | 174 | 1 |
| wing sell | 3670 | 9941 | 2 | 5 | 43 | 0.5 | 3124 | 2 | 6 | 174 | 1 |

*An event = orders of the same module, role and right with gaps ≤ 2 s.*

Largest order by month (D0):

| und | month | orders | gcd_qty | max_order_lots | max_order_qty | n_orders_at_max |
|---|---|---|---|---|---|---|
| NIFTY | 2026-06 | 2603 | 65 | 27 | 1755 | 15 |
| NIFTY | 2026-07 | 4103 | 65 | 27 | 1755 | 10 |
| NIFTY | 2026-08 | 3305 | 65 | 27 | 1755 | 18 |
| NIFTY | 2026-09 | 2703 | 65 | 27 | 1755 | 53 |
| NIFTY | 2026-10 | 1362 | 65 | 54 | 3510 | 3 |
| SENSEX | 2026-06 | 2290 | 20 | 23 | 460 | 1 |
| SENSEX | 2026-07 | 6497 | 20 | 43 | 860 | 1 |
| SENSEX | 2026-08 | 2401 | 20 | 50 | 1000 | 1 |
| SENSEX | 2026-09 | 1567 | 20 | 50 | 1000 | 1 |
| SENSEX | 2026-10 | 3128 | 20 | 29 | 580 | 1 |

### A2 Limit price

| klass | side | n | buf_med | buf_p05 | buf_p95 | buf_cv | share_within_1tick_of_15pct |
|---|---|---|---|---|---|---|---|
| body buy-back | Buy | 9335 | 0.145 | 0.033 | 0.2 | 0.518 | 0.228 |
| body long buy | Buy | 1067 | 0.129 | 0 | 0.214 | 0.804 | 0.658 |
| body long sell | Sell | 831 | 0.139 | 0 | 0.2 | 0.505 | 0.925 |
| body sell | Sell | 8955 | 0.147 | 0.106 | 0.178 | 0.202 | 0.168 |
| hedge other | Buy | 116 | 0.155 | 0.082 | 0.571 | 0.766 | 0.698 |
| hedge other | Sell | 37 | 0.146 | 0.065 | 0.371 | 0.526 | 0.622 |
| lump salvage | Buy | 1 | 0.038 | 0.038 | 0.038 |  | 0 |
| lump salvage | Sell | 311 | 0.222 | 0 | 0.667 | 0.702 | 0.569 |
| other | Buy | 1 | 0.027 | 0.027 | 0.027 |  | 0 |
| other | Sell | 6 | 0.1 | 0 | 0.2 | 1.095 | 1 |
| stop module | Buy | 213 | 0.157 | 0.108 | 0.318 | 0.402 | 0.249 |
| stop module | Sell | 174 | 0.144 | 0 | 0.2 | 0.376 | 0.678 |
| wing buy | Buy | 5242 | 0.156 | 0.091 | 0.364 | 0.522 | 0.746 |
| wing sell | Sell | 3670 | 0.171 | 0 | 0.5 | 0.645 | 0.653 |

*`buf` = limit beyond the first fill, as a share of the fill. Only 40% of orders are within one tick of "fill × 1.15" because the limit is set from the LTP at decision time, which differs from the fill by a median 1.3%. By price level the buffer is a constant ~15% from ₹1 up (rupee gap grows with price); below ₹1 it is 20% (tick size).*

### A3 Order type and fills

| module | klass | validity | orders | lots | partial | multi_fill | fill_secs_med | fill_secs_p90 |
|---|---|---|---|---|---|---|---|---|
| h_ | hedge other | IOC | 153 | 787 | 0.078 | 0.078 | 1 | 1 |
| h_ | wing buy | IOC | 5242 | 9370 | 0.019 | 0.018 | 1 | 1 |
| h_ | wing sell | IOC | 3670 | 9941 | 0.04 | 0.04 | 1 | 1 |
| m_ | other | IOC | 7 | 32 | 0.143 | 0.143 | 1 | 1 |
| num | body buy-back | DAY | 9335 | 11498 | 0.025 | 0.025 | 1 | 1 |
| num | body long buy | DAY | 1067 | 1216 | 0.008 | 0.008 | 1 | 1 |
| num | body long sell | DAY | 831 | 2496 | 0.055 | 0.055 | 1 | 1 |
| num | body sell | DAY | 8955 | 10190 | 0.028 | 0.028 | 1 | 1 |
| s_ | stop module | DAY | 229 | 2249 | 0.441 | 0.441 | 1 | 1 |
| s_ | stop module | IOC | 158 | 1266 | 0.253 | 0.253 | 1 | 1 |
| v_ | lump salvage | IOC | 312 | 952 | 0.054 | 0.054 | 1 | 1 |

*The log holds only orders with at least one fill (lots filled = lots ordered in 99.99%), so IOC orders that found no fill, rejections and cancels are **not visible**.*

### A4 Fill vs the minute bar

| klass | side | n | outside_bar | pos_med | pos_p25 | pos_p75 | abs_gap_to_close_med | signed_vs_close_med | bar_width_med |
|---|---|---|---|---|---|---|---|---|---|
| body buy-back | Buy | 9335 | 0.037 | 0.603 | 0.342 | 0.831 | 0.044 | 0.006 | 0.172 |
| body long buy | Buy | 1067 | 0.011 | 0.5 | 0.333 | 0.833 | 0.068 | 0.014 | 0.2 |
| body long sell | Sell | 831 | 0.006 | 0.25 | 0 | 0.5 | 0.035 | 0 | 0.176 |
| body sell | Sell | 8955 | 0.043 | 0.335 | 0.138 | 0.61 | 0.04 | -0.002 | 0.139 |
| hedge other | Buy | 116 | 0 | 0.5 | 0.333 | 0.8 | 0.041 | 0 | 0.167 |
| hedge other | Sell | 37 | 0 | 0.25 | 0.131 | 0.42 | 0.037 | 0.022 | 0.391 |
| lump salvage | Buy | 1 | 0 | 0.5 | 0.5 | 0.5 | 0.008 | -0.008 | 0.045 |
| lump salvage | Sell | 311 | 0.003 | 0.1 | 0 | 0.5 | 0.056 | 0 | 0.242 |
| other | Buy | 1 | 0 | 1 | 1 | 1 | 0 | 0 | 0.054 |
| other | Sell | 6 | 0 | 0.417 | 0.333 | 0.625 | 0.1 | -0.1 | 0.6 |
| stop module | Buy | 213 | 0.084 | 0.529 | 0.312 | 0.902 | 0.064 | 0.036 | 0.309 |
| stop module | Sell | 174 | 0.062 | 0.343 | 0.109 | 0.598 | 0.05 | 0 | 0.25 |
| wing buy | Buy | 5242 | 0.002 | 0.667 | 0.5 | 1 | 0.029 | 0 | 0.083 |
| wing sell | Sell | 3670 | 0.003 | 0.2 | 0 | 0.5 | 0.038 | 0 | 0.167 |

### A5 Dripping inside events

| klass | events | multi_order_events | share_multi | orders_per_multi_med | orders_per_multi_p90 | span_s_med | same_second_gap_share | gap_s_med | lots_per_order_in_multi |
|---|---|---|---|---|---|---|---|---|---|
| body buy-back | 4194 | 1809 | 0.43 | 3 | 6 | 0 | 0.78 | 0 | 1 |
| body long buy | 475 | 161 | 0.34 | 3 | 9 | 0 | 0.76 | 0 | 1 |
| body long sell | 594 | 115 | 0.19 | 2 | 5 | 0 | 0.78 | 0 | 1 |
| body sell | 5907 | 1466 | 0.25 | 2 | 5 | 0 | 0.69 | 0 | 1 |
| hedge other | 118 | 7 | 0.06 | 4 | 11 | 0 | 0 | 0 | 8.5 |
| lump salvage | 312 | 0 | 0 |  |  |  |  |  |  |
| other | 7 | 0 | 0 |  |  |  |  |  |  |
| stop module | 108 | 81 | 0.75 | 4 | 7 | 0 | 0 | 0 | 9.25 |
| wing buy | 5202 | 17 | 0 | 2 | 6.4 | 0 | 0 | 0 | 19 |
| wing sell | 3124 | 375 | 0.12 | 2 | 3.6 | 0 | 0 | 0 | 2 |

## 2. Lots per event (Part B)

### B2 Rule-exact quantities

| test | n | share_fit | share_equal_sides | median_lots_each_side |
|---|---|---|---|---|
| scheduled pair is exactly 1 CE + 1 PE lot | 765 | 0.865 | 0.956 | 1 |
| wing-buy event lots == S-L gap before the event (all) | 5202 | 0.936 |  | 1 |
| wing-buy event lots <= S-L gap before (all) | 5202 | 0.961 |  |  |
| wing-buy event lots == S-L gap before the event (NIFTY) | 2594 | 0.944 |  | 1 |
| wing-buy event lots <= S-L gap before (NIFTY) | 2594 | 0.975 |  |  |
| wing-buy event lots == S-L gap before the event (SENSEX) | 2608 | 0.927 |  | 1 |
| wing-buy event lots <= S-L gap before (SENSEX) | 2608 | 0.948 |  |  |
| wing-sell event lots <= long excess L-S before | 3121 | 0.97 |  | 2 |
| wing-sell event lots == long excess L-S before | 3121 | 0.888 |  |  |
| lump-salvage order lots <= long excess L-S before | 311 | 0.942 |  | 2 |

### B3 Size models (leave-one-cycle-out; baselines and placebo)

| task | model | n | exact | within1 | mae | rho | rel_mae_vs_best_baseline | ci_lo | ci_hi |
|---|---|---|---|---|---|---|---|---|---|
| solo sells: lots per cell given a sale | baseline: class median (other cycles) | 2103 | 0.514 | 0.711 | 1.489 |  |  |  |  |
| solo sells: lots per cell given a sale | baseline: previous event of the same cycle and right | 2103 | 0.354 | 0.622 | 1.874 | 0.144 |  |  |  |
| solo sells: lots per cell given a sale | baseline: always 1 lot | 2103 | 0.514 | 0.711 | 1.489 |  |  |  |  |
| solo sells: lots per cell given a sale | LOCO boosting: causal (before the minute) | 2103 | 0.406 | 0.772 | 1.204 | 0.465 | -0.191 | -0.218 | -0.166 |
| solo sells: lots per cell given a sale | LOCO boosting: causal + same-minute buy-backs | 2103 | 0.415 | 0.771 | 1.194 | 0.484 | -0.198 | -0.231 | -0.164 |
| solo sells: lots per cell given a sale | LOCO boosting: ladder depth only (gap_fav) | 2103 | 0.189 | 0.753 | 1.559 | 0.026 | 0.047 | -0.011 | 0.099 |
| solo sells: lots per cell given a sale | placebo (training targets shuffled), ladder depth only (gap_fav) | 2103 | 0.197 | 0.806 | 1.517 |  | 0.019 |  |  |
| buy-back events: lots per cell given a buy-back | baseline: class median (other cycles) | 1964 | 0.194 | 0.733 | 2.221 |  |  |  |  |
| buy-back events: lots per cell given a buy-back | baseline: previous event of the same cycle and right | 1964 | 0.289 | 0.556 | 2.76 | 0.218 |  |  |  |
| buy-back events: lots per cell given a buy-back | baseline: always 1 lot | 1964 | 0.411 | 0.605 | 2.399 |  |  |  |  |
| buy-back events: lots per cell given a buy-back | LOCO boosting: causal book/market (before the minute) | 1964 | 0.229 | 0.668 | 1.974 | 0.444 | -0.111 | -0.145 | -0.076 |
| buy-back events: lots per cell given a buy-back | LOCO boosting: plus bar of the minute (crossing counts) | 1964 | 0.253 | 0.67 | 1.903 | 0.496 | -0.143 | -0.173 | -0.105 |
| buy-back events: lots per cell given a buy-back | LOCO boosting: only crossing count n_cross14 | 1964 | 0.179 | 0.685 | 2.144 | 0.267 | -0.035 | -0.055 | -0.011 |
| buy-back events: lots per cell given a buy-back | placebo (training targets shuffled), only crossing count n_cross14 | 1964 | 0.184 | 0.687 | 2.231 | 0.08 | 0.004 |  |  |

*Rule set in the plan: "found" = error ≥ 20% below the best baseline **and** ρ ≥ 0.5 (CI of the error change below 0); "associated" = ρ ≥ 0.3; else "unresolved". Verdicts: solo causal **associated**, solo + same-minute buy-backs **associated**, buy-back causal **associated**, buy-back with the bar of the minute **associated**, solo ladder-depth only **unresolved**. The model beats the baselines on average error (placebo does not) but is worse than "always 1 lot" at hitting the exact count: it ranks sizes, it does not decide them.*

### B4 Size against the book

| what | n | median | q25 | q75 | share_ratio_1 | rho |
|---|---|---|---|---|---|---|
| counter-sell lots / other-right buy-back lots (same minute) | 730 | 1 | 0.385 | 2 | 0.215 | 0.203 |
| solo-sell lots / own-right short lots open | 2103 | 0.022 | 0.011 | 0.043 |  | 0.068 |
| buy-back lots / right lots open | 1964 | 0.025 | 0.014 | 0.057 | 0.002 | 0.055 |

### B5 Scaling with premium

| what | n_events | rho_lots_vs_price | med_lots | premium_value_cv |
|---|---|---|---|---|
| solo type: counter-sell solo | 687 | 0.138 | 2 | 1.262 |
| solo type: extreme solo | 164 | -0.086 | 2 | 1 |
| solo type: late solo | 16 | 0.086 | 1 | 0.908 |
| solo type: opening solo | 96 | 0.107 | 6 | 0.964 |
| solo type: other solo | 750 | 0.101 | 1 | 0.856 |
| solo type: replacement solo | 573 | 0.137 | 2 | 1.566 |
| buy-back cells | 1964 | -0.03 | 2 |  |

*Buy-back cells: lots == number of lots whose minute high is ≥ 1.4× entry in 4.7% of cells; ≤ that number in 47%; == 10% of open lots in 5.1%. The system does not buy back "everything that crossed".*

## 3. Position management (Part C)

### C1 Book level and shape (no-stop cycles unless stated)

| und | version | cp | cycles | carry_in | peak | peak_minute | shorts_1509 | shorts_final |
|---|---|---|---|---|---|---|---|---|
| NIFTY | V1 | CE | 8 | 55.5 | 149.5 | 284 | 52.5 | 0 |
| NIFTY | V1 | PE | 8 | 58 | 113 | 196.5 | 32.5 | 0 |
| NIFTY | V2 | CE | 4 | 58.5 | 82.5 | 148 | 0 | 0 |
| NIFTY | V2 | PE | 4 | 42.5 | 106 | 39.5 | 0 | 0 |
| SENSEX | V1 | CE | 11 | 50 | 98 | 230 | 14 | 0 |
| SENSEX | V1 | PE | 11 | 19 | 66 | 194 | 19 | 0 |
| SENSEX | V2 | CE | 6 | 38.5 | 103 | 250 | 48 | 0 |
| SENSEX | V2 | PE | 6 | 19.5 | 42 | 129 | 20.5 | 0 |

### C2 Ceiling test

| und | version | cp | measure | cycles | median_peak | cv | min | max | share_within_10pct_of_median |
|---|---|---|---|---|---|---|---|---|---|
| NIFTY | V1 | CE | lots | 6 | 162 | 0.2 | 127 | 209 | 0.333 |
| NIFTY | V1 | CE | notional (lakh) | 6 | 2548.23 | 0.197 | 2010.14 | 3226 | 0.333 |
| NIFTY | V1 | PE | lots | 6 | 123 | 0.272 | 74 | 172 | 0.333 |
| NIFTY | V1 | PE | notional (lakh) | 6 | 1953.76 | 0.278 | 1142.22 | 2735.13 | 0.333 |
| NIFTY | V2 | CE | lots | 1 | 67 |  | 67 | 67 | 1 |
| NIFTY | V2 | CE | notional (lakh) | 1 | 984.572 |  | 984.572 | 984.572 | 1 |
| NIFTY | V2 | PE | lots | 1 | 166 |  | 166 | 166 | 1 |
| NIFTY | V2 | PE | notional (lakh) | 1 | 2439.39 |  | 2439.39 | 2439.39 | 1 |
| SENSEX | V1 | CE | lots | 8 | 130 | 0.341 | 73 | 188 | 0.25 |
| SENSEX | V1 | CE | notional (lakh) | 8 | 2004.27 | 0.338 | 1125.44 | 2916.81 | 0.25 |
| SENSEX | V1 | PE | lots | 8 | 110.5 | 0.448 | 59 | 175 | 0 |
| SENSEX | V1 | PE | notional (lakh) | 8 | 1708.56 | 0.453 | 915.381 | 2708.47 | 0 |
| SENSEX | V2 | CE | lots | 4 | 150.5 | 0.363 | 92 | 202 | 0 |
| SENSEX | V2 | CE | notional (lakh) | 4 | 2186.1 | 0.354 | 1365.07 | 2936.84 | 0 |
| SENSEX | V2 | PE | lots | 4 | 50.5 | 0.54 | 34 | 109 | 0.5 |
| SENSEX | V2 | PE | notional (lakh) | 4 | 734.962 | 0.552 | 494.319 | 1617.31 | 0.5 |

*Hazard of a body sale in a minute when shorts on that right are within 10% of the leave-one-out typical peak: 26.7% (4323 cells) against 23.2% otherwise; hour-matched ratio 1.19. Rule: a cap needs ≥ 70% of cycles within ±10% **and** a hazard drop of ≥ 50%. Neither holds. Groups with one cycle (NIFTY V2) are trivially "within 10%" and are not counted.*

### C3 Does the book feed back on selling?

| model | auc | lo | hi | cells | positives | gain_vs_base |
|---|---|---|---|---|---|---|
| base (time of day, side, underlying) | 0.7832 | 0.7587 | 0.8084 | 13490 | 3258 | 0 |
| base + spot | 0.8212 | 0.7925 | 0.8484 | 13490 | 3258 | 0.038 |
| base + spot + book (existing features) | 0.8323 | 0.8128 | 0.8512 | 13490 | 3258 | 0.0491 |
| base + spot + book + inventory (S, CE-PE imbalance, S vs cap) | 0.8328 | 0.8136 | 0.8514 | 13490 | 3258 | 0.0496 |
| base + inventory only | 0.7825 | 0.7596 | 0.8075 | 13490 | 3258 | -0.0007 |

### C4 Balance after solo sales

| type | n | share_to_lighter_right | binom_p | median_imbalance_before | share_cycles_ge_0_5 |
|---|---|---|---|---|---|
| all solo sells | 4915 | 0.392 | 0 | 37 | 0.154 |
| counter-sell solo | 1684 | 0.397 | 0 | 38 | 0.32 |
| extreme solo | 406 | 0.3 | 0 | 61.5 | 0.238 |
| late solo | 39 | 0.436 | 0.522 | 16 | 0.286 |
| opening solo | 286 | 0.493 | 0.859 | 2 | 0.458 |
| other solo | 1136 | 0.434 | 0 | 32 | 0.261 |
| replacement solo | 1364 | 0.355 | 0 | 45 | 0.16 |

### C5 Hedge ratio and wing cost (D0, per cycle, medians)

| und | cid | stop_cycle | premium_sold | body_bought_back | wing_bought | wing_sold | wing_net_cost | wing_net_pct_of_premium_sold | wing_bought_pct_of_premium_sold | gross_wing_lots | body_sell_lots |
|---|---|---|---|---|---|---|---|---|---|---|---|
| NIFTY | 6 | 0 | 14480.2 | 17183.7 | 312.35 | 167.55 | 81.25 | 0.006 | 0.022 | 310 | 325 |
| SENSEX | 23 | 0 | 38042.3 | 46970.3 | 886.65 | 675.3 | 290.7 | 0.007 | 0.021 | 244 | 307 |

### C6 Exposure at the stop and at 15:08

| event | cid | minute | S_CE | S_PE | L_CE | L_PE | stop_orders | stop_lots | stop_lots_per_order_med | stop_span_s | lot_notional_lakh | S_total | L_total | short_notional_lakh |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 15:08 close, no stop | 17 | 354 | 57 | 38 | 57 | 38 | 0 | 0 |  |  | 15.44 | 128 | 128 | 1933.71 |
| stop (minute before the first stop order) | 14 | 3 | 37 | 31 | 37 | 30 | 35 | 233 | 6 | 39.73 | 15.47 | 67 | 67 | 1055.55 |

## 4. Adversarial read: what could be wrong

* **Counts come from one-minute cells.** The system drips 1-lot orders inside a minute (D-1: "one lot each time the price prints a new extreme"). The count is set by the tick path, which these bars cannot show, so "weakly predictable" may be "predictable with ticks". *Not testable here.*

* **Fill position in the bar is partly selection.** A system that sells after a premium drop will print sells in the lower part of the bar whatever its execution quality. The numbers are right for *this* system's fills; they are not a spread estimate.

* **Cap test is underpowered.** 1–8 cycles per underlying × version × right. "No ceiling observed" is the strongest honest statement; a margin or capital limit would not show in lot counts anyway.

* **State reconstruction.** Running shorts / longs per right are rebuilt from the order log; the change in S equals the lots of the order in 98.9% of body sells (97.9% for wing buys), the rest are same-second ordering ties.

* **Scale is the real system's, not yours.** About 130 lots per right at peak is roughly ₹20 crore of notional per right. The backtest has to say what scale it runs at (see below).

* **Discovery data.** Everything here is in-sample on the 32 cycles; nothing here has been tested on cycles it did not see.

## 5. For the backtest: quantity and price rule per class

| class | quantity rule to use | fill price rule | evidence |
|---|---|---|---|
| scheduled pair | 1 CE + 1 PE lot at each timetable second | order-minute close (±0.6% median bias), stress ±4% | quantity Observed, rule-exact |
| hedge wing buy | exactly the gap S−L on the right (≈ 94%), IOC | order-minute close | Observed, rule-exact |
| wing release / lump salvage | ≤ long excess L−S; release size 2 lots per order (median) | order-minute close | partly (size < excess in 11%) |
| clearance (15:09+) | all shorts, in 1-lot orders in the same seconds | order-minute close | Observed (D0_STOP_CLEAR) |
| solo sells | **distribution, not a rule:** median 1 lot per minute-cell (51% single, long tail); size ranked by features (ρ ≈ 0.47) | order-minute close | associated |
| buy-backs | **distribution:** median 2 lots per cell (41% single); ranked by crossing counts (ρ ≈ 0.50) | order-minute close | associated |
| stop liquidation | the whole book in sized orders (median 6 lots) over ~40 s | order-minute close, expect partial fills | Observed |
| order envelope | 1-lot DAY orders for body, IOC for hedge/lump, limit = LTP×(1±0.15), split at 27 (NIFTY, 54 from October) / 50 (SENSEX) lots | — | Observed |

## 6. Next
* Decision needed for the backtest: run the quantity of solo sells and buy-backs (a) drawn from the fitted distribution per class and cell features, (b) fixed at the class median (1 lot / 2 lots), or (c) scaled to your own capital instead of the real system's ~₹20 crore per right. Each is a different experiment.
* Remaining unresolved from earlier steps: other solo, far-OTM roll-out, small pair types, burst trigger.


## Addendum — written after the first results (not pre-registered)
* **Scheduled-pair 1+1 check.** My first test grouped orders by strike and a 6-second bucket and found 86.5% exactly 1+1 (below the 90% I wanted); the 2+2 / 3+3 / 4+4 cases are adjacent 1+1 waves merged by the bucket. At order level all 1,722 scheduled-pair orders are 1 lot and every CE order has a PE order within 3 s at the same strike (the latter is how the pair label is defined, so only the 1-lot part is evidence). **Post-hoc.**
* **D-1 engine default corrected** from a 1% limit buffer to 15% after A2; the 15% had been recorded earlier in `bl_common.K15` and I had not used it. No test result changed (19 engine tests pass).
* The cycle with an unlabelled version (NIFTY 2026-08-18) is a stop cycle with the stop at the open; it appears in the stop rows only.
