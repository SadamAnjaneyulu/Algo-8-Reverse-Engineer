# Phase 1, Gate 2B: solo strike reference. Result

*2026-11-25. Plan `PHASE1_GATE2B_PLAN.md` (with Addendum 1), written before the evaluation. Experiments `P1-2B-0` (rules S0-S6), `P1-2B-1` (addendum S8, S9), attribution `P1-2B-2`. Existing data only; no engine change. Evidence: historical reproduction on the 32 development cycles. Nothing committed.*

## Gate report
| Field | Content |
|---|---|
| Gate | 2B: solo strike reference |
| Status | **CONDITIONAL**: no alternative rule is supported; the engine rule S1 stands; the residual is quantified and not reducible with the available data |
| Baseline | F (B1): matched ladder-solo orders have the exact strike 25.6% of the time (547 matched; 39.7% one step off; 34.7% two or more) |
| Latest result | teacher-forced on real solo sells (n = 1,139): **S1 exact 0.501, within one step 0.881**; best alternatives S2 0.536, S4 0.531, S1r 0.505 (none meets the +0.05 bar); union of all rules 0.733; real strike inside the +/-4 window 99.5% |
| Criteria | the preregistered support rule (+0.05 exact vs S1, bootstrap interval above 0, >= 20 of 32 cycles; LOCO for S5): **no rule passes** |
| Root causes | (1) the strike rule is **incomplete but not wrong**: with real context it is right about half the time; (2) the loss from 0.50 to 0.256 in F is mostly **inherited context** (the simulator's own last sale, timing and book differ from the real ones) |
| Corrections | none (nothing supported) |
| Regression | none (no engine change) |
| Evidence | `outputs/phase1/2B_strike_eval*.json/csv`, `2B_strike_attribution.json`, `src/bl_p1_2b_strike*.py` |
| Remaining | strike agreement of ladder orders can only rise if the solo timing/count context improves (Gate 2A residual, data-limited) or the real decision-time variable is found (not identifiable from fills and minute bars) |
| Next action | Gate 2C (15:00+ block) |

## Results (P1-2B-0 and P1-2B-1; real context, information strictly before each order)
| Rule | Exact | Within 1 | vs S1 (exact) | 95% interval | Cycles >= S1 | Supported |
|---|--:|--:|--:|---|--:|:-:|
| S0 ATM of previous close | 0.190 | 0.858 | -0.312 | [-0.359, -0.262] | 1 | no |
| **S1 engine rule** (premium nearest the last same-side sale) | **0.501** | **0.881** | | | | baseline |
| S1r relative distance | 0.505 | 0.885 | +0.004 | [+0.001, +0.007] | 32 | no (below +0.05) |
| S2 last same-side strike | 0.536 | 0.875 | +0.034 | [+0.008, +0.064] | 26 | no (below +0.05) |
| S3 ATM of the minute open | 0.189 | 0.867 | -0.313 | [-0.357, -0.264] | 1 | no |
| S4 offset persistence | 0.531 | 0.894 | +0.030 | [-0.003, +0.067] | 21 | no |
| S5(f) premium fraction (LOCO f = 1.0 in 32/32 folds, i.e. S0) | 0.190 | 0.858 | -0.312 | | 0 | no |
| S6 other-side last price | 0.175 | 0.483 | -0.327 | | | no |
| S8 stack on the most-held strike | 0.226 | 0.567 | -0.276 | [-0.325, -0.220] | 2 | no |
| S9 held strike nearest ATM | 0.190 | 0.861 | -0.312 | [-0.360, -0.260] | 1 | no |
By group (S1 exact): NIFTY 0.473, SENSEX 0.523; before 15:00 0.477, from 15:00 0.581.

## Where F's strike loss comes from (P1-2B-2; 403 matched ladder pairs with a last sale)
* Simulator strike equals the real strike: **0.248**.
* The **same rule fed the real context** equals the real strike: **0.474**. So about **0.23 of the 0.50 is lost to context** (the simulator's own last-sale price, timing and book).
* Of the 303 pairs where the simulator's strike is wrong, the rule on real context would have been right in **41%**; in the other 59% the rule itself misses.
**Reading (Inferred):** solo strike selection in the engine is about as good as spot-and-premium bars allow (a clearly better rule did not appear in ten candidates, and the union ceiling of 0.73 shows the rest is not captured by any of them). The F-level shortfall is mostly a consequence of upstream divergence, which Gate 2A found to be data-limited. Expected maximum gain from better context alone is about +0.2 on matched ladder orders; it cannot be claimed or realised without the real decision-time inputs.

## Classification and limits
Solo strike reference: **Partial** (rule form decoded, 0.50 exact with real context; residual quantified; irreducible without decision-time information). Same development cycles; module labels inferred; previous-close premium is a lagged proxy (G3: median drift 2.5%); ten rules plus one fitted constant counted. No further strike-rule search without a genuinely new mechanism.
