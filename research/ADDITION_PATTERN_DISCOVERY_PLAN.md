# Addition-pattern study: protocol and measurement corrections

This is a retrospective decision-pattern study, not a profitability backtest or
a claim to recover the original code. All times are IST. The chronological
evaluation period has already been inspected in earlier research; it is not a
blinded holdout. Full-sample clock exploration preceded model evaluation.

## Targets and clocks

Reconstruct parent orders from date/exchange/order identity, preserving partial
fills. A pure new-short parent must increase short inventory on every fill under
both same-second tie orderings; exclude mixed/tie-sensitive parents. Requested
quantity must reconcile with summed fills. Outputs expose source row references,
not broker order or client identifiers.

Use 21 quarter-hour opportunities per observed session, 09:30 through 14:30.
The primary target requires CE and PE new-short parents at the same strike whose
first fills occur in **[quarter − 2 seconds, quarter + 3 minutes)**. Pairing does
not require identical order-label minutes. Also retain a strict first-fill
window [quarter, quarter + 3 minutes), and the coarser order-label window
[quarter − 1 minute, quarter + 3 minutes). They are timing sensitivities, not
separate observations.

**Correction during research:** initial grouping by identical order-label minutes
missed CE/PE pairs across minute boundaries. Minute windows also missed afternoon
NIFTY executions at xx:xx:59 immediately before a quarter. Inspection of source
timestamps motivated the two-second tolerance. Preserve both older target
definitions in the opportunity output for audit. This is an observed execution
window, not an exporter-confirmed submission/signal time.

Separately reconstruct execution bursts by clustering parent first fills within
two seconds of the preceding first fill in the session, then pairing by strike.
Off-quarter bursts between 09:30 and 14:45 are descriptive cases. Multiple
strikes/bursts in a minute count once in matched comparisons. This does not
assign an original basket identity, or cover late protective buys.

Only sessions with recorded fills supply target labels. Sessions without fills
cannot distinguish inactivity from omitted data; list them rather than labeling
them negative. Report pre-expiry and expiry separately, keeping complete cycles
together in splits. This is conditional on the observed export, not a complete
universe of eligible trade/no-trade dates.

## Causal feature construction

For window start T, embargo all features at **T − 1 minute**. Use fills strictly
before that cutoff and bars whose start is at most **T − 2 minutes**, so their
close is already available. Target orders and target-minute prices cannot enter.

State features: reconstructed short/long quantities, time since an already known
paired sale, recent buybacks, cycle MTM/capital, its change and drawdown. Marks
come from the independent replay; missing marks stay missing.

Market features: completed spot returns/ranges over 1/5/15 minutes, distance from
the last sold strike, that straddle's premium changes, same-strike IV estimates
and changes. The option reference is an **already executed paired sale's strike**,
not the subsequently selected strike. Quote coverage still comes from the
retrospective traded-contract universe; it is not a historical full-chain feed.

## Models and evaluation

Calibration: expiries through 31 August. Evaluation: September–October. Estimate
a smoothed clock attendance table by index, phase and window. Enhanced models'
calibration clock probabilities use four-fold cross-fitting excluding complete
expiry cycles; evaluation probabilities use calibration counts only.

Comparisons: clock-only; clock multiplied by whether a short book is still open;
market-only (including index/phase/day-to-expiry metadata); clock+spot;
clock+market; clock+state; clock+state+market. Fixed depth-3 trees, at least 40
calibration rows per leaf, calibration-only median imputation plus missing flags.
No profit optimization. Tree probabilities use Laplace smoothing and back off
to a parent node if fewer than three cycles support the leaf. Exported raw tree
rules must be read with this backoff, not treated as the actual prediction rule.

Report precision, recall, F1, balanced accuracy when both classes exist, Brier
error and per-cycle metrics, including negatives and active-short-book subsets.
Bootstrap paired Brier differences by expiry ISO week, keeping both indices
together, with 10,000 draws. Compare market models with book-state controls as
well as clock-only. Small cluster counts and prior inspection limit inference.

## Secondary exploratory checks

These were added after the initial global-model results, not preregistered:

- NIFTY pre-expiry afternoon: compare nine single-feature depth-1 models against
  clock-only using leave-one-calibration-cycle-out prediction. Select on earlier
  cycles only, then report later-cycle results, including failures.
- Off-quarter cases: match other observed sessions on index, phase, clock,
  calibration/evaluation block and whether a short book is open. Take up to three
  nearest-date eligible controls from five candidates. Compare known spot moves,
  strike distance, leg premium change, recent covers and IV change. These are
  descriptive associations; one-minute embargo misses immediate re-entry events.
- Later sold strikes: compare with preceding completed cash-index and option-
  parity forward proxies. This descriptive diagnostic uses the minute preceding
  the first fill, separately from the longer prediction-feature embargo.

A repeated schedule is decoder progress. A predictive price association is a
trigger candidate. Neither alone establishes economic alpha; that requires
independent, risk-matched replay with faithfully specified sizing, hedges,
stops and execution costs.
