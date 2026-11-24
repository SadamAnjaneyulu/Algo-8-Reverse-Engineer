# Why the premium exists, and why Algo 8 is built the way it is

> **Correction, 24 Nov 2026.** The first version of this report measured the overnight gap to the **09:16** open and said the largest gap in 3 years was 2.77%. The first print of the day (09:15) shows **4.6%** (NIFTY, 3 Feb 2026), 3 nights above 2%, 14 above 1%. The overnight ratios below use the 09:16 basis; on the first-print basis the overnight realised ÷ implied variance is 0.63, the median night 0.39 (not 0.27), 28% of nights above priced (not 15%) and the top 10% of nights carry 63% of the realised gap variance (not 68%, n = 224). The conclusion (overnight premium = rare-gap insurance) is unchanged; the statement that the sample 'never had a large gap' was wrong. See `UNRESOLVED_THREE.md`.

*Plan: `PREMIUM_AND_ARCHITECTURE_PLAN.md` (written before the tests). 275 cycles, Nov 2023 – Nov 2026. Every cycle was used before: **exploratory**. Figure: `figures/bl_premium_arch.png`. Builds on `DESIGN_THESIS.md`.*

## The refined idea (version 2)
The first version ("options near expiry are over-priced; sell them, carry overnight, re-balance, survive the tails") holds. The tests below split it into **two different premia with two different causes**, and show that the inventory architecture is shaped by **margin and the gap tail**, not by return:

> **1. The overnight premium is gap insurance.** On a typical night the opening gap realises about a quarter of the variance that was priced (median 0.27); the premium is paid back on rare large gaps (the top 10% of nights carry 68% of all realised gap variance; P&L skewness -4.3). Selling the overnight is **selling insurance against a gap**.
>
> **2. The expiry-day premium is a steady over-pricing, not jump insurance.** Jumps are only 7% of D0 realised variance; even the smooth (continuous) part is only 0.74 of what is priced, and the typical day realises 0.84. Something other than tail risk keeps expiry-day options rich. The leading remaining candidate (**Inferred, untested**) is structural demand for short-dated options and the inventory cost of the sellers who supply it; it cannot be identified here without signed order flow.
>
> **3. Algo 8 sells the middle of the gap distribution and buys back the far tail.** Its overnight book is covered by cheap far wings and the lump; with them the carried book's mean gap loss **stops growing beyond about 3%** (≈ ₹7–8 lakh) while without them it keeps growing (≈ ₹30 lakh at ±5%), and they cut the overnight margin to 0.51× (PSR 6%) of an unhedged book, but cost ≈ ₹17.6k per cycle. The largest first-print gap on a cycle night in 3 years was **4.6%** (NIFTY, 3 Feb 2026); on that single night the long legs were worth ≈ ₹7 lakh in the simulator (full book +₹5.2 lakh net, without D-1 longs −₹1.8 lakh), about 40 average cycles of their cost. Nothing larger occurred, so the sample cannot show their value in a 7–13% gap.
>
> **4. The expiry-day rules are capital rules.** Without the D0 hedge controller or the D0 stop/take-profit, the expiry-day book outgrows ₹2 crore of approximate margin in 52% and 55% of cycles (PSR 9.3%; 15% with them). They exist to keep the size the capital allows, and they also cut the expiry-day scenario loss.

## Question 1 — why does the premium exist?
| Mechanism | Verdict | Key evidence |
|---|---|---|
| **Jump / gap insurance** | **Supported for the overnight**; **not the main reason on D-1 and D0** | Overnight: median night 0.27 of priced, 15% of nights above priced, top 10% carry 68%; D-1/D0: jumps 7–10% of realised variance and the continuous part alone is well below implied |
| **Closed-market / calendar-time pricing** (weekends priced, not realised) | **Not supported** (18 cycles; descriptive) | Multi-day gaps price 2.6× the variance of a one-night gap and realise 4.2×: weekends are **not** over-priced relative to single nights |
| **Demand pressure for options** | **Not testable with this data** (neither supported nor refuted) | Volume rose, not fell, after SEBI's 20 Nov 2024 measures (NIFTY ×2.4, SENSEX ×11.3 in units; lot sizes changed and SENSEX weeklies grew); the premium did not shrink reliably; pre-determined volume does not predict the premium (Spearman -0.01 overnight, -0.03 D0). Volume is not **net buying**; the mechanism needs signed flow |
| **Time-varying risk premium** | **Descriptive** | On D-1 and D0 the premium is largest when implied volatility is high (D0 ratio 1.06 in the low-IV third: no premium); overnight the opposite (richest in calm cycles) |

