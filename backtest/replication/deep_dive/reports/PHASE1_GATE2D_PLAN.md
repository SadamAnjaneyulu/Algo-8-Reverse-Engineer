# Phase 1, Gate 2D: breakout / pair sizing (remaining body-sell mismatches). Preregistration

*Written 2026-11-25 **before** any Gate 2D run. Experiments `P1-2D-*`. Baseline B1. Existing data only. Evidence: historical reproduction on the 32 development cycles. Nothing committed.*

## 1. Problem
Misses with inferred module *pair*: 486 of the 1,179 missing real body sells (M1 356, M4 96, M3 33); extras from breakout orders 117 (X1 mostly: the simulator fires where a real order is already matched elsewhere). Matched breakout strikes: exact 78.6% (straddle) and 69.6% (extra). **Every simulated breakout order is 1-lot** (458 straddle + 229 extra orders, all 1 lot).

## 2. Evidence already in the repository (not re-run)
* Decoded (D1-04, `BODY_SOLO_DECODE.md`): the reactive entry fires on the two-candle channel break; **its size grows with the depth of the break** (Spearman 0.42 for extras, 0.29 for pairs; about 3 lots for a hair-line break, about 6 for a break of more than one strike step); real orders are single lots (91-99%).
* The engine implements the sizing (`pairs_per_depth_step`, `extra_a`, `extra_b`) but evaluates depth at the **first second of the break** (`breakout_size_after_s = 0`): the depth is about zero, so n = 1 pair and few extras; and breakout orders are sent as one order of n lots (not single lots like the real log). The delay parameter exists but was never evaluated at order level.
* Repeat entries inside a candle-side (49 of 274 pair-minutes): no rule found (D1-04); **not reopened**.

## 3. Hypotheses
| ID | Hypothesis |
|---|---|
| B1 | Breakout entries are sized by the depth reached **a short time after the first break** (a tracker) and sent as **single-lot orders** (the real log) |
| B2 | Sizing at the first second (baseline) |
| B3 | Repeat entries inside a candle-side | not tested (no rule) |
| B4 | The residual is a tick-path effect (as for solo sells) | the residual after B1 |

## 4. Variants (enumerated now; 4 runs counted)
New switch `breakout_one_lot` (default False): breakout straddle and extra orders are sent as single-lot orders (one decision id, as `ladder_solo` in steps mode). No other change.
| ID | Change | Purpose |
|---|---|---|
| BK0 | `breakout_one_lot` only (size delay 0) | separates the granularity effect from the sizing effect |
| BK1 | + `breakout_size_after_s = 10` | B1 |
| BK2 | + 30 | B1 |
| BK3 | + 60 | B1 |
Delay is selected leave-one-cycle-out among {0, 10, 30, 60}.

## 5. Acceptance criteria (fixed now; B1 values as in Gate 2A)
Same A1-A9 as `PHASE1_GATE2A_PLAN.md` section 7 (body-sell F1 >= 0.7786, strict F1 >= 0.6054, recall >= 0.7525 with precision >= 0.7766, simulated lots closer to the real 4,671, scheduled straddles >= 2,076 matched with exact-second share >= 0.659, other class F1 >= B1 - 0.02, book L1 <= 0.528, body-sell F1 improved in >= 20 of 32 cycles, leave-one-cycle-out agreement >= 80% and pooled held-out F1 >= 0.7686). Failing any = rejected and archived.

## 6. Stop rule
If none passes, breakout sizing is classified **Partial**, the residual quantified (by module and category from the ledger), and **Gate 2D is CONDITIONAL**; no further sizing search without a new mechanism.

## 7. Limits stated in advance
Same cycles; module labels inferred; the replay's intrabar path is a convention (depth after 10-60 s depends on it); four runs counted.
