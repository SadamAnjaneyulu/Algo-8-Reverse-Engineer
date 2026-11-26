# Algo 8 — the overnight lump (`v_`): trigger, structure, size and fate

*Exploratory follow-up of `D1_LONG_SIDE.md`, done at the user's request. **No plan was written before these steps**, so every result here is post-hoc and in-sample: 30 cycles with a lump, out of 32. Figure: `figures/bl_lp_summary.png`.*

## 0. Result
| Question | Answer | Evidence |
|---|---|---|
| **Trigger: when** | A **clock**, with three regimes that change on fixed dates: 15:06–15:14 until 2026-08-05, 15:23–15:24 for 2026-08-12 to 08-19, and **15:30–15:35 from 2026-08-24**. These look like code or config changes, not a market signal. | Observed (date steps) |
| **Trigger: whether** | A lump is placed when shorts are carried overnight. The two cycles without one: a book already flat at 14:46 (stopped out), and a book with only 34 heavy-side shorts. Other small heavy sides also got tiny lumps (34 → 1 lot, 35 → 9 lots). | Observed |
| **Which side** | The **heavier short side** (more short lots), only that side in 80% of cycles. | Observed |
| **Order structure** | One decision, split into exchange freeze-quantity chunks: **27 lots for NIFTY (27 × 65 = 1,755) and 50 lots for SENSEX (50 × 20 = 1,000)**. All are IOC at one strike, sometimes with 1–2 small top-ups later (17 top-ups). | Observed |
| **Strike** | About **2.2 σ√T OTM** using the ATM straddle (median 1.5% of spot). Best rule: 34% exact, 62% within one strike. A fixed % of spot gives 6%. | Observed, rule partial |
| **Size** | Roughly **0.83 × heavy-side shorts (NIFTY), 0.50 × (SENSEX)**. No tested rule does better than about **±13 lots (≈ 24% median error)** out-of-cycle. | **Unresolved** |
| **What it does** | Before the lump, a move in the heavy direction loses a median ₹29 L within 6% (intrinsic). After it, the worst loss is a median ₹15 L: the tail is roughly halved and becomes much more uniform across cycles (coefficient of variation 0.34 → 0.17). It is **not** a delta hedge (it removes about 5% of book delta). | Observed |
| **D0 fate** | The `v_` module itself sells lump lots on D0 in **18 of 30 cycles** (57% of lump lots), from 10:41 (median first sale) to 14:45 (median last), at a median **7% of the purchase price**, never above it. Modules share contracts: counting every module, 96% of lump contracts are fully closed on D0. So the remaining lots are sold by the body, hedge or stop streams; they do not expire. | Observed |

**Reading (inferred):** the lump is end-of-day **gap insurance** on the side that would lose most from an overnight move. It is placed at a clock time, about 2 σ√T out, and sized roughly in proportion to the heavy-side shorts. It costs about ₹19k per cycle (median) and in every cycle where `v_` sold it, it recovered at most about half its premium (median 7%): the cost of protection against a gap that did not happen in this sample.

## 1. Timing regimes (main decisions)
| regime | cycles | first | last |
|---|---|---|---|
| until 2026-08-05 | 13 | 15:06:45 | 15:14:19 |
| 2026-08-12 to 08-19 | 3 | 15:23:02 | 15:24:00 |
| from 2026-08-24 | 14 | 15:30:23 | 15:34:45 |


## 2. Size: everything tried (none decodes it)
| Hypothesis | Result |
|---|---|
| Fixed share of heavy-side shorts | NIFTY 0.83, SENSEX 0.50; leave-one-cycle-out error about 14 lots |
| Subset of heavy-side shorts (by sell type, moneyness or time sold; non-negative weights) | MAE 13.5–14 lots; no subset gets weight ≈ 1 with the others ≈ 0 |
| Rupee budget (MTM P&L, gross/net premium, heavy-side premium or mark) | spend ÷ budget coefficient of variation ≥ 0.44: rejected |
| Fixed worst-case loss cap (loss after the lump) | tighter (CV 0.17) but ₹10–21 L: not a fixed cap |
| Equalising the heavy and light tails (margin-style) | after the lump, the heavy tail is still about 2.0× the light tail: rejected |
| Overnight delta neutralisation | removes about 5% of book delta: rejected |

Log-linear size models, leave-one-cycle-out:

| model | MAE_lots | median_abs_err_pct | within_5_lots | within_10_lots |
|---|---|---|---|---|
| S_h | 14.4 | 28.0 | 30% | 50% |
| S_h + und | 14.7 | 28.0 | 30% | 40% |
| S_h + lump price | 13.3 | 24.0 | 37% | 60% |
| S_h + und + lump price | 17.0 | 35.0 | 27% | 43% |
| loss at lump strike | 12.8 | 24.0 | 33% | 50% |
| S_h + und + price + loss | 15.0 | 30.0 | 30% | 50% |


