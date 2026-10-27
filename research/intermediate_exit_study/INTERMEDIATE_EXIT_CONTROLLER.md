# Algo 8 — intermediate exit controller

**No tested trigger has adequate out-of-cycle evidence for an 80–90% general
exit rule.** Twelve fixed hypotheses were tested, with no expansion of the bank.
The best chronological average-cycle F1 comes from a sampled side-drawdown rule;
its pooled precision is **18.0%**, recall **16.6%**. A 50% premium-loss rule reaches
**36.4% precision, 9.8% recall**. Relative discrimination improves over the simple
baselines, but most exits remain unexplained.

## The original 32 absent and 27 retained cases

The original 59 motifs include **long protection as well as short exposure**.
The absent group has **9 short covers / 23 long closures**; the retained group has
**7 short covers / 20 long closures**. Long-wing sales are not short stops.

The upstream audit of the 32 absent cases finds:

| observed_role | upstream_class | cases |
| --- | --- | --- |
| long_protection | initialization_unobserved | 1 |
| long_protection | no_same_role_allocation_near_entry | 11 |
| long_protection | other_strike_near_recorded_entry | 8 |
| long_protection | same_contract_previously_held_but_already_reduced | 3 |
| short_exposure | no_same_role_allocation_near_entry | 2 |
| short_exposure | other_strike_near_recorded_entry | 2 |
| short_exposure | same_contract_previously_held_but_already_reduced | 5 |

In total, ten have another strike near the actual active epoch's first entry;
13 have no comparable allocation near that entry; eight previously held the same
role but reduced it earlier; one lacks initialization. “Near” means +/-120 seconds,
clipped before the exit. It does not establish unique allocation ownership or
absence at every other time. All eight earlier reductions include the candidate's
risk reason bit, sometimes alongside an allocation change; that is its simulated
reason, not an explanation of the original strategy.

Of the 27 retained cases, 26 retain the same direction; **M06 instead holds a short
where the log closes a long**. For the seven actual short covers, pre-close values
are below. Percentages use pooled live entry cost and the supplied Rs20m capital
reference; adverse spot sign is positive for rising CE / falling PE spot risk.

| motif_id | index | right | premium_loss_pct | side_drawdown_pct | adverse_spot5_pct |
| --- | --- | --- | --- | --- | --- |
| M12 | NIFTY | PE | — | — | — |
| M13 | NIFTY | PE | — | — | — |
| M15 | NIFTY | PE | — | — | — |
| M32 | SENSEX | PE | -89.536 | 0.173 | -0.066 |
| M33 | SENSEX | PE | -71.598 | 0.173 | -0.066 |
| M43 | SENSEX | CE | 33.614 | 0.980 | 0.094 |
| M44 | SENSEX | PE | -61.757 | 0.229 | -0.094 |

M12, M13 and M15 close during **09:15**, before the first completed session candle;
their market features remain missing. Also, a terminal close can follow earlier
partial reductions: [episode links](short_motif_episode_links.csv) distinguish those
times. [All 59 upstream cases](upstream_32_27_audit.csv), [entry source histories](motif_active_entry_history.csv)
and [all 27 condition checks](motif_27_pre_event_condition_audit.csv) retain the exceptions.

## Cases, information boundary and controls

**11,716 closing Buy children → 8,197 contract/second atoms → 4,251 reduction
episodes.** Covers within 120 seconds are grouped unless a new short opening,
date change or outcome-stratum change intervenes. An episode is an observable
batch, not a certified original decision. Every source fill/quantity is retained.

The 32 known-initialization cycles contain **3,512 intermediate episodes and 326
final-liquidation episodes**. Three expiry-only starts contribute another 366
intermediate / 47 final episodes, retained as a sensitivity cohort. Two episode
starts have no short in the strict pre-second book because exposure is created
within that second; those cases remain observable limitations.

Features use fills **strictly before the event second** and only the preceding
completed candle. Same-second fills, exit price, later closed size, future re-entry
and parent lifetime totals are excluded. The ledger includes live quantity/cost,
FIFO/LIFO remaining entry histories, option movement, underlying movement, age,
recent allocation, side P&L and sampled peak drawdown. Missing live marks make
side P&L unavailable. Greeks are the inherited flat-ATM-IV approximation, not
broker Greeks; sampled drawdowns are not tick high-water marks. Costs are excluded
from marked P&L. Full-chain eligibility and original allocation ownership are unknown.
Availability means nominal candle completion; actual feed latency and the export
seconds' exchange-time semantics are not independently certified.

