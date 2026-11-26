# Phase 1 final loop, Investigation A: option-premium-triggered solo ladder. Preregistration

*Written 2026-11-25 **before** any premium-trigger computation. Experiments `P1-9-A*`. Baseline: frozen B1 (`one_lot_v2`); strongest previous candidate: V01 book condition (archived near-miss, Gate 2A). Existing data only (one-minute index bars; option bars for the whole downloaded chain, forward-filled where nothing traded; the real log). Evidence label: historical reproduction on the 32 development cycles. Nothing committed. Selection counted: 2 binary rules at the decision level, at most 1 engine variant.*

## 1. Mismatch classes an option-premium trigger could explain (from the 2A ledger and T3)
* 675 of the 1,179 missing real body sells are solo-labelled; the engine's spot condition ("new 60-minute extreme of the index") holds at only 8% of the unmatched real solo sells and 71% of all real solo-sell minutes (base rate 6.8%).
* The solo side is "the option that just became cheaper" (78%/85%). A trigger on the option's own premium can fire when spot is not at a 60-minute extreme but the premium is (time decay, implied-volatility moves, a drift towards the money), which spot cannot see. It can also over-fire: on D-1 premiums decay through the day, so premium lows are frequent. That is the hypothesis' main risk and the reason it is tested at decision level first.

## 2. Mechanism hypothesis (H6)
The original system sells a right when **that right's premium** makes a fresh extreme low (the decision variable is the option price), not when the index does. Falsifiable prediction: the premium-extreme indicator separates real solo-sell minutes from other minutes better than the spot-extreme indicator **and** covers the real solo sells the spot indicator misses without a comparable rise in the base rate.

## 3. Inputs and decision-time conventions (fixed now)
| Item | Definition |
|---|---|
| Cells | (cycle, right, minute j = 1..374) of the 32 D-1 sessions. Cells where a real **non-solo** body sell (inferred module scheduled/pair/other, not `solo`) occurs on that right in minute j are excluded (explained by other rules) |
| Label y | a real solo-labelled body sell (`outputs/bodysell/ledger_real.csv`, inferred module `solo`) on that right in minute j |
| Spot indicator S(N) | engine convention: CE: minute-j spot low < min of the previous N minute lows; PE: minute-j spot high > max of the previous N minute highs; window `max(j-N, 0)..j-1` (>= 1 completed bar). N = 60 (the engine's gate) |
| Premium indicator P(N) | contract c = ATM of the previous completed minute's spot close on that right (the pair rule; decision-time, no fitted constant); minute-j low of c's own bars < min of c's previous N minute lows (both rights: premium **falling**). N = 60 |
| In-minute information | the minute's own running extreme is used for both S and P, exactly as the engine uses the current minute's low/high (a stated convention); no bar after minute j is read |
| Bars | option bars cover the whole chain, forward-filled; the ATM contract always has a bar |

## 4. Tests and criteria (fixed now)
Cell level, pooled, cluster bootstrap over cycles (4,000 draws); F1 of the indicator as a classifier of y.
| # | Criterion (rule P alone) |
|---|---|
| PA1 | F1(P) - F1(S) >= +0.03 and the 95% interval of the difference has lower bound > 0 |
| PA2 | coverage of the B1-**missed** real solo sells by P >= 40% and lift (coverage / base rate of P) >= 3 |
| PA3 | precision(P) >= 0.8 x precision(S) (no false-positive collapse) |
Secondary rule U = S OR P (counted as the second test): supported if F1(U) - F1(S) >= +0.03 with interval lower bound > 0, recall(U) >= recall(S) + 0.10, and precision(U) >= 0.8 x precision(S).
**Stop rule:** if neither P nor U meets all its criteria, H6 is **rejected at the decision level** (classified Unresolved/data-limited with the measured numbers) and **no engine variant is built**. A supported rule goes to one engine variant: the fresh-extreme condition is replaced by the supported indicator, the spot rung (`ref -/+ 0.2 step`), lots (one), strike rule, book logic and reset behaviour unchanged; scored under `one_lot_v2` against B1 with the Gate 2A criteria A1-A9 (unchanged) plus: strict F1 not below B1, scheduled straddles >= 2,076 matched, extras not above B1's 873, real solo-sell recall not lower than B1's, no lookahead (perturbation test), and improvement in >= 20 of 32 cycles. Failing any = rejected and archived. Trigger re-arming, cooldown and duplicate handling are those of the existing ladder (reference advances by the rungs crossed; a sale in the minute blocks nothing else; the 40-per-minute guard unchanged).

## 5. Expected effects (stated in advance)
If H6 is true: missed solo sells fall (recall up), false solo sells do not rise materially, timing offsets of matched solo sells shrink. If false: P has a high base rate (theta-driven lows), lift small, precision collapses.

## 6. Limits stated in advance
Same development cycles; module labels of real orders are inferred; the minute low is an upper bound of what the engine sees intrabar; premium of one contract (ATM of previous close) is a proxy for the original variable; real fills at a different strike than the ATM contract are not scored by strike here.
