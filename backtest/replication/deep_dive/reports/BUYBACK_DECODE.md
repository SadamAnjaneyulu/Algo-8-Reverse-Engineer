# Algo 8 — D-1 body buy-backs: decoding the stop (and what limits accuracy)

*Plan `BUYBACK_DECODE_PLAN.md`, written before the tests. In-sample, D-1 of 32 live cycles: 1,324 buy-back lots (all 1-lot orders) in 841 events (same contract, within 3 s). Ratios use the order's limit-implied **decision price** (the price the algorithm saw), not minute bars, wherever the ledger allows. Figure: `figures/bl_bb_summary.png`.*

## 0. Result
| Question | Answer | Evidence |
|---|---|---|
| Is there a stop on the lot's own premium? | **Yes, for about half of the events.** 410 of 841 events have decision price ÷ cheapest open entry ≥ 1.45×, mode 1.5–1.7×, almost nothing above 1.8× (median 1.47×). | Observed |
| Is it a fixed threshold? | **No, it is graded.** The hazard per contract-minute rises 2% → 9% → 24% → 41% across 1.4–1.8× and does not jump at one level. The same holds in every underlying, version and cycle, so it is not a mix of different settings. The intrabar version (minute high ÷ entry) ranks best: AUC 0.81, out-of-fold threshold about 1.61–1.66×. | Observed |
| How many lots per stop? | The open lots on that contract that are above about 1.55× (71% within one lot). Not the whole contract: only 18% of stops close all lots on it. | Observed |
| Clocked checks? | No. Buy-back minutes are spread evenly across the hour (mild :00 and :05 excess). 48% fill at second :00. | Observed |
| Right-level controller (whole CE or PE book)? | Rejected. Right-level ratio before a buy-back ranges 0.74–1.45×; after it, it is not pinned to a level. | Observed |
| The other half (low-ratio, near ATM)? | **Fast adverse moves.** The best variable is the 3-minute premium rise (AUC 0.80, same in both halves). Not delta control (AUC 0.59), not a strike breach (0.53), not side balance (larger side 69% = chance). No threshold separates them (tree F1 0.13). Followed by a re-sale (roll) in only 14–22% of cases. | Observed; trigger unresolved |
| Ceiling of the decoded rule | Run on the **real** sells, the best stop design gives buy-back F1 **0.586** (plain close ≥ 1.5×: 0.572). The limit is the rule, not inherited sell errors. Timing tolerance ±3 minutes lifts it only to about 0.62 (free-running). | Observed |

**Accuracy impact (free-running, out-of-fold):** buy-backs 0.550 → **0.558**, wing sells 0.538 → 0.547, overall 0.684 → **0.686**. A small gain. The decoded structure is right, but half of the buy-backs have no recoverable trigger at one-minute resolution.

## 1. Stop variables tested (contract-minute panel, 102,270 rows, label = buy-back in the minute)
| variable | AUC | threshold (fold 1/2) | F1 ±1 min (out-of-fold) |
|---|---|---|---|
| rh_min | 0.806 | 1.610/1.627 | 0.399 |
| vel_h5 | 0.852 | 1.307/1.256 | 0.328 |
| vel_h3 | 0.866 | 1.239/1.198 | 0.313 |
| rc_min | 0.78 | 1.513/1.522 | 0.313 |
| vel_c5 | 0.833 | 1.253/1.218 | 0.301 |
| vel_h2 | 0.863 | 1.281/1.192 | 0.28 |
| vel_c3 | 0.843 | 1.207/1.161 | 0.278 |
| vel_h1 | 0.857 | 1.173/1.149 | 0.272 |
| vel_c2 | 0.835 | 1.139/1.146 | 0.27 |
| vel_c1 | 0.821 | 1.133/1.133 | 0.236 |
| spot_adv5 | 0.804 | 0.782/0.878 | 0.207 |
| spot_adv3 | 0.811 | 0.717/0.843 | 0.187 |
| spot_adv2 | 0.801 | 0.633/0.454 | 0.167 |
| spot_adv1 | 0.789 | 0.537/0.295 | 0.128 |


