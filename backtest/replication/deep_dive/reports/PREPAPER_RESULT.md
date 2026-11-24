# Pre-paper-trading validation — result

*Plan and gates: `PREPAPER_PLAN.md` (committed before any run; gates approved by you before the runs). 275 cycles, Nov 2023 – Nov 2026, simulator of the reconstructed strategy, verified cost schedule, constant lot (NIFTY 65 / SENSEX 20) unless stated. Every cycle was used before: this measures **robustness of the reconstruction**, not new evidence. Figure: `figures/bl_prepaper.png`.*

## Verdict: **NO-GO** — 5 of 8 gates pass
| gate | value | passed |
|---|---|---|
| G1 Costs | mean net ₹70,801 (all) / ₹54,242 (OOS) / ₹33,361 (costs ×1.5, slippage ×2) | PASS |
| G2 Execution | mean net with 1-minute delay ₹45,786 | PASS |
| G3 Parameter stability | no ±20% / ±5-min change flips or halves the mean | PASS |
| G4 Overfitting | PBO 0.60; Deflated Sharpe 1.00 at N = 83 (1.00 at N = 1,000) | **FAIL** |
| G5 Noise floor | real timetable ₹70,801 vs random-timetable null: 95th pct ₹70,902; real above 95% of 20 null runs | **FAIL** |
| G6 Path / tail | 1-year 95th-pct max drawdown ₹29.6 lakh; P(1-year loss > 10%) 0.1% | PASS |
| G7 Capacity | 98.7% of fill volume at ≤ 10% of minute volume | PASS |
| G8 Margin-capped book | mean net ₹63,943; 10.9% of cycles still above ₹2 crore | **FAIL** |

**Failing:** G4 Overfitting, G5 Noise floor, G8 Margin-capped book. By the rule you approved, Algo 8's reconstruction does **not** go to paper trading as it stands. The single most important finding is outside the gates: **the simulator loses money after 3 Aug 2026** (closing auction + STT 0.15%), and the 5 most recent cycles (after the real log ends) are its worst run — while the real system's log over the same weeks is still positive. Paper trading **this** simulator would test a strategy that is not behaving like Algo 8 in the current market regime.

## 1. Headline (simulator, verified costs)
| sample | cycles | mean net (₹) | win_rate | profit_factor | total (₹) | return on ₹2 crore per year |
|---|---|---|---|---|---|---|
| all, constant lot | 275 | 70,801 | 59% | 1.77 | 19,470,271 | 32.4% |
| IS | 175 | 88,312 | 61% | 2.00 | 15,454,530 | 25.7% |
| OOS | 64 | 54,242 | 59% | 1.53 | 3,471,499 | 5.8% |
| live window | 36 | 15,118 | 47% | 1.17 | 544,242 | 0.9% |
| all, margin-capped | 275 | 63,943 | 59% | 1.75 | 17,584,408 | 29.2% |
| all, after funding cost (6.5%) | 275 | 56,577 | 57% | 1.58 | 15,558,703 | 25.9% |

* Costs + slippage take **43%** of gross. Constant-lot net here (₹70,801) is higher than the ₹61k of `ALPHA_SOURCE.md` because brokerage is now charged per order instead of being scaled with the lot restatement; the verified schedule raises the NSE fee before Oct 2024 (0.0495%).
* Funding the ₹2 crore at 6.5% a year costs ≈ ₹14.2k per cycle (91 cycles a year).
* Performance falls by sample: IS ₹88.3k → OOS ₹54.2k → live window ₹15.1k per cycle. Linear trend of the weekly series: -524 ₹ per week per week (t = -0.85, not significant on its own).