The fixed five-minute control pool has **41,934** observations;
**3,244** are excluded for a cover within +/-120s.
Matching yields **4,982 unique controls for 2,655/3,878 intermediate cases**.
These control descriptives retain all 35 received cycles; predictive validation
below uses only the 32 cycles with known initialization.
Primary controls use the same contract/session/cycle/right, quantity ratio .5–2,
entry-age/recent-allocation bins and <=60-minute distance. Secondary other-strike
controls are explicitly separate. No control is reused; unmatched cases remain
in scoring. Future proximity labels controls only and never enters a trigger.

Same-contract descriptive condition rates, among available observations:

| hypothesis | case_rate_pct | control_rate_pct |
| --- | --- | --- |
| premium_loss50 | 12.782 | 6.924 |
| side_drawdown_halfpct | 51.519 | 42.648 |
| iv_rise1point5 | 19.651 | 10.758 |

These comparisons are not causal estimates. [Control-selection audit](control_selection_audit.csv),
[all pairs](matched_nonexit_controls.csv) and [feature contrasts](matched_feature_contrasts.csv)
show missingness, unmatched cases and support. Minutes/orders are not independent
inferential samples; uncertainty uses whole cycles.

## Registered trigger tests and chronological results

Rules fire on activation or a known new same-contract short addition, with a
five-minute refractory period. Persistent thresholds do not fire every minute;
missing inputs abstain. Precision uses the **full active-short scoring risk set**,
not the matched-control sample. Signals match the same contract's first reduction
one-to-one within **+/-120 seconds**. This allows early warning/execution delay;
it does not identify a submission timestamp.

The table covers **24 chronological test cycles / 2,200 intermediate episodes**.
Each fold uses at least eight strictly earlier-expiry cycles. Clock-only baselines
fit three five-minute bins; inventory-only baselines fit a median event-size
threshold, by index/right/phase with pooled fallback. All twelve trigger levels
remain fixed. `training_selected` chooses by training-cycle mean F1 only.

All percentages below are pooled except `macro_cycle_f1`, which weights cycles
equally. Coverage is feature availability, not matching accuracy.

| hypothesis | precision | recall | macro_cycle_f1 | false_positives | missed_exits | event_feature_coverage |
| --- | --- | --- | --- | --- | --- | --- |
| side_drawdown_halfpct | 18.047 | 16.636 | 18.767 | 1662 | 1834 | 94.318 |
| iv_rise1point5 | 19.830 | 18 | 16.670 | 1601 | 1804 | 90.682 |
| training_selected | 18.394 | 15.727 | 16.436 | 1535 | 1854 | 92.182 |
| premium_loss50 | 36.364 | 9.818 | 15.707 | 378 | 1984 | 94.727 |
| trailing_rebound25 | 10.561 | 19.500 | 13.072 | 3633 | 1771 | 94.727 |
| inventory_only | 11.310 | 10.909 | 10.262 | 1882 | 1960 | 100 |
| allocation_profit25 | 7.547 | 17.591 | 9.452 | 4741 | 1813 | 94.727 |
| protection_deficit | 8.687 | 11.636 | 9.180 | 2691 | 1944 | 100 |
| clock_only | 13.641 | 6.727 | 8.695 | 937 | 2052 | 100 |
| abs_delta75 | 22.047 | 5.091 | 6.713 | 396 | 2088 | 93.500 |
| premium_profit50 | 10.562 | 4.273 | 5.457 | 796 | 2106 | 94.727 |
| adverse_spot5_quarterpct | 38.519 | 2.364 | 3.393 | 83 | 2148 | 89.364 |
| side_loss1pct | 14.314 | 3.318 | 3.348 | 437 | 2127 | 94.318 |
| adverse_entry_halfpct | 19.792 | 1.727 | 2.664 | 154 | 2162 | 78.727 |
| favourable_spot5_quarterpct | 7.353 | 0.455 | 0.707 | 126 | 2190 | 89.364 |

