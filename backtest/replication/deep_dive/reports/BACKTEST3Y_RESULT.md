# Algo 8 reconstruction — combined D-1 + D0 backtest on 3 years of one-minute option data

*Plan `BACKTEST3Y_PLAN.md` with Addendum 1 (in-sample / out-of-sample division) and Addendum 2 (fill-pricing amendment), both written before the OOS run. Scripts `bl_bt3_*.py`. Figure `figures/bl_bt3_summary.png`. Dataset commit `eb40973…`. Frozen D0 parameters `outputs/bl_bt3_frozen.json`.*

## 0. Result

**On the locked out-of-sample cycles (64, 2025-11-20 → 2026-11-12, run once) the reconstructed D-1 + D0 strategy earned ₹0.56 lakh net per cycle (₹1.16 lakh gross), a profit factor of 1.56 and a weekly Sharpe of 1.56, but the 95% interval of the mean net cycle P&L (₹-0.26 to ₹1.45 lakh, t = 1.28) includes zero.** The in-sample figure is almost the same (₹0.57 lakh net per cycle on 175 cycles, t = 3.00), so the estimate is stable, but 64 cycles cannot separate it from zero, and it halves under triple slippage or double costs.

| | cycles | orders per cycle | win rate (cycles) | profit factor | mean net per cycle | t | 95% interval of the mean (₹ lakh) | weekly Sharpe | return on ₹2 crore | max drawdown |
|---|---|---|---|---|---|---|---|---|---|---|
| **OOS, timetable B/V2 (point line), net** | 64 | 1328 | 59% | 1.56 | ₹0.56 lakh | 1.28 | -0.26 to 1.45 | 1.56 | 18.0% | -7.5% |
| OOS, timetable A/V1 (band), net | 64 | 1192 | 59% | 1.34 | ₹0.34 lakh | 0.86 | -0.43 to 1.08 | 1.04 | 10.8% | -7.6% |
| IS (development), B/V2, net | 175 | 1270 | 58% | 1.82 | ₹0.57 lakh | 3.00 | 0.20 to 0.97 | 2.08 | 50.2% | -10.3% |
| IS, A/V1, net | 175 | 1179 | 61% | 1.67 | ₹0.42 lakh | 2.46 | 0.09 to 0.77 | 1.63 | 37.1% | -10.5% |
| Rule-fitted live window, net (in-sample for the rules) | 36 | 1035 | 47% | 1.17 | ₹0.15 lakh | 0.39 | -0.55 to 0.92 | 0.65 | 2.7% | -3.9% |

*Gross (simulator fills, no slippage or costs): OOS B/V2 ₹1.16 lakh per cycle, profit factor 2.34, Sharpe 3.03; IS B/V2 ₹1.06 lakh. Return on ₹2 crore is the total over the period, not annualised (OOS ≈ one year).*

| question | answer |
|---|---|
| Does the out-of-sample result agree with the in-sample one? | **Yes.** Net per cycle ₹0.56 lakh (OOS) vs ₹0.57 lakh (IS), win rate 59% vs 58%. The timetable version was chosen on IS only. |
| Is it statistically distinguishable from zero? | **Not out of sample** (t = 1.28, 64 cycles; the A/V1 band t = 0.86). In sample t = 3.00. NIFTY and SENSEX cycles of the same week are not independent, so the real t is lower. |
| How sensitive is it to the unverified cost model? | **Very.** OOS B/V2 net per cycle: base ₹0.56 lakh, slippage ×3 ₹0.08, slippage ×6 ₹-0.64, costs ×2 ₹0.21, one-minute delay ₹0.34, fills at the real in-bar position ₹0.57. The older timetable A/V1 is ≈ 0 at slippage ×3 and costs ×2. |
| How good is the reconstruction against the real system? | On the 32 live cycles with logs, the fully simulated chain tracks the real cash P&L with Spearman **0.72** (0.81 when D0 is fed the real D-1 book), **earns ₹6.8 lakh against the real ₹18.9 lakh on the same 32 cycles (about 36%): it ranks the cycles but earns far less than the real system did**, finds 14 cycle stops against 11, sends 1110 orders per cycle against about 1,136. |
| Which timetable? | Unknown before June 2026. The pre-registered rule chose **B/V2** from IS (₹0.57 vs ₹0.42 lakh per cycle); OOS reproduces the ranking (₹0.56 vs ₹0.34). Both stay reported: the band is part of the result. |

## 1. The in-sample / out-of-sample division

