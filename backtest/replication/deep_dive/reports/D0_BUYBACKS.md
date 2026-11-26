# Algo 8 — D0 chunk 2: body buy-backs

*Plan `D0_BUYBACKS_PLAN.md` (addendum 2b written after B1–B5, before its tests). In-sample: D0 of 30 cycles. Out-of-fold = cycle halves by parity. Figure: `figures/bl_d0b_summary.png`.*

## 0. Result
* **D0 buy-backs rank at AUC 0.815** (CI 0.781–0.851; causal **0.787**). Lower than selling (0.932).
* **The stop on the lot's own premium carries over from D-1, refit lower.**
  * The hazard climbs steadily with the lot's premium high / entry: 0.5% per minute at 1.0–1.1×, 3.8% at 1.5–1.6×, 11% at 1.7–1.8×.
  * The best single threshold is **1.4× on the minute high** (D-1: 1.6×). Out-of-fold lot F1 0.390, against 0.363 for the D-1 stop unchanged.
* **A take-profit exists on D0** (not on D-1): a lot whose premium falls to 0.1× of entry is bought back. With it, lot F1 is **0.394** (recall of deep-profit lots 30%), against nulls of 0.157 (+15 min) and 0.223 (random minutes).
* **Most D0 buy-back lots come in bursts that cut a side, not one lot at a time.** Bursts of 5+ lots (390) carry 64% of in-scope buy-back lots. A typical one spans 3 strikes (90th percentile 5) and takes 10% of the right's open lots (IQR 6%–22%). 39% contain both profit and loss lots, and a burst takes only 33% (median) of the lots above its lowest ratio. **What starts a burst is not found:** the best single variable is the adverse 5-minute spot move (AUC 0.66; halves 0.71 / 0.61). Premium imbalance, delta share and the side's loss do not reach 0.70. *Unresolved.*
* **Straddle partners again.** 33% of mid-profit buy-backs have a same-strike loss buy-back on the other right within ±60 s (null 9%), as on D-1. But a partner rule adds nothing to lot F1.
* **Only half of all D0 buy-back lots are in loss** (49%; D-1: 87%). The rest:
  * the 15:10+ clearance (chunk 4);
  * afternoon cover-backs of decayed lots;
  * partners.