Side drawdown's average-cycle F1 advantage is **10.1 percentage points over clock**
(whole-cycle bootstrap 95% interval **5.0–14.8**) and **8.5 points over inventory**
(**3.4–14.4**). This supports limited relative discrimination, not identification
of the original stop. Absolute precision/recall remain low. Shared calendar shocks
and prior inspection of every date limit this internal validation.

[All chronological/LOCO cycle scores](cycle_validation_scores.csv),
[train/test cycle lists](validation_folds.csv), [ranked hypotheses](ranked_trigger_hypotheses.csv),
[baseline parameters](baseline_fold_parameters.csv), [cycle bootstrap comparisons](cycle_bootstrap_comparisons.csv)
and [timing sensitivity at +/-60/120/300s](ranked_trigger_hypotheses.csv).
LOCO excludes whole cycles but may train on later dates; it is separate from the
chronological check. Every fixed candidate is retained, including failures.

Index/right results for the leading fixed rule and training-selected pipeline:

| hypothesis | underlying | option_type | cycles_with_observed_exits | precision_pct | recall_pct |
| --- | --- | --- | --- | --- | --- |
| side_drawdown_halfpct | NIFTY | CE | 11 | 19.077 | 18.129 |
| side_drawdown_halfpct | NIFTY | PE | 11 | 25.292 | 16.169 |
| side_drawdown_halfpct | SENSEX | CE | 13 | 16.706 | 18.858 |
| side_drawdown_halfpct | SENSEX | PE | 13 | 16.275 | 13.798 |
| training_selected | NIFTY | CE | 11 | 24.074 | 15.205 |
| training_selected | NIFTY | PE | 11 | 25.126 | 12.438 |
| training_selected | SENSEX | CE | 13 | 14.976 | 16.866 |
| training_selected | SENSEX | PE | 13 | 18.932 | 16.643 |

[Phase-specific results](index_side_phase_scores.csv) and
[all feature coverage/condition frequencies](feature_coverage_by_cycle.csv) retain
weak subgroups. No index/right subgroup justifies a shared or distinct recovered
exit rule. A condition can remain true long before an exit; condition-at-exit
frequency must not be mistaken for timed trigger matching.

## Final liquidation and baseline preservation

Final liquidation is labeled only on expiry at/after 15:00, after the right's last
received new short, with no shorts left at the received end. Future records define
this **outcome only**. Early shutdowns and late nonterminal reductions remain
intermediate. The independent dated deadline diagnostic produces **101/326**
final matches from **116** signals, with 15 false signals
and 225 missed finals. [Separate final scores](separate_final_liquidation_scores.csv).
Risk signals near final outcomes still count against intermediate precision:
[overlap audit](final_overlap_false_intermediate_signals.csv).

The unchanged model 28 has **188** intermediate matches from
**497** own-inventory cover episodes, against **3512** observed
intermediate episodes. [Comparator scores](unchanged_model28_exit_scores.csv).
This study uses actual inventory; comparing its metrics to autonomous model 28
cannot establish an improved autonomous controller. No prior configuration,
findings, counts or result files are replaced.

## Supported observations and remaining uncertainty

Supported: upstream strike, allocation and earlier-risk-action divergences explain
candidate absence in identifiable subsets. Long closures differ from short covers.
Premium stress, IV change and sampled drawdown distinguish some exits from controls,
but similar states also persist without closure. [Every false signal and missed
exit](trigger_counterexamples.csv.gz) and [representative counterexamples](representative_counterexamples.csv)
are preserved.

**None meets the registered requirement of >=80% precision AND recall, >=80%
feature coverage and >=5 chronological cycles.** There is no recovered general
exit controller or demonstrated economic alpha. The finite study stops here.
Unresolved explanations include allocation/side ownership and stop resets,
portfolio targets/limits, instantaneous quotes/Greeks and pending decisions.
Original decision/submission/cancellation records remain absent.

[Case ledger](exit_case_ledger.csv.gz), [atomic covers](short_cover_atoms.csv.gz),
[source children](short_cover_children.csv.gz), [pre-event risk set](pre_event_risk_set.csv.gz),
[registered protocol](REGISTERED_PLAN.md), [measurement notes](MEASUREMENT_NOTES.md),
[reproduction instructions](README.md), [input hashes](input_manifest.json) and
[validation audit](validation_audit.json). Software tests validate accounting and
information boundaries, not original-strategy truth.
