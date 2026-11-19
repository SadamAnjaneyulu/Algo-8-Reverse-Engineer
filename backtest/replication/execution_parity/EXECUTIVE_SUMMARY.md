# Executive summary — Algo 8 execution behavioural parity

**Question (Rahul's direction):** is our reconstructed execution engine behaviourally close to the original? Not Sharpe, not Calmar, not drawdown; no alpha yet; the three historical years are not one regime.
**Decision (rule pre-registered in `EXECUTION_PARITY_METHODOLOGY.md` §9): NOT READY.** Several core components are MISMATCH. This is a research-readiness decision, not a claim about what Algo 8 "really" does. **Everything below is in-sample** (the rules were read from the 35 live cycles, which are not a holdout) and, after the independent review, a **revised, contaminated evaluation**; pre-review outputs are preserved.

## What was tested
Three modes against the original ledger (41,421 fills, 35 cycles): **Mode 3** accounting replay (all fills, four ownership conventions); **Mode 2** fully simulated (the engine generates its own events); **Mode 1** component-isolated (each rule evaluated on the actual book and market). 21 components scored with pre-fixed thresholds (all provisional) and a phase-preserving chance baseline; no single parity percentage. Historical mechanics were replayed on 274 eligible cycles, segmented by expiry-calendar structure.

## What matches (or nearly)
* **Hard criteria (not behaviour):** the new event-driven core equals the stored R1/R2 simulator event-by-event on 70 runs; accounting conserves under every ownership convention; no look-ahead found in the core. Two of these checks are tautological by construction (stated in the scorecard).
* **D-1 scheduled ladder: PARTIAL.** Entries in the 17 ladder slots: precision 89 %, recall 79 % (lift 1.9 over the schedule-only null); strike exact 79 % in those windows; quantity 69 % in-sample, 62 % leave-one-cycle-out.
* **15:14 final flatten: PARTIAL.** After 2026-08-03, 10 of 12 cycles close their whole short book in the 15:14 minute (1,213 of 1,529 lots overall); the pre-registered falsifier is not met. Two cycles in the first weeks after the stated cut-over do not.

## What does not match
* **D0 behaviour (the bulk of the order flow):** the engine produces **no** D0 body sells (the original has 12,686 lots) and reproduces **5 %** of D0 body buy-backs. **Inventory path: 5 % of contract-minutes exact**; the engine carries 35 % of the original overnight short book.
* **Strike over all body sells: 44.7 % exact** (79 % in the D-1 ladder windows, 30 % in other D-1 orders, 42 % on D0); **wing strike 32 %** (55 % within one step).
* **Per-lot stop** (32 cells): when the rule fires a buy-back follows (precision 63–74 % for the own-entry reference, 10–12× chance) but it explains only 7–17 % of body buy-backs.
* **Cycle stop:** with causal minute marks it is reproduced in 1/0/0 of 11 original stops (L = 1.30/1.35/1.44 lakh). With the close of the decision minute (non-causal diagnostic) the same thresholds find 10/9/8 of 11 with no false positive in 19 non-stop cycles, and 8 of 11 stops fire within 15 minutes of the D0 open: **mostly a data-resolution limit, not a wrong threshold** (hypothesis, in-sample).

## Unresolved (see `UNRESOLVED_EXECUTION_RULES.md`)
Lot ownership (89 % ambiguous), body-buy interpretation, wing association, passive lots at a stop, pre-log positions, parent-order linkage, the off-schedule and D0 entry triggers, flatten cut-over date, settlement price. **A basis disagreement matters:** at contract level 24 of 35 cycles end exactly flat and the rest hold long wings only (one D-1-only cycle holds shorts), while the role-routed lot engine reports shorts held to settlement. The "deep-OTM lots are carried to expiry" finding therefore depends on the unvalidated role-routing assumption (S18: UNRESOLVED).

## Historical mechanics by expiry structure (not parity)
NIFTY expiries moved Thursday → Tuesday on 2025-09-02; SENSEX Friday → Tuesday (2025-01) → Thursday (2025-09). The live ledger is NIFTY-Tuesday / SENSEX-Thursday. The engine's hard checks pass in all 274 eligible cycles, but price-quality assumptions (fills priced from a missing open, zero-volume fills, exits on untraded bars) and the size-dependent rupee cycle stop differ several-fold between structures (descriptive, small cells, no intervals). The engine's stop fires in 1 of 35 live cycles (R1; 12 of 35 actually stopped), so incidence figures describe a rupee threshold, not the original.

## Readiness
**NOT READY**: no behavioural component is a MATCH; D0 entries, D0 buy-backs, strike (all sells), wing strike, per-lot stop, causal cycle stop and inventory are MISMATCH. What can be reused now is a research **harness** (core, accounting, comparison engine, eligibility register), not a replica (`NEXT_PHASE_ALPHA_READINESS.md`). Whether alpha research can proceed on a D-1-only execution scope is Rahul's decision; it is not made here.

## Most important next data requirement
**Platform parent-order / basket ids plus sub-second timestamps.** They would settle whether D0 sales are scheduled, replacement or reduction actions, tie wings to bodies, make the stop events at the D0 open testable, and fix the unit of an "event". Full prioritised list with the question each answers: `NEXT_PHASE_ALPHA_READINESS.md` §5.

## Files
`PARITY_SCORECARD.md` · `EXECUTION_PARITY_METHODOLOGY.md` (pre-registered + addendum) · `UNRESOLVED_EXECUTION_RULES.md` · `DISCREPANCY_REGISTER.md` · `HISTORICAL_REGIME_ROBUSTNESS.md` · `INDEPENDENT_REVIEW.md` · `NEXT_PHASE_ALPHA_READINESS.md` · `reports/REPOSITORY_AUDIT.md` · `src/`, `tests/`, `outputs/` (reproduction in `README.md`).
