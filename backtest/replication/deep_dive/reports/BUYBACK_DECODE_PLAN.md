# D-1 body buy-back — decoding the stop rule: plan

*Written before the tests. In-sample, D-1 of 32 live cycles. Known so far (`BODY_CLOSE_LOGIC.md`): buy-backs are single-leg (the leg's own premium against its own entry), the hazard rises gradually from 1.4× to about 1.8× of the cheapest open entry ("graded"), about half are at second :00 (minute-clocked), 36% of the sub-1.2× ones come within 3 s of a stop-like buy-back on the same right, and 15–21% have no rule. The free-running reconstruction scores buy-backs F1 0.55 with a single threshold θ = 1.5 on the previous close.*

## Why the hazard could look graded although the rule is sharp
A real stop is a step: below the trigger nothing happens, at the trigger it fires. It shows up as gradual when the **variable or the price feed is wrong**. Candidate explanations, each a different variable:
* **V1. Reference:** the cheapest open entry, the average entry, the most expensive entry, or the decision (limit-implied) price instead of the fill.
* **V2. Price:** the previous close, the current minute's high (intrabar), or the current minute's open.
* **V3. Trailing stop:** the price over the **lowest price since entry** (a trailing stop), instead of over the entry.
* **V4. Points, not ratio:** the premium rise in rupees or in strike steps.
* **V5. Spot-based stop:** the spot through the sold strike by d steps (classic seller stop), or the option delta crossing a level.
* **V6. Time-varying threshold:** the threshold depends on time of day or time since entry.

## Tests
1. **Panel:** every D-1 contract-minute with open body shorts, built from the real orders strictly before the minute. Label = a body buy-back on that contract in the minute. Ownership-free: contract level.
2. For each variable: AUC, and **sharpness**, the best single-threshold rule's F1 (minute exact and ±1, threshold chosen on the other cycle half). A sharp rule shows a hazard near 0 below the threshold and high above it.
3. Two-variable rules (threshold pairs and a depth-2 tree), out-of-fold.
4. **Cluster add-on:** when a stop fires on a contract, also buy back other open contracts on the same right that satisfy a second, lower condition (ratio ≥ θ2, or within n strikes). Parameters out-of-fold.
5. **Quantity:** when a contract is bought back, how many lots: all its open lots, the lots above the threshold, or one.
6. The best rule goes into the free-running simulator. The whole D-1 reconstruction is re-scored with no other change.

## Decision rule
* A variable "explains" the stop only if its out-of-fold threshold F1 beats the current rule (close ÷ cheapest entry) by ≥ 0.05 in both cycle halves.
* All candidates are reported.
* Steps added after the results are labelled post-hoc.
