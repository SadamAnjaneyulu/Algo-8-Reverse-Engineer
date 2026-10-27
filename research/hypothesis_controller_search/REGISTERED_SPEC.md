# Constrained controller search — registered specification

Registered before candidate evaluation, 27 October 2026. Source research:
58ae0cf; strong register v3 at 4e00077. No previous search outputs are overwritten.

## Scope and decision information

Reuse the audited playbook fill/event ledgers and reconciled accounting. Preserve
atomic seconds and child source IDs in the canonical evidence. Autonomous
controllers decide on a complete minute grid in the 65 received cycle-sessions,
using only the immediately preceding completed candle. They receive their own
simulated inventory, costs, cash, peaks, previous covers and pending instructions.
They never receive historical inventory or action labels as decision features.
Observed sessions/expiries are a conditional calendar, not inferred eligibility.
Three uncertain missing pre-expiry histories are separately reported, not negative
labels. Prices remain missing; no interpolation or synthetic contracts. The
stored contract universe was selected by historical trading and is a material
selection restriction. No rule uses future quotes to select a contract.

Execution: current minute open for zero-minute latency; next minute open for
one-minute latency sensitivity. These are hypothetical fills, not bid/ask.
Missing/nonpositive execution quotes leave requests unfilled. Prior zero-volume
bars are excluded from contract selection; current volume is only an ex-post
quality flag. Orders expire after their specified execution minute. Base requests
are fragmented into observed 65/20 units for costs; fills aggregate for scoring.
Main replay uses safe target-bounded closes; conditional duplicate-close mechanics
are a separate diagnostic, never a discovered autonomous allocation signal.

## Grammar and stages

Main Cartesian bank: 6 allocations x 12 exits x 3 entry gates x 4 wing policies
x 4 re-entry policies x 2 deadlines x 2 spot references = 13,824 unique definitions.

- Allocation: index/phase clock modes; pooled normalized clock modes; fixed one
  base; cumulative clock target restoration; replacement of own covers; clock
  with own exposure cap and IV scaling. All fitted quantities/caps use June–July
  expiries only. Opening seed is three base units unless the fitted clock mode
  supplies another value. Clock windows are the 17 established recurring slots
  plus 09:16. Expiry new allocations require own active short book, except a
  recorded-session-conditioned 09:16 initialization when no carry exists.
- Exits: deadline only; premium loss 30/50/75%; 90% profit; trail activated at
  50% profit with 20% entry-premium giveback; adverse spot 0.3/0.5%; own side
  equity loss Rs100,000; own full-cycle equity loss Rs200,000 on expiry; 4% of
  own preceding-session short debit on expiry; premium50 OR capital200k.
  Costs are pooled per contract; side/portfolio peak/reset scopes are explicit.
  The 4% interpretation is one hypothesis, not the supplied stop's verified meaning.
- Gates: none; lagged 15-minute range <=0.35% (first candle at opening);
  lagged path efficiency <=0.70 (first candle body/range at opening).
  Missing required gate inputs mean abstain, not invented benign state.
- Wings: initial distance then routine 2.5% premium budget; budget always;
  fixed distance always; seed/budget plus held-wing decay refresh below 25% cost
  after 15 minutes. SENSEX seed distance changes from 4,000 to 2,000 on 16 Sep,
  a previously inspected configuration prior. Each side's budget is independent.
- Re-entry: scheduled only; cover cooldown5 plus one-base same-side re-entry;
  cooldown15 plus re-entry; lock allocations after first whole short-book flat.
- Deadlines: 15:14; pre-3-Aug 15:27 and later 15:14. Short and remaining-wing
  closures are separate instructions; inability to fill remains explicit.
- References: last completed spot close or median of last three completed closes.

Stage1 labels the simple baseline slices; stage2 compares one-component changes;
stage3 evaluates the full fixed bank. Stage4 deterministically refines the four
best *fitting* configurations with a small declared neighborhood: allocation
scale 0.75/1.25; budget 2/3%; latency1; partial close fraction0.5; loss thresholds
+/-5 percentage points; side/portfolio thresholds x0.75/x1.25; late deadline
+/-1 minute. Semantically inactive changes are discarded; all definitions/hash
IDs, parent IDs and reasons are recorded. No later split chooses the neighborhood.

## Scoring fixed before search

Target: contract/minute/action aggregate, retaining four action roles separately.
Greedy chronological one-to-one matching per exact contract/action allows +/-2
minutes, with independent exact, +/-1 and +/-2 timing counts. A separate
one-grid strike-tolerance diagnostic is not exact matching. Zero-action minutes
remain in the inventory path and false predicted actions count as false positives.
Primary event component = macro F1 of new shorts, covers, wing buys and wing sells.
Quantity = 1 - sum absolute matched quantity errors plus unmatched quantities /
sum predicted and actual action quantities (bounded [0,1]). Inventory component
= 1 - sum contract L1 errors / sum predicted+actual gross quantities, over every
minute; role/net errors and unprotected-minute counts are separately reported.
Final closure component matches the observed final short-flat time within two
minutes, with unresolved residual targets not assigned fake closure times.
Score = .40 event macroF1 + .20 quantity + .30 inventory + .10 final closure
minus .002 per complexity point. Alternative weights:
event-heavy .60/.15/.15/.10; inventory-heavy .25/.15/.50/.10.
Complexity counts rule branches, non-default thresholds, index/phase-specific
schedules and state/reset logic. Economics never enters selection.

Fit expiries through31Jul; internal selection/validation Aug; already-inspected
later check Sep–Oct. Rank using Aug score, simpler on ties, report all splits.
Stage4 parents use fit scores only. Report expanding-origin top choices
(Jun->Jul, Jun-Jul->Aug), later frozen comparison, cycle bootstrap intervals,
NIFTY/SENSEX and pre-expiry/expiry separately. No split is called researcher-blind.
Require broad precision AND recall; high timing/size accuracy conditional on a
matched event is not overall reconstruction accuracy. Pareto comparison uses
raw reconstruction score versus complexity, no P&L selection.

## Robustness and identifiability

Top cohort includes baseline, best fit, best Aug, best alternative-weight choices,
component champions and simple Pareto representatives, not a chosen later winner.
Persist full predictions/mismatches/inventory and cycle economic diagnostics for
this cohort. Check 0/1/2-minute tolerance, latency1, strict positive-volume price
coverage, and cycle-level uncertainty. Selection-based equivalence groups use
prediction hashes; near-equivalence uses top-cohort action overlap. Show concrete
contradictions for top pair. Same decisions cannot establish the original code.

Gross/net P&L is a secondary, candle-execution diagnostic; unresolved active
positions are marked only with available final quotes. No invented settlement,
margin, capital allocation or screenshot return replication. Cost stress:
25bps premium turnover + Rs20/base-unit request + Rs0.05/transacted unit;
higher turnover stress50bps. Missing final marks remain missing.
