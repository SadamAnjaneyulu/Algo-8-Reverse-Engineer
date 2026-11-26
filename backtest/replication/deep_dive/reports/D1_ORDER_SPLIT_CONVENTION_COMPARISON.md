# D-1 execution convention `one_lot_v2` vs baseline `freeze_v1`: before/after comparison

*2026-11-25. Software + order-level scoring comparison. **Not** a validation. Evidence label for every scoring number: **historical reproduction** (same 32 development cycles, engine parameters fitted on them). Mode F, spec v1.1. No P&L. Everything uncommitted.*

## Result
| | Finding |
|---|---|
| **Decisions** | **Unchanged.** 8,629 decision keys (cycle, second, right, side, strike, role) and 11,553 lots are identical in both runs; 0 keys differ; every non-split order is identical row by row. |
| **Legacy lot-level F1** | **0.6877975245953666 in both runs** (D-1 gate 0.6878). Granularity moved; decisions did not. |
| **Convention** | Opening wings and body buy-backs are now 1-lot orders. Real log: 186/186 and 1,324/1,324 are 1-lot (observed). The other classes are multi-lot in the real log (body sell 0.2%, wing buy 18.8%, wing sell 40.3%, lump 93.2%), so they are correctly **not** split. |
| **A defect I found and fixed on the way** | The first v2 run **rejected 29 orders** at the 40-orders-per-minute risk guard (SENSEX 9 Jul, 16 Jul, 13 Aug): 20 buy-backs, 7 wing sells, 1 wing buy, 1 ladder order. Quantity was not preserved, so that run was **not** the experiment you specified. It is archived (`outputs/scoring/d1_F_v2_onelot_attempt1_guard_blocked`), not used. |
| **Fix** | The 1-lot children of one decision share **one** slot of the per-minute limit; the limit still binds decisions. Baseline behaviour is unchanged. This is part of the convention's definition, recorded as such. |

## What changed in the order-level score
Orders in the replay: 8,735 → 9,035 (real 9,915). Lots unchanged.

| Class | Orders v1 → v2 | Real orders | Recall v1 → v2 | Precision v1 → v2 | F1 v1 → v2 |
|---|---:|---:|---:|---:|---:|
| Opening wings | 62 → 186 | 186 | 0.672 → **0.979** | 0.968 → 0.758 | 0.793 → 0.854 |
| Body buy-backs | 757 → 933 | 1,324 | 0.431 → **0.490** | 0.741 → 0.689 | 0.545 → 0.573 |
| Body sell, lump, wing buy, wing sell | unchanged | | wing buy +0.002, others identical | | |

Pooled, cumulative tolerance 60 s, strictness lots-exact: F1 **0.458 → 0.472**; keys-only: 0.736 → 0.739. At 0 s keys-only F1 0.215 → 0.213. Lots-exact match share of real orders at 60 s: 0.430 → 0.451.

## Interpretation (what this does and does not show)
* **This is a measurement-granularity effect, not a better reconstruction.** One-to-one matching cannot pair a 3-lot simulated order with three real 1-lot orders; it pairs one and leaves two missing. With 1-lot orders the same decisions can be matched. The identical legacy F1 proves no decision changed.
* **Opening wings now match almost completely at the key level** (182 of 186 real orders matched). Precision fell because the simulator's 186 single lots now each have to match, and some land at other seconds, strikes or matched to other-class orders (class-blind keys: 46 real opening-wing orders paired to a different-class simulated order). That is information the multi-lot version hid.
* **The large gap is still there:** the simulator sends 933 buy-back lots; the real log has 1,324 (70%). The convention does not touch that; it is the same residual as before (buy-back rule, see register).
* **Cardinality check:** more simulated orders can raise matches by chance. Against the +15-minute placebo, the share of real orders matched within 60 s (keys-only) rose **0.692 → 0.706 (+0.014)** on the real alignment but **0.310 → 0.311 (+0.001)** on the shifted one; the exact-tier placebo is identical (354). So the gain is not explained by the extra orders alone. The placebo is a time-shift check, not a universal chance baseline.
* Pooled bootstrap CI (cycle-clustered) of the F1: 0.7226-0.7493 → 0.7259-0.7522 (overlapping).

## Verification
* Code written / inspected / **executed**: `d1_strategy` suite **42 passed** (`test_order_split.py` 7 new, `test_order_type.py`); `deep_dive` `tests/test_order_split_convention.py` 4 passed over the saved runs.
* Mutation-checked: removing the shared rate slot makes the rate-slot test fail (my first version of that test did **not** and was rewritten); the default is `freeze_v1`; an unknown value raises.
* Re-run with the convention: 32 cycles, 0 rejected, legacy F1 identical, `outputs/scoring/d1_F` (baseline) untouched.

## Files
`d1_strategy/d1_algo/{config,engine,risk}.py`, `d1_strategy/test_order_split.py`; `src/bl_score_d1_F.py` (env `ORDER_SPLIT`), `src/bl_split_compare.py`; `outputs/scoring/{d1_F, d1_F_v2_onelot, d1_F_v2_onelot_attempt1_guard_blocked, split_comparison, execution_convention.json}`.

## Not done / next (in your order)
1. TF-E for D-1 and comparison with F.
2. Mismatch classes (no P&L tuning).
3. Standalone D0 engine, D0 and end-to-end scoring.

*This convention is an execution assumption. It does not turn any reconstructed rule into a confirmed one.*

## Addendum (2026-11-25, after review): accepted guard rule and its conditions
Accepted by the reviewer: the per-minute cap counts **strategy decisions**, not the child orders of one split decision. Implemented with a **decision ID** on every order (`OrderRequest.decision_id`; all children of one `_submit` share it, independent decisions never do) and `RiskGuard.check` counting distinct decision IDs under `one_lot_v2`. Conditions met and tested (`d1_strategy/test_order_split.py`, 12 tests, mutation-checked): the 40-per-minute cap is still enforced on independent decisions in both conventions; every child still passes the quantity, price, short-lot and halt checks (the engine has no margin check, so none is bypassed); `freeze_v1` is unchanged and its replay equals the saved baseline exactly; the blocked first attempt (29 rejected orders) stays archived in `outputs/scoring/d1_F_v2_onelot_attempt1_guard_blocked`. The `one_lot_v2` replay after the refactor is identical to the run reported above.
**Reading of the score change:** the order-level F1 gain (0.458 to 0.472) is a **measurement-granularity effect**, not evidence of better strategy reproduction; the legacy lot-level F1 is identical to 16 digits.
