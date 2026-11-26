# Phase 1, Gate 2D: breakout / pair sizing. Result

*2026-11-25. Plan `PHASE1_GATE2D_PLAN.md`, written before the runs. Experiments `P1-2D-BK0` to `BK3` (`outputs/phase1/2D/`). Existing data only; evidence: historical reproduction on the 32 development cycles. Nothing committed.*

## Gate report
| Field | Content |
|---|---|
| Gate | 2D: breakout / pair sizing (the remaining body-sell block: inferred module *pair*, 486 misses) |
| Status | **FAIL: all variants rejected**; Gate 2D **CONDITIONAL** (residual quantified) |
| Baseline | B1 body sells: F1 0.7586, strict F1 0.5954, 4,091 lots (real 4,671), 873 extra, 1,179 missing |
| Latest result | BK0 (single-lot orders only): **identical to B1** (all simulated breakout orders were already 1-lot). BK1 (size delay 10 s): F1 0.7594, strict **0.5754**, recall 0.748, precision 0.771, extras 977. BK2 (30 s): 0.7542, strict 0.5773, extras 952. BK3 (60 s): 0.7180, strict 0.5375, extras 1,116 |
| Criteria | A1-A9 as registered: every variant fails A1 (F1 +0.02), A2 (strict +0.01) and A3; BK1 passes A4-A7 but fails A8 (improves F1 in 18 of 32 cycles, needs 20); leave-one-cycle-out picks BK1 in 32 of 32 folds with pooled F1 0.7594 (below the 0.7686 bar) |
| Root cause | not identified as a rule. Sizing the entry by depth after a delay adds lots (4,091 to 4,264) but also adds as many false as true orders: recall rises (0.733 to 0.748), precision and strict agreement fall |
| Corrections | none accepted; `breakout_one_lot` exists (default off, tested, mutation-checked) |
| Regression | none; scheduled straddles unchanged |
| Evidence | `outputs/phase1/2D/{BK0..BK3,evaluation.json}`, `src/bl_p1_2a_run.py` (variants BK*), `d1_strategy/test_ladder_candidates.py` |

## Reading
* Hypothesis B1 (delayed depth sizing sent as single lots) is **not supported** at order level. This agrees with the earlier lot-level finding (`D1_LOTS.md`: depth sizing predicts the count weakly, Spearman 0.30, and was rejected out-of-fold).
* The breakout and pair misses are therefore classified with the solo sells: **timing and count are set by a tick path that one-minute bars cannot show.** Breakout strikes (78.6% exact for straddles, 69.6% extras) and repeat entries (49 of 274 pair-minutes) stay **Partial / Unresolved**; repeat entries were not reopened (no rule found earlier).
* Classification: breakout/pair trigger **Decoded** (first entry per candle-side 93%), size **Partial**, repeats **Unresolved**.

## Limits
Same development cycles; four runs counted; the intrabar path is a convention (depth after 10-60 s depends on it).
