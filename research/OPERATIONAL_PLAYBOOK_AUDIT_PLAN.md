# Operational reconstruction specification

Continue from research commit 984164c and strong-register version 2. No new
indicator bank, economic strategy, broker request or parameter search is planned.

1. Independently recompute signed inventory, average cost, realized P&L and cash
   from validated incremental raw fills. Do not use the old ledger's update
   function. Reconcile each fill's independently inferred opening/closing amount
   and all cached session-minute quantities/P&L where available. Net simultaneous
   fills for event transitions; retain child-fill ordering and tie uncertainty.
2. Produce complete before/after contract books at every execution second,
   source-linked fill records, per-day/cycle summaries and final-role extinction
   sequences. Value both actual inventories at the same immediately preceding
   option candle, with missing/stale quotes and unavailable Greeks explicit.
   These are prior-quote estimates, not executable NAV or original basket IDs.
3. Recompute 09:17 ordinary opening inventories and all nominal quarter-window
   sizes directly from raw-flow roles. Describe full distributions and symmetry.
   Compare a clock-modal quantity baseline with replacement-only and previous-
   post-window target restoration. Fit modes only on expiries through July;
   August is a validation block and September/October a later inspected check.
4. Use only a small fixed market classification: prior-15-minute return down
   below −0.10%, flat within ±0.10%, up above +0.10%; close-path efficiency <=0.30
   choppy, >=0.70 directional, otherwise mixed; prior-15-minute range <=0.15%,
   0.15–0.35%, >0.35%. Opening comparisons use only the completed first candle,
   lagged prior-session trend and available gap. Never label an opening using
   the rest of its future session. Report groups separately by clock type,
   index, phase and independent sessions/cycles; no optimized thresholds.
5. Candidate pre-expiry no-entry dates are bounded to the preceding stored
   continuous-index session for each of the 35 logged expiries. Missing trade
   history cannot be labeled a rejected entry. This is not the complete exchange
   calendar or original eligible universe.
6. Report existing finite exit-controller validation with its precise target,
   precision/recall and scope. Check fixed supplied ₹200,000 capital-loss
   interpretations without fitting a replacement percentage. Original 4% carry
   denominator/reset/action remain unverified. Max quantities/payoff/Greeks are
   observations, not inferred configured caps or broker margin.
7. Work through NIFTY 29 June (ordinary opening/ladder), NIFTY 13 July (separate
   losing CE reductions), SENSEX 6 August (flat/re-entry) and SENSEX 8 October
   (late final liquidation). Chosen to illustrate distinct known operations,
   not representative economic profitability or independent validation.
8. Deliver root ALLOCATION_ENTRY_EXIT_RISK_PLAYBOOK.md with all 13 requested
   sections, the five required table types, state transitions, evidence counts,
   negative examples and the nine direct answers at beginning and end.

## Raw-sequence follow-up

Inspection of the specified 6 August liquidation example exposed same-contract
close/opposite-reopen/neutralize sequences. Audit this observable motif across
the logs: opposite reopening within ten seconds after an atomic close to zero,
then back to zero within sixty seconds. A conservative candidate subset also
requires the old sign to have existed for at least sixty seconds and opposite
size not to exceed the just-closed size. These are descriptive bounds chosen
after seeing that example, not independently validated original rules. Tag
fully covered parent sources without rewriting original inventory roles or
asserting that every motif is an execution error. Re-evaluate already-frozen
stop matches on the complement without refitting any stop parameters.
