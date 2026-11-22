# D0 (expiry day) — decoding plan

*Written before the tests. In-sample: D0 of 32 live cycles, 29,959 orders and 49,997 lots (3.7× D-1). Builds on `d0_reconstruction/` (timing structure found: Clock-B buy-back minute, grid-A sale windows, 15:14 clearance, −₹1.44 L cycle stop; triggers not recovered) and on everything decoded for D-1.*

## Phases
1. **Inventory.**
   * Lots by module and role and by hour; the carried book at the D0 open (from the real D-1 orders).
   * How much D0 activity acts on carried lots and how much on lots sold during D0.
   * The 15:14 clearance and the stop cycles.
2. **Do the D-1 mechanisms carry over?** Each is tested on D0 as decoded on D-1, with no refitting:
   * the hedge controller (long = short per right; wing strike at 2.5% of ATM);
   * the scheduled timetable (fixed minute waves across cycles of a version);
   * the reactive two-candle breakout;
   * the solo ladder at fresh extremes;
   * the buy-back stop on the lot's own premium (carried lots use their D-1 entry);
   * premium speed and breakout exits;
   * rebalancing (opposite-right counter-sells).
3. **Decode what does not carry over.** Same discipline as D-1: plans written before tests, out-of-fold parameters, nulls, post-hoc steps labelled.
4. **Reconstruction and accuracy.** A free-running D0 simulator started from the real carried book (and, as a chained variant, from the simulated D-1 book). Scored with lot-level F1 and AUC, out-of-fold and on unseen cycles, as for D-1.

## Evidence rules
Observed / Inferred / Unresolved / Not testable. No metric is added to flatter a result.
