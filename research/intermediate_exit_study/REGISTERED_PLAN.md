# Intermediate exit study — fixed protocol

Registered at repository base `8e32701`, before constructing new exit features or
scoring these candidates. All dates were inspected in earlier research: this is
cycle-excluded internal validation, not a blind external test. Existing files,
counts, configurations and selected model 28 are immutable inputs.

## Units, outcomes and clocks

1. Preserve all 59 prior motifs and the exact 32 absent / 27 retained labels.
   Their prior quantities distinguish long protection from short exposure. First
   audit upstream entry, strike, target and allocation histories using only
   records before each original close. Do not reinterpret long sales as covers.
2. Retain every Buy child with positive canonical closing quantity. Aggregate
   within contract/second, then group successive short-cover atoms separated by
   at most 120 seconds unless an intervening short opening breaks the episode.
   A group is a reduction episode, not a certified decision. Keep atomic and
   source-child maps. First fill is the event timestamp; later quantity is outcome.
3. A final-liquidation atom is on expiry, at/after 15:00, after the last received
   new short on that right, with no short quantity left at the received end.
   This uses future records ONLY to define an outcome stratum. No final-status,
   episode membership, future flat/re-entry, fill price or closed size is a
   trigger feature. Any episode crossing strata is split. Other covers, including
   early full-side shutdowns and late nonterminal reductions, remain intermediate.
4. Feature cutoffs use all received fills STRICTLY BEFORE the observation second
   and the preceding completed minute candle only. No same-second child ordering
   informs trigger features. A current-minute close, future high/low or final
   parent total is prohibited. Market data must have availability <= cutoff.
   Peak measures use past sampled marks only; missing marks are not carried.
5. Main inference uses 32 pre-initialised cycles; the 3 expiry-only received starts
   remain in ledgers and a sensitivity table with unknown prior history. Entry
   lots and side cash are reconstructions, not original allocation ownership.

## Features and frozen hypotheses

Pooled live entry cost, FIFO/LIFO remaining-lot cost and loss range, active-epoch
entry history, exact pre-event position, age, time since latest same-contract and
same-side short addition, prior option change, adverse/favourable spot change,
side equity and past sampled peak drawdown. Equity includes both long and short
cash/marks of that right, gross of costs, denominator the supplied Rs20m reference.
Greeks use the inherited flat-ATM-IV approximation; availability and approximation
are explicit. Missing inputs abstain, never become zero or trigger a condition.

Exactly 12 fixed hypotheses, no parameter search or combinations beyond these:

| ID | Condition |
|---|---|
| premium_loss50 | preceding premium >= 1.5 * live pooled entry cost |
| premium_profit50 | preceding premium <= .5 * live pooled entry cost |
| trailing_rebound25 | premium >= 1.25 * past sampled minimum in active short epoch |
| side_loss1pct | side cash + marked positions <= -1% of reference capital |
| side_drawdown_halfpct | past sampled side equity peak minus current >= .5% capital |
| adverse_spot5_quarterpct | CE spot return5 >= .25%; PE return5 <= -.25% |
| favourable_spot5_quarterpct | CE return5 <= -.25%; PE return5 >= .25% |
| adverse_entry_halfpct | adverse move from remaining FIFO weighted entry spot >= .5% |
| abs_delta75 | inherited model absolute contract delta >= .75 |
| iv_rise1point5 | ATM IV rises >= 1 percentage point over preceding 5 minutes |
| protection_deficit | same-right long quantity < short quantity by >= one base unit |
| allocation_profit25 | same-right short added in preceding 120s AND premium <= .75 cost |

Baselines: (a) clock-only, top three five-minute bins by event/opportunity rate
in other training cycles, index/right/phase-specific with pooled fallback;
(b) current-inventory-only, threshold at training median event base quantity,
index/right/phase-specific with pooled fallback. Baseline parameters never use a
held-out cycle. Also describe frozen model-28 covers without changing its replay.
Each rule fires on first true observation, false-to-true transition or known new
same-contract short quantity; refractory 5 minutes per contract. Clock bins fire
at their first eligible observation, not every minute. Inputs are the received
inventory risk set, so this study is conditional trigger discrimination, not a
new autonomous strategy backtest. All later signals continue to use the received
inventory. This limitation is mandatory in conclusions.

## Controls and evaluation

- All active-short contract-minute observations form the scoring risk set, without
  future eligibility filters. Minutes are opportunities, NOT independent samples.
  Match signals one-to-one to same-contract episode starts within +/-120s; show
  +/-60s and +/-300s sensitivity. Timing tolerance permits earlier warning and
  delayed observed fills; it does not identify a submission timestamp. Report
  precision, recall, F1, false signals, missed episodes and feature coverage.
  Score final predictions/outcomes separately; also show predictions close to
  final events that count as false intermediate signals.
- Explanatory controls: fixed five-minute grid, active short, no cover atom within
  +/-120s. Up to 2 controls per intermediate case, no reuse; primary same contract,
  session and cycle, within 60 minutes, quantity ratio [.5,2], age bins <=15,
  15–60, >60m and same-side recent-allocation bins <=2, 2–10, >10m. Secondary
  fallback same session/cycle/right, other strike with relative moneyness within
  two strike grids; keep tiers separate. Outcomes exclude controls only for
  labeling; they cannot enter features. Both past and future control times are
  permitted; do not claim causal effects. Report unmatched cases, exclusion counts,
  reuse, time differences and paired feature contrasts; no minute-level p-values.
- Leave-one-whole-cycle-out: fit only the two baseline parameters and choose a
  candidate using mean training-cycle F1, then test excluded cycle. Show fixed
  hypotheses individually, index/right strata, cycle counts and cycle-bootstrap
  uncertainty. No random row split. No independent-order confidence intervals.
- Chronological check: expanding earlier-expiry cycles only, at least eight
  training cycles; exclude same-expiry cycles together. Rank/select using training
  cycles only. Also retain the previous June–July / August / Sep–Oct strata.
- A supported general trigger requires precision AND recall >=.8 in expanding
  validation, coverage >=.8, >=5 cycles, and improvement over both baselines across
  cycles. If none meets it, stop with a negative finding. Do not expand the bank.

## Deliverables

Case/atomic/child exit ledgers; upstream 32/27 audit; pre-event risk set and
feature manifest; control-selection audit and matched pairs; fixed hypothesis
catalogue; per-cycle chronological/LOCO predictions and scores; ranked hypotheses
with counterexamples and index/right diagnostics; concise report; reproducible
code, tests and immutable-input hashes. No prior result is replaced.
