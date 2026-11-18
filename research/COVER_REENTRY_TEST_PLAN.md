# Cover-to-re-entry controlled study

Specification recorded before computing the matched results. This is a targeted
state-transition study, not another parameter bank or a causal identification claim.

## Primary question

Does a just-observed short cover improve prediction of a subsequent fresh
same-side short after timer phase, time, inventory, recent entries and market
state are accounted for? The previous parent counts estimate
P(recent cover | new short), not P(new short | cover).

## Landmarks, treatment and outcomes

- A landmark T is a side/session minute boundary. A cover during [T−1m,T) is
  known at T. Collapse the cover's child fills into that minute.
- Primary treatment: a cover minute with no same-side cover in [T−6m,T−1m).
  Controls: no same-side cover in [T−6m,T). Both require an observed active
  same-side short at T−1m and some short exposure still active at T.
- Common landmarks run 09:16–15:04 IST, permitting complete 1/5/10-minute
  future windows before the 15:15 cash-session transition. Full-flat reductions
  and other excluded covers are counted separately rather than negative labels.
- Primary outcome: any fresh same-side short-parent first fill in [T,T+5m).
  Sensitivities: horizons 1 and 10; off-timer first fills; opposite-side first
  fills; fills whose candidate order-label minute is >= T. Same-minute
  cover/entry bursts are described separately and a no-same-minute-entry
  treatment sensitivity is reported.
- Candidate timer windows are fixed at 09:16 and each quarter 09:30–14:30,
  T−2 seconds through T+3 minutes. They are descriptive known schedules, not
  inferred original order-submission times.
- A backward five-minute entry outcome is a diagnostic for trading bursts;
  it is not a future prediction target.

## Controls and matching

Primary matching is within the same underlying/expiry/session/right, so it also
holds configuration, calendar, index and CE/PE side fixed. Require the same
minute modulo 15, same nominal timer-in-next-five-minutes status, and at most
45 minutes' clock separation. Select one nearest control with replacement,
using outcomes neither for distance nor calipers. Record reused controls.

Use features known at T: log own/opposite short units, long units, same-side
equity/premium-loss state, signed book Delta, Vega, Gamma, ATM IV, adverse spot
returns, range and recent entry activity. Fit robust scaling on earlier rows
only. Require own zero/nonzero state agreement, own/opposite quantity ratios
within a factor two after +1 normalization, and mean scaled distance <= 1.

The primary distance uses remaining inventory at T, because the question is
incremental predictive information given the current book. A pre-cover T−1m
distance is a sensitivity. Conditioning on post-cover inventory can block a
mechanical exposure-replacement channel; neither design identifies causation.
Missing inputs retain indicators and are not treated as zero-valued observations.

Report unmatched treated landmarks, all/matched rates, balance and same-cycle
paired differences. Bootstrap by expiry week, preserving within-cycle pair
dependence. Matching is fixed during bootstrap; uncertainty in model selection,
matching, unobserved controls and old inspected data remains.

## Incremental prediction

Compare fixed regularized logistic models with versus without recent cover
features. Use group-separated earlier cross-validation, freeze earlier fits,
then report later loss, Brier and average precision. Base inputs already include
timer, side, current inventory, recent entries and market/risk state. No later
threshold optimization. A fixed 0.5 prediction threshold is descriptive only.
Both indices and pre-expiry/expiry phases are reported separately.

## Interpretation

Evidence of timing association is not proof that a cover causes re-entry.
An original 80–90% trigger requires high precision and broad event coverage;
retrospective conditional percentages or fitted effects do not satisfy that.
The strong-findings register receives a new rate finding only with an explicit
qualifying denominator, exclusions and scope.

## Balance-diagnostic amendment

After the primary matched results were inspected, NIFTY's later expiry matches
showed standardized differences above 0.25 in recent entry activity and range.
Add a clearly labeled stricter sensitivity: match recent-entry activity exactly
(new parent in the prior minute and prior five minutes, each zero/nonzero),
require each adverse-return/range/since-entry feature within 0.5 earlier IQR,
and mean distance <= 0.5. These choices respond to measured imbalance, not to
selection for a larger future-entry effect, and are not independent validation.
The no-same-minute-entry sensitivity applies that exclusion to controls too.
Also report whether opposite-side covers occurred in the treatment minute and
whether both rights receive a future entry; these are exploratory process checks.
