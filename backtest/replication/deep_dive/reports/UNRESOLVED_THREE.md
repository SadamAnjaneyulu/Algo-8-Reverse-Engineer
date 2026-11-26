# The three unresolved questions — result

*Plan: `UNRESOLVED_THREE_PLAN.md` (committed before the tests). Builds on `PREMIUM_AND_ARCHITECTURE.md`. 275 cycles (Nov 2023 – Nov 2026), 35 of them with the real order log. Every cycle was used before: **exploratory**. Figure: `figures/bl_unres.png`.*

## 0. Corrections first
1. **Overnight gap — corrected twice.** My first reports used the 09:16 open (largest cycle-night gap **2.77%**). In the previous version of this report I called that wrong because the first print (09:15) of 3 Feb 2026 is **4.62%**. Checking the raw bars (review, 24 Nov): that print existed only at the opening tick — NIFTY printed 26,264.90 against a previous close of 25,079.90, then traded down to 25,783.15 and closed the first minute at 25,784.45 (**2.77%**), and several 09:15 option prints were stale (a 26400 call at ₹0.90, a 25700 put at ₹631). **For anything that can be traded, the 09:16 measure (2.77%) is the right one**; the first print is kept only as an upper bound for tail statistics. Only 1 of 275 cycle nights differ by more than 1% between the two. The −5.13% daily-file gap of 7 Apr 2025 is not a cycle night.
2. **What the 3 Feb 2026 night was worth to the long legs** (previous version: "≈ ₹7 lakh" — wrong attribution). The overnight mark-to-market of the carried book at the first tradeable minute was −₹53k with the long legs and −₹2.14 lakh without them: **the gap protection was worth ₹1.62 lakh** (≈ 9 average cycles of their cost). The cycles' net results differ by ₹6.97 lakh, but ≈ ₹5.4 lakh of that comes from the two books being managed differently later on D0, not from the gap. The overnight ratios on the 09:16 basis (0.61; median night 0.27; top 10% of nights 68%) stand; the first-print versions (0.63 / 0.39 / 63%, n = 224) use partly stale 09:15 option prints and are **withdrawn**.
3. **What I could not obtain** (stated before any test): NSE's daily SPAN files and a long index history (the container cannot reach them; one attempt to reach a market-data site with a spoofed browser header was blocked by the environment and not retried), and any signed option order flow.

## 1. The answers in brief
| Question | Answer | Level |
|---|---|---|
| **Q2 Real margin** | Not obtained from NSE. On the **real** order log the modelled peak margin is a median **₹1.58 crore** (1.13–1.73), above ₹2 crore in **9%** of cycles: the real book sits at ≈ 80% of the capital at its peak (expiry day) and uses ≈ ₹0.42 crore overnight. That is **consistent with a binding ₹2 crore constraint**; it does not prove it | Observed under an unverified scan range |
| **Q3 Extreme gaps** | With its long legs the carried book is **long the far tail** (it *gains* at 10–15% gaps); without them the same shorts lose ₹59.1–131.8 lakh on average at 10–15% and, with IV doubled, breach the ₹2 crore capital in 3% of books at +10% and 10% at +15% (downside worst case ₹1.99 crore). In expectation the legs are **about break-even** against their ₹17.6k per cycle; a 3-year sample cannot settle it. They are **survival insurance at roughly a fair price** | Observed (stress) / Unresolved (frequency) |
| **Q1 Expiry-day premium** | Not jumps (earlier), **not pinning**, **not visible order-flow pressure**. One mechanism is supported: **the official settlement is an average, so the last half hour is calmer than a spot print** (variance ratio 0.63); the 15:00 straddle loses 15% against the last print but earns 12% against the settlement. It existed until the closing auction session started on 3 Aug 2026 and is gone since. Over-pricing also **rises with distance from the money, puts more than calls**. The rest is unexplained | Observed (E1, E3); Not supported (E2, E4); Unresolved (the remainder) |

## 2. Question 2 — the true margin
**What is verified and what is not.**
| Item | Status |
|---|---|
| Index price scan range = 6σ·√2 with a 9.3% floor; volatility scan 25% of EWMA volatility, minimum 4% | **Search snippets of NSE Clearing's pages (two separate searches); the pages themselves timed out twice** — best available, not verified |
| Extreme-loss margin 2% on short index options (+2% on expiry day from 20 Nov 2024) | SEBI circular of 1 Oct 2024 as reported by Zerodha / ICRA; the circular text was not opened |
| Daily SPAN files with the actual parameters | **Not reachable** |

