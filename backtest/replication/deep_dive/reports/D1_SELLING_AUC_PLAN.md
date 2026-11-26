# D-1 selling — one AUC for all sell types: plan

*Written before running. In-sample, D-1 of 32 live cycles. Target set by the user: overall AUC ≈ 0.85 before moving to the hedge module.*

## Panel and label
* Cells: every D-1 cycle × minute (09:16–15:29, j = 1…374) × right (CE, PE) = 23,936 cells (same grid as `bl_solo_panel`).
* Label y = 1 if at least one body `open_short` lot on that right is sold in that minute, **any type**: scheduled, reactive, solo, after-15:00 solo and deep-OTM batch.

## Features (from the decoded rules and earlier studies only; nothing new)
* **Timetable:** the share of the *other* cycles of the same schedule version with a scheduled sale in minute j. It is recomputed leave-one-cycle-out, so the held-out cycle's own timetable is never used.
* **Reactive rule:** the decoded machine fires in minute j (up or down break of the previous two clock-aligned 30-minute candles' true high/low; first per side per candle; 10:30–15:15). Also the break side relative to the right, and the break depth.
* **Solo variables** (`bl_solo_panel`): fresh favourable extremes on closes and true high/low over 5/15/30/60 minutes; favourable moves over 5/15/30/60 minutes; own-side and other-side book ratio; own and other short lots; position in the 15-minute range; hour.
* **Premium low:** the fresh 5/15/30-minute low of the ITM and the ATM option on that right (`bl_sl_prem`).
* **Clock:** minute j.

## Models and scoring
* Gradient boosting with fixed settings (depth 3, learning rate 0.05, 150 iterations, minimum leaf 20, L2 1.0), fitted leave-one-cycle-out (32 folds). Logistic regression is reported for comparison.
* **Primary metric:** pooled out-of-cycle AUC over all cells, with a 95% cluster-bootstrap CI over cycles (1,000 draws).
* **Breakdowns** (same AUC, different subsets of positives): AUC for each sell type's cells against all no-sale cells; and the AUC **without scheduled minutes** (cells where the LOCO timetable share is above 0.5 are removed), so that the timetable alone cannot carry the score.

## Variants (all reported)
* **A, primary:** the features above. The extreme, reactive-break and premium-low features use the current minute's high/low, so there is a mild look-ahead inside the minute, the same convention as the F1 scoring.
* **B, causal:** every market feature lagged one minute.
* **C, with order history (teacher-forced):** A plus minutes since the last real sale on that right and lots sold so far today on that right. This uses the real past orders, so it is labelled as such and is not the reconstruction score.

## Decision rule
* The target is met if **variant A** has AUC ≥ 0.85.
* The scheduled-excluded AUC and variant B are always reported next to it.
* No feature, setting or variant is added after seeing results without a post-hoc label.
