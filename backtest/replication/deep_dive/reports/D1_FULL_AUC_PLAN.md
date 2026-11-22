# Complete D-1 activity (body + hedge) — one AUC against the real ledger: plan

*Written before running. In-sample, D-1 of 32 live cycles.*

## Panel
* Cells: cycle × minute (09:16–15:44, j = 1…389, so the 15:30+ lumps are included) × right (CE/PE).
* Labels, one per activity class. The cell is 1 if at least one order of that class falls in it:
  1. **body sell**: `num` open_short;
  2. **body buy-back**: `num` cover_short;
  3. **wing buy**: `h_` open_long;
  4. **wing sell**: `h_` close_long;
  5. **body-stream long**: `num` open_long / close_long (opening wings and their closes);
  6. **lump**: `v_` open_long.
* **Any activity** = any of the six. The few `s_` / `m_` orders on D-1 (one stop cycle) count in "any activity" only.

## Features (decoded rules and their inputs; nothing new)
* **Sell block:** the D-1 sell features from `D1_SELLING_AUC_PLAN.md`: timetable share (leave-one-cycle-out), the reactive machine, fresh extremes, premium lows, favourable moves, clock.
* **Book state at the minute start** (contract level, all modules, orders strictly before the minute): short lots S and long lots L on the right, the gap S − L, open short lots by premium ratio (current price ÷ average entry; ≥ 1.2/1.4/1.5/1.6/1.7, and the maximum ratio), using the previous close (causal) and the current minute's high (same-minute).
* **Moves:** adverse spot move over 1 and 5 minutes.
* **Clock:** minute; second-zero clocking is not visible at minute level; the lump window by date regime (15:06–15:14 until 2026-08-05, 15:23–15:24 for 08-12 to 08-19, 15:30–15:35 from 08-24, from `D1_LUMP.md`); the opening minute (09:16).
* **Body → hedge link**, in two versions:
  * (i) **hedge given the real body** (the hedge module's test): real body sells and buy-backs on the right in this and the previous minute;
  * (ii) **chained**: in their place, the out-of-cycle predicted body-sell probability from the sell model (variant A of `D1_SELLING_AUC`).

## Models and scoring
* Gradient boosting, the same fixed settings, leave-one-cycle-out. One model per class, plus one for "any activity".
* AUC per class with a 95% cycle-bootstrap CI (1,000 draws).
* **Overall:** (a) the AUC for "any activity"; (b) the macro average of the six class AUCs; (c) the pooled AUC over all class × cell pairs (every class's score and label stacked).

## Variants
| Variant | Market features | Body → hedge link |
|---|---|---|
| **A, primary** | same minute | (i) real body orders |
| **A-chained** | same minute | (ii) predicted body sells only; no real orders in the current minute |
| **B, causal** | lagged one minute | (i) |

All variants use book state from the real past orders (teacher-forced state, the usual setting for decoding: "given its position, what does it do"). This is stated next to every result.

## Decision rule
* Report all variants.
* Steps added after seeing results are labelled post-hoc.
