# D-1 long side (protective wings) — decoding plan

*Written before the tests. In-sample: D-1 of 32 live cycles. Builds on `BODY_HEDGE_MODULE_DEEP_INVESTIGATION.md`. That study found the hedge (`h_`) works as a balance controller (one decision buys the short − long gap S − L per right, about 4 s after the body fill; 93.7% of waves), with the strike priced at about 2.5% of the sold option (38% exact on minute closes) and releases weakly preferring the cheapest/outermost wing. Its D-1 findings are re-checked here, not assumed.*

## Scope: every D-1 long-side order
* `h_` open_long and close_long (the wings);
* body (`num`) open_long and close_long (seed wings at 09:15–09:17 and others);
* `v_` lumps (open_long, late D-1).

## Blocks
**L1. Inventory and lifecycle.** Lots by module, role and time of day. The contract-level book through the day: S and L per right, over all modules, starting flat at the D-1 open. How long L = S holds; L − S at the D-1 close and how it relates to `v_` lots. Wing premium and distance from spot (strike steps and σ units).

**L2. Wing strike rule** (new data: option one-minute open/high/low/close). The reference price is the body order's **fill price** (`px_avg`) or its limit-implied decision price. The candidate wing prices are the option's minute open of the decision minute, the close of the previous minute, and the minute's high/low range. Rules:
* (a) nearest premium to k × reference;
* (b) cheapest strike with premium ≥ k × reference (ceiling) or ≤ (floor);
* (c) delta target (Black–Scholes delta from the ATM straddle σ√T);
* (d) distance target in σ√T units;
* (e) fixed offset in steps from the sold strike or from ATM.

k, the delta target, z and the offset are chosen on alternating cycle halves. Scores: exact strike and within one strike, on simple wing buys (one trigger lot, one wing lot). Null: the reference shuffled within the same 30-minute slot.

**L3. Wing quantity.** Re-check S − L on D-1 at wave level, including multi-lot waves and waves that follow reactive/solo bursts.

**L4. Releases (D-1 wing sells).** When S falls (body buy-backs), which wing contract is sold. Candidates: outermost, cheapest, oldest/newest, the wing nearest to 2.5% of the bought-back short's price, the wing originally bought against that short (time-paired). Scored exact against chance (1 / number of strikes held).

**L5. Body-stream wings** (`num` open_long/close_long on D-1): timing (09:15–09:17 seed, 15:15), strikes, size, and their relation to the controller (are they counted in L?).

**L6. `v_` lumps on D-1:** timing (minute/second), right (heavier side?), size versus S, L and the day's move, strike rule, and whether the controller leaves the over-hedge in place.

**L7. Protection profile (descriptive):** for each right at each hour, the worst-case loss of the short-plus-wing book to a spot move, and how the wings cap it. Margin itself is not available.

## Evidence rules
Observed / Inferred / Unresolved / Not testable. Parameters are chosen out-of-fold, and post-hoc steps are labelled. Not testable: bid/ask, broker margin, sub-second body fills.
