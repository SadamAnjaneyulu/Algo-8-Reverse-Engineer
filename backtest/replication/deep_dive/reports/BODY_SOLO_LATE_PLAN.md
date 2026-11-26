# After-15:00 solo sells — decoding plan

*Written before the tests. In-sample, D-1 of 32 live cycles. Late solo = regular solo lots (body `open_short`, not in a scheduled/reactive pair, within 4 strikes of ATM) at or after 15:00; deep-OTM batch sells reported alongside for comparison.*

## Hypotheses (all tested, none assumed)
* **H1 Overnight delta shaping** — before the close the book is brought towards a target net delta (e.g. ≈ 0) for the overnight carry; each late sale reduces |book delta| (all modules incl. wings).
* **H2 Financing the wings** — late sells fund the late long-wing purchases (hedge `h_` and lump `v_` modules): premium received by late sells tracks premium paid for late longs.
* **H3 Inventory shaping** — late sells bring CE/PE lots (or premium) towards a target ratio for the carry.
* **H4 Pair-linked** — late sells are completions of pair-type entries (reactive at 15:25–15:30, scheduled) or leg replacements.
* **H5 Market-triggered** — late breakouts, speed, volatility (realised and straddle-implied), indicators (RSI, range position).
* **H6 Clock** — fixed late times (15:00, 15:15, 15:20, 15:23, 15:29).

## Tests
1. Describe: lots, cycles, minute/second profile, CE/PE, strike offset, premium level, bursts.
2. Order-flow event study (±2 min, ±10 s) around late solo sells vs control seconds in 15:00–15:30, by module/role; ₹ flows of late sells vs late long purchases per cycle.
3. Greeks with the whole book (all modules; Black–Scholes from the ATM straddle): delta, gamma, vega at each late sale vs controls; change produced by the sale; book delta at 15:00 vs 15:30; share of late sales that reduce |delta| vs the other right.
4. Market: late fresh extremes, 1/5/15-min moves, realised vol, straddle change, RSI-type and range-position indicators; option volume at the sold strike net of Algo 8.
5. Models: per-minute panel 15:00–15:29 × right, leave-one-cycle-out logistic/boosting by block (clock, market, Greeks, inventory, order-flow), out-of-fold rule search; report what explains the regime and how well.

## Evidence rules
Observed / Inferred / Unresolved / Not testable; post-hoc steps labelled; out-of-fold parameters; no metric added to flatter a result.
