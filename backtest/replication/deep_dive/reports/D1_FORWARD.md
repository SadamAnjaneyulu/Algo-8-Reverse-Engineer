# Algo 8 — complete D-1 reconstruction on unseen cycles (forward test)

*The rules are applied to cycles whose data were **not** used to fit anything. In-sample caveat: the rule **structure** was designed after looking at all 32 cycles, so even these forward numbers are somewhat optimistic for genuinely new data.*

## 0. Result
| Measure | On unseen cycles | Earlier figure (all cycles, out-of-fold) |
|---|---|---|
| **Lot-level accuracy (F1, ±1 min)** | **0.63** same version · **0.62** after a version change | 0.69 |
| Precision / recall | 77% / 54% | 78% / 62% |
| **AUC (any D-1 activity, minute × right)** | **0.92** same version · **0.91** after a version change | 0.96–0.98 |

**Expected range on new cycles:** lot-level F1 about **0.60–0.65** and AUC about **0.90–0.92**, if the system keeps its configuration. If it changes version again (as it did on 2026-09-16), these hold up surprisingly well (0.62 / 0.91), because most of the scheduled timetable and every decoded trigger carried over. The real risks are new timetables, new lump time windows and new modules.

## 1. Setup
* **A, same version:** within V1 the first 14 cycles are learned from and the last 7 tested; within V2, the first 7 and the last 4. Everything is learned from the training cycles only: the scheduled timetable (minutes with a scheduled sale in ≥ 50% of training cycles), the lump time (the regime of the latest training cycle; config changes are not given), reactive size and extras, the buy-back stop θ, lump ratio, opening-wing offset, and the AUC model with its timetable share.
* **B, version change:** learned from all 21 V1 cycles and tested on all 11 V2 cycles, applying the **V1 timetable** to V2.
* Test cycles include the stop-out cycle and the deep-OTM batch cycle, which makes them harder (more not-modelled lots).

## 2. Scores
| split | cycles learned from | unseen cycles | lot F1 (timing) | precision | recall | F1 + strike within one | F1 out-of-fold, same cycles | AUC any activity | AUC out-of-fold, same cycles |
|---|---|---|---|---|---|---|---|---|---|
| A same version (V1 14->7, V2 7->4) | 21 | 11 | 0.633 | 77% | 54% | 0.590 | 0.656 | 0.921 | 0.966 |
| B version change (train V1, test V2) | 21 | 11 | 0.624 | 69% | 57% | 0.555 | 0.660 | 0.912 | 0.953 |


## 3. By class (unseen cycles, lot F1)
| cls | A same version (V1 14->7, V2 7->4) | B version change (train V1, test V2) |
|---|---|---|
| body_buyback | 0.554 | 0.5 |
| body_sell | 0.71 | 0.678 |
| lump | 0.529 | 0.635 |
| not_modelled | 0.0 | 0.0 |
| opening_wings | 1.0 | 0.921 |
| wing_buy | 0.695 | 0.667 |
| wing_sell | 0.543 | 0.478 |


## 4. What the numbers mean
* About **63%** of D-1 lot decisions are reproduced in the right minute (±1) and on the right side on unseen cycles. About **59%** also have the strike within one step.
* AUC about **0.92** means the reconstruction ranks the minutes where the real system acts far above the rest, on days it has not seen.
* The drop from the in-sample figures (F1 0.69 → 0.63, AUC 0.97 → 0.92) is the honest cost of new data.
* A truly independent check needs new live cycles (after 2026-10-22) scored with the rules frozen now.

## Evidence labels
* **Observed:** executed forward tests.
* **Not testable here:** genuinely new cycles, i.e. future data.
* For split A, the lump time came from the latest training cycle overall, a V2 cycle. Some V1 test cycles had an earlier lump regime, so their lump scores are conservative.
