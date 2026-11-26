# Phase 1, Gates 3b (wing release) and 3c (overnight lump): preregistration

*Written 2026-11-25 **before** any 3b/3c computation. Experiments `P1-3B-*`, `P1-3C-*`. Baseline B1 (frozen). Existing data only. Evidence: historical reproduction on the 32 development cycles. Teacher-forced on the real position (no engine run unless a rule is supported). Nothing committed.*

## 3b. Wing release: which long is sold
**Evidence (not re-run):** the controller sells exactly the excess of long over short lots on a right about 4 s after a body order (quantity <= excess in 96% of 500 sell decisions); *which* wing: outermost 44%, cheapest 44% against 26% by chance (`D1_LONG_SIDE.md`). The engine sells the outermost wing first. **Population:** the real wing sells (`h_` `close_long`, 600 orders) with at least two held wing contracts on that right just before the order (the choice only matters then). Held wings come from the real log replay (lots with buy times).
| ID | Rule: the contract sold |
|---|---|
| W1 | outermost: largest distance from the previous-close ATM (engine rule) |
| W2 | cheapest previous-minute close premium |
| W3 | the most recently bought wing contract |
| W4 | the oldest bought wing contract |
| W5 | innermost (nearest the ATM) |
| W6 | the contract with the most lots |
Metric: exact contract agreement, pooled and per cycle; chance = mean of 1/(held contracts). **Supported** (X vs W1): +0.05 exact, cluster-bootstrap (cycles, 4,000) 95% interval above 0, >= 20 of 32 cycles at least equal. If supported: engine switch and acceptance on the wing-sell class (F1 >= B1 0.497 + 0.03, wing buy not below B1 - 0.02, body sells and buy-back F1 not below B1 - 0.005, legacy lot F1 >= 0.6878 - 0.005, L1 <= 0.528). Not supported: wing release choice **Partial** and 3b CONDITIONAL.

## 3c. Overnight lump
**Evidence (not re-run):** side = the heavier short side (only that side in 80% of cycles; confirmed), clock regimes by date (confirmed), strike about 2.2 sigma-sqrt(T) out (exact 34%, within one 62%: Partial), **size unresolved** (engine: 0.827x NIFTY / 0.503x SENSEX of the heavy-side shorts; error about +/-13 lots, 24% median). **Population:** the real lump orders (`v_`, 73 orders, 1,489 lots) aggregated per cycle (total lots, side(s), first-order time); the real position at the first lump order.
| ID | Rule for the total lump lots (one constant per underlying, fitted leave-one-cycle-out) |
|---|---|
| M1 | a x (heavy-side short lots) (engine form) |
| M2 | a x (heavy - light short lots) |
| M3 | a x (total short lots) |
| M4 | a constant number of lots per underlying |
Metric: held-out mean absolute error in lots and the median relative error; chance reference M4. **Supported** (X vs M1): held-out MAE lower by >= 20% with the cluster-bootstrap 95% interval of the paired difference below 0 and X better in >= 20 of the cycles with a lump. Not supported: lump size stays **Unresolved**, the existing engine form stands, 3c CONDITIONAL. The lump strike and side are not retested.

## Limits stated in advance
Same development cycles; cycles with a lump about 30 (small sample, wide intervals); held wings come from fills (which wing lot was sold is not in the log; oldest-first removal within a contract is a convention); module labels inferred; ten rules counted.
