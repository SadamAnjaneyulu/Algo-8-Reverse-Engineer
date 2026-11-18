# Allocation, side-exit and cross-index tests

Continue the user-authorized reconstruction, with an 80–90% precision AND event
coverage goal. Record failures; do not turn a high historical fit into original
code or economic alpha. All prices and times are historical; no broker orders.

1. Export per-window new-short/new-long quantities, parent multiplicity, premium
   receipts/spending, and inventory. Use 09:16 and quarter windows separately
   for NIFTY/SENSEX and pre-expiry/expiry. Premium cashflow and underlying
   notional are not margin, capital allocation or loss budget.
2. Reconstruct observable contract-side short episodes and FIFO/LIFO short-lot
   attribution. Infer short/protection parent associations with ambiguity flags,
   not invented unique basket IDs. First reductions and subsequent covers are
   different targets. Keep exact fill-derived quantities separate from models.
3. Join prior completed-minute spot, premiums, Delta/Gamma/Vega/Theta and IV,
   option volume/OI and known prior inventory. Use actual-book state and export
   causal cutoffs. Zero SENSEX OI remains unavailable; traded-contract data do
   not constitute a full option-chain OI or max-pain history.
4. Test stop/profit/trailing/delta/spot and risk-state candidates on no-action
   opportunities too, with earlier-only parameter selection and later-cycle
   checks. Compare shared normalized rules with per-index rules and CE/PE rules.
   Check spot direction rather than assuming a CE cover means a falling index.
5. Add Greeks to range/entry candidates at the 27 suppressed active-book expiry
   windows and extra-entry opportunities. Compare clocks and active-book
   baselines. Report the complete false-signal/coverage tradeoff at 80/90% targets.
6. Evaluate any sufficiently specified matched controller after explicit costs
   and comparable risk. If it remains conditional on actual positions or lacks
   a verified sizing/margin controller, label economics as diagnostic, not a
   standalone replay or recovered alpha.

Calibrate through 31 August expiry; later dates have already been inspected,
so these checks are chronological research, not an untouched holdout. Inventory
attribution and hedge links need sensitivity checks. Source credentials are not
needed; use only the repository's trade and market data.

During the audit, reclassify the old 27 missing-pair windows: 12 contain both
rights at different strikes, six one-sided selling and nine no new short.
Retain the old pair target only as a named historical sensitivity. Add any-short
and both-right targets. Remove physical fills within two seconds of the next
quarter from the new off-schedule target; add one-right and different-strike
entries that the old paired target omitted. These corrections precede economic
interpretation and are not selected for higher model scores.
