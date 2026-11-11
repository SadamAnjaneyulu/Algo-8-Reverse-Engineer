# Opportunity-panel design for Track A (for review — nothing here has been run)

This is the exact design proposed for Phase 2. **No panel has been built, no model trained and no outcome joined to a feature.** Event
counts come from the clean ledger ([`results/opportunity_counts.csv`](results/opportunity_counts.csv)).

## 1. Common rules

| Item | Rule |
|---|---|
| **Time unit** | Decision minute *m*. Features at *m* use bars completed before *m* (catalog §1). Outcome = the action is decided in minute *m* (`decision_minute`: order minute for body orders; minute containing the tag time for tagged orders). |
| **Event unit** | One event per (panel unit, decision minute). Several child orders in the same minute are one event; lots are kept as a quantity outcome. |
| **Eligibility** | A row exists only while the action is possible: session open, book active (after the first entry of the cycle, before the cycle stop or final flatten), and the relevant inventory non-empty. |
| **Baseline B0 (clock, calendar, inventory)** | `tod_min`, `dow`, `dte_days`, `tte_session_min`, day (D-1 / D0), underlying; seconds to the next schedule clock and to the next Clock-B tick; short lots per right, long lots per right, open contracts, lots sold today, minutes since the last entry and the last exit. No price. |
| **Baseline B1 (known mechanics)** | B0 plus the position-relative price state already established in PRs #3–#5: previous close ÷ lowest open entry price of the contract (or its maximum across the right / book), and cumulative cycle mark-to-market at previous closes. These use only OHLC and the ledger. |
| **Feature families added one at a time** | Momentum, mean reversion, volatility, market structure (index); option OHLC; option volume. Each is added alone to B0 and to B1. |
| **Why two baselines** | Stops are known to fire near 1.5× the entry price. Without B1, any option-premium feature would re-discover that and look like an "indicator". **A candidate trigger signature must add information over B1.** |
| **Splits** | Whole cycles, chronological: DEV 18 / VAL 8 / TEST 9 (same as PR #3). Thresholds and any tuning on DEV only. All three are previously inspected; none is confirmation. |
| **Matched no-action controls** | For every event row, up to 5 non-event rows from other sessions of the same underlying and split, same day type (D-1 / D0), `tod_min` within ± 10 minutes, same inventory tercile; and up to 5 from the same session at least 10 minutes from any event of that class. Event studies compare both. |
| **Methods** | Conditional event studies (feature path from *m* − 30 to *m*, events vs controls); logistic regression; depth ≤ 3 trees; family ablation; permutation tests; cycle-level bootstrap. No boosted model before these. |
| **Permutation nulls** | (i) Date derangement: features taken from a different session of the same underlying at the same time of day (keeps clock and inventory, breaks the market link). (ii) Within-session circular shift of the feature series by 20–120 minutes. |
| **Metrics** | PR-AUC and its gain over the baseline (ΔAP), precision, recall and lift at the DEV-chosen threshold, coverage, per-cycle stability. Accuracy is not reported. |
| **Multiple testing** | 6 families × 7 action classes × 2 baselines = 84 primary comparisons; Benjamini–Hochberg across them. Single-feature statements only for one representative per redundancy cluster. |
| **Minimum sample** | A class × split cell needs ≥ 30 event minutes and ≥ 5 cycles; otherwise it is reported as insufficient. |

**Evidence labels (fixed in advance).**

| Label | Requirement |
|---|---|
| CONFIRMED | Not attainable on this sample (no untouched data). |
| STRONG | ΔAP over **B1** with a 90 % cycle-bootstrap interval above 0 on VAL and on TEST; both permutation nulls p < 0.01 after FDR; same sign in both underlyings; an interpretable threshold reproduced by a depth ≤ 3 tree on VAL and TEST. |
| PARTIAL | ΔAP over B1 significant on DEV and on one of VAL / TEST, or over B0 only. |
| HYPOTHESIS | Event-study difference without out-of-split support. |
| UNKNOWN | None of the above. |

## 2. The seven panels

| # | Action class | Panel unit and eligibility | Outcome(s) | Events available |
|---|---|---|---|---|
| 1 | **Scheduled entries** | (cycle, session, schedule slot *k*, right); slot = 09:16 + 15 *k*; row at the slot's clock minute | D-1: the slot fires 544 / 544 times, so **only size is modelled** (lots sold vs the modal ladder: below / at / above). D0: slot fires or not, and size. | 13,354 body sells in total (scheduled + extra); 4,408 on D-1, 8,946 on D0 |
| 2 | **Extra entries** | (cycle, session, right, minute) outside every schedule window, book active | An off-grid body sale decided in *m*. Split in two: **(2a)** within 60 s after a same-right buy-back (replacement-type; PR #5 phase 3) and **(2b)** free extra entry (no buy-back in the prior 60 s). Only 2b is the "extra entry" target. | ≈ 52 % of short entry orders are off-grid (PR #5 phase 1) |
| 3 | **Individual buy-backs** | (open short contract, minute), D-1 and D0 separately | (3a) Stop-labelled buy-back of that contract in *m*. (3b) **Crossed-state panel**: only minutes where previous close ≥ 1.5× the lowest open entry; outcome = stopped in *m* or not. 3b targets the open question from PR #5: why most crossings are not acted on. A label-free version (any unscheduled buy-back) is run alongside because the stop label uses a 1.45× rule. | 3,245 orders, 895 decision minutes (DEV 1,920 / VAL 735 / TEST 590 orders) |
| 4 | **Side-level reductions** | (cycle, session, right, minute) with ≥ 2 open short contracts on that right | Start of a side-level reduction episode in *m*; later minutes of the same episode are excluded. | 803 orders, 281 decision minutes (DEV 481 / VAL 161 / TEST 161) |
| 5 | **Basket reductions** | (cycle, session, minute) with shorts open on both rights | Start of a basket reduction episode in *m*. | 1,529 orders, 418 decision minutes (DEV 1,063 / VAL 308 / TEST 158) |
| 6 | **Clock-B rebalances** | (cycle, D0 session, Clock-B tick at :14 / :29 / :44 / :59 from 09:29) | The tick acts (any Clock-B buy-back) or not. Contract choice is not re-modelled here (PR #3). | 682 rebalance + 414 no-replacement orders; 236 + 86 decision minutes; TEST has only 93 + 46 orders |
| 7 | **Hedge adjustments** | (7a) each body sale → wing bought within ± 10 s, and its strike distance; (7b) each reduction → wing released within 60 s; (7c) overnight lump (one per cycle) | 7a and 7b: yes / no and quantity. 7c: descriptive only. | 9,657 wing buys, 2,441 releases, 80 lump orders in 30 cycles (too few to model) |

## 3. Known weak points of this design

* **Small classes.** Clock-B and side-level reductions have about 90–160 TEST orders in 9 cycles. Intervals will be wide; a null result there is weak evidence of absence.
* **Label dependence.** Classes 3–6 come from the PR #3 taxonomy, which is itself rule-based. Label-free variants are included where possible.
* **Scheduled entries on D-1 have no variance in timing.** Only size can be studied.
* **Decisions in the 09:15 minute (3.3 % of orders)** have no same-day candle. They are kept with previous-session features only and reported separately.
* **Family, not formula.** Redundant features cannot be separated (catalog §4).
* **Not confirmation.** Every session has been inspected before.