With σ = the cycle's opening ATM implied volatility (median 0.113), 6σ√2 exceeds 9.3% in only 7.3% of cycles, so the 9.3% floor is the operative scan range in 93% of cycles.

**Test on the real book** (35 cycles, 39,874 real orders, positions rebuilt minute by minute and valued on the same option chains):
| statistic | value |
|---|---|
| real peak margin, median (₹ crore) | 1.58 [1.13, 1.73] |
| real cycles with peak margin > ₹2 crore | 0.09 [0.00, 0.18] |
| simulator, same cycles: peak margin median (₹ crore) | 1.31 |
| simulator, same cycles: share of cycles > ₹2 crore | 0.14 |
| Spearman real vs simulator peak margin | 0.49 [0.16, 0.73] |
| ratio of medians real / simulator | 1.20 |
| real overnight (D-1 close) margin, median (₹ crore) | 0.42 |
| real: peak short units, median | 4,550 |

* **Plan rule:** *consistent with a binding ₹2 crore constraint* if the median is between ₹1.0 and ₹2.0 crore and at most 10% of cycles exceed ₹2 crore → **met** (1.58 crore; 8.6%). *Model–real agreement* needs a cycle-level Spearman ≥ 0.6 → **not met** (0.49). So the model gets the **level** right (simulator median 1.31 vs real 1.58 crore; the real system runs ≈ 20% larger than the simulator) but not which cycle is large.
* **Where the capital goes:** peak margin of a real cycle is ₹0.57 crore on D-1 and ₹1.70 crore on D0 (median of cycle maxima). The overnight carry is cheap in capital (≈ ₹0.42 crore); the expiry-day book is what meets the ₹2 crore limit — which is what the D0 hedge and the D0 stop/take-profit control (`PREMIUM_AND_ARCHITECTURE.md`: without them 52–55% of simulated cycles exceed it).
* **Caveat that can reverse the reading:** if the true scan range is lower than 9.3% (older regime 3σ, ≈ 2–3%) every margin falls by roughly a third to a half and the real book would sit well below ₹2 crore — then capital is **not** the binding constraint. Only the daily SPAN files settle this.

## 3. Question 3 — extreme gaps
**What the data contain.** Largest first-print gaps on cycle nights:

| night (D-1 → D0) | index | gap at the first print | gap at the 09:16 open | daily file |
|---|---|---|---|---|
| 2026-02-02 → 2026-02-03 | NIFTY | +4.62% | +2.77% | +4.75% |
| 2026-03-18 → 2026-03-19 | SENSEX | -2.53% | -1.86% | -2.58% |
| 2025-04-11 → 2025-04-15 | SENSEX | +2.09% | +1.79% | +2.23% |
| 2026-02-27 → 2026-03-02 | NIFTY | -1.84% | -1.32% | -2.08% |

Over all 770 nights of the daily files the largest gaps are NIFTY 5.13% and SENSEX 5.33%. The daily files' opens are **opening prints** (like the 09:15 tick of 3 Feb 2026), so this distribution and the tail fit below are an **upper bound** on tradeable gaps. The 3 years are calm: nothing near the 7–13% moves of 2008 or March 2020.

**Documented history (third-party lists, close-to-close, not opening gaps).** The Stable Investor and Learn Stock Market lists give **21 NIFTY falls of 5% or more between 2000 and 2022** (up to −12.98% on 23 Mar 2020, −12.24% in 2004, −12.20% in 2008); a news search adds 4 Jun 2024 (−5.93%). The lists are not complete after 2022 and list no rises or opening gaps. That is **≥ 0.35% of nights** over ≈ 5,972 nights, clustered in 2008 and 2020. Whether such a fall arrives as an overnight gap or intraday is **not known**; it is used below as an upper bound (gap = whole move) and with half of it.

**Stress of the book carried overnight** (gap applied at the D-1 close, implied volatility × 1.5, time value kept; loss in ₹ lakh, mean over books / worst book):