## 1. Population
* 9,656 D0 body buy-back lots, 2,126 of them on lots carried from D-1.
* In scope (before 15:10 and before the cycle's stop): 7,058 lots:
  * loss 4,277;
  * mid-profit 1,616;
  * deep-profit 1,165.
* **Lot convention.** The highest-ratio open lot on the contract is removed (D-1 convention). FIFO assigns a different origin for 22% of lots, and gives 38% in loss instead of 49%.

## 2. Hazard by the lot's own premium (B1)
| ratio_bin | hazard_pct | lot_minutes | events |
|---|---|---|---|
| (0.0, 0.1] | 0.52 | 141277 | 734 |
| (0.1, 0.2] | 0.22 | 141170 | 306 |
| (0.2, 0.25] | 0.14 | 59469 | 81 |
| (0.25, 0.3] | 0.11 | 54423 | 59 |
| (0.3, 0.4] | 0.16 | 100747 | 166 |
| (0.4, 0.5] | 0.16 | 94643 | 148 |
| (0.5, 0.75] | 0.14 | 218331 | 316 |
| (0.75, 1.0] | 0.26 | 211080 | 548 |
| (1.0, 1.1] | 0.54 | 76295 | 409 |
| (1.1, 1.2] | 0.76 | 56030 | 424 |
| (1.2, 1.3] | 0.93 | 38375 | 355 |
| (1.3, 1.4] | 1.44 | 25512 | 367 |
| (1.4, 1.5] | 2.00 | 17273 | 346 |
| (1.5, 1.6] | 3.83 | 9848 | 377 |
| (1.6, 1.7] | 6.94 | 5969 | 414 |
| (1.7, 1.8] | 11.04 | 3569 | 394 |
| (1.8, 2.0] | 12.11 | 3783 | 458 |
| (2.0, 2.5] | 10.70 | 4260 | 456 |
| (2.5, 99.0] | 14.46 | 961 | 139 |


**By hour block and ratio (hazard % per lot-minute):**

| ratio (high/entry) | 09:15-11:00 | 11:00-13:00 | 13:00-15:10 |
|---|---|---|---|
| (0.0, 0.25] | 0.01 | 0.11 | 0.58 |
| (0.25, 0.5] | 0.03 | 0.05 | 0.33 |
| (0.5, 1.0] | 0.09 | 0.11 | 0.41 |
| (1.0, 1.3] | 0.48 | 0.50 | 1.14 |
| (1.3, 1.6] | 2.13 | 1.60 | 2.41 |
| (1.6, 2.0] | 10.00 | 10.63 | 8.39 |
| (2.0, 99.0] | 5.55 | 11.49 | 18.74 |


* The hazard is **graded**: there is no single wall.
* Above 2× in the afternoon it reaches 19% per minute.
* Below 0.25× it is near zero until 13:00, then 0.6%. This is the take-profit.

## 3. Machines (B2)
* Teacher-forced on the real book: real sells, and lots leave at their real buy-back.
* Out-of-fold, cycle halves. Lot F1 at ±1 minute.

| machine | F1 | ci_lo | ci_hi | precision | recall | sim_lots | real_lots | recall_loss | recall_mid | recall_deep |
|---|---|---|---|---|---|---|---|---|---|---|
| K1 D-1 stop unchanged (high >= 1.6x) | 0.363 | 0.316 | 0.406 | 0.655 | 0.251 | 2704 | 7058 | 0.402 | 0.085 | 0.050 |
| K2a refit theta and price | 0.390 | 0.348 | 0.424 | 0.531 | 0.307 | 4083 | 7058 | 0.476 | 0.141 | 0.108 |
| K2b theta per hour block | 0.365 | 0.326 | 0.399 | 0.511 | 0.284 | 3917 | 7058 | 0.426 | 0.159 | 0.142 |
| K2c theta per origin | 0.386 | 0.346 | 0.426 | 0.514 | 0.309 | 4253 | 7058 | 0.480 | 0.145 | 0.108 |
| K3 + take-profit | 0.394 | 0.358 | 0.424 | 0.424 | 0.368 | 6125 | 7058 | 0.492 | 0.277 | 0.302 |
| K4 + same-strike partner | 0.394 | 0.361 | 0.424 | 0.424 | 0.368 | 6125 | 7058 | 0.492 | 0.277 | 0.302 |
| K5 + block clock | 0.394 | 0.360 | 0.424 | 0.424 | 0.368 | 6125 | 7058 | 0.492 | 0.277 | 0.302 |
| null: final machine shifted +15 min | 0.157 | 0.121 | 0.188 | 0.169 | 0.147 | 6125 | 7058 | — | — | — |
| null: rate-matched random minutes | 0.223 | 0.188 | 0.261 | 0.240 | 0.208 | 6125 | 7058 | — | — | — |
| secondary: final machine, own-book semantics | 0.429 | 0.382 | 0.470 | 0.402 | 0.460 | 8068 | 7058 | — | — | — |


* Chosen per half: {"theta": 1.4, "price": "high", "org_mult": [0.8, 1.0], "tp": 0.1, "tp_gate": 0} ; {"theta": 1.4, "price": "high", "theta_blk": [1.5, 1.4, 1.4], "tp": 0.1, "tp_gate": 0}.
* Per-hour-block θ and per-origin θ do not help out-of-fold. The partner and block-clock steps were not chosen on either training half.
* `recall_*` = recall of that group's lots against all predictions (optimistic per group).
* Own-book semantics (a lot leaves only at the machine's own exit, as in a simulator) gives 0.429.

## 4. Clock (B3) and context (B4)
| group | lots | sec00 | block_min14 | block_min0 | uniform_one_minute |
|---|---|---|---|---|---|
| all | 7058 | 0.126 | 0.111 | 0.118 | 0.067 |
| deep-profit | 1165 | 0.041 | 0.157 | 0.073 | 0.067 |
| loss | 4277 | 0.163 | 0.080 | 0.128 | 0.067 |
| mid-profit | 1616 | 0.087 | 0.158 | 0.124 | 0.067 |


| group | context | share | null | lots |
|---|---|---|---|---|
| mid-profit | partner | 0.331 | 0.091 | 1616 |
| mid-profit | recentre | 0.085 | 0.026 | 1616 |
| mid-profit | roll | 0.396 | 0.213 | 1616 |
| deep-profit | partner | 0.161 | 0.060 | 1165 |
| deep-profit | recentre | 0.077 | 0.055 | 1165 |
| deep-profit | roll | 0.321 | 0.273 | 1165 |
| loss | partner | 0.075 | 0.044 | 4277 |
| loss | recentre | 0.150 | 0.082 | 4277 |
| loss | roll | 0.338 | 0.213 | 4277 |


* **Clocking is moderate.** About 11–12% of lots fall in the last minute of a 15-minute block and 12% in the first minute of the next, against 6.7% uniform. 13% are at second :00.
* **Mid-profit lots are often partners or rolls.** Partner 33% vs 9%; same-right sale within 60 s 40% vs 21%. The two overlap.

## 5. Bursts and side-level triggers (addendum 2b)
**What starts a burst (≥ 3 lots), single-variable AUC:**

| variable | timing | AUC | ci_lo | ci_hi | AUC_half_even | AUC_half_odd |
|---|---|---|---|---|---|---|
| stop_rmax | same-minute close | 0.626 | 0.584 | 0.668 | 0.679 | 0.584 |
| stop_rmax | previous close (lag 1) | 0.581 | 0.549 | 0.621 | 0.632 | 0.541 |
| prem_imb | same-minute close | 0.630 | 0.608 | 0.662 | 0.637 | 0.626 |
| prem_imb | previous close (lag 1) | 0.609 | 0.589 | 0.631 | 0.610 | 0.609 |
| lot_imb | same-minute close | 0.564 | 0.539 | 0.586 | 0.545 | 0.578 |
| lot_imb | previous close (lag 1) | 0.564 | 0.538 | 0.587 | 0.545 | 0.578 |
| delta_share | same-minute close | 0.620 | 0.601 | 0.641 | 0.615 | 0.623 |
| delta_share | previous close (lag 1) | 0.602 | 0.585 | 0.624 | 0.591 | 0.611 |
| unreal_loss | same-minute close | 0.476 | 0.445 | 0.508 | 0.507 | 0.453 |
| unreal_loss | previous close (lag 1) | 0.460 | 0.436 | 0.488 | 0.481 | 0.443 |
| adv_mv5 | same-minute close | 0.658 | 0.622 | 0.694 | 0.711 | 0.614 |
| adv_mv5 | previous close (lag 1) | 0.629 | 0.601 | 0.660 | 0.665 | 0.598 |


**Burst size (Spearman):**

| variable | bursts | n | spearman | p |
|---|---|---|---|---|
| n_above14 | all bursts | 1770 | 0.235 | 0.000 |
| n_above14 | bursts >= 3 lots | 674 | 0.302 | 0.000 |
| prem_imb | all bursts | 1770 | 0.202 | 0.000 |
| prem_imb | bursts >= 3 lots | 674 | 0.204 | 0.000 |
| n_open | all bursts | 1770 | 0.063 | 0.008 |
| n_open | bursts >= 3 lots | 674 | -0.005 | 0.893 |
| delta_share | all bursts | 1770 | 0.182 | 0.000 |
| delta_share | bursts >= 3 lots | 674 | 0.123 | 0.001 |


**Rebalancing band machine** (own-book semantics; band and fraction fitted on one half):

| machine | F1 | precision | recall | sim_lots | real_lots | chosen |
|---|---|---|---|---|---|---|
| band alone | 0.333 | 0.526 | 0.244 | 3269 | 7058 | stop_rmax > 2.13 (q 0.1) / stop_rmax > 1.83 (q 0.1) |
| band + K3 | 0.431 | 0.405 | 0.461 | 8032 | 7058 | unreal_loss > 707 (q 0.2) / unreal_loss > 1.45e+03 (q 0.05) |
| K3 alone (own-book, reference) | 0.432 | 0.406 | 0.462 | 8022 | 7058 | K3 / K3 |


* **No side-level trigger.** No variable reaches the pre-set AUC 0.70 in both halves. The adverse spot move (0.658) and premium imbalance (0.630) are the strongest; the side's unrealised loss is at chance (0.476).
* **Burst size** follows the number of lots above 1.4× (ρ 0.30) and premium imbalance (ρ 0.20), not the open lots (ρ -0.01).
* **The band machine adds nothing.** With K3, F1 0.431, against K3 alone 0.432 (both own-book). Alone it scores 0.333.
* **Reading (Inferred).** The bursts are where several lots cross the stop together during an adverse move. The size of each cut is a separate decision that these variables do not recover.

## 5b. Lots carried from D-1 (addendum 2c, post-hoc)
* **Carried lots barely follow their own premium.** Their hazard is flat (about 1–3.7% per minute from 1.5× upward), against 15–26% for lots sold on D0.
* **Re-basing their stop to the D0 opening premium does not help.**
  * The single-variable AUC on carried lot-minutes is 0.525 against the D0 open and 0.552 against the D-1 entry (difference CI -0.052 to +0.007).
  * Out-of-fold machine F1 is 0.357 against 0.400 (paired difference CI -0.068 to -0.018). **Rejected.**
* What drives carried-lot buy-backs is unresolved. 64% of all D0 buy-back lots in 09:15–09:30 are carried lots, against 21% in 12:00–14:00. Their AUC is near chance on either reference.

| ratio_bin | D-1 entry | D0 open |
|---|---|---|
| (0.0, 0.25] | 0.21 | 0.38 |
| (0.25, 0.5] | 0.05 | 0.15 |
| (0.5, 0.75] | 0.05 | 0.06 |
| (0.75, 1.0] | 0.12 | 0.06 |
| (1.0, 1.1] | 0.25 | 0.24 |
| (1.1, 1.2] | 0.70 | 0.17 |
| (1.2, 1.3] | 0.66 | 0.35 |
| (1.3, 1.4] | 0.93 | 0.27 |
| (1.4, 1.5] | 0.96 | 0.22 |
| (1.5, 1.6] | 3.45 | 0.13 |
| (1.6, 1.8] | 3.50 | 0.36 |
| (1.8, 2.0] | 1.97 | 0.37 |
| (2.0, 2.5] | 1.04 | 0.93 |
| (2.5, 99.0] | 3.70 | 1.99 |


## 6. One ranking number (B5)
| variant | AUC | ci_lo | ci_hi | cells | positives |
|---|---|---|---|---|---|
| A same-minute market + book | 0.815 | 0.781 | 0.851 | 14910 | 1964 |
| B completed bars (causal) | 0.787 | 0.747 | 0.836 | 14910 | 1964 |
| clock only | 0.690 | 0.656 | 0.728 | 14910 | 1964 |
| A book ratios only (no market) | 0.783 | 0.734 | 0.826 | 14910 | 1964 |


**By group:**

| group | cells_with_buyback | A same-minute market + book | B completed bars (causal) | clock only | A book ratios only (no market) |
|---|---|---|---|---|---|
| loss | 1226 | 0.838 | 0.806 | 0.658 | 0.805 |
| mid-profit | 742 | 0.799 | 0.767 | 0.756 | 0.761 |
| deep-profit | 462 | 0.863 | 0.853 | 0.812 | 0.845 |


## 7. Kept and rejected
| rule | result | decision | evidence |
|---|---|---|---|
| Own-premium stop, D-1 level 1.6× unchanged | F1 0.363 | carries over (weaker) | Observed |
| Own-premium stop refit: 1.4× on the minute high | F1 0.390 | kept | Observed |
| Take-profit: premium ≤ 0.1× entry | F1 0.394 (deep-profit recall 30%) | kept | Observed |
| θ per hour block / per origin | no out-of-fold gain | rejected | Observed |
| Same-strike partner buy-back | context 33% vs null 9%; no F1 gain | structure kept, rule rejected | Observed |
| Block clock (minutes 14 / 0) | ~1.8× uniform; no F1 gain | descriptive only | Observed |
| Side-level trigger (imbalance, delta, side loss, spot move) | no AUC ≥ 0.70 in both halves | rejected / unresolved | Observed |
| Carried lots: stop re-based to the D0 open (post-hoc) | F1 0.357 vs 0.400 | rejected | Observed |
| Final machine vs nulls | 0.394 vs 0.157 (+15 min) / 0.223 (random) | passes (1.8× random) | Observed |


## 8. Caveats
* **In-sample.** 30 cycles. The structure was found on the same cycles. Scores are out-of-fold over halves.
* **Lot convention.** Buy-backs remove the highest-ratio lot. FIFO would change the lot ratios (Section 1).
* **Teacher-forced.**
  * The book is real (real sells and, in B2, real removals).
  * The stop time is real (chunk 4 decodes it).
  * The 15:10+ clearance is excluded (chunk 4).
* **Matcher.** Lot F1 uses minute and right only (histogram matcher: exact minute, then ±1).
* **Post-hoc.** Addendum 2b was written after B1–B5 and a descriptive look at bursts; addendum 2c after the B1 figure.

## Run order
`bl_d0b_ledger.py` → `bl_d0b_tests.py` (~2 min) → `bl_d0b_mach.py` → `bl_d0b_auc.py` (~1 min) → `bl_d0b_side.py` (~7 min) → `bl_d0b_burst.py` → `bl_d0b_carry.py` (~3 min) → `make_d0b_report.py`. Outputs `outputs/bl_d0b_*`, `bl_summary_d0b0…6.json`.
