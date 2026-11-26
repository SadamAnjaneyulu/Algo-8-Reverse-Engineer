# Algo 8 — D-1 lot construction: why lot accuracy lags activity accuracy, and fixes

*Plan `D1_LOTS_PLAN.md`, written before the analysis. In-sample, D-1 of 32 cycles. Fixes are validated out-of-fold **and** on unseen cycles (forward splits of `D1_FORWARD.md`). Figure: `figures/bl_lots_summary.png`.*

## 0. Result
* **Why lots lag activity.** Of the real lots not reproduced, **43% are a quantity shortfall**: the right minute and right side, but too few lots. Then come missed events (31%), timing 2–5 minutes off (18%) and classes not modelled (8%).
* **Main source of the shortfall: solo sells.** In minutes where the real system's main sell is solo, it places 2.7 lots against 1.3 simulated. The wing buys inherit the same shortfall, because the hedge buys the gap.
* **Mechanism found:** solo lots per minute grow with the **depth of the break beyond the 60-minute extreme**: about 1.3 lots when barely beyond it, 2.3 at 0.2–0.4 steps, 6.6 at 0.7–1 step. This is the same depth-scaling as the reactive extras. The "one lot per 0.2-step rung" idea was rejected (ρ 0.06).
* **The fixes do not pass the acceptance rule.** They were solo depth sizing, the late-solo rule and the opposite-right counter-sell, each chosen on training cycles only:
  * out-of-fold halves: overall F1 0.685 → 0.689 (+0.004).
  * A same version (V1 14->7, V2 7->4): overall F1 0.633 → 0.633 (-0.000).
  * B version change (train V1, test V2): overall F1 0.624 → 0.612 (-0.011).
  * Out-of-fold, solo sizing was not even chosen. Adding lots wins as many true lots as it adds false ones, because the depth signal predicts the count only weakly (ρ 0.30). **Rejected; the simulator keeps its current settings.**
* **What a perfect fix would be worth** (oracle ceilings of the overall lot F1):
  * correct lot count at every event already found: **0.67 → 0.83**;
  * plus correct timing: 0.89;
  * plus every event found: 0.98.
  * Lot count is the biggest prize, worth about +0.16.
* **Why the count cannot be predicted from minute bars.** Real multi-lot solo minutes are not one sized order. Only 49% of their gaps are within the same second; the lots are **dripped over about 5 seconds** (median gap 0.5 s). This is the signature of a tracker that sells one lot each time the price prints a new extreme inside the minute. The count is set by the tick path, which one-minute bars do not show. Scheduled lots, by contrast, sit at fixed seconds 9 s apart (timetable), and reactive lots go in the same second (sized decision).
* **What would raise it:** one-second (or tick) spot and option prices for the D-1 sessions. With them, the solo tracker and the stop triggers can be replayed at the second they act. Recommended before any further minute-level rule mining.

## 1. Error budget (current reconstruction, out-of-fold)
| cause | real lots not reproduced | share |
|---|---|---|
| quantity shortfall | 2361 | 43% |
| missed event | 1680 | 31% |
| timing (2-5 min) | 989 | 18% |
| not modelled | 457 | 8% |

| cause | simulated lots not real |
|---|---|
| quantity excess | 1381 |
| timing (2-5 min) | 842 |
| spurious event | 403 |


By class (unmatched lots):
| cls | missed event | not modelled | quantity excess | quantity shortfall | spurious event | timing (2-5 min) |
|---|---|---|---|---|---|---|
| body_buyback | 389 | 0 | 275 | 212 | 28 | 137 |
| body_sell | 430 | 0 | 327 | 826 | 76 | 397 |
| lump | 144 | 0 | 61 | 253 | 142 | 791 |
| not_modelled | 0 | 457 | 0 | 0 | 0 | 0 |
| opening_wings | 0 | 0 | 2 | 2 | 6 | 0 |
| wing_buy | 362 | 0 | 436 | 891 | 103 | 373 |
| wing_sell | 355 | 0 | 280 | 177 | 48 | 133 |


## 2. Quantity at events found (same minute, body sells)
| real_main | cells | real_lots_mean | sim_lots_mean | lots_short | lots_extra |
|---|---|---|---|---|---|
| deep | 2 | 24.0 | 1.0 | 46 | 0 |
| late | 46 | 3.59 | 1.52 | 102 | 7 |
| reactive | 364 | 1.59 | 1.82 | 102 | 185 |
| scheduled | 1421 | 1.42 | 1.42 | 81 | 91 |
| solo | 319 | 2.71 | 1.32 | 450 | 9 |