| split3 | cycles | NIFTY | SENSEX | first_d0 | last_d0 |
|---|---|---|---|---|---|
| EMBARGO | 1 | 1 | 0 | 2025-11-18 | 2025-11-18 |
| IS | 175 | 105 | 70 | 2023-11-09 | 2025-11-13 |
| LIVE_FITTED | 36 | 18 | 18 | 2026-06-23 | 2026-10-22 |
| OOS | 64 | 31 | 33 | 2025-11-20 | 2026-11-12 |

*IS = D0 up to 2025-11-17 (the boundary of the earlier backtest); OOS = after it; LIVE_FITTED = the June–October 2026 cycles the rules were fitted on, in-sample for the rules although later than the boundary; EMBARGO = D-1 in IS, D0 in OOS.*

## 2. Full metrics

| split | run | basis | cycles | orders | trades_per_day | win_rate | profit_factor | mean_rs | median_rs | t_stat | ci_cycle_lo | ci_cycle_hi | ci_month_lo | ci_month_hi | total_rs | return_pct_on_2cr | sharpe_weekly | max_drawdown_pct |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| IS | B/V2 | gross | 175 | 222262 | 635.03 | 0.66 | 2.87 | 105507 | 102066 | 5.28 | 66839.4 | 146640 | 67609.5 | 137412 | 1.84637e+07 | 92.32 | 3.63 | -9.64 |
| IS | B/V2 | net | 175 | 222262 | 635.03 | 0.58 | 1.82 | 57402.8 | 52847.2 | 3 | 19976.9 | 97071.7 | 20870.7 | 88314.8 | 1.00455e+07 | 50.23 | 2.08 | -10.26 |
| IS | A/V1 | gross | 175 | 206412 | 589.75 | 0.69 | 2.69 | 87109.6 | 100834 | 4.86 | 52333.7 | 123420 | 52195.2 | 120104 | 1.52442e+07 | 76.22 | 3.19 | -9.85 |
| IS | A/V1 | net | 175 | 206412 | 589.75 | 0.61 | 1.67 | 42430.1 | 48344.3 | 2.46 | 9032.32 | 77310.1 | 9334.44 | 73436.3 | 7.42526e+06 | 37.13 | 1.63 | -10.45 |
| OOS | B/V2 | gross | 64 | 84992 | 664 | 0.64 | 2.34 | 115882 | 154871 | 2.52 | 30593.7 | 208830 | 24118.9 | 205311 | 7.41642e+06 | 37.08 | 3.03 | -7.24 |
| OOS | B/V2 | net | 64 | 84992 | 664 | 0.59 | 1.56 | 56342.3 | 84488.3 | 1.28 | -25680.7 | 145061 | -31639.2 | 141895 | 3.60591e+06 | 18.03 | 1.56 | -7.54 |
| OOS | A/V1 | gross | 64 | 76256 | 595.75 | 0.67 | 2.04 | 87922.7 | 145243 | 2.16 | 8204.29 | 165351 | 3401.96 | 164503 | 5.62706e+06 | 28.14 | 2.56 | -7.31 |
| OOS | A/V1 | net | 64 | 76256 | 595.75 | 0.59 | 1.34 | 33786.9 | 86773.1 | 0.86 | -42723.8 | 108421 | -47701.8 | 108756 | 2.16236e+06 | 10.81 | 1.04 | -7.61 |
| LIVE_FITTED | observed | gross | 36 | 37273 | 517.68 | 0.53 | 1.87 | 60327.5 | 35584 | 1.5 | -12269.4 | 142709 | 13196.1 | 111420 | 2.17179e+06 | 10.86 | 2.47 | -2.79 |
| LIVE_FITTED | observed | net | 36 | 37273 | 517.68 | 0.47 | 1.17 | 15118.4 | -12225 | 0.39 | -55138.9 | 92057.8 | -30060.6 | 62440.3 | 544260 | 2.72 | 0.65 | -3.93 |

### By index (net)