### A1 — jumps vs continuous variance
| segment | realised ÷ implied | continuous ÷ implied | jump share of realised | median cycle ratio | cycles with ratio > 1 | top 10% of cycles carry | P&L skewness | NIFTY / SENSEX ratio |
|---|---|---|---|---|---|---|---|---|
| D-1 day | 0.74 [0.66, 0.84] | 0.67 [0.61, 0.73] | 10% [6%, 15%] | 0.67 | 32% | 34% of realised | -3.1 | 0.70 / 0.81 |
| overnight | 0.61 [0.47, 0.78] | — (all jump) | 100% (gap) | 0.27 | 15% | 68% of realised | -4.3 | 0.47 / 0.77 |
| D0 day | 0.79 [0.71, 0.87] | 0.74 [0.66, 0.82] | 7% [6%, 8%] | 0.84 | 35% | 29% of realised | -1.4 | 0.67 / 0.94 |

* **Overnight** is the textbook insurance profile: most nights cheap, a few nights expensive, strongly negative skew.
* **D-1 and D0** are not: the premium survives with jumps removed, and the typical day realises less than priced. NIFTY is richer than SENSEX in every segment (D0 SENSEX ratio 0.94, close to fair).

### A2 — weekends and holidays (overnight)
| group | cycles | implied overnight variance (bp²) | realised gap variance (bp²) | realised ÷ implied |
|---|---|---|---|---|
| 1 calendar day | 243 | 3,098 | 1,744 | 0.56 [0.42, 0.74] |
| 2-4 calendar days | 15 | 8,045 | 7,269 | 0.90 [0.50, 1.43] |

### A3 — demand: SEBI natural experiment (effective 20 Nov 2024)
| segment | before 20 Nov 2024 | after | after − before [95%] | NIFTY / SENSEX change |
|---|---|---|---|---|
| D-1 day | 0.64 | 0.79 | 0.15 [-0.01, 0.32] | +0.10 / +0.20 |
| overnight | 0.50 | 0.63 | 0.14 [-0.09, 0.38] | -0.06 / +0.36 |
| D0 day | 0.86 | 0.76 | -0.09 [-0.29, 0.07] | -0.12 / -0.17 |

The before/after shifts are mixed in sign and their intervals include zero. Confounds: volatility regime, NIFTY's expiry weekday change, lot-size changes, SENSEX's growth as BSE's only weekly. **Not a clean test of demand.**

### A4 — by implied-volatility level (D-1 opening ATM IV terciles, realised ÷ implied)
| segment | low | mid | high |
|---|---|---|---|
| D-1 day | 0.91 | 0.73 | 0.71 |
| overnight | 0.41 | 0.53 | 0.69 |
| D0 day | 1.06 | 0.87 | 0.66 |

## Question 2 — why this inventory architecture?
Approximate exchange margin (SPAN-like scenario margin + 2% exposure margin on short notional, + 2% on expiry day from 20 Nov 2024). **The NSE price scan range could not be verified**, so every result is shown for 4%, 6% and 9.3% (volatility scan 4 points; 0 and 8 give the same conclusions, `outputs/arch/arch_stats.csv`). Constant lot size. Peak margin is evaluated every 15 minutes of both days.

| variant | net ₹/cycle | median peak margin, ₹ cr (PSR 4 / 6 / 9.3%) | cycles with peak margin > ₹2 cr | overnight margin vs full | return on peak margin, Δ vs full [95%] (PSR 6%) | p5 / worst cycle (₹k) |
|---|---|---|---|---|---|---|
| full strategy | 61,071 | 1.29 / 1.31 / 1.33 | 13% / 15% / 15% | — | — | -377 / -1,346 |
| no D-1 longs (wings + lump) | 78,621 | 1.30 / 1.33 / 1.41 | 13% / 15% / 15% | 1.48× / 1.96× / 2.69× | +0.11 pp [+0.06, +0.16] | -367 / -1,436 |
| no overnight lump | 69,141 | 1.30 / 1.35 / 1.39 | 14% / 16% / 17% | 1.21× / 1.28× / 1.29× | +0.05 pp [+0.03, +0.07] | -375 / -1,450 |
| no D0 hedge controller | 69,342 | 1.46 / 1.71 / 2.05 | 27% / 37% / 52% | 1.00× / 1.00× / 1.00× | -0.06 pp [-0.11, +0.00] | -373 / -1,346 |
| no D-1 per-lot stops | 39,444 | 1.34 / 1.34 / 1.34 | 16% / 18% / 19% | 1.24× / 1.26× / 1.26× | -0.17 pp [-0.40, +0.04] | -466 / -1,361 |
| no D0 stop / take-profit | 82,436 | 2.13 / 2.14 / 2.16 | 53% / 55% / 55% | 1.00× / 1.00× / 1.00× | -0.09 pp [-0.29, +0.12] | -425 / -1,346 |
| no cycle stop | 80,945 | 1.46 / 1.52 / 1.54 | 17% / 20% / 20% | 1.00× / 1.00× / 1.00× | +0.07 pp [-0.05, +0.20] | -438 / -1,420 |

**Overnight gap stress** of the book carried at the D-1 close (mean over cycles; implied volatility × 1.25; time value kept, i.e. conservative; D0 actions after the gap not included):

