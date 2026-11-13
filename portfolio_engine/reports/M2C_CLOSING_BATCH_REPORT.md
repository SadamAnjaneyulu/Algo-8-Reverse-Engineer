# M2-C closing-batch report (Model C: C1 first-fill chaining, C2 last-to-first chaining)

Branch `engineering/position-lifecycle-basket-reconstruction`; implementation commit `9b6a496e` (starting head `a4de4f22`). Mode `HISTORICAL_OBSERVED_REPLAY`; source `Trades_GKOHNP140.csv` sha256 `86e65ab6…f528` → TP-01 ledger sha256 `3b47c55150d79535…`.
**A closing batch is an analytical grouping of closing parent orders that executed close together. It is not an opening basket, not evidence of one decision, and "larger" is not "better". Group counts below are descriptive only.**

| Item | Status |
|---|---|
| C1 first-fill chaining (10 s primary; 2, 5, 30, 60 s) | **Executed — PASS** (see §6 for the independent review) |
| C2 last-to-first chaining (same thresholds) | **Executed — PASS** (identical to C1 on this data; reason in §3) |
| Number-block variant | **Audited, `UNRESOLVED — REVIEW REQUIRED`; NOT implemented** (`M2C_NUMBER_BLOCK_AUDIT.md`) |
| Reporting-unit audit | Executed (`M2C_UNIT_AUDIT.md`) |