| book | -10%: mean / worst (₹ lakh) | -5%: mean / worst (₹ lakh) | +5%: mean / worst (₹ lakh) | +10%: mean / worst (₹ lakh) |
|---|---|---|---|---|
| real book (long legs as traded) | -10.5 / 11.0 | 3.0 / 10.0 | -0.2 / 10.0 | -21.0 / 10.0 |
| same shorts, long legs removed | 59.1 / 130.7 | 27.0 / 62.1 | 38.2 / 63.2 | 84.1 / 208.2 |
| simulated full book | -3.6 / 52.7 | 7.0 / 34.7 | 3.5 / 32.6 | -9.0 / 38.8 |
| simulated, no D-1 longs | 64.7 / 151.2 | 29.8 / 71.5 | 30.1 / 62.1 | 65.1 / 136.4 |
| simulated, no lump | 21.5 / 88.7 | 16.8 / 49.6 | 12.5 / 35.1 | 14.2 / 52.6 |

* The **real** carried book is net long convexity: it loses at most ₹10.0–11.0 lakh in its worst case at 5–10% gaps and **gains** ₹26.8 lakh on average at −15%. Without the long legs the same shorts lose ₹27.0 lakh at 5%, ₹59.1 lakh at −10%, ₹131.8 lakh at +15%.
* **Share of books losing more than the ₹2 crore capital** (IV × 2.0):

| gap (IV ×2.0) | real book | real, long legs removed | simulated full | simulated, no D-1 longs | real no-longs: worst loss (₹ crore) |
|---|---|---|---|---|---|
| -15% | 0% | 0% | 0% | 2% | 1.99 |
| -10% | 0% | 0% | 0% | 0% | 1.31 |
| +10% | 0% | 3% | 0% | 0% | 2.17 |
| +15% | 0% | 10% | 0% | 1% | 4.13 |

**Frequency of large gaps (what a calm sample can say).** Generalised Pareto fit to |gap| above its 95th percentile (39 exceedances; shape 0.21, 95% interval [-0.28, 0.54], i.e. consistent with anything from a thin to a heavy tail):

| |gap| ≥ | NIFTY: probability per night [95%] | SENSEX | exponential tail (NIFTY) | shape 0.3 (NIFTY) | break-even probability, simulated / real books |
|---|---|---|---|---|---|
| 3% | 0.444% [0.097%, 0.868%] | 0.582% | 0.4033% | 0.540% | 1.89% / 1.45% |
| 5% | 0.086% [0.001%, 0.250%] | 0.095% | 0.0299% | 0.139% | 0.71% / 0.56% |
| 7% | 0.026% [0.000%, 0.121%] | 0.020% | 0.0022% | 0.053% | 0.41% / 0.33% |
| 10% | 0.006% [0.000%, 0.060%] | 0.003% | 0.0000% | 0.018% | 0.24% / 0.20% |

The fitted probability of a 5% gap (0.086% per night) is **a quarter of the documented frequency** of 5% falls (0.35%): the 2023–26 sample under-represents crises, as expected. Break-even probabilities are the frequencies at which a gap of that size, alone, repays the legs' net cost of ₹17.6k per cycle.

**Do the long legs pay in expectation?** Net cost of the legs in the simulator: ₹17.6k per cycle (this already contains their payoff on 3 Feb 2026). The comparison that matters is the **extra** benefit from gaps larger than those in the sample (₹ per cycle, base volatility shock 1 + 10·|gap|, capped at 2):

| books | volatility shock | gap-protection value over the 770 nights (₹ per cycle) | same, GPD tail model | extra from tail beyond the sample (GPD) | extra from documented falls 2000–2022, gap = full move | same, gap = half the move |
|---|---|---|---|---|---|---|
| simulated books | base: 1 + 10|gap| (cap 2) | 45,413 | 45,512 | 98 | 15,741 | 4,852 |
| real books | base: 1 + 10|gap| (cap 2) | 62,170 | 61,844 | -326 | 16,144 | 5,165 |

* Fitted tail beyond the sample adds ≈ ₹98 per cycle: **nothing**, because a tail fitted to 3 calm years has none to add.
* Documented falls add ≈ ₹15,741 per cycle if every one arrived as an overnight gap of its full size, ₹4,852 if half — **against a cost of ₹17,550**. Counting upside gaps (not listed) could roughly double it. So the legs are **at or just below break-even on the documented history, and clearly below on the fitted tail**.
* **Reading rule of the plan:** they *pay in expectation* only if both the fitted tail and the documented comparator exceed the cost → **not met**. They *prevent ruin* if the hedged book stays inside ₹2 crore at the largest documented gap while the unhedged one does not → **met** (hedged worst loss ₹10.0 lakh at ±15%, IV × 2; unhedged worst ₹4.13 crore). Verdict: **survival insurance, roughly fairly priced, not provably profitable**.
* What this ignores: day-of management after the gap (the cycle stop cannot act on an opening gap but later rules can), exchange circuit breakers at the open for moves of 10% or more (positions cannot be closed anyway), and margin calls.

