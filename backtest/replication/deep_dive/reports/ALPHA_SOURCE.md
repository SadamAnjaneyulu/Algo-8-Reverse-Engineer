# Where does the edge come from? — result

*Plan: `ALPHA_SOURCE_PLAN.md` (written before the tests). Data: the 275 cycles of the combined backtest (IS 175, OOS 64, rule-fitted live window 36; the 276 complete cycles less one embargo cycle; the naive benchmark has 274 because one cycle lacks a matching strike). **Exploratory** — every cycle was already used, so nothing here is out-of-sample evidence. Figure: `figures/bl_bt3_alpha.png`.*

## The answer in five lines
1. **RESULT — the profit is mainly a short-premium (short-volatility) carry; net direction is small and the fill model is not the source.** Premium decay (theta + vega + residual: **366k per cycle on the trading-minute clock, 368k on the calendar clock — the same total either way**) exceeds the gamma loss (**-287k**) by ≈ 79k; delta adds 13k and execution 10k (10% of gross, below the 25% reading threshold of the plan).
2. **The edge is thin relative to the carry:** the net of decay and gamma is ≈ 21% of the decay collected. A small change in realised versus implied volatility flips it.
3. **Per ₹ of premium sold the strategy earns the same mean as a naive straddle** (7.0% vs 7.5%; difference -0.5%, 95% interval [-8.7%, 8.2%]). **What the rules change is the dispersion**, not the mean return per ₹ sold (see below). The naive straddle's own mean is not distinguishable from zero in 3 years ([-1.6%, 16.1%]); the strategy's is ([4.7%, 9.1%]).
4. **Where in time:** 85% of the holding P&L comes from short lots held **during the expiry day (D0)**; D-1 daytime is small, the overnight step is small.
5. **What the rules do:** the reactive *selling* rules (solo ladders, D0 waves, counter-sells) are what carries the *size* of the edge (removing them lowers gross by ₹16k–78k per cycle); **the direction of the ladder matters** (flipped-direction placebo −₹35k/cycle net, same sign in IS, OOS and live window) and the loss sits in delta (−₹31k of the −₹36k gross). **Correction (`DESIGN_THESIS.md`):** I first read this as a trend-aligned element; a market-only test shows the index **reverts** after the ladder's trigger and that the ladder sale mainly **re-balances the book's delta** (it lowers |book delta| at 74% of triggers). The ladder is a hedge built from option sales, not a trend bet. The *protective* rules (wings, lump, hedge, cycle stop) **cost mean P&L** in this simulator.

## 1. Physical decomposition (Method 1)
Holding P&L per cycle in ₹ (actual lots), split with Black–Scholes sensitivities from each contract's own implied volatility (r = 6.5%). **Reconciliation:** holding + execution equals gross P&L to within ₹28,135 in total over 275 cycles (0.10% of gross); the largest single-cycle gap is ₹24,612 on SENSEX 2026-11-05 (cause not found; it is 3.8% of that cycle).

**Trading-minute clock (primary: 375 minutes a day, 250 days; overnight is one minute):**

| split | delta | gamma | theta | vega | resid | holding total | execution | gross |
|---|---|---|---|---|---|---|---|---|
| IS | 3k | -237k | 199k | 99k | 31k | 96k | 9k | 106k |
| LIVE_FITTED | 37k | -282k | 354k | -128k | 73k | 54k | 7k | 60k |
| OOS | 28k | -429k | 331k | 125k | 47k | 102k | 13k | 116k |
| ALL | 13k | -287k | 250k | 76k | 40k | 92k | 10k | 102k |

**Calendar clock (sensitivity: overnight and weekends count as elapsed time):**

| split | delta | gamma | theta | vega | resid | holding total | execution | gross |
|---|---|---|---|---|---|---|---|---|
| IS | 2k | -237k | 234k | -63k | 160k | 96k | 9k | 106k |
| LIVE_FITTED | 33k | -282k | 401k | -318k | 219k | 54k | 7k | 60k |
| OOS | 26k | -428k | 382k | -68k | 191k | 102k | 13k | 116k |
| ALL | 11k | -287k | 290k | -97k | 175k | 92k | 10k | 102k |

