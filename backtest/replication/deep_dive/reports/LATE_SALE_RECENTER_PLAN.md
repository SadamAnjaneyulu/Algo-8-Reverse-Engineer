# Re-centring hypothesis: does distance-to-spot of the held shorts trigger the late sale? (pre-registration)

*Written 2026-11-24 **before** any test below ran. Follows `LATE_SALE_FOCUSED.md`. This is **one mechanism, not a new screen**: the side finding (sell the option that just became cheaper, 78% post / 85% held-out) suggests a single state variable might explain both side and timing: **how far the nearest short on that side has drifted away from spot**. After a rally the held put shorts are further out of the money and cheaper; a rule that keeps the short book a fixed distance from spot would then sell new puts. Frozen rule, score and hashes untouched.*

## Mechanism and what it predicts
* **H-R:** a late sale on side X is triggered when the nearest held short on side X is more than some distance (in strike steps) out of the money, and the new strike is placed closer to the money.
* **Predictions (all testable strictly before the minute):** (1) the sale hazard rises with D, the distance of the nearest held same-side short (OTM steps, positive = out of the money); (2) in single-side minutes the side sold is the one with the larger D; (3) D adds to clock + straddle change in a leave-one-cycle-out model; (4) the new strike is closer to spot than the nearest existing same-side short; (5) the same holds on the pre-auction held-out cycles.

## Definitions (fixed)
* Price series: futures (post-auction), published index (pre-auction), close of minute j−1 (strictly before). Strike step: NIFTY 50, SENSEX 100.
* **D(side, j)** = OTM steps of the nearest net-short strike held on that side at the start of minute j: (K − P)/step for calls, (P − K)/step for puts. Undefined when the side holds no short (reported as its own share; ranks filled with the block median).
* Same sample, window and hazard machinery as the focused tests (stratified AUC within (cycle, side), curveball null, 1,000 permutations).

## Tests (family of 5, BH 10%)
| ID | Statistic | Rule |
|---|---|---|
| **R1** | Hazard AUC of D, post-auction | supported if AUC ≥ 0.60 and BH significant, same direction in ≥ 60% of cycles |
| **R1-held-out** | Same on pre-auction cycles | direction fixed (AUC > 0.5); supported if AUC ≥ 0.60 and one-sided p ≤ 0.05; inconclusive if power is low |
| **R2** | Single-side minutes: share where the sold side has the **larger D**; cycle-cluster bootstrap | supported if share ≥ 0.65 and CI lower bound > 0.50 |
| **R2-held-out** | Same on pre-auction cycles | as R2, direction fixed |
| **R3** | Leave-one-cycle-out ΔAUC of (clock + straddle change + D) vs (clock + straddle change); linearised cluster-robust CI | supported if the CI excludes 0 |

## Descriptive, no p-values
* **R4:** for every real late sale, D of the **new strike** vs D of the nearest held same-side short just before it. Share placed closer to the money (re-centring), at the same strike, or farther out; share with no same-side short.
* **R5:** distribution of D at sale minutes vs other minutes (median, IQR) and the best single threshold on D in the development cycles (reported as descriptive; chosen post-hoc, not a rule).
* **R6:** does D beat the futures direction (FUT5L) as the side predictor in R2, or do they agree?

## Decision rules and limits
* Supported only if the post-auction test passes its size rule **and** the held-out version does not contradict it. D uses the book as reconstructed from the order log (hidden or manual orders are not seen).
* Same development cycles as before; the held-out set is small (7 cycles with late sales). R5's threshold is post-hoc.
* If H-R holds, the next step is a pre-registered forward test with D recorded by the shadow recorder; if not, the late sale is not a simple re-centring rule.