## 2. B1 — costs and execution
| test | mean net per cycle (₹) | OOS (₹) | live window (₹) | cycles > 0 |
|---|---|---|---|---|
| gross (no costs, no slippage) | 124,657 | 113,442 | 60,327 | 64% |
| **baseline: verified costs + slippage** | 70,801 | 54,242 | 15,118 | 59% |
| NSE fee 0.03553% instead of 0.03503% | 70,793 | 54,230 | 15,109 | 59% |
| costs × 1.5 | 54,401 | 36,536 | 1,272 | 57% |
| costs × 2 | 38,002 | 18,830 | -12,574 | 53% |
| slippage × 2 | 49,755 | 30,469 | -2,387 | 56% |
| slippage × 3 | 28,709 | 6,696 | -19,892 | 52% |
| slippage × 6 | -34,428 | -64,623 | -72,406 | 45% |
| costs × 1.5 + slippage × 2 | 33,361 | 12,770 | -16,226 | 53% |
| costs × 2 + slippage × 3 | -4,069 | -28,687 | -47,557 | 48% |
| costs × 2 + slippage × 2 | 16,966 | -4,929 | -30,066 | 50% |
| fills delayed 1 minute | 45,786 | 32,077 | -5,626 | 55% |
| fills delayed 2 minutes | 47,781 | 27,014 | 3,241 | 55% |
| fills at realistic in-bar position | 44,225 | 31,402 | -2,162 | 54% |
| size × 0.5 (slippage scaled) | 25,879 | 17,394 | -282 | 56% |
| size × 2 (slippage scaled) | 129,077 | 92,279 | 19,661 | 59% |
| margin-capped (S2) | 63,943 | 44,072 | 14,787 | 59% |

* **Break-even:** costs and slippage together can rise to **2.31×** before the mean net reaches zero. Slippage alone fails between ×3 and ×6.
* Delayed and in-bar fills cut the mean by ≈ 35–38% but keep it positive (the path is not re-simulated: stops would also trigger differently).
* Sizing: doubling size with proportionally worse slippage gives ₹129.1k per cycle (not 2 × ₹70.8k): returns per rupee fall with size.

## 3. B2 — parameter sensitivity (change in mean net vs the frozen strategy)
| parameter | -40% | -20% | +20% | +40% | -15min | -5min | +5min | +15min | OOS mean at −40% / +40% (₹) |
|---|---|---|---|---|---|---|---|---|---|
| cycle_stop | -15% | -13% | 0% | -5% |  |  |  |  | 53,811 / 50,667 |
| d0_counter_ratio | -5% | -4% | 2% | 5% |  |  |  |  | 51,499 / 57,672 |
| d0_ladder_step | 10% | 7% | -7% | -11% |  |  |  |  | 57,377 / 47,389 |
| d0_stop_theta | -21% | -8% | 5% | 5% |  |  |  |  | 38,565 / 67,148 |
| d0_take_profit | 5% | 2% | -5% | -5% |  |  |  |  | 57,895 / 55,506 |
| d1_ladder_step | 7% | 3% | 3% | 2% |  |  |  |  | 59,463 / 53,257 |
| d1_lump_ratio | 4% | 2% | -4% | -7% |  |  |  |  | 54,908 / 48,641 |
| d1_stop_ratio | 3% | 4% | -6% | -19% |  |  |  |  | 76,776 / 8,120 |
| d1_wing_budget | 3% | 3% | -1% | -2% |  |  |  |  | 54,580 / 53,107 |
| timing |  |  |  |  | 1% | -6% | -11% | -18% | 63,822 / 43,461 (±15 min) |

* No ±20% change (or ±5-minute timing shift) flips the sign or halves the mean: **G3 passes**. The surface is mostly a plateau.
* Two weak spots: a **looser D-1 per-lot stop** (+20% / +40%) cuts the **out-of-sample** mean from ₹54,242 to ₹29,147 / ₹8,120; shifting the timetable **15 minutes later** costs 18%.

