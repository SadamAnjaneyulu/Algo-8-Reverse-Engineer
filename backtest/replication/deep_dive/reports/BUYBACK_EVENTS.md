# Algo 8 — D-1 buy-backs modelled as rebalancing events: accuracy

*Plan `BUYBACK_EVENTS_PLAN.md`, written before running. In-sample, D-1 of 32 cycles. The event parts were chosen on one cycle half and scored on the other. Figure: `figures/bl_ev_summary.png`.*

## 0. Result: the event model does not improve accuracy
* On the real sells, buy-back F1 0.588 → **0.587** (-0.001).
* Free-running: buy-back F1 0.547 → **0.555** (+0.008); overall D-1 F1 0.685 → **0.691** (+0.006).
* Decision rule from the plan: the model counts as an improvement only if both the buy-back F1 on the real sells and the overall free-running F1 rise. **Verdict: does not improve.**

## 1. Scores
| mode | model | buy-back F1 | buy-back precision | buy-back recall | wing-sell F1 | body-sell F1 | overall D-1 F1 |
|---|---|---|---|---|---|---|---|
| real sells | plain stop (reference) | 0.588 | 0.721 | 0.496 | 0.565 | 1.000 | 0.846 |
| real sells | rebalancing events | 0.587 | 0.716 | 0.497 | 0.563 | 1.000 | 0.846 |
| free-running | plain stop (reference) | 0.547 | 0.672 | 0.462 | 0.534 | 0.757 | 0.685 |
| free-running | rebalancing events | 0.555 | 0.669 | 0.474 | 0.541 | 0.760 | 0.691 |


## 2. Event parts chosen (per fold)
| mode | fold | theta | cluster | partner | counter | react_d | solo_d | obj_train |
|---|---|---|---|---|---|---|---|---|
| tf_bb | 0 | 1.6 | nan | False | nan | 1.5 | nan | 0.5909 |
| tf_bb | 1 | 1.6 | nan | False | nan | 1.0 | nan | 0.597 |
| free | 0 | 1.6 | nan | False | one | 1.5 | nan | 0.6742 |
| free | 1 | 1.6 | nan | False | one | nan | nan | 0.7311 |


## 3. Reading
* **Counter-sell:** the only part chosen in both free-running folds is one solo lot sold on the other right when a stop fires. It adds a small, consistent gain (overall +0.006, body sells +0.003, buy-backs +0.008). This matches the rebalancing pattern found in `BUYBACK_STOP3.md`.
* **Reactive continuation exit:** chosen in both real-sell folds (d = 1.0 / 1.5 steps), but it gains nothing out-of-fold; chosen in one free-running fold only. Not stable.
* **Same-right cluster and straddle-partner buy-back:** never chosen. They match real events only together with the stop's minute and lot count, and add more false lots than true ones.
* Lot-level accuracy is limited because a modelled event must fall in the same minute (±1) as the real one, on the same right, with the same number of lots. The decoded structure (who is exited with whom) is right more often than the exact minute.

## Evidence labels
Observed (executed, out-of-fold). In-sample: the event structure was found on the same 32 cycles (`BUYBACK_STOP3.md`).
