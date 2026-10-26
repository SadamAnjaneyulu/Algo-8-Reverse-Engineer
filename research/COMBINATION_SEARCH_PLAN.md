# Combined-rule inverse search

The user explicitly authorizes trial-and-error and curve fitting to discover
programmed Algo 8 conditions. Perform the search; distinguish exact historical
reproduction from recovery of the original code and from economic alpha.
This continues the six remaining priorities in ALGO8_CURRENT_PICTURE.md.

## Search and timing

1. Extend the causal minute matrix with actual prior position/pooled-entry-cost
   state, trailing premium stress, order history and distance from prior entries.
   At physical minute T, use fills strictly before T and the completed T−1 bar.
   Quarter-window targets retain a one-minute embargo because they tolerate
   first fills one second before T. No current target quantity/strike is a feature.
2. Search AND/OR expressions up to three atoms using a deterministic beam over
   calibration-ranked atoms, then cooldowns, per-session signal limits, book
   eligibility and quantity caps. Add joint entry/exit lock variants. Retain
   negative opportunities, expression complexity and every search score.
3. Compare decision-tree combinations and deliberately flexible all-observed
   fits. The latter are explicit curve-fit diagnostics, not chronological tests.
4. Search composite exit programs: loss OR profit/trailing condition OR time,
   with multiple capital/P&L bases, profit activation, first/final closure labels,
   opening sensitivity and later-entry locks. First crossings use the actual book;
   this does not simulate counterfactual portfolio evolution after a wrong order.
5. Fit conditional hedge-budget programs with different leaf parameters by
   quote/market/position state. Compare constant-budget baselines and a per-event
   representability ceiling within the searched quote/selector universe.
6. Fit allocation quantity combinations against quarter-window CE/PE totals,
   using whole-cycle calibration CV. Distinguish order size from total exposure.
7. Fit retrospective change points in observed schedule/seed-wing configurations.
   A perfect date switch is descriptive, not a forecast or proof of software
   version history. Eligibility on unobserved no-trade dates remains unidentified.
8. Where quotes permit, examine fixed-horizon four-leg markouts after selected
   causal signals with explicit costs and tail-risk normalization. This is a
   conditional economic diagnostic, not an executable full-cycle clone or proof
   of independent alpha. Export quote exclusions and later-week uncertainty.

## Ranking and reporting

Calibrate through 31 August expiry; September–October are chronological checks,
already seen in earlier research. Some new grammars are informed by all observed
results. Select readable programs on calibration only; publish training and later
precision, recall, false signals, quantity/strike errors and per-cycle outcomes.
Give cycles equal influence where appropriate. Include time/book baselines.

Search a finite grammar, not every conceivable program. Count parameter/context
evaluations without describing them as independent experiments. Save full-sample
fits separately and never use their fit percentage as a replication result.
All market data, raw trade logs and previous result artifacts remain unchanged.

The short-term deliverable is a set of explicit candidate programs, their
matching/failing executions, and an updated account of which functions still
cannot be identified from this export and the incomplete traded-option chain.

## Completed extensions

After the initial combined results, extend the finite search with past-known
same-strike option OI/volume/PCR and budget × volume/OI eligibility. Treat zero
reported OI as missing (all SENSEX observations), and export reference timestamps.
Audit execution-minute versus inferred order-minute targets. Export full-history
trees as executable JSON with complete branch text; explicitly label them
historical resubstitution. These extensions follow inspection of initial results,
not a preregistered or independently blinded protocol.

Results and all six unresolved functions are reconciled in
[COMBINATION_SEARCH_FINDINGS.md](COMBINATION_SEARCH_FINDINGS.md).