## 1. Definitions as implemented (approved D2; whole-second timestamps; `gap <= threshold`, inclusive)
* **Unit:** parent order, represented by its **closing portions** (observed layer; convention-independent). 16,817 closing parents, 17,760 closing portions, 1,377,065 closing units; **26 mixed parents are in scope with their closing portions only** (7,620 closing units of their 14,105 total fill units; the opening part never contributes to a timestamp).
* **Streams:** same underlying, same expiry, same trading session (IST date). CE/PE, long/short, body/wing are descriptive attributes only.
* **Order:** `(first closing-fill second, smallest closing source_row_id, parent_order_id)`; single linkage over **adjacent** parents in that order.
* **C1:** link when `first(next) − first(previous) ≤ g`. **C2:** link when `first(next) − last(previous) ≤ g` (previous = the immediately preceding parent in the C1 order; a parent whose interval started earlier but ended later than the previous parent's is not consulted — a literal reading of the approved rule). Overlap flags: `interval_overlap` (closed intervals share a point, including same-second ties) and `strict_overlap` (`first(next) < last(previous)`).
* **IDs:** `INF:CLOSING_BATCH@CB_FIRST_FILL_GAP_10S:<UND>:<EXPIRY>:<SESSION>:<NNN>` and `…@CB_LAST_TO_FIRST_GAP_10S:…`; each threshold has its own token; membership rows carry `grouping_version CB1` and a `parameter_hash`.
* **Missing / duplicate metadata:** a closing portion without a parent id is reported as unattributable and never pooled (0 in the real data); a parent id reused across sessions is two members and listed (0 in the real data).

## 2. Results (C1; C2 identical — §3)
| g (s) | batches | singleton batches | parents / batch median · p99 · max | duration (s) median · p99 · **max** | max duration ÷ g | adjacent pairs linked | pairs with gap = g | pairs with gap = g+1 s |
|---:|---:|---:|---|---|---:|---:|---:|---:|
| 2 | 7,127 | 3,893 | 1 · 14 · 78 | 0 · 5 · 57 | 28.5 | 9,690 | 661 | 1,633 |
| 5 | 3,777 | 690 | 2 · 30 · 96 | 3 · 23 · 66 | 13.2 | 13,040 | 441 | 233 |
| **10 (primary)** | **3,065** | 336 | 3 · 38 · 122 | 4 · 49 · 125 | 12.5 | 13,752 | 79 | 59 |
| 30 | 2,171 | 159 | 4 · 75 · 128 | 4 · 161 · 481 | 16.0 | 14,646 | 25 | 29 |
| 60 | 1,502 | 77 | 5 · 112 · 198 | 6 · 435 · **1,175** | 19.6 | 15,315 | 33 | 19 |
(16,752 adjacent pairs = 16,817 parents − 65 streams.) Every view represents all 16,817 parents and 17,760 closing portions (1,377,065 units) exactly once; "unbatched" parents = singleton batches (above). **Chaining effect made visible:** the longest batch lasts up to 28.5× its threshold (e.g. 1,175 s at 60 s), and 66 % of parents (11,139) share their first-fill second with another parent (3,438 equal-timestamp groups), so many "batches" are simultaneous executions. **Timestamp precision:** at 2 s, 661 adjacent pairs sit exactly at the threshold and 1,633 one second beyond it — a one-second change in resolution would change many memberships; at 10 s only 79 / 59.
**Stability across thresholds:** views are nested (each smaller-threshold batch lies inside one larger-threshold batch). Identical batches between consecutive thresholds: 2→5 s 1,307 of 7,127; 5→10 s 2,527 of 3,777; 10→30 s 1,709 of 3,065; 30→60 s 1,110 of 2,171. Outputs: `reports/m2c_data/` (gzip TSV: batches, member parent orders, member closing portions; per method; `manifest.json` with content hashes; deterministic across reruns), `m2c_summary.json`.

## 3. C1 vs C2
C2 links ⊇ C1 links by construction (`last ≥ first`). **On this data C2 adds no link at any threshold** (links only in C2 = 0; identical batches 100 %): of 16,817 closing parents only **1** has `last > first` (a 57-second spread); every other parent's closing fills share one second. `interval_overlap` is flagged on 7,701 links but is dominated by same-second ties; `strict_overlap` occurs on 1 link per view. C2 therefore does not materially change membership here; it remains a valid sensitivity for data with spread-out partial fills.

## 4. Invariants proved (executed on all 10 real views and on synthetic counterexamples)
Each eligible parent in at most one batch per view; each closing portion exactly once per view; batched + unattributable = all portions; no opening-only parent; mixed parents contribute closing portions only (7,620 < 14,105 units); Σ closing quantity = 1,377,065 per view; the observed-layer hash is unchanged by building the views; batches read only the observed layer so FIFO/LIFO/AVG cannot enter; ids unique across all 10 views; nesting properties hold; outputs reproduce byte-identically (`test_real_outputs_reproduce_the_committed_manifest`).

## 5. Tests
`python3 -m pytest portfolio_engine/tests/test_closing_batches.py -q` → 20 passed (17 synthetic counterexample tests + 3 real-ledger slow tests). Counterexamples: identical timestamps, input-order independence, multi-fill parent, mixed parent (opening execution must not join a batch), different contracts, CE+PE, overlap (C2 joins what C1 does not), long gap then cluster, transitive chain, inclusive boundary, equal-timestamp tie order, C2 tie dependence, session / expiry / underlying boundaries (23:59:59 vs 00:00:01 IST), missing parent id, parent id reused across sessions, opening-only/duplicated member rejection, observed-ledger immutability, view independence. **Three tests failed during development because of mistakes in my test construction (an expected 2-second boundary, a wrong IST-midnight offset, a builder that replaced the empty parent id); the engine was correct in all three; the tests were corrected and are kept.**

## 6. Independent review
REVIEWER_SECTION_PENDING

## 7. Evidence classification
CONFIRMED_OBSERVATION: closing portions, their parents and timestamps, and the temporal clustering at each threshold. UNRESOLVED: whether any batch corresponds to one algorithm decision; the 10 s threshold is registered for analysis, not a recovered rule. NOT_TESTABLE: original basket identifiers, batch trigger conditions. Not claimed: any link between batch structure and profitability, intent, or the opening basket.

## 8. Remaining uncertainty
Whole-second timestamps; the exit trigger and whether batches are one decision (needs decision logs); the number-block semantics (`M2C_NUMBER_BLOCK_AUDIT.md`); C2's single-previous-parent rule (a literal reading, flagged); the chaining effect at larger thresholds.
