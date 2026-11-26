# Algo 8 — the final alpha, and every open question answered

*24 Nov 2026. Synthesis of all 22 branches and of `ALPHA_SOURCE.md`, `DESIGN_THESIS.md`, `PREMIUM_AND_ARCHITECTURE.md`, `UNRESOLVED_THREE.md`. Checks behind §0 are in `src/bl_final_checks.py` → `outputs/final/`. Every cycle has been looked at before, so everything here is **exploratory**; the only untouched evidence will be new cycles.*

## 0. What was wrong (found in review)
| # | Statement made earlier | What is true | Whose error |
|---|---|---|---|
| 1 | "The largest overnight gap was 2.77% — that was a measurement error; the real figure is +4.6% (3 Feb 2026)" | **+4.6% was the opening tick only.** NIFTY printed 26,264.90 at 09:15 against a previous close of 25,079.90, traded down to 25,783 **within that same minute** and closed it at +2.77%. Several 09:15 option prints were stale (a 26400 call at ₹0.90, a 25700 put at ₹631). **For anything tradeable, 2.77% is the right number.** Only 1 of 275 cycle nights differs by more than 1% between the two measures | Mine (my "correction" was wrong); repeated in the review |
| 2 | "On 3 Feb 2026 the wings were worth ≈ ₹7 lakh" | ₹6.97 lakh is the difference in the **whole cycle's net result** between the full strategy and the version without D-1 longs. The **overnight** protection (mark-to-market of the carried book at the first tradeable minute) was **₹1.62 lakh** (−₹0.53 lakh with the long legs, −₹2.14 lakh without). The other ≈ ₹5.4 lakh came from the two books being managed differently later on expiry day | Mine; repeated in the review |
| 3 | "The settlement effect exists in 2023–Nov 2025 and disappears in 2026 (reason unknown)" | It disappears **on 3 Aug 2026, when SEBI's closing auction session started** (documented earlier in the `research/strong-findings` branch). Before: variance ratio 0.54 [0.43, 0.65] over 246 cycles, **including Jan – 2 Aug 2026 (0.59)**; after: 1.01 [1.00, 1.03] over 29 cycles, with the settlement equal to the last print | Mine (unexplained); the review's "2026" framing is imprecise |
| 4 | First-print overnight ratios (0.63 / median 0.39 / top 10% = 63%) | Withdrawn: they used partly stale 09:15 option prints. The 09:16-basis figures stand (0.61; median night 0.27; top 10% of nights = 68% of realised gap variance) | Mine |
| 5 | "The fitted tail shows the long legs add nothing" | A tail fitted to 3 calm years cannot see 2008- or 2020-type gaps; near-zero means "the sample is silent", not "no value". The daily-file gaps are opening ticks, so that fit is if anything an upper bound for *tradeable* gaps | Agreed with the review; now stated explicitly |

**Correct points in the review, adopted:** keep the three levels of resolution separate; the settlement result is not evidence of manipulation; the ₹5–16k tail benefit is a **model** estimate; 135 passing tests show the code does what it says, **not** that the financial conclusions are right.

## 1. The alpha (final)
> **Algo 8 is a short-volatility strategy for the last ~30 hours of a weekly index option. Its edge is the variance risk premium: realised variance near expiry is ≈ 20–40% below what option prices imply (realised ÷ implied 0.61–0.79). It harvests that premium in two different forms — an overnight gap-insurance premium (carried in a fully covered book, the "BTST" leg) and an expiry-day over-pricing (sold continuously while time value collapses). It does not forecast direction: it keeps the book balanced by selling the side the market moves away from, and it bounds the damage with per-lot stops, a ≈ ₹1.4 lakh cycle stop, and far wings that make the overnight book long the extreme tail. The edge is thin (≈ 20% of the premium collected survives the gamma loss), roughly half of it goes to costs, and part of the historical expiry-day premium (settlement averaging) was removed by the closing-auction rule from 3 Aug 2026.**

What it is **not**: an indicator system, a directional or trend system, an IV-timing system, a seasonal system.