* **The theta / vega split is not identified.** It depends on the clock: the overnight step shows vega +62k (trading clock) versus -274k (calendar clock). What is clock-independent: gamma (-287k vs -287k), delta, execution, and **theta + vega + residual** (366k vs 368k). I therefore state the finding as **"premium decay minus gamma"** and do not claim "vega" or "theta" individually.
* Residual (unexplained by the model) is 40k on the primary clock and 175k on the calendar clock — the trading clock fits the data better (₹40k vs ₹175k residual per cycle), but the residual is not small enough to ignore.
* Reading rule of the plan: theta + vega is the largest positive component and delta + gamma net to a loss ⇒ **volatility-premium type**. Delta is not the main positive component; execution is 10% of gross (< 25%).

**By position type and session (trading clock, ₹ per cycle):**

| side | session | delta | gamma | theta | vega | resid | holding |
|---|---|---|---|---|---|---|---|
| long | D-1 day | -0k | 4k | -19k | 14k | -3k | -3k |
| long | D0 day | -1k | 9k | -40k | 29k | -6k | -8k |
| long | overnight step | -3k | 9k | -0k | -13k | -2k | -9k |
| short | D-1 day | -2k | -53k | 103k | -51k | 16k | 13k |
| short | D0 day | 4k | -200k | 207k | 33k | 34k | 78k |
| short | overnight step | 16k | -56k | 1k | 62k | 0k | 22k |

Short lots held on D0 produce 85% of the holding P&L; long lots (wings, lump, hedge) lose 21k per cycle on net — they are paid for with decay.

## 2. Implied versus realised volatility (observed, model-based)
ATM implied volatility (average of call and put, trading-minute clock) and realised volatility of the index minute returns (annualised on the same 93,750-minute year), averages over 275 cycles, % per year:

| und | iv_D1_open | iv_D1_mid | iv_D1_close | iv_D0_open | iv_D0_mid | iv_D0_late | rv_D1 | rv_D0 | overnight gap, mean |%| |
|---|---|---|---|---|---|---|---|---|---|
| NIFTY | 11.8 | 12.4 | 13.1 | 10.6 | 9 | 6.1 | 9 | 9.9 | 0.33 |
| SENSEX | 12.3 | 12.9 | 13.8 | 11.1 | 9.8 | 7.5 | 9.4 | 12.2 | 0.34 |

* On D-1, implied volatility (≈ 12–14%) is **above** realised (≈ 9%): the premium sold is rich on average.
* On D0, implied (≈ 11% at the open) is about equal to realised for NIFTY and **below** realised for SENSEX (≈ 9.8% vs 12.2% mid-day); late on D0 the ATM implied volatility is not reliable (price of a few rupees, minutes to expiry). This is consistent with the D0 gamma loss being large (-200k) and offset by decay (207k).
* **Not tested:** why implied exceeds realised (risk premium, demand for protection, expiry-day convexity) or whether it persists.

