# D-1 buy-backs as rebalancing events in the simulator: plan

*Written before running. In-sample, D-1 of 32 cycles. Based on `BUYBACK_STOP3.md`.*

## Event model (each part can be switched on or off; options chosen on the other cycle half)
1. **Trigger:** a lot's own premium (minute high ÷ its entry) reaches θ ∈ {1.6, 1.65}. This is the decoded stop.
2. **Same-right cluster:** in the same minute, other lots on that right whose own ratio is ≥ θ2 are bought back too. θ2 ∈ {off, 1.2, 1.4}.
3. **Straddle partner:** the lots at the same strike on the other right are bought back too. Options: {off, on}.
4. **Counter-sell:** solo lots are sold on the other right, at the solo strike rule (premium nearest the previous sale on that right). Size ∈ {off, 1 lot, as many lots as were bought back}.
5. **Reactive continuation exit:** a reactive or attached-extra lot held ≤ 10 minutes is bought back when the spot has continued d ∈ {off, 1, 1.5} strike steps in its break direction since the sale (only the leg on the break side).
6. **Solo reversal exit:** a solo lot is bought back when the spot has reversed d2 ∈ {off, 1.5, 2} steps against it since the sale.

## Scoring
* **Free-running:** options chosen per fold by the **overall D-1 lot F1**, because the counter-sell also changes sells. Every class is reported: buy-backs, sells, wings, lump.
* **On the real sells (tf_bb):** parts 1–3 and 5–6, chosen by buy-back F1. The counter-sell cannot be scored there, because the sells are real.
* Compared with the current simulator (plain stop at about 1.6×): free-running overall 0.686, buy-backs 0.558; on the real sells 0.588.

## Decision rule
* The event model counts as an improvement only if it beats the current simulator out-of-fold on the overall F1 (free-running) and on the buy-back F1 (real sells).
* Otherwise the current simulator stays.