## 2. Every question, answered
| # | Question | Answer | Evidence | Source |
|---|---|---|---|---|
| 1 | What does Algo 8 do mechanically? | D-1: ATM straddles from 09:16 on a ≈15-minute clock in 1-lot child orders, re-centred to the moving ATM, each with a cheap far wing (≈ 2.5% of the ATM premium); carry a long-covered book overnight; D0: keep selling on clocks while the book is active, re-balance, stop out lots, flatten by 15:14 (after 3 Aug 2026) | **Strong** (real logs, 31–35 cycles) | `STRONG_FINDINGS` F01–F34; D-1/D0 decodes |
| 2 | What idea was it built on? | "Near-expiry options over-price movement; sell them, carry the overnight, don't predict" — the client calls it a **BTST** algorithm; its sibling Algo 7 trades the expiry day only | **Strong** for intent (client wording + structure); intent itself cannot be proven | `DESIGN_THESIS.md` |
| 3 | Where does the P&L come from? | Premium decay (θ+vega+residual, ≈ ₹3.66 lakh per cycle) exceeds the gamma loss (≈ ₹2.87 lakh) by ≈ ₹0.79 lakh; delta ≈ +₹0.13 lakh; fill model ≈ 10%; 85% of holding P&L from short lots on D0 | **Observed** (model decomposition; θ/vega split not identified) | `ALPHA_SOURCE.md` |
| 4 | Is it directional or indicator-driven? | No. 75 index + 14 option indicators show no use; momentum has no skill; after the ladder's trigger the index **reverts** (−1.4 bp at 15 min, −5.5 bp to the D-1 close) | **Strong** | audit STR-03; stage-2; `DESIGN_THESIS.md` T3 |
| 5 | Is the premium real? | Realised ÷ implied variance: **0.74** (D-1), **0.61** (overnight), **0.79** (D0), all intervals below 1 | **Strong** (3 years of market data) | `DESIGN_THESIS.md` T1 |
| 6 | Why is the overnight premium rich? | Gap insurance: the median night realises 27% of what is priced; the 10% largest-gap nights carry 68% of the realised gap variance; P&L skew −4.3. Weekend/holiday pricing is **not** the reason | **Strong** (mechanism); who buys it: **not testable** | `PREMIUM_AND_ARCHITECTURE.md` |
| 7 | Why is the expiry-day premium rich? | Not jumps (7% of variance), not pinning, no visible order-flow pressure. **One supported mechanism:** until 2 Aug 2026 the settlement was an average, so the last half hour was calmer than the options priced (a 15:00 straddle earned +36% of its premium against the settlement); far-OTM options, puts more than calls, are priced well above their payoff (weak). The remainder is **unexplained** (structural demand is the leading untested candidate) | Settlement: **Observed**; moneyness: **Weak**; rest: **Unresolved** | `UNRESOLVED_THREE.md` |
| 8 | Why did that effect disappear in 2026? | The **closing auction session (3 Aug 2026)**: after it the settlement is an auction price, equal to the last print in the data (ratio 1.01) | **Observed** (post-hoc test of a mechanism documented earlier) | `outputs/final/final_e1_cas.csv` |
| 9 | What does the ladder do? | Re-balances delta: sells calls after new lows, puts after new highs; lowers the book's absolute delta at 74% of triggers (opposite sale: 0.02%). It is a hedge built from option sales, not a trend bet | **Strong** (T6 post-hoc) | `DESIGN_THESIS.md` |
| 10 | What does the 15-minute clock do? | Not a risk reducer (dispersion ratio 0.97 [0.91, 1.03]); most likely execution/size handling (1-lot DAY orders, freeze limits, averaging entry) | Risk role **not supported**; execution role **inferred** | `DESIGN_THESIS.md` T5 |
| 11 | Why the wings and the lump? | They make the overnight book **long the far tail**: with them the carried book gains at 10–15% gaps; without them the same shorts lose ₹0.59–1.32 crore on average and breach the ₹2 crore capital in 3–10% of books (IV doubled, upside gaps). They halve overnight margin (1.5–2.7× without them). Cost ≈ ₹17.6k per cycle net | **Observed** (stress model) | `PREMIUM_AND_ARCHITECTURE.md`, `UNRESOLVED_THREE.md` |
| 12 | Do the wings pay for themselves? | **About break-even, not proven.** Their net cost (₹17.6k/cycle) already includes the one large night (3 Feb 2026, overnight value ₹1.62 lakh). Extra expected benefit from larger gaps: ≈ ₹0.1k (tail fitted to 3 calm years) to ≈ ₹5–16k (documented 5–13% NIFTY falls of 2000–2022 treated as overnight gaps of half or full size, ≈ 1 per 280 nights) — a model estimate. They are **survival insurance at roughly a fair price** | **Unresolved** (needs a long gap history) | `UNRESOLVED_THREE.md` §3 |
| 13 | Why the D0 hedge and D0 stop / take-profit? | **Capital rules**: without them 37–55% of simulated cycles exceed ₹2 crore of approximate peak margin (15% with them) | **Observed** under an unverified scan range | `PREMIUM_AND_ARCHITECTURE.md` |
| 14 | Is ₹2 crore the binding constraint? | The **real** book's modelled peak margin: median **₹1.58 crore** [1.13, 1.73], above ₹2 crore in 9% of cycles; overnight only ≈ ₹0.42 crore. Consistent with a binding cap — **conditional** on the 9.3% scan range (from NSE pages seen only in search snippets). The model matches the level (real ≈ 1.2× simulator) but not which cycles are large (Spearman 0.49) | **Conditional** | `UNRESOLVED_THREE.md` §2 |
| 15 | Is it seasonal or regime-bound? | No supported calendar, month or regime effect; the only supported family (D0 opening gap) is fragile | **Not supported** | `BACKTEST3Y_REGIME.md` |
| 16 | Does it survive out of sample and costs? | Simulator, locked OOS (64 cycles): ₹0.56 lakh per cycle net, profit factor 1.56, t = 1.28 (interval includes 0); ≈ ₹0.08 lakh at 3× slippage, negative at 6×. Real logs (32 cycles): gross ₹18.9 lakh, positive under moderate/conservative costs, negative under adverse costs, depends on two winners | **Weak** | `BACKTEST3Y_RESULT.md`; `final_alpha_attribution` |
| 17 | Is it better than a naive straddle? | Same mean per ₹ of premium (7.0% vs 7.5%, difference not significant) with ≈ 3× lower dispersion: the rules buy stability, not extra return | **Observed** | `ALPHA_SOURCE.md` |
| 18 | How well is it reconstructed? | D0 lots by evidence tier 84.9% (target 90% not reached); the simulator earns ≈ 36% of the real P&L on the same 32 cycles | **Partial** | D0 deep dive; `BACKTEST3Y_RESULT.md` |
| 19 | Is it deployable? | **No, not yet.** Next stage is paper/forward trading with the pre-registered measurements below | — | — |