## 4. Question 1 — why is the expiry-day premium rich?
**E1 — the settlement is an average (supported, but not in 2026).** Settlement = the official close of the D0 date. If it is built from last-half-hour prices it should vary less than a spot print over 15:00–15:30.

| stat | all [95%] | IS | OOS | live window (36) |
|---|---|---|---|---|
| Var[ln(settle / spot 15:00)] / Var[ln(spot 15:29 / spot 15:00)] | 0.63 [0.53, 0.74] | 0.52 | 0.54 | 0.97 |
| short straddle from 15:00 to the 15:29 print, % of premium | -15.2% [-30.8%, -1.8%] | -40.1% | -4.9% | 15.7% |
| short straddle from 15:00 to the official settlement, % of premium | 11.6% [0.1%, 22.2%] | 9.8% | 13.9% | 12.2% |
| extra premium from settlement averaging (settlement minus print), % of premium | 26.8% [17.4%, 37.1%] | 49.9% | 18.8% | -3.5% |
| realised / implied variance, 15:00 to settlement | 0.71 [0.54, 0.91] | 0.92 | 0.59 | 0.59 |
| realised / implied variance, 15:00 to the 15:29 print | 1.12 [0.88, 1.42] | 1.76 | 1.09 | 0.60 |

* The settlement's variance over the last half hour is **37% lower** than the 15:29 print's (0.63 [0.53, 0.74]; a pure 30-minute average would give ≈ 0.33).
* The market prices the print, not the average: at 15:00 the implied variance is **fair-to-cheap against the 15:29 print** (1.12) and **rich against the settlement** (0.71). The same 15:00 straddle loses 15% to the print and earns 12% to the settlement: **+27% of the 15:00 premium** [17%, 37%] comes from the averaging.
* **Why it vanished in 2026 — explained (post-hoc test, mechanism documented earlier in the `research/strong-findings` branch):** SEBI's **closing auction session took effect on 3 Aug 2026**; from then on the closing price is an auction price, not a 30-minute average. Split at that date: before, variance ratio **0.54** [0.43, 0.65] over 246 cycles (Jan – 2 Aug 2026 alone: 0.59); after, **1.01** [1.00, 1.03] over 29 cycles, with the settlement equal to the last print (median difference 0.0 bp). The extra premium went from 37% of the 15:00 premium to -1%. I did not read NSE's closing-price rule itself; that the daily-file close equals the official settlement is assumed.
* The strategy buys back at **15:14**, so it does not hold the settlement leg: the 15:14 → settlement slice is worth 0.6% of the 09:16 premium [-1.8%, 3.3%] — within noise.

**E2 — pinning (not supported).** At 14:00 the largest-open-interest strike within ±2% of spot (open interest available for 154 of 275 cycles): the settlement is +0.03 strike steps from it relative to a placebo from other cycles [-0.10, +0.18]; closer than the placebo in 57% of cycles [49%, 66%] — the interval includes 50%.

**E3 — moneyness (tail demand pattern).** Price versus realised payoff at settlement, options sold at the D0 09:16 open:

| option (09:16 open, held to settlement) | expires in the money | mean price | mean payoff | price ÷ payoff [95%] | price − payoff, % of ATM straddle |
|---|---|---|---|---|---|
| call 0.5% away | 19.6% | 52.57 | 46.46 | 1.13 [0.81, 1.8] | 2.3% |
| call 1% away | 7.3% | 20.94 | 17.15 | 1.22 [0.73, 2.9] | 1.4% |
| call 1.5% away | 3.6% | 9.25 | 6.46 | 1.43 [0.71, 8.2] | 1.0% |
| call 2% away | 1.1% | 4.68 | 1.51 | 3.11 [1.20, 732.4] | 1.2% |
| call 3% away | 0.0% | 1.82 | 0 | no payoff in 275 cycles | 0.7% |
| put 0.5% away | 16.4% | 55.62 | 44.76 | 1.24 [0.88, 1.9] | 4.1% |
| put 1% away | 8.4% | 23.67 | 12.69 | 1.86 [1.19, 3.8] | 4.1% |
| put 1.5% away | 1.8% | 11.07 | 1.75 | 6.31 [2.97, 42.5] | 3.5% |
| put 2% away | 0.0% | 5.72 | 0 | no payoff in 275 cycles | 2.1% |
| put 3% away | 0.0% | 2.12 | 0 | no payoff in 275 cycles | 0.8% |