| split | run | index | cycles | win_rate | profit_factor | mean_rs | t_stat | ci_cycle_lo | ci_cycle_hi | sharpe_weekly | max_drawdown_pct |
|---|---|---|---|---|---|---|---|---|---|---|---|
| IS | A/V1 | NIFTY | 105 | 0.57 | 1.45 | 29778.2 | 1.33 | -14231.4 | 76598.1 | 0.93 | -5.18 |
| IS | A/V1 | SENSEX | 70 | 0.67 | 2.05 | 61407.9 | 2.27 | 9637.39 | 111830 | 1.96 | -8.58 |
| IS | B/V2 | NIFTY | 105 | 0.57 | 1.59 | 38701.2 | 1.7 | -6718.71 | 85428.2 | 1.19 | -5.39 |
| IS | B/V2 | SENSEX | 70 | 0.6 | 2.14 | 85455.2 | 2.56 | 23076 | 149290 | 2.2 | -8.67 |
| OOS | A/V1 | NIFTY | 31 | 0.61 | 1.77 | 54369.5 | 1.31 | -28070.1 | 130635 | 1.7 | -3.53 |
| OOS | A/V1 | SENSEX | 33 | 0.58 | 1.12 | 14451.6 | 0.22 | -115559 | 135399 | 0.28 | -6.7 |
| OOS | B/V2 | NIFTY | 31 | 0.58 | 1.81 | 57874 | 1.36 | -26470 | 138587 | 1.76 | -3.01 |
| OOS | B/V2 | SENSEX | 33 | 0.61 | 1.43 | 54903.4 | 0.72 | -88735.7 | 202562 | 0.91 | -6.73 |

### OOS (B/V2) by year and index

| year | und | cycles | net_mean | net_total_lakh | win |
|---|---|---|---|---|---|
| 2025 | NIFTY | 6 | 134670 | 8.08 | 0.83 |
| 2025 | SENSEX | 6 | 128259 | 7.7 | 0.83 |
| 2026 | NIFTY | 25 | 39443 | 9.86 | 0.52 |
| 2026 | SENSEX | 27 | 38602.2 | 10.42 | 0.56 |

## 3. Stress tests (net, per cycle)

**IS, B/V2**

| scenario | mean per cycle (Rs) | total (Rs lakh) | win rate |
|---|---|---|---|
| base | 57403 | 100.5 | 0.58 |
| slippage x3 | 25485 | 44.6 | 0.53 |
| slippage x6 | -22392 | -39.2 | 0.46 |
| costs x2 | 25265 | 44.2 | 0.53 |
| delay 1 min | 37475 | 65.6 | 0.55 |
| delay 3 min | 32951 | 57.7 | 0.53 |
| real in-bar position | 52039 | 91.1 | 0.58 |
| gross | 105507 | 184.6 | 0.66 |

**IS, A/V1**

| scenario | mean per cycle (Rs) | total (Rs lakh) | win rate |
|---|---|---|---|
| base | 42430 | 74.3 | 0.61 |
| slippage x3 | 12685 | 22.2 | 0.55 |
| slippage x6 | -31933 | -55.9 | 0.45 |
| costs x2 | 12630 | 22.1 | 0.53 |
| delay 1 min | 28166 | 49.3 | 0.55 |
| delay 3 min | 23597 | 41.3 | 0.53 |
| real in-bar position | 38795 | 67.9 | 0.6 |
| gross | 87110 | 152.4 | 0.69 |

**OOS, B/V2**

| scenario | mean per cycle (Rs) | total (Rs lakh) | win rate |
|---|---|---|---|
| base | 56342 | 36.1 | 0.59 |
| slippage x3 | 8191 | 5.2 | 0.55 |
| slippage x6 | -64035 | -41 | 0.44 |
| costs x2 | 20893 | 13.4 | 0.56 |
| delay 1 min | 33928 | 21.7 | 0.56 |
| delay 3 min | 27084 | 17.3 | 0.55 |
| real in-bar position | 57134 | 36.6 | 0.59 |
| gross | 115882 | 74.2 | 0.64 |

**OOS, A/V1**

| scenario | mean per cycle (Rs) | total (Rs lakh) | win rate |
|---|---|---|---|
| base | 33787 | 21.6 | 0.59 |
| slippage x3 | -10728 | -6.9 | 0.56 |
| slippage x6 | -77501 | -49.6 | 0.42 |
| costs x2 | 1922 | 1.2 | 0.55 |
| delay 1 min | 16043 | 10.3 | 0.61 |
| delay 3 min | 8323 | 5.3 | 0.59 |
| real in-bar position | 39438 | 25.2 | 0.59 |
| gross | 87923 | 56.3 | 0.67 |

## 4. Where the P&L comes from (OOS B/V2, gross, ₹ lakh)

| day | cls | lots | gross_lakh |
|---|---|---|---|
| D-1 | body_buyback | 2140 | -240.72 |
| D-1 | body_long | 384 | -1.04 |
| D-1 | body_sell | 7948 | 570.18 |
| D-1 | lump | 2734 | -11.45 |
| D-1 | wing_buy | 7442 | -14.12 |
| D-1 | wing_sell | 2018 | 4.1 |
| D0 | body_buyback | 28878 | -809.64 |
| D0 | body_long | 2224 | -1.27 |
| D0 | body_sell | 25280 | 718.72 |
| D0 | stop | 4794 | -140.21 |
| D0 | wing_buy | 19445 | -14.69 |
| D0 | wing_sell | 25525 | 14.3 |