The strongest single association is the **intrinsic loss at the lump strike** (Spearman 0.80 with lots). That is the loss the book would take if the spot moved exactly to the lump strike. As a model it still leaves about ±13 lots. The real input is probably something the ledger does not contain, such as broker margin (SPAN) or a risk figure from the algorithm's own valuation. *Not testable.*

## 3. Strike rule (out-of-fold, all decisions)
| rule | param_fold | exact | within1 |
|---|---|---|---|
| % OTM of spot | 1.950/1.750 | 6% | 36% |
| σ√T units (ATM straddle) | 2.200/2.200 | 34% | 62% |
| premium = k × ATM same-right price | 0.060/0.080 | 21% | 47% |
| delta target | 0.015/0.025 | 23% | 62% |


## 4. D0 fate (`v_` module's own sales; other modules also close these contracts, see §0)
| und | expiry | bought | sold_d0 | buy_px | sell_px | first_sale | last_sale | n_sale_orders |
|---|---|---|---|---|---|---|---|---|
| NIFTY | 2026-06-30 | 74 | 47 | 4.14 | 1.1 | 09:25 | 14:25 | 7 |
| NIFTY | 2026-07-07 | 62 | 62 | 5.52 | 0.18 | 14:14 | 14:58 | 34 |
| NIFTY | 2026-07-14 | 50 | 0 | 6.85 | nan |  |  | 0 |
| NIFTY | 2026-07-21 | 56 | 56 | 4.65 | 0.67 | 10:39 | 14:31 | 26 |
| NIFTY | 2026-07-28 | 82 | 82 | 5.81 | 0.16 | 09:15 | 15:20 | 32 |
| NIFTY | 2026-08-04 | 69 | 61 | 5.47 | 0.94 | 09:16 | 13:49 | 10 |
| NIFTY | 2026-08-18 | 70 | 0 | 3.23 | nan |  |  | 0 |
| NIFTY | 2026-08-25 | 47 | 47 | 5.85 | 0.35 | 13:55 | 14:32 | 10 |
| NIFTY | 2026-09-08 | 70 | 37 | 5.35 | 1.51 | 09:25 | 13:38 | 19 |
| NIFTY | 2026-09-22 | 62 | 51 | 6.69 | 2.55 | 10:42 | 14:01 | 12 |
| NIFTY | 2026-09-29 | 77 | 0 | 8.73 | nan |  |  | 0 |
| NIFTY | 2026-10-06 | 14 | 13 | 6.43 | 0.11 | 15:05 | 15:14 | 5 |
| NIFTY | 2026-10-13 | 62 | 22 | 5.18 | 2.72 | 09:17 | 09:18 | 3 |
| NIFTY | 2026-10-19 | 40 | 0 | 8.05 | nan |  |  | 0 |
| SENSEX | 2026-06-25 | 54 | 68 | 21.42 | 1.51 | 12:32 | 14:20 | 33 |
| SENSEX | 2026-07-02 | 18 | 18 | 18.91 | 0.38 | 12:15 | 15:16 | 7 |
| SENSEX | 2026-07-09 | 54 | 54 | 15.0 | 0.91 | 14:43 | 14:59 | 18 |
| SENSEX | 2026-07-16 | 82 | 53 | 12.39 | 6.78 | 09:15 | 11:01 | 12 |
| SENSEX | 2026-07-23 | 42 | 0 | 20.25 | nan |  |  | 0 |
| SENSEX | 2026-07-30 | 30 | 30 | 21.24 | 0.6 | 09:19 | 15:11 | 11 |
| SENSEX | 2026-08-06 | 14 | 0 | 32.95 | nan |  |  | 0 |
| SENSEX | 2026-08-13 | 20 | 15 | 15.96 | 0.36 | 13:26 | 15:33 | 13 |
| SENSEX | 2026-08-20 | 37 | 0 | 15.76 | nan |  |  | 0 |
| SENSEX | 2026-08-27 | 43 | 0 | 14.5 | nan |  |  | 0 |
| SENSEX | 2026-09-10 | 79 | 0 | 19.81 | nan |  |  | 0 |
| SENSEX | 2026-09-17 | 18 | 0 | 58.88 | nan |  |  | 0 |
| SENSEX | 2026-09-24 | 35 | 0 | 16.28 | nan |  |  | 0 |
| SENSEX | 2026-10-01 | 40 | 40 | 15.91 | 0.8 | 14:28 | 15:05 | 17 |
| SENSEX | 2026-10-15 | 1 | 0 | 9.25 | nan |  |  | 0 |
| SENSEX | 2026-10-22 | 87 | 87 | 19.14 | 3.11 | 09:18 | 15:03 | 35 |


## Evidence labels
* **Observed:** timing regimes, side, chunking, D0 fate, tail effect.
* **Inferred:** the gap-insurance purpose; code-change regimes.
* **Unresolved:** exact size and exact strike.
* **Not testable:** broker margin and the system's own risk numbers.
* Everything here is post-hoc and in-sample.
