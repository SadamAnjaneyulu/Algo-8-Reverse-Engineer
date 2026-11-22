# Algo 8 — D-1 buy-backs, second pass: stops on losing positions and the market factor

*Plan `BUYBACK_STOP2_PLAN.md`, written before the tests. It follows the user's premise that buy-backs happen in loss (profitable shorts are carried) and that market movement plays a part. In-sample, D-1 of 32 cycles. Figure: `figures/bl_bs_summary.png`.*

## 0. Result
* **The premise holds:** **87%** of buy-back orders are on a lot in loss at the decision price (89% on fills).
  * The other 13% (177 orders, every lot on the contract in profit) are out of the money (median -1.0 strikes). A third of them (33%) come together with a buy-back on the other right, against 16% for in-loss ones: a two-sided cut-back, not a stop.
* **Market movement matters, as you suspected.** For a lot in loss, a fresh 30–60-minute spot breakout against the position multiplies the per-minute buy-back hazard about **10×** at every premium level (table below). At 1.7–1.8× of entry: 62% with a breakout against 22% without. With teacher-forced scoring, "premium ≥ 1.5× AND breakout" lifts contract-minute F1 from 0.39 to **0.49** (+0.08 in both halves).
* **But it is an accelerator, not the stop condition.** Run order by order on the real book, the plain intrabar premium stop stays best:
  * Minute high ≥ 1.6× entry: F1 0.588.
  * "Premium AND breakout": 0.545. Lots that cross 1.6× without a breakout are still bought back within minutes; waiting for the breakout delays them.
  * The **close** or typical price does worse than the **high** (0.553 / 0.531). The stop reacts to intrabar touches.
* **Adding a market exit does not help.** The combined rule "A OR B" was tested out-of-fold:
  * A = intrabar stop at about 1.6×.
  * B = in loss AND a breakout or premium-speed condition at a lower ratio.
  * On the real book it gives 0.566, below A alone (0.588); one fold chose no B part at all. Free-running it gives 0.553, against 0.558 for the current simulator stop.
  * The best deterministic buy-back rule therefore stays the intrabar own-premium stop (about 1.6×). Whole D-1 free-running F1 is unchanged at about 0.686.

## 1. Hazard: premium loss × breakout (lots in loss)
| minute high ÷ entry | hazard % (no breakout) | hazard % (fresh 60-min breakout against) |
|---|---|---|
| (1.0, 1.2] | 0.3 | 5.9 |
| (1.2, 1.3] | 0.3 | 5.2 |
| (1.3, 1.4] | 0.5 | 3.5 |
| (1.4, 1.5] | 0.5 | 5.3 |
| (1.5, 1.55] | 1.8 | 14.6 |
| (1.55, 1.6] | 3.5 | 25.5 |
| (1.6, 1.65] | 5.5 | 31.8 |
| (1.65, 1.7] | 6.3 | 39.0 |
| (1.7, 1.8] | 22.3 | 62.2 |
| (1.8, 9.0] | 11.8 | 74.1 |


## 2. Single stop indicators (loss gate; teacher-forced; out-of-fold thresholds)
| indicator | semantics | AUC_in_gate | thr | F1 | precision | recall |
|---|---|---|---|---|---|---|
| ratio_h | state | 0.812 | 1.596/1.635 | 0.393 | 0.442 | 0.362 |
| ratio_h | cross | 0.812 | 1.596/1.635 | 0.344 | 0.519 | 0.26 |
| vel3 | state | 0.876 | 1.141/1.141 | 0.324 | 0.299 | 0.356 |
| don60 | state | 0.77 | - | 0.323 | 0.22 | 0.613 |
| ratio_c | state | 0.773 | 1.525/1.525 | 0.316 | 0.269 | 0.386 |
| rsi_against | state | 0.854 | 21.724/22.890 | 0.309 | 0.238 | 0.458 |
| vel3 | cross | 0.876 | 1.169/1.169 | 0.291 | 0.345 | 0.256 |
| ratio_c | cross | 0.773 | 1.503/1.588 | 0.288 | 0.403 | 0.233 |
| trail_prem | cross | 0.778 | 1.724/1.763 | 0.283 | 0.373 | 0.228 |
| don60 | cross | 0.77 | - | 0.256 | 0.175 | 0.487 |
| rsi_against | cross | 0.854 | 25.769/22.890 | 0.254 | 0.272 | 0.24 |
| don20 | state | 0.786 | - | 0.252 | 0.155 | 0.671 |
| boll | state | 0.726 | - | 0.238 | 0.155 | 0.522 |
| trail_prem | state | 0.778 | 1.689/1.763 | 0.214 | 0.151 | 0.372 |