| overnight gap | full (mean loss, ₹ lakh) | no D-1 longs | no lump | no D-1 stops |
|---|---|---|---|---|
| -5% | 7.9 | 29.7 | 17.6 | 12.2 |
| -3% | 7.8 | 15.9 | 11.9 | 10.9 |
| -2% | 5.6 | 9.2 | 7.5 | 7.6 |
| -1% | 2.3 | 3.6 | 3 | 3.2 |
| +1% | 2.4 | 3.8 | 2.9 | 3.2 |
| +2% | 5.1 | 9.5 | 6.8 | 6.9 |
| +3% | 6.2 | 16.2 | 9.9 | 8.8 |
| +5% | 4 | 30.1 | 12.9 | 7.4 |

Largest overnight gap actually seen in 3 years: **4.62%** (only 3 cycles above 2%, 14 above 1%).

### Component by component
| Component | Tail it protects against | Cost | Margin effect | What happens without it |
|---|---|---|---|---|
| **Wings (all D-1 longs)** | Overnight gap beyond ~2% | ≈ ₹17.6k per cycle (net) | Overnight margin 1.96× higher without them at PSR 6% (1.48× at 4%, 2.69× at 9.3%); **peak** margin almost unchanged (the peak is on D0) | Higher mean P&L and return on peak margin in this sample; mean loss in a ±5% gap ≈ 30 lakh instead of 6 lakh. **Break-even:** they pay for themselves if a ±5% gap happens more than once every 136 cycles (≈ 1.3 years at two expiries a week; ±3%: once every 51 cycles) |
| **Overnight lump** | Gap on the heavier side | ≈ ₹8.1k per cycle | Overnight margin 1.28× without it | Gap loss about 2.6× larger at ±5% |
| **D0 hedge controller** | Expiry-day intraday move | ≈ ₹8.3k per cycle | Median peak margin 1.31 → 1.71 cr (PSR 6%); cycles above ₹2 cr 15% → 37% | **Does not fit the capital**; return on peak margin lower at PSR 9.3% (interval excludes zero) |
| **D0 stop / take-profit** | Expiry-day book growth (path) | mean +₹21k without it (interval includes 0) | Median peak margin 2.14 cr — **above ₹2 crore** in 55% of cycles | Peak margin ≈ 1.6× higher; the strategy as sized cannot run on ₹2 crore |
| **D-1 per-lot stops** | Trending D-1 (path) | removing them lowers net by ₹22k (interval includes 0) | Overnight margin 1.26× without them | Worse return on margin (-0.17 pp, interval includes 0), larger gap loss |
| **Cycle stop (≈ ₹1.2–1.4 lakh)** | A bad day turning into a disaster | ≈ ₹20k per cycle | Cycles above ₹2 cr 15% → 20% | 5th-percentile cycle ₹61k worse, worst ₹74k worse |

**Reading against the plan's rule:** no protective component raises the **return on peak margin** in this sample (wings and lump lower it slightly, intervals excluding zero; the others are within noise, except the D0 hedge at PSR 9.3% which helps). So none "pays for itself after margin" **in this 3-year sample, whose largest gap was 4.6%**. Their measurable jobs are: (a) **capital feasibility** — the D0 hedge and D0 stops keep the expiry-day book within ₹2 crore; (b) **gap insurance** — the wings and lump halve losses in gaps the sample did not contain; (c) **path protection** — the stops cut the 5th-percentile and worst cycles.

## How the two questions connect
The overnight premium exists **because** of rare large gaps (Q1). A seller who keeps the whole overnight premium also keeps the whole gap tail. Algo 8 keeps the part of the premium paid for gaps of roughly 1–3% and **buys back the far tail** with wings that cost ≈ ₹18k a cycle. In this 3-year sample the largest gap was 4.6% and the long legs cost ≈ ₹18k a cycle net (that figure already includes their payoff on the 3 Feb 2026 night). Whether they pay in expectation depends on gaps larger than any in the sample (see `UNRESOLVED_THREE.md`).

## Evidence levels
| Claim | Level |
|---|---|
| Overnight premium = gap insurance (rare, concentrated, negative skew) | **Observed** (3 years, market data) |
| D0 premium is not jump compensation | **Observed** |
| Weekends are over-priced relative to single nights | **Not supported** (descriptive, 15 cycles) |
| Demand pressure causes the premium | **Not testable** with OHLCV + volume (no signed flow) |
| D0 hedge and D0 stops keep the book within ₹2 crore | **Observed under the approximate margin model**, across the scan-range grid |
| Wings and lump cap the overnight gap loss (flat beyond ~3%) and halve the overnight margin | **Observed** under the model (stress, not history) |
| Wings pay for themselves | **Unresolved**: break-even needs a ±5% gap about once every 136 cycles; the 3 years contain one night of 4.6% (worth ≈ ₹7 lakh) and none larger |
| The real broker margin equals this model | **Unknown** (PSR not verified; real margin calls, peak-margin snapshots, broker add-ons not modelled) |

## Next tests
1. The real NSE SPAN risk-parameter files (price scan range per day) to replace the grid.
2. 2020–2022 chains: the March 2020 gaps are exactly the tail the wings insure.
3. Signed flow (open-interest change by strike, buyer/seller-initiated volume) to test demand.