## 4. B3 — overfitting and noise floor
* **Deflated Sharpe:** weekly Sharpe 0.288 (≈ 2.08 annualised) against a selection threshold of 0.046 → DSR 0.998 at N = 83 configurations (0.996 at N = 1,000). **Passes** — but the variants are near-copies of one strategy and much of the sample is in-sample for the rules, so this is generous.
* **Probability of backtest overfitting (CSCV, 41 variants, 16 blocks, 12,870 splits): 0.60** → **fails** (< 0.5 required). Picking the best-looking variant in-sample gives a below-median variant out-of-sample 60% of the time: the parameter tuning has no out-of-sample value. It does not say the premium is fake; it says fine-tuning is curve-fitting.
* **Random-timetable null (20 runs, same structure, random times):** mean ₹64.7k (range ₹54.1k – ₹73.2k); the real timetable's ₹70.8k beats 95% of them but sits ₹101 below the 95th percentile → **fails G5 by a hair**. Consistent with earlier findings: **the premium is harvested at almost any time of day; the exact clock is not the edge.**

## 5. B4 — path and tail risk (weekly, ₹2 crore capital)
| measure | constant lot (₹) | margin-capped (₹) |
|---|---|---|
| mean_week | 123,230 | 111,294 |
| sharpe_annual | 2.08 | 2.02 |
| max_drawdown | 1,957,164 | 1,957,164 |
| longest_underwater_weeks | 13.00 | 13.00 |
| one_year_pnl_median | 6,367,732 | 5,804,727 |
| one_year_pnl_p5 | 1,625,341 | 1,454,806 |
| one_year_mdd_p95 | 2,960,946 | 2,815,882 |
| p_loss_10 | 0.00 | 0.00 |
| p_negative_year | 0.01 | 0.01 |

* Historical maximum drawdown ₹19.6 lakh (9.8% of capital), longest time under water 13 weeks. One-year block bootstrap: 95th-percentile drawdown ₹29.6 lakh; a one-year loss of more than 10% essentially never appears (**G6 passes**) — **because the bootstrap resamples the 3-year history, which has no crash**; it cannot produce the tail it never saw.
* Overnight implied-volatility shock on the carried book (no gap): ×1.5 → mean loss ₹83.6k, worst ₹4.1 lakh; ×2 → mean ₹45.1k, worst ₹6.8 lakh (the wings are long volatility, which is why ×2 is not worse on average). Gap shocks: `UNRESOLVED_THREE.md` §3.
* Ten worst cycles:

| und | expiry | split | net | gap at 09:16 | cycle stop |
|---|---|---|---|---|---|
| SENSEX | 2026-03-19 | OOS | -1,345,932 | -1.86 | hit |
| SENSEX | 2025-04-15 | IS | -851,532 | 1.79 | hit |
| SENSEX | 2026-11-05 | OOS | -678,182 | 1.76 | hit |
| SENSEX | 2025-04-08 | IS | -475,795 | 1.34 | hit |
| NIFTY | 2026-04-13 | OOS | -447,383 | -1.78 | hit |
| NIFTY | 2025-04-09 | IS | -446,058 | -0.65 | hit |
| NIFTY | 2026-11-03 | OOS | -434,194 | 0.39 | hit |
| NIFTY | 2024-09-26 | IS | -406,626 | 0.01 | hit |
| NIFTY | 2024-07-18 | IS | -402,167 | -0.16 | hit |
| NIFTY | 2024-10-03 | IS | -377,493 | -1.03 | hit |

## 6. B5 — liquidity and capacity
| size | threshold | share_of_fill_units_at_or_below | share_of_fills_at_or_below |
|---|---|---|---|
| 1.00 | 0.05 | 98.1% | 98.9% |
| 1.00 | 0.10 | 98.7% | 99.2% |
| 1.00 | 0.25 | 99.1% | 99.4% |
| 2.00 | 0.05 | 97.0% | 98.3% |
| 2.00 | 0.10 | 98.1% | 98.9% |
| 2.00 | 0.25 | 98.8% | 99.2% |

**G7 passes:** 98.7% of the simulated fill volume is at most 10% of that contract's traded volume in the same minute; doubling size barely changes it. Capacity is not the constraint at this size.

