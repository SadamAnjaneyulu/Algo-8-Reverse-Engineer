# Algo 8 — pushing the D-1 reconstruction accuracy: everything tried, and where the limit is

*Plan for the learned policies: `D1_ML_PLAN.md`, written before running. In-sample, D-1 of 32 cycles. "Unseen" = forward splits of `D1_FORWARD.md`. Figure: `figures/bl_push_summary.png`.*

## 0. Result
* **Best reconstruction: the decoded rules.**
  * Lot-level F1 **0.684** out-of-fold.
  * **0.633** on unseen cycles of the same version, **0.624** after a version change.
  * AUC on unseen cycles 0.92 / 0.91.
  * Minute-cell activity F1 0.89 at ±1 minute.
* **Nothing tried beats it on unseen cycles.** This covers 9 attempts: stop-design variants, rebalancing events, quantity fixes and learned (gradient-boosting) policies for solo sells and buy-backs. Each was chosen on training cycles and validated out-of-fold and on unseen cycles. The best gain on any test is under +0.01, inside the noise, and none improves both out-of-fold and unseen.
* **The learned policies are informative but do not help the whole system.**
  * The solo-sell model ranks sell cells better than the decoded ladder: exact-minute cell F1 0.41 vs 0.33 on training cells.
  * In the full free-running simulation it places more lots, the hedge mirrors every extra sell, and overall precision falls as much as recall rises.
  * The learned buy-back policy is less precise than the simple intrabar stop.
* **Where the remaining gap is** (oracle ceilings):
  * exact lot counts at events already found would lift F1 **0.67 → 0.83**;
  * plus exact timing: 0.89;
  * plus all events found: 0.98.
* **Why the limit is in the data, not the method.** The lot count and the exact minute are set inside the minute: solo lots are dripped over about 5 s, and stops fire on intrabar touches. One-minute bars cannot show this, whatever model is used.

## 1. Scoreboard (overall D-1 lot F1)
| attempt | out-of-fold F1 | unseen F1 (same version) | unseen F1 (version change) | decision |
|---|---|---|---|---|
| Decoded rules (current simulator) | 0.684 | 0.633 | 0.624 | kept |
| Decoded buy-back stop design (minute high ~1.6x) | 0.686 | – | – | kept (equal) |
| Reactive repeat entries | 0.686 | – | – | rejected (never chosen) |
| Buy-back: premium AND breakout | 0.678 | – | – | rejected |
| Buy-back: premium stop OR market exit | 0.683 | – | – | rejected |
| Rebalancing events (cluster, partner, counter-sell, exits) | 0.691 | – | – | rejected (rule) |
| Lot fixes (solo depth sizing, late rule, counter-sell) | 0.689 | 0.633 | 0.612 | rejected |
| Learned solo-sell policy | 0.685 | 0.635 | 0.607 | rejected |
| Learned buy-back policy | 0.678 | 0.625 | 0.627 | rejected |
| Both learned policies | 0.682 | 0.622 | 0.615 | rejected |


## 2. Learned policies (detail)
| setup | model | cycles | F1 | precision | recall | F1_within1 | F1_strict |
|---|---|---|---|---|---|---|---|
| out-of-fold halves | baseline | 32 | 0.685 | 0.782 | 0.609 | 0.623 | 0.449 |
| out-of-fold halves | + sell policy | 32 | 0.685 | 0.673 | 0.697 | 0.618 | 0.429 |
| out-of-fold halves | + buy-back policy | 32 | 0.678 | 0.768 | 0.607 | 0.616 | 0.443 |
| out-of-fold halves | + both policies | 32 | 0.682 | 0.669 | 0.696 | 0.613 | 0.424 |
| A same version (V1 14->7, V2 7->4) | baseline | 11 | 0.634 | 0.772 | 0.537 | 0.59 | 0.464 |
| A same version (V1 14->7, V2 7->4) | + sell policy | 11 | 0.635 | 0.673 | 0.601 | 0.59 | 0.45 |
| A same version (V1 14->7, V2 7->4) | + buy-back policy | 11 | 0.625 | 0.761 | 0.531 | 0.585 | 0.46 |
| A same version (V1 14->7, V2 7->4) | + both policies | 11 | 0.622 | 0.656 | 0.591 | 0.579 | 0.444 |
| B version change (train V1, test V2) | baseline | 11 | 0.624 | 0.687 | 0.571 | 0.555 | 0.428 |
| B version change (train V1, test V2) | + sell policy | 11 | 0.607 | 0.57 | 0.649 | 0.539 | 0.396 |
| B version change (train V1, test V2) | + buy-back policy | 11 | 0.627 | 0.687 | 0.577 | 0.561 | 0.432 |
| B version change (train V1, test V2) | + both policies | 11 | 0.615 | 0.577 | 0.659 | 0.546 | 0.4 |


## 3. Reading for the PM
* **Decisions:** what the system does, when, and on which side is reproduced well. AUC is about 0.92 on unseen days, minute cells 0.89.
* **Execution detail:** how many lots and the exact minute is about 0.63 on unseen days.
* **With this data,** further modelling on the same 32 cycles mainly fits noise. Every extra layer tried in this pass lost out-of-sample.
* **Two ways forward:**
  1. One-second or tick option and spot data for the D-1 sessions. This addresses the +0.16–0.22 gap directly.
  2. More live cycles, for a true holdout and more sell and stop events to learn from.

## Evidence labels
Observed (executed, out-of-fold and forward). The learned-policy thresholds came from an inner cross-fit inside the training cycles.
