# Final dependency audit before Stage 2

PR #8, after `420943c4`. Nothing in PR #3, PR #5 or earlier outputs is modified, existing register rows are unchanged, and
Stage 2 has not started. Every number is from executed code in [`final_audit/`](final_audit/).

## 1. Decision report: what Stage 2 may use

| Status | Components |
|---|---|
| **Safe as inputs** | Raw fills and the column-163 order table · market grids · the **session-aware lot ledger** (`rr_common.ledger`) · exit taxonomy and closing-order ledger · D-1 per-lot stop evidence (EXT-02 to EXT-04, EXT-06) · side / basket / Clock-B selection (MGT-03 to MGT-06) · allocation ids (slot, chain), entry prices and exit ownership by convention · PR #5 closure-granularity, contract-choice and wing-coupling tests (identical after correction) · replacement / re-entry links and the non-identifiability of ownership (identical) · the stop-reference verdict "UNKNOWN, 0 of 18 rules at 80 / 80" · the cycle stop as a band on cumulative MTM (−₹1.38 to −1.43 L) · the client-rule verdicts (RSK-07, RSK-08) · the 1DTE / 0DTE comparison · the OHLCV feature library |
| **Safe as conclusions, provisional as numbers** | D0 carried-position cells (small samples; one cell falls below the 30-event threshold) · exit-model conclusions (no model at 80 / 80) with the carried-exit and profit-taking values superseded · replay match rates (replay P&L sums are fragile) |
| **Provisional** | PR #3's cached `exit_lots_*`, `exit_cm`, `exit_bm` (carried / entry-day / `n_carried` fields) until rebuilt with the corrected mapping · the PR #5 `carried` columns · Stage 1 segment counts in `algo8_skeleton` (superseded values in [`stage1_segment_counts_old_vs_corrected.csv`](final_audit/results/stage1_segment_counts_old_vs_corrected.csv)) · the exact stop constant · the mechanism behind the stop-module overshoot · **ML-07 robustness (unreconciled, open)** |

Full list with evidence: [`dependency_impact_register.csv`](dependency_impact_register.csv) (26 components).

## 2. Task 1: PR #5 on the corrected ledger