## 7. Margin-capped sizing (S2)
Causal cap (90th percentile of the previous 8 cycles' modelled peak margin): mean multiplier 0.93, mean net ₹63.9k per cycle, but **10.9% of cycles still exceed ₹2 crore** → **G8 fails**. A cap set from past cycles cannot anticipate a large cycle; the real system must control margin **inside** the cycle (stop adding), which the simulator does not model. (Margin rests on the unverified 9.3% scan range.)

## 8. The regime problem (most important)
| era | cycles | mean net (₹) | mean gross (₹) | costs_share_of_gross | win_rate | after funding (₹) |
|---|---|---|---|---|---|---|
| Nov 2023 – Sep 2024 (STT 0.0625%, NSE fee 0.0495%) | 63 | 65,388 | 119,870 | 45% | 59% | 51,164 |
| Oct 2024 – Mar 2026 (STT 0.1%) | 149 | 95,041 | 150,328 | 37% | 63% | 80,817 |
| Apr – 2 Aug 2026 (STT 0.15%) | 34 | 72,347 | 128,126 | 44% | 65% | 58,123 |
| from 3 Aug 2026 (STT 0.15% + closing auction) | 29 | -43,796 | -905 | gross ≤ 0 | 31% | -58,020 |

Real log vs simulator around the closing auction (same cycles):
| era | cycles | real gross (₹) | real net, conservative costs (₹) | simulator gross (₹) | rank correlation sim vs real |
|---|---|---|---|---|---|
| before 3 Aug 2026 | 12 | 85,969 | 29,393 | 126,951 | 0.36 |
| from 3 Aug 2026 | 23 | 68,926 | 29,191 | 32,131 | 0.80 |

* After 3 Aug 2026 the simulator still ranks cycles like the real system (rank correlation 0.80) but earns about half of the real gross per cycle.
* The **5 cycles after the real log ends** (2026-10-27 – 2026-11-12) average ₹-173.8k net in the simulator — the worst stretch of the 3 years, with no real data to compare.
* Reading: the reconstruction is **least reliable exactly in the regime paper trading would run in** (STT 0.15%, closing auction, 15:14 exit). Whether the real Algo 8 still has an edge now is supported only by 23 real post-auction cycles (₹69k gross, ₹29k net at conservative costs per cycle).

## 9. What it would take to reach GO
1. **Rebuild the post-3-Aug-2026 behaviour** (D0 timetable, 15:14 exit, transition minutes 15:15–15:20) against the 23 real post-auction cycles until the simulator earns what the real system earns there — then rerun this battery.
2. **Freeze one configuration and stop tuning** (PBO says tuning adds nothing); keep the frozen parameters.
3. **Intra-cycle margin control** in the simulator (stop adding when modelled margin reaches the cap) → retest G8; obtain NSE SPAN files to verify the scan range.
4. G5 is a near-miss and says the clock is not the edge; it does not need a fix, but it should not be marketed as one.

## 10. If you paper-trade anyway — the forward-test design (pre-registered)
* Run the frozen strategy on paper for every NIFTY and SENSEX cycle; log per cycle: net P&L under the verified costs, modelled peak margin, overnight tradeable gap, realised ÷ implied variance by segment, and the simulator's prediction for the same cycle.
* **Power:** per-cycle standard deviation is ₹314.0k; to distinguish a mean of ₹70.8k from zero at 95% confidence with 80% power needs ≈ **154 cycles** (≈ 1.7 years). Paper trading will not prove the edge quickly; it can only catch a broken implementation or a clearly negative regime.
* **Stop rules (pre-registered):** stop the paper test if cumulative net falls below −₹20 lakh, or if the mean over any 26 consecutive cycles is below −₹30k, or if the simulator–paper gap per cycle exceeds ₹1 lakh on average over 10 cycles (implementation broken).

## Limits
Simulator ≈ 36% of the real P&L overall (≈ 0.5× after 3 Aug 2026); B1 re-prices fills without re-simulating paths; margin uses an unverified scan range; bootstrap and stress use 3 calm years; all cycles were used before. 135+ passing tests show the code reproduces its outputs, not that the conclusions are right.
