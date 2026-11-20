# Search for the variable(s) behind solo (single-leg) sells — plan, written before any model is fitted

**Goal.** Find what else (beyond spot move, own-leg profit, other-leg loss) predicts the start of a solo CE/PE sale episode. Observational, in-sample; no trading rule is recommended.

**Event and panel.** As in the move test: right-minute panel (D-1 and D0 separately), event = episode start of a solo sale (single-leg sale with none on that right in the previous 5 minutes), risk set = other minutes (slot minutes and the 5 minutes after a start excluded). Features use data strictly before the minute.

**Baseline (known).** fav30 (30-min favourable spot move, %), own_ratio, other_ratio.

**Candidate library (fixed now, 6 families, ~35 features).**
1. *Spot dynamics:* fav5/15/60, fav_open, dd_ext, abs15, realised volatility over 30 min (rv30), rv30 ÷ day-so-far realised vol.
2. *Position / inventory:* shorts on own and other right, their difference, long wings per right, own-leg share of shorts, number of short strikes, spot distance from the book's strikes.
3. *P&L:* asymmetry (other_ratio − own_ratio), combined book loss %, short-book MTM in ₹ as % of ₹2 Cr (own, other, total).
4. *Greeks (Black–Scholes, IV implied from each contract's minute close, r = 6.5 %, no dividends):* net delta of the whole book (contract level, all modules) in lots and in ₹ notional % of ₹2 Cr, delta per short lot, signed so that + = the book is exposed in the direction a sale of this right would reduce (`delta_need`), own-leg and other-leg delta, net gamma, net vega.
5. *Volatility (VIX proxies, no VIX series in the repo):* ATM implied vol, its 15/30-minute changes and ratio to the day's first minute, ATM straddle price as % of spot and its 15/30-minute change.
6. *Time / activity:* minutes since open, minutes since the last slot, minutes since the last sale on own / other right, solo lots on own / other right in the last 30 min, scheduled (paired) lots in the last 30 min.

**Why delta is a primary hypothesis.** A short straddle/strangle seller who keeps the book roughly delta-neutral would sell calls when the book has become long delta (after a fall) and puts when it has become short delta (after a rise) — that reproduces "solo CE into falls, solo PE into rises", "other leg losing" and "own leg profitable" as side effects.

**Tests (all leave-one-cycle-out, LOCO).**
1. Univariate AUC with cluster bootstrap over cycles; Holm over the library.
2. Incremental value: logistic model on the baseline vs baseline + one candidate (or one family); LOCO AUC and log-loss gain; paired cycle bootstrap CI of the gain; a candidate "adds information" only if the CI excludes 0 **and** it beats the median gain of 200 permuted copies of itself.
3. Flexible model (gradient boosting if available) LOCO AUC with all families, then family-drop importance.
4. Mechanism check for delta: does an episode move the book's net delta toward zero? (before vs after, vs matched non-episode minutes); does the episode size scale with the delta to neutralise?

**Decision rule fixed now.** A variable is reported as "the missing variable" only if (a) it passes test 2, (b) the baseline + that variable matches or beats baseline + all other single candidates, and (c) the result holds on both rights and both underlyings. Otherwise the answer is "not identified" with the ranked evidence.

**Limits.** No VIX or tick data; IV from minute closes; the 5-minute episode definition and 0.15-style choices are analysis conventions; in-sample, 32 cycles on D-1 (33 on D0).