OR-combinations (entry stop OR premium speed) reach F1 0.43–0.44 out-of-fold (±1 minute, contract-minute), against 0.40 for the entry stop alone.

## 2. Stop design chosen in the simulator (out-of-fold, objective = buy-back lot F1)
| fold | tp | price | theta | vel | cluster | F1_train |
|---|---|---|---|---|---|---|
| 0 | 0.4 | close | 1.55 | (3, 1.4) | None | 0.591 |
| 1 | 0.4 | high | 1.6 | (5, 1.5) | None | 0.563 |


Both folds choose an entry stop near **1.55–1.6×**. Fold 1 prefers the intrabar high, fold 0 the previous close plus a 3-minute speed trigger. Neither chooses the same-right cluster add-on.

## 3. The rule on the real sells (isolates the stop rule)
| variant | cls | real_lots | sim_lots | precision | recall | F1 |
|---|---|---|---|---|---|---|
| TF-buyback: decoded stop on real sells | body_buyback | 1324 | 958 | 0.697 | 0.504 | 0.586 |
| TF-buyback: decoded stop on real sells | wing_buy | 4336 | 4422 | 0.902 | 0.92 | 0.911 |
| TF-buyback: decoded stop on real sells | wing_sell | 1192 | 901 | 0.657 | 0.497 | 0.566 |
| TF-buyback: plain stop close>=1.5x on real sells | body_buyback | 1324 | 1016 | 0.658 | 0.505 | 0.572 |
| TF-buyback: plain stop close>=1.5x on real sells | wing_buy | 4336 | 4444 | 0.903 | 0.926 | 0.914 |
| TF-buyback: plain stop close>=1.5x on real sells | wing_sell | 1192 | 981 | 0.61 | 0.502 | 0.55 |


## 4. After the buy-back: what limits the whole D-1 reconstruction now
Body-sell errors, free-running, by real sell type (recall) and by simulated type (precision):
| side | type | lots | matched | share |
|---|---|---|---|---|
| real (recall) | scheduled | 2122 | 2077 | 0.979 |
| real (recall) | solo intraday | 1172 | 569 | 0.486 |
| real (recall) | reactive | 754 | 497 | 0.659 |
| real (recall) | solo after 15:00 | 336 | 63 | 0.188 |
| real (recall) | deep-OTM batch | 287 | 1 | 0.004 |
| simulated (precision) | scheduled | 2112 | 2083 | 0.986 |
| simulated (precision) | solo | 980 | 522 | 0.533 |
| simulated (precision) | reactive | 474 | 459 | 0.968 |
| simulated (precision) | extra | 233 | 143 | 0.614 |


* Scheduled pairs are essentially exact.
* The losses come from **solo intraday** (49% reproduced, simulated precision 53%), **reactive lot counts** (66%; the rule is 97% precise but under-sizes) and two classes not modelled (after-15:00 solo, deep-OTM batches).
* **Reactive repeat entries** (a new running-candle extreme beyond the channel after the first entry) were added and **rejected**: out-of-fold, both folds choose zero repeats, and the overall F1 stays at 0.686.

## 5. Why this is close to the limit of this data (quant view)
* A stop that is sharp in the real system looks graded at one-minute resolution when the trigger price is a **tick or quote we cannot see** (LTP vs bid/ask), when checks are asynchronous, or when the entry reference differs slightly per lot. The decision prices in the ledger narrow this (mode 1.5–1.7×) but cannot remove it.
* The low-ratio half reacts to **speed**, which needs intrabar paths (ticks or seconds) to turn a ranking (AUC 0.80) into a rule.
* Everything here is in-sample on 32 cycles. More rule mining on the same data mainly fits noise: every extra condition tried (cluster, speed variants, repeats) gains less than 0.01 out-of-fold.
* What would raise accuracy: **tick or one-second option data** for the stop and speed triggers, and **more cycles** (out-of-sample) to separate real rules from chance.

## Evidence labels
* **Observed:** sections 0–4.
* **Inferred:** the price-feed explanation in §5.
* **Unresolved:** the exact trigger of the low-ratio half, reactive lot sizes, solo selection.
* **Not testable:** intrabar sequencing, quotes, original risk inputs.