**Method.** `analysis/allocation/` was copied into the two sandboxes of the previous audit and its seven scripts run in each:
*corrected* (PR #3 code with only `minute_index` session-aware) and *control* (unchanged). **The control reproduces all 35
committed PR #5 files exactly**, so every difference is the correction. PR #5's files are untouched.
Cell-level comparison: [`pr5_corrected_ledger_comparison.csv`](pr5_corrected_ledger_comparison.csv) (14,356 changed cells in metric tables, plus one summary row per row-level ledger);
file summary: [`final_audit/results/pr5_file_summary.csv`](final_audit/results/pr5_file_summary.csv).

**What depends on the session mapping:** only (a) the `carried` flag of a lot, (b) whether a contract-minute or event is
counted as D-1 or D0. Allocation ids, entry prices and which lot a buyback closes do **not** depend on it.

| PR #5 result (register) | Depends on | Old → corrected | Verdict |
|---|---|---|---|
| Allocation ids, entry prices, exit ownership (ALC-01) | nothing | identical; only `carried` changes (945 lots; `carried_lots` in 16 slot and 15 chain allocations) | **stable** |
| Closure granularity T1, contract choice T2 and its bootstrap, wing coupling T4 (ALC-02, ALC-06) | nothing | **identical** (lot-level 0.560 vs contract average 0.493 at hit@1) | **stable** |
| Reference sharpness T3 | D-1 / D0 minute | AP ± 0.003; events ± 2 | **stable** |
| Stop reference and constant (ALC-03) | segments | 0 of 18 rules at 80 / 80 (unchanged); DEV-selected k unchanged in all 108 global and 324 per-segment cells; oracle ceiling 0.52 (0.66 association-only) unchanged; precision ≤ ± 0.026, recall ≤ ± 0.127, both maxima in D0-carried cells | **stable: UNKNOWN retained** |
| … FIFO, D0 carried, TEST cell | segments | 32 → 29 stop buybacks: below the 30-event assessability threshold (assessable cells 6 → 5) | **becomes inconclusive** |
| Exit-ratio quantiles (ALC-04: ≈ 95 % of stop buybacks at ≥ 1.5× the lowest entry) | segments | 5th percentile moves ≤ 0.008 (D-1 fresh), ≤ 0.002 (D0 fresh), ≤ 0.005 (D0 mixed); up to 0.047 in D0-carried TEST cells | **stable**; D0-carried cells provisional |
| Allocation-average discriminator (ALC-05) | day split | exit-level table identical; matched-hazard δ ± 0.003; no verdict label changes | **stable** (still not separable) |
| Stop lag | segments | shares ± 0.002 | **stable** |
| Replacement / re-entry links, association null, variant stability, ownership pairs, lifecycle ledger (ALC-07, ALC-08) | nothing (order-date based) | **identical**, except `sale_atm_steps` in 6 of 4,654 links | **stable** (ownership identified for 3.5 % of pairs) |

No PR #5 conclusion changes. The only finding that weakens is the FIFO D0-carried TEST cell.

## 3. Task 2: the stop module and the normal logic

Timelines: [`stop_controller_order_timelines.csv`](stop_controller_order_timelines.csv) (1,757 fills of 1,303 orders: from 2 min before
each stop decision to the end of that session, with module, order number, number block, order-entry minute, tag decision
time, submission class and its evidence, and fill-time position roles). Inventory after every fill:
[`stop_inventory_transitions.csv`](stop_inventory_transitions.csv) (short and long lots by right, contracts, flat flag).

**Evidence levels** (the export has no submission timestamps):

| Level | Rule | Orders in the timelines |
|---|---|---:|
| Proven before | first fill in an earlier second than the decision | 450 |
| Proven after | order number above the first `s_` order **of the same number block** | 214 |
| Proven by tag | `h_` / `v_` decision time after the decision (40) or before it with a later fill (20, in flight) | 60 |
| Bounded | number below the first `s_` order of its block, filled after the decision: before the stop module's first submission, not provably before the decision instant | 151 |
| Inferred | block without `s_`: order-entry minute only | 6 |
| Undetermined | same minute and no `s_` in the block (4); fill in the decision second (1) | 5 |
| Stop module | `s_` tag | 417 |

Fills are stamped to the second and decisions to the microsecond, so a fill in the decision second cannot be ordered against
the decision. "Position at the decision" below means the position before the decision second.

| Stop (expiry, und, decision) | Short / long lots before the decision second | s_ orders (first to last fill, s) | Other-module orders after the decision: proven after / in flight / undetermined | s_ overshoot lots (sell + buy) | Other-module short-opening lots: new contracts / wings | First flat (s) | Final flat (s) |
|---|---|---|---|---|---|---|---|
| 06-30 N 14:25:13 (D0) | 141 / 141 | 37 (3–39) | 39 / 4 / 0 | 149 | 10 / 0 | 14 | 39 |
| 07-14 N 09:15:17 (D0) | 56 / 120 | 39 (2–55) | 34 / 0 / 0 | 117 | 11 / 3 | 45 | 55 |
| 08-18 N 09:15:07 (D0) | 63 / 164 | 53 (5–20) | 5 / 0 / 4 | 166 | 0 / 0 | 5 | 20 |
| 09-01 N 14:46:25 (D-1) | 71 / 65 | 30 (3–11) | 15 / 0 / 0 | 34 | 0 / 12 | 3 | 11 |
| 09-22 N 14:14:29 (D0) | 210 / 216 | 13 (1–4) | 19 / 0 / 0 | 1 | 0 / 0 | 5 | 5 |
| 10-13 N 09:18:01 (D0) | 104 / 98 | 47 (2–306) | 24 / 3 / 0 | 0 | 3 / 1 | 10 | 306 |
| 10-19 N 09:26:19 (D0) | 120 / 344 | 31 (2–11) | 17 / 1 / 0 | 0 | 1 / 210 | 3 | 11 |
| 07-16 S 11:00:46 (D0) | 98 / 98 | 26 (6–31) | 25 / 2 / 0 | 122 | 0 / 0 | 10 | 31 |
| 08-06 S 09:22:40 (D0) | 66 / 66 | 35 (118–130) | 19 / 1 / 0 | 92 | 2 / 0 | 119 | 546 |
| 08-20 S 09:14:13 (D0) | 120 / 157 | 57 (59–204) | 35 / 78 / 0 | 220 | 16 / 0 | 80 | 204 |
| 09-24 S 09:15:00 (D0) | 124 / 159 | 23 (11–44) | 15 / 62 / 0 | 67 | 4 / 0 | 26 | 44 |
| 10-15 S 09:16:28 (D0) | 60 / 65 | 26 (2–8) | 7 / 0 / 0 | 0 | 4 / 0 | 8 | 12 |

"First flat" = first moment the short book is empty; "final flat" = the moment after which it stays empty.
First flat: median 10 s. Final flat: median 35 s, maximum 546 s (SENSEX 6 Aug). No position remains at the end of any stop session.

### 3.1 Stop-module overshoot (it liquidates positions that are already gone)

112 `s_` orders overshoot: 88 sells open **830 short lots** (8 stops) and 24 buys open 138 long lots (7 stops)
([`stop_module_overlap.csv`](final_audit/results/stop_module_overlap.csv)).

| Test | Result |
|---|---|
| Does the `s_` order quantity equal the position held before the decision second? | **Sells 78 of 88, buys 23 of 24** |
| Was the same position reduced by another module between the decision and the `s_` fill? | Sells: 80 orders / 700 lots by other modules only, 5 / 104 by other modules and an earlier `s_` order, 3 / 26 by an earlier `s_` order only. Buys: 23 / 137 other modules, 1 / 1 both |
| Which modules, and when were their orders submitted? | Body 67 overshoots, wing / lump modules (`h_`, `v_`) 42. Submission of those orders: **after the decision for 76 overshoots**, in flight for 33 (19 by tag time, 14 bounded), undetermined for 2 (an overshoot can overlap orders of two classes) |
| Sequence "`s_` buys back shorts → another module sells the wing → `s_` sells the same wing" | 58 of 85 overlapping sells (562 lots) |

**Supported by the order evidence:** the stop module sends quantities equal to the position at its decision and does not
net out what other modules liquidate in the meantime; other modules keep submitting orders after the stop decision; the
overshoot is then reversed by later `s_` orders. **Duplicate stop-module action alone** explains only 3 orders (26 lots).
**Not established:** whether this is a race (a stale snapshot) or a designed liquidate-then-recheck loop, and why the other
modules sell the wings (hedge release after the buybacks is consistent with the sequence in 58 cases, but is an inference).

### 3.2 Short positions opened by other modules after a stop

62 orders (67 fills, 277 lots) in 8 of 12 stops ([`stop_post_short_causes.csv`](final_audit/results/stop_post_short_causes.csv)):

* **226 lots (11 orders, 4 stops) are wing over-sales:** contracts held long at the decision, sold by the body after the
  stop module had also sold them (all proven after by order number). The mirror image of §3.1. All bought back by `s_`
  within 5 s.
* **51 single-lot sales in contracts that were flat or short** (8 stops). Tested against the four explanations (flags overlap):

| Explanation | Test | Result (of 51) |
|---|---|---|
| In-flight orders | submitted before the first `s_` order of their block | **5** (bounded evidence; 30 Jun and 19 Oct, filled 1–2 s after the decision) |
| Normal scheduled execution | fill inside a schedule clock window, and the share of non-stop sessions with a body short sale in that same clock minute | **37 on a clock window** (5 stops at the D0 open or the 09:31 slot); in 36 of them that minute has a body sale in ≥ 90 % of non-stop sessions (mean 0.96) |
| Replacement / re-entry | sale within 60 s after a body buyback of the same right; contract bought back earlier in the session | 32 follow a body buyback; 35 are re-entries. Of the **14 off-grid** sales, 13 follow a body buyback within 60 s and 13 are re-entries (30 Jun, 13 Oct, 19 Oct) |
| Duplicate / overlapping stop-module action | — | not applicable to these 51 (it explains the 226 wing lots and §3.1) |

46 of the 51 were submitted after the stop (44 proven by order number, 2 inferred). All 51 are bought back: 28 by `s_`
(median 2 s, max 5 s) and 23 by the body (median 31 s, max 49 s).
The explanations are **not separable order by order**: on-clock sales after a stop at the open also follow buybacks. What
the evidence supports: the body keeps running its scheduled and replacement logic after a stop (37 scheduled-like; of the 14 off-grid sales, 5 in flight, 8
more replacement-like, 1 unexplained), and the stop module keeps flattening what appears, as late as 306 s after
the decision (NIFTY 13 Oct). On SENSEX 6 Aug two scheduled-slot sales 8 min after the stop were closed by the body itself.

## 4. Task 3: robustness (ML-07)

**Status: unreconciled (open).** No robustness number is reported or approximated here.

| Attempt | Setting | Outcome |
|---|---|---|
| 1 (previous audit) | patched sandbox, default threads, alongside other jobs | stopped at the 1-hour job limit |
| 2 (previous audit) | patched, restarted with a 2-hour limit; control queued behind its models | patched reached the second ablation after 120 CPU-minutes and was stopped; control stopped at the 2-hour limit |
| 3 (this audit) | patched and control side by side, `timeout 110m`, 1 thread each | both killed by a container restart before any stage finished |
| 4 (this audit) | same, 2 threads each, `timeout 110m` | **running when this document was committed**; if both finish, the comparison will be added as a separate commit and register row |

The suite re-fits 16 LightGBM models, bootstraps 12 model × algorithm pairs 2,000 times and rebuilds the minute panel three
times. Under the session's limits (2-hour background jobs, container restarts) it has not completed. ML-07 therefore stays
as committed in PR #3: its inputs changed in 0.38 % of contract-minute rows, and its results are **not re-verified**.

## 5. Limits

* Order numbers are a submission sequence only inside a block; the block split (jump > 500) is an inference from the numbers.
* Fill times have one-second resolution; body orders have no decision time.
* "Scheduled-like" and "replacement-like" are timing coincidences with known patterns, not observed triggers.
* PR #5 was re-run through the PR #3 pipeline with the corrected mapping; decision-time ordering of events around stops (DAT-12) is unchanged in it.
* All data are in-sample.

## 6. Files and register

| File | Content |
|---|---|
| `final_audit/pr5_compare.py` | committed vs control vs corrected for every PR #5 result file |
| `final_audit/stop_controller.py` | timelines, inventory transitions, overshoot and cause tests, schedule propensity |
| `final_audit/results/` | file summary, corrected PR #5 metric tables, overlap and cause tables, per-stop summary, Stage 1 segment counts |

New register rows only: **ALC-10** (PR #5 re-run), **RSK-12** (stop-module interaction; fill-level counts that supersede those
in RSK-10 and ALC-09), **DAT-14** (decision-second resolution; superseded Stage 1 segment counts), **ML-09** (ML-07 status).