Spot-only stops (ATR since entry, Chandelier, Supertrend, Parabolic SAR, EMA cross, Bollinger) are all far weaker than the premium stop alone, and none acts as a stop on its own.

## 3. Two-indicator rules and the breakout window (teacher-forced)
| rule | F1_half1 | F1_half2 | F1 |
|---|---|---|---|
| ratio_h (state) AND don60 (state) | 0.45 | 0.502 | 0.476 |
| ratio_h (state) AND don20 (state) | 0.438 | 0.504 | 0.471 |
| ratio_h (state) AND vel3 (state) | 0.436 | 0.49 | 0.463 |
| ratio_h (state) OR vel3 (state) | 0.414 | 0.459 | 0.436 |
| ratio_h (state) AND rsi_against (state) | 0.422 | 0.446 | 0.434 |
| ratio_h (state) OR vel3 (cross) | 0.409 | 0.455 | 0.432 |


| market | family | params | F1 | precision | recall |
|---|---|---|---|---|---|
| don45_close | A | [np.float64(1.5), np.float64(1.5)] | 0.493 | 0.595 | 0.423 |
| don30_close | A | [np.float64(1.5), np.float64(1.5)] | 0.492 | 0.587 | 0.425 |
| don45_close | B | [(np.float64(1.7), np.float64(1.5)), (np.float64(1.9), np.float64(1.5))] | 0.489 | 0.574 | 0.431 |
| don30_close | B | [(np.float64(1.9), np.float64(1.5)), (np.float64(1.9), np.float64(1.5))] | 0.489 | 0.58 | 0.425 |
| don60_close | B | [(np.float64(1.7), np.float64(1.5)), (np.float64(1.7), np.float64(1.5))] | 0.485 | 0.552 | 0.434 |
| don60_close | A | [np.float64(1.5), np.float64(1.5)] | 0.483 | 0.599 | 0.407 |


## 4. Price feed for the premium stop (real book, order by order, θ out-of-fold)
| price | theta_folds | precision | recall | F1 |
|---|---|---|---|---|
| close | [np.float64(1.5), np.float64(1.45)] | 0.615 | 0.501 | 0.553 |
| open_now | [np.float64(1.5), np.float64(1.45)] | 0.616 | 0.498 | 0.551 |
| close_now | [np.float64(1.55), np.float64(1.55)] | 0.675 | 0.468 | 0.553 |
| typical | [np.float64(1.5), np.float64(1.55)] | 0.636 | 0.456 | 0.531 |
| high | [np.float64(1.6), np.float64(1.6)] | 0.721 | 0.496 | 0.588 |


## 5. A OR B rule (chosen per fold; real book and free-running)
| mode | fold | theta | theta_lo | N | v | qty | F1_train |
|---|---|---|---|---|---|---|---|
| tf_bb | 0 | 1.6 | 1.4 | 30.0 | 1.25 | one | 0.5894 |
| tf_bb | 1 | 1.6 | nan | nan | nan | nan | 0.5916 |
| free | 0 | 1.65 | 1.4 | nan | 1.15 | one | 0.5695 |
| free | 1 | 1.6 | 1.4 | nan | 1.15 | one | 0.5563 |


## 6. Reading
* The buy-back logic is a **per-lot own-premium stop near 1.6× of entry, acting on intrabar prices**.
* Market breakouts against the position make it fire much faster. This is consistent with the live premium staying above the level during a breakout, while minute-high touches without a breakout are partly wicks the system's feed may not see. *Inferred.*
* The rest, roughly the low-ratio half, are in-loss exits during adverse moves. Every rule tried for them adds more false exits than true ones at minute resolution (A-or-B is negative out-of-fold), and they are not separable by any spot indicator tested (Supertrend, SAR, Chandelier, ATR, Donchian, Bollinger, EMA, RSI).
* The 13% in profit are two-sided cut-backs, not stops.

## Evidence labels
* **Observed:** §0–5.
* **Inferred:** the price-feed explanation.
* **Post-hoc:** the price-feed test, the A-or-B family, and the window refinement (the plan fixed the families, not these refinements).
* **Multiple testing:** about 30 indicators × 2 semantics plus combinations were tried. Only rules that improve in both cycle halves are reported as gains.