## 3. Solo lots per minute vs break depth (real, intraday, stand-alone)
| depth beyond 60-min extreme (steps) | real solo lots per minute | minutes |
|---|---|---|
| (-9.0, 0.0] | 1.28 | 67 |
| (0.0, 0.1] | 1.43 | 129 |
| (0.1, 0.2] | 1.8 | 95 |
| (0.2, 0.4] | 2.32 | 66 |
| (0.4, 0.7] | 2.81 | 27 |
| (0.7, 1.0] | 6.6 | 5 |
| (1.0, 9.0] | 9.25 | 4 |


## 4. Fixes: chosen settings and scores
| setup | solo_a | solo_b | late_n | counter | F1_train |
|---|---|---|---|---|---|
| out-of-fold halves | nan | nan | nan | one | 0.6736 |
| out-of-fold halves | nan | nan | 1.0 | one | 0.733 |
| A same version (V1 14->7, V2 7->4) | 1.0 | 1.0 | nan | one | 0.6617 |
| B version change (train V1, test V2) | 1.0 | 1.0 | 1.0 | one | 0.6577 |


| setup | model | cycles | F1 | precision | recall | F1_within1 | F1_strict |
|---|---|---|---|---|---|---|---|
| out-of-fold halves | baseline | 32 | 0.685 | 0.782 | 0.609 | 0.623 | 0.449 |
| out-of-fold halves | fixed | 32 | 0.689 | 0.747 | 0.64 | 0.624 | 0.443 |
| A same version (V1 14->7, V2 7->4) | baseline | 11 | 0.634 | 0.772 | 0.537 | 0.59 | 0.464 |
| A same version (V1 14->7, V2 7->4) | fixed | 11 | 0.633 | 0.734 | 0.557 | 0.587 | 0.458 |
| B version change (train V1, test V2) | baseline | 11 | 0.624 | 0.687 | 0.571 | 0.555 | 0.428 |
| B version change (train V1, test V2) | fixed | 11 | 0.612 | 0.617 | 0.608 | 0.539 | 0.41 |


By class:
| ('cls', '') | ('A same version (V1 14->7, V2 7->4)', 'baseline') | ('A same version (V1 14->7, V2 7->4)', 'fixed') | ('B version change (train V1, test V2)', 'baseline') | ('B version change (train V1, test V2)', 'fixed') | ('out-of-fold halves', 'baseline') | ('out-of-fold halves', 'fixed') |
|---|---|---|---|---|---|---|
| body_buyback | 0.554 | 0.559 | 0.5 | 0.511 | 0.547 | 0.556 |
| body_sell | 0.71 | 0.706 | 0.678 | 0.654 | 0.757 | 0.756 |
| lump | 0.529 | 0.538 | 0.635 | 0.64 | 0.648 | 0.663 |
| not_modelled | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| opening_wings | 1.0 | 1.0 | 0.921 | 0.921 | 0.974 | 0.974 |
| wing_buy | 0.695 | 0.69 | 0.667 | 0.643 | 0.725 | 0.725 |
| wing_sell | 0.543 | 0.549 | 0.478 | 0.491 | 0.534 | 0.542 |


## 5. Oracle ceilings and within-minute structure
| scenario | TP | sim | F1 |
|---|---|---|---|
| current (out-of-fold, lump at ±1 min) | 8168 | 10794 | 0.668 |
| + perfect lot count at every event found | 10529 | 11774 | 0.828 |
| + perfect timing (2–5 min errors corrected) | 11371 | 11774 | 0.894 |
| + every event found, no spurious events | 13051 | 13051 | 0.977 |
| + not-modelled classes | 13508 | 13508 | 0.995 |


| sub | minutes | lots_mean | span_s_median | same_second_share | median_gap_s |
|---|---|---|---|---|---|
| deep | 5 | 57.6 | 31.0 | 0.92 | 0.0 |
| late | 70 | 4.2 | 4.5 | 0.43 | 1.0 |
| reactive | 172 | 2.66 | 0.0 | 0.62 | 0.0 |
| scheduled | 445 | 2.35 | 10.0 | 0.16 | 9.0 |
| solo | 216 | 3.94 | 5.0 | 0.49 | 0.5 |


## 6. What remains, and why
* **Missed events:** mostly buy-backs whose exact trigger is not recoverable at minute resolution (see `BUYBACK_STOP3.md`), plus solo minutes the ladder misses.
* **Timing:** lump orders spread over an 8-minute window in the early regime, and solo drips span neighbouring minutes.
* **Not modelled (3%):** stop module, 15:15 flatten, deep-OTM batches.

## Evidence labels
Observed (executed). Fixes chosen on training cycles and scored on held-out and unseen cycles. In-sample caveat: the mechanisms were found on the same 32 cycles.
