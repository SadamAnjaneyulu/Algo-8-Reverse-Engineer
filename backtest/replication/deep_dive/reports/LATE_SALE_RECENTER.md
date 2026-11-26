# Re-centring hypothesis: not supported

*Plan: [`LATE_SALE_RECENTER_PLAN.md`](LATE_SALE_RECENTER_PLAN.md), written before the run. One mechanism, five p-valued tests (BH 10%), same development cycles plus the pre-auction held-out set. Frozen rule, score and hashes untouched.*

## Result first
**The late sale is not a simple "keep the short book a fixed distance from spot" rule.** The distance of the nearest held same-side short from spot (D) does not predict when a sale happens, adds nothing to the clock and straddle change, and the new strike is usually **not** placed closer to the money.

| ID | Result | BH ≤ 10% | Verdict |
|---|---|---|---|
| R1 hazard AUC of D, post-auction | 0.564 vs null 0.537, p = 0.22; 11 of 17 cycles same direction | no | Not supported (size rule needs ≥ 0.60) |
| R1 held-out (pre-auction) | 0.542 vs 0.529, p = 0.44; 4 of 7 cycles | no | Not supported (low power) |
| R2 sold side has the larger D | 69% [50%, 86%], 36 minutes; p = 0.026 | no (0.13) | Not supported; weaker than futures direction (78%) |
| R2 held-out | 62% [20%, 94%], 13 minutes; p = 0.33 | no | Not supported |
| R3 D added to clock + straddle change | ΔAUC −0.017 [−0.051, +0.017] | no | Adds nothing |

## What the new strikes actually do (descriptive, R4)
Of the 148 post-auction late sales (every one had a same-side short already):
* **10%** placed the new strike **closer to the money** than the nearest existing same-side short (re-centring),
* **44%** at the **same strike** (stacking more lots on an existing strike),
* **46%** **farther** out.

Pre-auction (28 sales): 4% closer, 25% same, 71% farther. So re-centring is not what the sales do. Stacking at an existing strike is the single most common action post-auction.

## R5/R6 (descriptive)
* D at sale minutes (median −1.49 steps, IQR −2.48 to −1.06) vs other minutes (−1.97, −2.71 to −1.39): a small shift, heavy overlap. The best single threshold (post-hoc, D ≥ −1.0) gives precision 12%, recall 21% against a 5.3% base rate: not a rule.
* D as the side predictor (69%) does not beat futures direction (78%).

## Limits and one caveat
* **Basis not removed:** post-auction D uses the futures price, which sits above the index by the basis (about one strike step), so call and put distances are offset in opposite directions. R1 and R3 are unaffected (the AUC is within a block, so a constant offset cancels), but R2 and the absolute D levels are affected. The pre-auction version uses the index and shows the same weak result, so I do not expect the basis to hide a strong effect, but I did not rerun with the option-implied forward.
* Book reconstructed from the order log only. Small samples; the held-out set has 7 cycles with late sales.

## Where this leaves the late sale
Combined with the earlier reports:
* **Which side:** the one that just became cheaper (replicated). Not explained by distance-to-spot of the held shorts.
* **Which strike:** often the same strike as an existing short (stacking), otherwise farther out; not a re-centring.
* **When:** minute-level clock concentration; a weak, thin straddle lead; no state variable passes.
* **Not:** risk control, premium target, lump-coupled, general pair, replacement, profit booking, re-centring.
* **Unresolved:** the actual trigger. The log has no decision time and hidden inputs may exist (an unlogged signal, a discretionary or manual component). Only forward recording with pre-order state can narrow it further.

Files: `src/bl_trig4_recenter.py`, `tests/test_recenter.py`, outputs in `outputs/trig4/`.