* The ratio **rises with distance** for both rights and is higher for **puts** (put 1.5% away: priced 6.3× its payoff; the 2% and 3% options never paid in 275 cycles). Intervals are wide, and this is the signature of tail/lottery demand **or** of 3 calm, mostly rising years in which puts expired worthless. In rupees the over-pricing is concentrated within ≈ 1.5% of the money (up to ≈ 4% of the ATM straddle premium per option).

**E4 — option order flow (not supported).** Signed volume of the ATM call and put (tick rule) in a 15-minute block against the next block's change in implied variance not explained by realised variance: Spearman -0.018 [-0.041, +0.006] over 6,049 blocks (the same-block correlation +0.22 is mechanical). No evidence of price pressure that reverses; the proxy is crude (no quotes, no true sign).

**E5 — where the D0 straddle premium accrues.**

| segment (short ATM straddle sold 09:16) | P&L, % of the 09:16 premium [95%] |
|---|---|
| 09:16 to 14:00 | 4.4% [-4.9%, 13.0%] |
| 14:00 to 15:14 | 1.3% [-4.6%, 6.9%] |
| 15:14 to official settlement | 0.6% [-1.8%, 3.3%] |
| 09:16 to official settlement (total) | 6.3% [-5.7%, 18.5%] |
| 09:16 to the 15:29 print (total) | 8.0% [-4.4%, 19.6%] |

No slice is individually distinguishable from zero: the straddle P&L is noisy; the variance ratios are what carry the evidence.

## 5. The idea, version 3
> Algo 8 sells two premia and holds three kinds of protection. **(1) Overnight:** gap insurance — the typical night is calm, a few are not; the long legs convert the carried book from short to **long the far tail**, which costs ≈ ₹18k per cycle net and is what keeps a 10–15% gap from reaching the ₹2 crore capital. **(2) Expiry day:** a persistent over-pricing, part of which is mechanical — the official settlement is an average, so the last half hour carries less risk than the options at 15:00 price — and part of which looks like a tail premium that is largest for puts; the rest is unexplained. **(3) Size:** the expiry-day book is held at about ₹1.6 crore of margin, close to the ₹2 crore capital, by the D0 hedge and stop/take-profit. The clock, the ladder and the stops keep the book balanced and bounded; none of it forecasts direction.

## 6. Evidence levels
| Claim | Level |
|---|---|
| The real book's modelled peak margin is ≈ 80% of ₹2 crore | **Observed** under an unverified scan range |
| Capital is the binding constraint on the expiry-day book | **Inferred** (consistent; reverses if the true scan range is ≪ 9.3%) |
| The carried book is long the far tail; the unhedged shorts would breach ₹2 crore in the worst 10–15% gaps | **Observed** (stress model) |
| The long legs pay in expectation | **Not supported**; **unresolved** (needs a tail the sample lacks) |
| Gaps ≥ 5% occur roughly once in 250–300 nights | **Documented** (close-to-close falls 2000–22, third-party lists) / **Unknown** as opening gaps |
| Settlement averaging explains part of the expiry-day premium (last half hour) | **Observed** before the closing auction (to 2 Aug 2026); **gone after 3 Aug 2026**, matching the rule change |
| Pinning, visible order-flow pressure | **Not supported** |
| Tail/lottery-type over-pricing, puts above calls | **Weak** (wide intervals; confounded by the sample's drift) |
| Who buys the expiry-day options | **Not testable** here |

## 7. What would settle the rest
1. **NSE daily SPAN risk-parameter files** for the cycle dates (the scan range per day) → replaces the margin assumption; **participant-wise open interest and volume** files → who holds the options; both are public NSE downloads the container cannot reach.
2. **Daily NIFTY / SENSEX open and close back to 2008** (including opening prints) → a real gap distribution and a real tail test of the long legs (2008, 2020, 2024).
3. **The official closing-price rule for NSE indices** (read from NSE's methodology) → confirm the averaging mechanism and see whether anything changed in 2026.
4. Forward logging: per cycle, the 15:00 → settlement variance ratio and the first-print gap.