*These are **cash flows by class and day, not P&L by module**: the D0 buy-backs close lots that D-1 sold, so D-1 rows read as credits and D0 rows as debits. The edge is the difference of large flows.*

### What each module adds (diagnostic, B/V2, mean per cycle in ₹)

| split | cycles | full_gross | full_net | d1_only_gross | d1_only_net | d0_adds_gross | d0_adds_net | orders_full | orders_d1_only |
|---|---|---|---|---|---|---|---|---|---|
| IS | 175 | 105507 | 57403 | 38941 | 22831 | 66565 | 34572 | 1270 | 361 |
| OOS | 64 | 115882 | 56342 | 51570 | 30844 | 64312 | 25498 | 1328 | 371 |

*"D-1 only" = the same D-1 rules, then on D0 only the carried book is managed (per-lot stops and take-profit, hedge, cycle stop, 15:14 clearance) and **nothing new is sold**. The difference is what the D0 module adds. This is a **second look at the OOS cycles** run after the headline result; it is a diagnostic of the frozen model, no parameter was changed because of it.*

## 5. Audit of my own pricing (read this before trusting any number above)

The first in-sample run gave profit factor 3.1 and a weekly Sharpe of 3.5 gross. I treated that as a warning, found two look-ahead biases in the fills inherited from the research simulators (reactive sells priced before the move that triggered them; stop buy-backs priced at the minute close instead of the stop level), amended the fill model **before** the OOS run (`BACKTEST3Y_PLAN.md`, Addendum 2) and withdrew the first numbers. The size of the bias:

| split | run | gross_legacy | gross_causal | net_legacy | net_causal | net_overstatement |
|---|---|---|---|---|---|---|
| IS | A/V1 | 113315 | 87110 | 68043 | 42430 | 0.38 |
| IS | B/V2 | 139038 | 105507 | 89913 | 57403 | 0.36 |
| LIVE_FITTED | A/V1 | 80388 | 60327 | 33209 | 15118 | 0.54 |

*Net overstatement = 1 − causal ÷ legacy. The amended model is still an approximation: one-minute bars do not show what came first inside the minute.*

## 6. What this does not show

* **On the live cycles the chain earns about 36% of what the real system earned** (same 32 cycles, gross, causal fills). The legacy pricing earned 71% of it. The reconstruction is the weaker engine on level, which is the right direction for a conservative backtest, but it also means the out-of-sample number is not an estimate of what the real system earns.
* **It is a test of reconstructed rules, not of the real system.** Real orders exist only for the 32 live cycles. For earlier years nothing says the 2026 system traded this way.
* **The timetable before June 2026 is unknown;** both versions are reported; the point line was chosen on IS.
* **Costs are the earlier project's model, flagged unverified there** (slippage max(₹0.10, 0.5%), dated statutory costs, ₹20 per order). The system sends about 1,200 orders per cycle, so costs are about 40% of gross; the result is a statement about that model, not about a broker.
* **64 out-of-sample cycles, ≈ one year, two indices that are correlated.** The mean is positive and agrees with IS, but its interval includes zero.
* **The D0 simulator is M0** (no strangle timetable, which is 3% of D0 lots and SENSEX before 16 Sep; no opening-sell reconstruction beyond the ladder and timetable). Lot counts per decision are the real system's, held constant while the exchange lot size changed (NIFTY 50 → 25 → 75 → 65; SENSEX 10 → 20), so ₹ P&L scales with the unit; `points_lots_mean` is in the metrics file.
* **The day-shifted placebo of the plan is not done** (the cycle cache holds only D-1 and D0).
* **Ticks, partial fills, margin and real liquidity are not modelled.** The 30-cycle rule fit and the pricing audit show the model is sensitive to how the first seconds of a minute are filled.
* **The OOS was run once.** Nothing was changed after its result was seen. Anything changed from here on is a new development step on a contaminated OOS.

## 7. Pipeline checks

* D0 simulator vs the earlier research simulator, real carried book, legacy pricing: **49 of 49 cycles identical**, max P&L difference 0.0e+00.
* Gross recomputed from the fills equals the simulator cash on every cycle (`gross_check_diff` = 0).
* No cycle failed or was dropped after seeing a result: IS 175/175, OOS 64/64, live window 36/36.
* Cycle stops: IS 31%, OOS 31%, live window 39% of cycles (real system: 11 of 32).