## 3. Where Algo 8 sits on the research ladder
| Stage | Status |
|---|---|
| Performance (did it make money?) | Real logs: positive gross, cost-dependent net |
| Statistical quality (unusual vs null?) | The **premium** is statistically clear (variance ratios); the **strategy P&L** is not (OOS t = 1.28) |
| Robustness (perturbations, unseen data) | Survives modest cost stress; fails 6× slippage; part of the premium removed by a rule change (Aug 2026) |
| Paper-trading candidate | Yes, with the measurements below |
| Deployment candidate | No |

## 4. Software validation ≠ empirical validation
* **Software:** 136 tests pass. They check that the scripts reproduce the saved outputs and that stated facts match those outputs.
* **Empirical:** every number above comes from data already examined; the margin rests on an unverified scan range; the gap tail rests on 3 calm years plus third-party lists of close-to-close falls; intent cannot be read from logs.

## 5. What would change the conclusions (data needed)
1. **NSE daily SPAN risk-parameter files** for the cycle dates → settles question 14 (and 13).
2. **Daily NIFTY / SENSEX open, close and first-minute prices back to 2008** → a real gap distribution; settles question 12.
3. **NSE participant-wise open interest / volume** → who buys the expiry-day options; addresses question 7's remainder.
4. **Forward logging per new cycle:** realised ÷ implied variance by segment, the tradeable overnight gap, peak margin, and the P&L of each module — against the numbers in this document.
