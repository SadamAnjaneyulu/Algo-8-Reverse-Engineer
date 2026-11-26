# Algo 8 — D-1 selling: one AUC for all sell types

*Plan `D1_SELLING_AUC_PLAN.md`, written before running. In-sample, D-1 of 32 live cycles. Figure: `figures/bl_auc_all_roc.png`.*

## 0. Result
* **Overall AUC 0.976** (95% CI 0.972–0.980). This is the primary variant A: leave-one-cycle-out gradient boosting on market data, the timetable, the decoded rules and the clock. **It is above your 0.85 target.** *Observed.*
* **The timetable alone does not explain it.** Without timetable minutes the AUC is **0.952**. The timetable share alone gives 0.800 on all cells.
* **The real past orders add nothing.** Removing the book state built from them (own/other book ratio, short lots) leaves the AUC unchanged at 0.976 (post-hoc check). Adding the order history (variant C) also leaves it unchanged.
* **The main caveat is the same-minute alignment.** Variant A uses the current minute's true high and low: the reactive break, fresh extremes and premium lows all come from the bar the sale falls in. With completed bars only (variant B) the AUC is **0.906** overall and **0.795** without timetable minutes. The drop is mostly the reactive pairs, which react to a break *inside* the minute.
  * So A measures "a tracker that watches the price live within the minute", which is how the reactive rule behaves (first break inside the bar).
  * B measures "a tracker that only sees closed bars".
  * Without ticks, part of A's edge may come from price after the sale inside the same minute. *Not testable here.*

## 1. Setup
* 23,936 cells: 32 cycles × 374 minutes × CE/PE.
* 2,635 cells contain a sale (11.0%), of any type: scheduled, reactive, solo, after-15:00 solo, deep-OTM batch.
* Features come only from the decoded rules and the earlier studies:
  * timetable share, recomputed leaving the held-out cycle out;
  * the decoded reactive machine (fire, side, depth);
  * fresh extremes on closes and true high/low over 5/15/30/60 minutes;
  * favourable moves and the position in the 15-minute range;
  * the option premium making a fresh 5/15/30-minute low (ITM and ATM);
  * clock.

## 2. AUC by variant
| variant (gradient boosting unless stated) | AUC all cells (95% CI) | AUC without timetable minutes (95% CI) | status |
|---|---|---|---|
| A same-minute (primary) | 0.976 (0.972–0.980) | 0.952 (0.942–0.959) | plan |
| B causal (market lagged 1 min) | 0.906 (0.899–0.913) | 0.795 (0.780–0.809) | plan |
| C A + real order history (teacher-forced) | 0.977 (0.973–0.980) | 0.952 (0.943–0.959) | plan |
| A0 same-minute, no book state | 0.976 (0.971–0.980) | 0.950 (0.940–0.958) | post-hoc check |
| B0 causal, no book state | 0.906 (0.899–0.913) | 0.796 (0.780–0.810) | post-hoc check |
| timetable + clock only | 0.833 (0.821–0.844) | 0.632 (0.602–0.659) | post-hoc check |
| A same-minute (primary) — logistic | 0.960 | 0.916 | plan |
| B causal (market lagged 1 min) — logistic | 0.875 | 0.727 | plan |
| C A + real order history (teacher-forced) — logistic | 0.960 | 0.916 | plan |

"Without timetable minutes" drops every cell where more than half of the other cycles have a scheduled sale (22,390 cells, 1,186 with a sale).

## 3. AUC by sell type (that type's cells vs all no-sale cells)
| sell_type | cells with a sale | A same-minute (primary) | B causal (market lagged 1 min) | timetable + clock only |
|---|---|---|---|---|
| scheduled | 1574 | 0.996 | 0.997 | 0.998 |
| reactive | 558 | 0.938 | 0.71 | 0.602 |
| solo | 627 | 0.973 | 0.859 | 0.575 |
| solo after 15:00 | 138 | 0.952 | 0.88 | 0.92 |
| deep-OTM batch | 5 | 0.88 | 0.779 | 0.644 |


## 4. How to read this against the F1 0.78
* AUC measures **ranking**: how well minutes with a sale are scored above minutes without one.
* The F1 0.78 in `D1_SELLING_RECONSTRUCTION.md` measures a **yes/no rule at the lot level** (which minute, how many lots, ±1 minute).
* A high AUC with a lower F1 means the conditions for a sale are well identified, but the exact yes/no choice among qualifying minutes, and the number of lots, are not. This holds above all for solo selling.

## Evidence labels
Observed: sections 0–3. Post-hoc: the A0/B0/timetable-only rows (a leakage check). Not testable: event order inside a minute.