## 3. Naive benchmark (Method 4)
One ATM straddle sold at the D-1 09:16 open and bought back at the D0 15:14 close, no management, one lot per leg at the constant lot size. Gross, no costs. The strategy sells the equivalent of ≈ 112 such straddles of premium per cycle (premium sold ÷ one straddle's premium; re-sales count again).

| split | cycles | naive straddle, gross % of premium | strategy, gross % of premium sold |
|---|---|---|---|
| ALL | 275 | 7.5% [-1.6%, 16.1%] | 7.0% [4.7%, 9.1%] |
| IS | 175 | 9.4% | 8.4% |
| LIVE_FITTED | 36 | 8.7% | 4.3% |
| OOS | 64 | 2.4% | 5.7% |

* Per straddle, the naive hold has mean ₹996, worst ₹-41,369, standard deviation ₹9,434; the strategy per straddle-equivalent of premium has mean ₹539, worst ₹-15,905, standard deviation ₹2,942. **Dispersion per ₹ sold is about 3.2× lower in the strategy.**
* The naive result is not stable across splits (9.4% IS, 2.4% OOS, 8.7% live window); the strategy's (8.4%, 5.7%, 4.3%) is positive in all three but varies too.
* **Caveat:** "premium sold" counts every re-sale, so the strategy's denominator is inflated by turnover; the comparison per ₹ is not per ₹ of risk. The ratio test does not show that the rules add mean return per unit of premium; it shows they do not obviously subtract it, while taking it with much smaller dispersion.

## 4. Ablations and placebos (Methods 2 and 3)
Re-running the whole chain with one rule removed (or broken). Δ vs the full strategy, per cycle, net of costs, with a week-cluster bootstrap interval; p5 Δ and worst Δ are the changes in the 5th-percentile and worst cycle (negative = the variant has a worse tail).

| variant | net Δ/cycle | gross Δ/cycle | net Δ IS / OOS / live | same sign in all 3 | p5 Δ | worst Δ | verdict |
|---|---|---|---|---|---|---|---|
| no D-1 timetable | -14k [−35k, 7k] | -25k | -29k / +4k / +29k | no | +51k | +99k | not distinguishable from zero |
| no D-1 breakout pairs | -8k [−17k, 2k] | -11k | -6k / -16k / -1k | yes | +1k | +256k | not distinguishable from zero |
| no D-1 solo ladder | -19k [−35k, −5k] | -24k | -21k / -26k / -1k | yes | -2k | +564k | removing it LOWERS net (it carries the edge) |
| no D-1 per-lot stops | -22k [−55k, 7k] | -23k | -12k / -80k / +37k | no | -88k | -15k | not distinguishable from zero |
| no D-1 wings | +18k [10k, 25k] | +14k | +20k / +13k / +15k | yes | +10k | -90k | removing it RAISES net (it hurts the mean) |
| no overnight lump | +8k [5k, 12k] | +8k | +9k / +7k / +5k | yes | +2k | -104k | removing it RAISES net (it hurts the mean) |
| no D0 new sells | -36k [−60k, −11k] | -78k | -48k / -26k / +7k | no | +74k | +0k | removing it LOWERS net (it carries the edge) |
| no D0 timetable waves | -24k [−46k, −4k] | -48k | -32k / -15k / +1k | no | +37k | +0k | removing it LOWERS net (it carries the edge) |
| no D0 breakout pairs | -2k [−4k, 0k] | -4k | -2k / +0k / -1k | no | +1k | +0k | not distinguishable from zero |
| no D0 solo ladder | -24k [−43k, −6k] | -43k | -34k / -16k / +11k | no | +34k | +0k | removing it LOWERS net (it carries the edge) |
| no D0 counter-sells | -6k [−12k, −1k] | -16k | -8k / -7k / +2k | no | +1k | +0k | removing it LOWERS net (it carries the edge) |
| no D0 stop / take-profit | +21k [−19k, 60k] | +4k | +36k / +9k / -28k | no | -48k | +0k | not distinguishable from zero |
| no D0 hedge | +8k [7k, 10k] | +0k | +9k / +8k / +5k | yes | +4k | +0k | removing it RAISES net (it hurts the mean) |
| no cycle stop | +20k [1k, 37k] | +36k | +17k / +12k / +46k | yes | -61k | -74k | removing it RAISES net (it hurts the mean) |
| D0 module only | -32k [−65k, 2k] | -52k | -54k / -9k / +35k | no | +69k | +160k | not distinguishable from zero |
| PLACEBO: ladder sells the opposite right | -35k [−70k, −1k] | -36k | -38k / -33k / -22k | yes | -73k | +164k | removing it LOWERS net (it carries the edge) |
| PLACEBO: waves shifted 37 min | -19k [−37k, −1k] | -22k | -27k / -9k / +6k | no | +2k | -82k | removing it LOWERS net (it carries the edge) |

* **Selling rules carry the size of the edge** (D-1 ladder, D0 new sells, waves, ladder, counter-sells). Caution: removing a selling rule also removes premium sold, so this is *scale* as well as *timing*. The two tests that keep the amount of selling and break something else:
  * **P1 direction:** selling the opposite right on the reactive ladder lowers net by -35k per cycle (interval [-70k, -1k]), same sign in IS, OOS and the live window ⇒ **the direction of the reactive sale is part of the edge** (it sells the right that is moving away from the money). In the flipped variant the change is almost entirely in **delta** (−₹31k of −₹36k gross; gamma +₹5k, theta −₹6k, vega −₹10k): the real ladder's direction earns directional P&L, the flipped one gives it back. **Correction:** I first called this a trend-aligned (momentum) rule. `DESIGN_THESIS.md` (T3, T6) shows the index reverts after the trigger and the ladder sale reduces |book delta| in 74% of triggers: the flipped ladder loses because it **un-hedges** the short-gamma book (its gross interval also includes zero), not because the real ladder forecasts trends.
  * **P2 timing:** shifting scheduled waves by 37 minutes lowers net by -19k [-37k, -1k] but the sign is **not** the same in all three splits (live window +₹6k): the exact minute of the waves is **at most weakly** supported.
* **Protective rules cost mean:** no wings +18k, no lump +8k, no hedge +8k, no cycle stop +20k per cycle (all with intervals above zero and the same sign in all splits). The tail benefit in the simulation is small or absent for wings (p5 improves without them; worst cycle worsens by ₹90k) and clear for the cycle stop (p5 −₹61k, worst −₹74k without it). **Margin and capital are not modelled here** — if the real system holds wings and a hedge for margin relief, the simulator cannot see that benefit (Unresolved).
* **Costs are half the gross edge:** the full strategy earns ₹124,657 gross and ₹61,071 net per cycle at constant lot size (51% lost to slippage, statutory costs and ₹20/order over ≈ 1,253 orders per cycle). Gross-only effects in the table (for example the D-1 timetable: gross -25k with an interval excluding zero, net -14k with an interval including zero) are **not established net of costs**. Real broker costs are unknown.

## 5. What is and is not supported
| claim | evidence level |
|---|---|
| The profit is carry from selling premium (decay exceeds gamma loss) | **Observed** (clock-independent total), model-based decomposition |
| Directional beta is not the main source | **Observed**: net delta 13k of 92k holding; the ladder's direction is a delta re-balancing choice, not a forecast (corrected in `DESIGN_THESIS.md`) |
| It is not produced by the fill model | **Observed**: execution term 10% of gross (but a 10% dependence on the assumed fill position remains) |
| Direction of the reactive sale matters | **Observed** in the simulator (placebo, same sign in IS / OOS / live, gross interval includes zero); reason = delta re-balancing (`DESIGN_THESIS.md`) |
| The exact minute of the waves matters | **Weak** (sign not consistent across splits) |
| The management rules raise the mean return per ₹ sold | **Not supported** (difference -0.5%, interval [-8.7%, 8.2%]) |
| The rules reduce dispersion per ₹ sold ≈ 3× | **Observed** (per straddle-equivalent, naive hold vs strategy) |
| Wings, lump, hedge protect the tail | **Not supported in this simulator**; margin benefit not modelled (**Unresolved**) |
| Implied volatility exceeds realised on D-1 | **Observed** (model-based ATM IV, trading clock) |
| The premium is a persistent, tradable risk premium | **Not testable here** (3 years, naive straddle's mean not distinguishable from zero) |
| Edge survives real costs | **Unknown** (cost model inherited, half the gross) |

## 6. Adversarial notes — why this could be fake
* **Same data used many times.** The exploratory ablations reuse every cycle; nothing here is untouched evidence.
* **Greek attribution is a model** (Black–Scholes, r = 6.5%, no dividends, per-contract implied volatility, minute marks); the residual is 40k–175k per cycle; the vega/theta split flips sign with the clock; overnight and expiry-minute implied volatilities are unreliable.
* **Ablation = my simulator with the assumed D-1 and D0 timetable**, causal fill pricing, and the 0.30 / 0.62 fill positions; a different (real) rule detail could change the ranking.
* **The strategy is a short-volatility book with a fat left tail** (worst cycle ≈ −₹1.3 million on a ₹2 crore base; p5 ≈ −₹377k); an apparently stable carry in 3 years that includes only a few stress events can end with a loss that wipes many cycles.
* **Per-₹-premium comparison is not per-unit-of-risk.**
* The naive straddle's mean is statistically indistinguishable from zero, so "the strategy beats the naive hold" is **not** claimed; the claim is "similar mean per ₹ sold, much lower dispersion".

## 7. Next tests (not run)
1. More years (2020–2022) for the naive-carry and per-₹-premium comparison — the cheapest way to reduce the uncertainty in item 3.
2. A margin model (SPAN-style) to price the wings/hedge benefit the simulator cannot see.
3. Day-shifted placebo (shift all selling rules by one day) as a second timing test.
4. Real broker costs, then repeat the net-of-cost ablations.
5. Forward / paper trading against this pre-registered reading.
