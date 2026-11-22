# D0 counter-sells — plan

*Written before the tests below. A quick look (event rates by buy-back reason) came first: other-right solo sale orders per buy-back event are 6.8 around stop-loss buy-backs against 1.8 for shifted times, and about 1× (equal to the shifted null) around take-profit, clearance and partner buy-backs. In-sample: D0 of the 30 cycles; solo sells 5,844 lots (`D0_SELL_TYPES.md`: counter-sell 20% of D0 sell lots); buy-back reasons from `D0_BB_TYPES.md`.*

## Definitions
* **Event:** the stop-loss buy-back lots (reason 3) on one right R, in one cycle and one minute, taken together. *Lots bought* = their number.
* **Counter-sell:** a solo sale (unpaired body sale) on the **other** right R′.

## Questions and tests
**C1 — Which buy-backs trigger counter-sells.** Other-right solo orders within ±90 s per event, by buy-back reason, against shifted times (±10 min and ±15 min with the clock kept). Accept a reason if the rate is at least 1.5× both nulls.

**C2 — Timing.** Lag histogram (5 s bins, −60 … +90 s) of R′ solo sales around stop-loss events. The share of sales before and after the buy-back.

**C3 — Cause or common cause (the key test).**
* A stop-loss on R happens when the spot has moved against R. The same move may also make R′ sell by itself (the solo ladder at fresh extremes).
* Minute panel: cells (cycle, minute, right R) in scope (before 15:10 and before the stop). Outcome = R′ solo lots sold in the minute and the next one.
* Compare cells with a stop-loss on R in the minute against cells without one, **within bins of the adverse 5-minute spot move** (10 bins).
* Also compare with cells that have a fresh 60-minute favourable extreme for R′.
* Accept "the buy-back adds sales beyond the spot move" if the within-bin difference is positive with a cycle-bootstrap CI that excludes 0 in at least 8 of 10 bins.

**C4 — Quantity.** Per event: lots sold on R′ in 0 … +60 s against lots bought. Table by lots bought, the median ratio, Spearman correlation, a regression slope.

**C5 — Strike and price.**
* The counter-sell strike against the ATM of the previous minute's close, against the strike of the stopped lot, and the premium sold ÷ premium bought back.
* The share at the nearest-ATM strike and within one step.

**C6 — Which stop-loss events trigger sales.**
* The share of events with at least one R′ sale within +60 s, by hour, lots bought, and ratio at the buy-back.
* A single-variable AUC for each, with cycle-bootstrap CIs.

## Acceptance and labels
* Observed / Inferred / Unresolved. Thresholds as stated. No fitted parameters.
