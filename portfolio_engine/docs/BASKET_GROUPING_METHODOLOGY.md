# Basket grouping methodology (M2-A, APPROVED decisions D1–D7 recorded below; authoritative section at the end)

Three independent views on the same fills. **None is an original Algo 8 basket.** Each is a partition of its own member universe; group counts are descriptive and are never a quality score. No parameter is chosen after looking at outputs.

## Source of each registered parameter (audited)
| Parameter | Where registered | Status |
|---|---|---|
| Entry windows `[T−2 s, T+3 min)`, 17 registered + 4 control pre-expiry, 23 expiry-day windows, submission classes, snapshot rule | `tp_reconstruction/tp03/config.yaml` (frozen, sha256 `942e36d8…c2f8`), `TP03_PHASE0_AUDIT.md` §B4 | **REGISTERED** |
| Closing-batch gap: primary 10 s, sensitivities 2, 5, 30, 60 s, plus order-number-block definition; unit = parent order | `tp03/config.yaml` `exit.batch`, `TP03_PHASE0_AUDIT.md` §C4 | **REGISTERED but never executed** — the brief calls it "TP-02 methodology"; TP-02 itself used per-closing ±5 s basket and ±10 s wing windows (`tp02/config.yaml`). TP-03 Phase 2 was not run, so there is **no existing batch output to reuse**; Model C is built fresh from the registered text |
| Opening-cluster time gap | none before M2-A | **APPROVED (D1) as a fixed sensitivity set** — see 'Approved decisions' below |
| Wing link windows (closing) 10 s, sensitivity 60 s | `tp02/config.yaml` `wing` | REGISTERED (TP-02) |
| Same-minute same-right wing↔body pairing | TP-03 Phase 1 E6 (`p1_structure_tests.py`) | used in Phase 1, not a registered rule |

## Model A — cycle container (`INFERRED:CYCLE`)
* Members: **inventory episodes**. Key: `(underlying, expiry)` from the instrument identity. Spans D-1 and D0. 35 containers (18 NIFTY, 17 SENSEX).
* Reported per container: opened / closed / remaining units, per CE/PE and long/short, realized P&L per convention, D-1 vs D0 split (TP-03 B6 identity), first/last fill, episodes by terminal status.
* Reconciliation: `Σ containers = portfolio`. Three cycles have no pre-expiry session and two have no D0 fills: represented as such, not filled in.

## Model B — opening cohorts (`INFERRED:OPENING_COHORT`)
* Members: **OpeningAllocations**, grouped through their **parent order** (partial fills of one parent are one member group; a parent is never split across cohorts).
* Key (primary, registered logic): `(underlying, expiry, session date, window label, opening role)`.
  * `window label`: the TP-03 attribution of the parent order — `W:<hh:mm>` for a registered/control window by the submission class (`ENTERED_INSIDE_WINDOW`, `DECISION_IN_WINDOW_FILL_OUTSIDE`, `AMBIGUOUS_BOUNDARY_MINUTE`, `SUBMITTED_BEFORE_WINDOW`), `INITIAL_ENTRY` for the cycle's first order minute, `OFF_WINDOW` otherwise. Window membership is by **submission class, never by fill time alone**.
  * `opening role`: `SHORT_BODY` (num sell), `LONG_BODY` (num buy), `LONG_WING` (h_ buy), `LUMP_LONG` (v_ buy), `STOP_SHORT` (s_ sell), `OTHER`.
* Two registered variants run side by side (TP-03 reporting rule): `OC_WIN_INCL` (boundary-ambiguous parents inside their window's cohort, flagged) and `OC_WIN_EXCL` (they form a separate `AMBIGUOUS_BOUNDARY` cohort, never merged into the window).
* Session boundary: cohorts never span sessions; carried inventory does not make an opening part of a later cohort. Reversal fills contribute only their opening remainder.
* **Gap sensitivities — PROPOSAL, not registered, awaiting approval:** cluster the opening parent orders of one `(und, expiry, session, role)` by **consecutive first-fill gap ≤ g**, `g ∈ {2, 5, 10, 30, 60}` s (the closing set with 10 s added, so opening and closing are comparable; chosen *before* any output exists). The window-attribution grouping stays primary. Reported as descriptive tables (group count, size distribution, units, share of cohorts that straddle a window boundary); **no value of g is selected or ranked.**

## Model C — closing batches (`INFERRED:CLOSING_BATCH`)
* Members: **ClosingPortions** grouped through their closing **parent order** (a parent with several fills is one decision).
* Registered primary definition: consecutive closing parent orders of **one underlying** with gap ≤ **10 s**; sensitivities **2, 5, 30, 60 s**; plus the **order-number-block** definition (same app key, consecutive order numbers within the registered gap of 20).
* **Ambiguity found in the registered text** — "gap" is not defined. Proposal for approval: parents ordered by **first-fill time**; gap = `first_fill(next) − first_fill(previous)` (single linkage; a batch grows while each step ≤ g). Sensitivity: `first_fill(next) − last_fill(previous)`. Decision-time bounds (tag time for tagged orders, `[order-entry minute, first fill]` for body orders) are recorded per parent but not used for linkage.
* A parent order with a closing portion *and* an opening remainder (reversal) contributes only its closing portion to Model C and only its opening portion to Model B.
* Recorded per batch: members, contracts, CE/PE, short-body vs long-wing (by the *closed episode direction*), opening-source allocation (FIFO / LIFO / pool), P&L class (PROFIT/LOSS/BREAKEVEN per convention with TP-01's 0.025-point tolerance), start/end, day type, expiry phase (TP-02 phases), TP-02 stop class (join on `close_row`), positions affected.
* A batch says which contracts were **closed in one event group**. It says nothing about how they were opened.

## Reconciliation and non-double-counting (all three models)
`Σ members over a view = universe total` (Model A episodes 2,667; Model B OAs 23,684 / units 1,414,545; Model C CPs 17,760 / units 1,377,065). Unassigned members form an explicit `UNASSIGNED` group, never silently dropped. Totals of different views are never added.

## Edge cases that must be tested
D-1 → D0 carry; reversal fills; parents with partial fills across seconds; two parents with identical first-fill seconds (tie → ordered by `source_row_id`, reported); boundary-ambiguous submissions; cycles with no pre-expiry session; expired-unclosed episodes; stop-module fills (`s_`) inside a batch (flagged, not removed).

## What is reported, and what is not
Reported: group counts, size distributions, unit reconciliation, overlap of group *boundaries* between sensitivities (e.g. share of 10 s batches that split at 5 s), ambiguous membership counts. **Not** reported as findings: any ranking of conventions, any "best" gap, any link between group structure and profitability.

## Wing ↔ body relationship methods (M2-D design)
A wing is **never forced** into one body. Five methods run independently; each yields scored candidate links plus explicit `UNMATCHED` quantity. All links are `INFERRED:WING_BODY:<method>`.
| # | Method | Level | Rule | Registered parameter | Limits |
|---|---|---|---|---|---|
| W1 | candidate set: same underlying / expiry / right / **parent entry minute** (approved D6); `nearest` flag by first-fill gap, ties flagged | opening and closing (parent×instrument items) | all candidates kept; no forced assignment | entry minute primary; ±60 s first-fill sensitivity (W1_S60, also same IST session) — **approved D6**; TP-02's ±10 s stays a separate historical analysis | proximity, not protection |
| W2 | proportional quantity | opening, closing | wing units spread over all body candidates in the same window/right in proportion to their units (fractional weights, no integer ownership) | same windows as W1 | weights are arithmetic |
| W3 | FIFO opening-lineage | opening | within `(und, expiry, right, session)` the cumulative wing units are queue-matched to cumulative body units in opening order | none | arithmetic pairing, no timing claim |
| W4 | order-number block | opening, closing | parents sharing an app key and an order-number block (gap ≤ 20) | `exit.batch` block gap | valid only where app keys equal (hedge parents use a second app key in ≈ 7.8 % of `h_` fills) → otherwise `NOT_APPLICABLE` |
| W5 | unresolved | — | any wing quantity not covered by W1–W4 under that method | — | reported, never forced |
Recorded per link: body and wing ids, time difference, units ratio, right, strike distance, per-fill premiums, alternative candidates, unmatched quantity, convention, evidence class. Where methods disagree the case is listed as `CONVENTION_SENSITIVE`. The window-level 1:1 finding (TP-03 E7, 79.7 %) is an observation about *windows*; it is not used to assign a lot-to-lot link.

## Adversarial checklist → counterexample tests (M2-F will report results)
| # | Failure mode | Planned counterexample / check |
|---|---|---|
| 1 | independent positions merged because opening times are close | two unrelated parents 1 s apart in different roles never share a cohort key; gap-cluster separation test |
| 2 | fills of one parent double-counted as decisions | 3-fill parent → one member group in B and C |
| 3 | closing batch read as opening basket | views are separate types; a batch id is never accepted where a cohort id is expected |
| 4 | wing matched to wrong body | two candidate bodies, equal distance → both kept, `AMBIGUOUS`, not picked |
| 5 | FIFO/LIFO difference shown as ownership | AVG emits `NOT_IDENTIFIABLE`; convention field mandatory |
| 6 | reversal as normal closure | 100 short + buy 130 → CP 100 + OA 30 in two episodes |
| 7 | several views double-count | I8/I9 tests: each view totals equal the universe, cross-view sums rejected |
| 8 | late fill in the wrong window | `DECISION_IN_WINDOW_FILL_OUTSIDE` case; submission class wins over fill time |
| 9 | session/D0 boundary false cohort | carried inventory opened D-1 never joins a D0 cohort |
| 10 | partial fills mislead size | requested vs filled kept; unfilled remainder flagged |
| 11 | fictitious expiry P&L | `EXPIRED_UNCLOSED` realized P&L stays 0 |
| 12 | inferred id mistaken for broker id | all ids start `INF:`; zero `EXPLICIT` rows asserted |


---
# Approved decisions D1–D7 (authoritative; supersede any 'proposal' wording above)
Approved by the reviewer after M2-A. **Status: REGISTERED methodology. No grouping has been executed.** Executed results will be recorded separately in the evidence registry.

## Timestamp precision (all models)
* Execution timestamps (`first fill`, `last fill`) are **whole UTC seconds** (export resolution); all gaps are integer seconds and the comparison is **`gap ≤ threshold`** (inclusive).
* The order-entry minute is **minute precision**, is **not an execution time**, and is stored as the epoch second of the minute start. Decision-time statements may use it only at that precision.
* Ties (equal timestamps) are broken by `first source_row_id` of the parent, then `parent_order_id` (string order). Tie counts are reported.

## D1 — Opening cohorts
* Primary = TP-03 window attribution (unchanged; never replaced by gap clustering).
* Additional execution-time proximity groupings with `g ∈ {2, 5, 10, 30, 60}` s, fixed, never selected between.
* Timestamp per parent = **first fill that carries an opening portion** (a mixed parent's closing executions never contribute). Deterministic **single linkage**: within each `(underlying, expiry, session date, opening role)` stream, sort parents by that timestamp and chain consecutive parents while `ts(next) − ts(previous) ≤ g`; a larger gap starts a new group. Underlying, expiry, session and role boundaries are never crossed.
* Reported per `g`: group count, size distribution, **maximum cluster duration and maximum member count** (chaining effect is made visible), unit reconciliation to 1,414,545.
* Window attribution = an **entry-window classification**; gap cohorts = **execution-time proximity**. Neither shows that one portfolio decision occurred.
* Convention ids: `OPEN_FIRST_FILL_GAP_{2,5,10,30,60}S`; window variants `OC_WIN_INCL`, `OC_WIN_EXCL`.

## D2 — Closing batches
* Decision unit = parent order, represented **by its closing portions only**; timestamp = **first closing-portion fill**; opening executions of a mixed parent never contaminate it.
* Primary `CB_FIRST_FILL_GAP_{10}S`; sensitivities 2, 5, 30, 60 s, same rule (first-fill single-linkage, consecutive parents of **one underlying**, `ts(next) − ts(previous) ≤ g`).
* Independent sensitivity 1: `CB_LAST_TO_FIRST_GAP_{2,5,10,30,60}S`: `first_cp_fill(next) − last_cp_fill(previous) ≤ g` (a negative difference = overlap = linked).
* Independent sensitivity 2: `CB_NUMBER_BLOCK_V1` (registered number-block variant). **Semantic ambiguity — recorded, not resolved:** `tp03/config.yaml exit.batch.block_definition` says "one app key and one order-number block with consecutive numbers (gap ≤ 20)", while the only block code (`tp02_common.number_blocks`, TP-02 `sequence_block_gap: 500`) starts a block when the number jumps by **more than 500** within `(date, app key)`; it is not stated whether the registered "gap ≤ 20" applies between consecutive *closing* parents only (order numbers are shared with interleaved opening orders), whether it is within a 500-block, or whether a time limit also applies. **Implementation of this variant stops for review before M2-C.**
* The three method families have **separate ids, membership rows, counts and reports**; they are never merged.
* TP-02's closing ±5 s basket and ±10 s wing associations are separate historical analyses; new batch results are **never** described as TP-02 results.

## D3 — Identifiers
`INF:<KIND>@<CONVENTION>:<UND>:<EXPIRY>[:<SESSION>]:<NNN>` with convention-specific tokens, e.g. `INF:CLOSING_BATCH@CB_FIRST_FILL_GAP_10S:…`, `INF:CLOSING_BATCH@CB_LAST_TO_FIRST_GAP_10S:…`, `INF:CLOSING_BATCH@CB_NUMBER_BLOCK_V1:…`, `INF:OPENING_COHORT@OPEN_FIRST_FILL_GAP_10S:…`. Membership rows carry `grouping_version` and `parameter_hash`. An id is never reused across conventions and never resembles a broker identifier.

## D4 — Schema
`ClosingPortion`, `parents.tsv` and the v1.1 files are approved (additive; M1 files and semantics unchanged). `parents.tsv` keeps missing values explicit (`NA`) and never derives an order number or app key from other fields. The 26 mixed parents are re-validated in M2-B.

## D5 — Boundary
Python **and** C++: position identity, lifecycle state, opening/closing quantity mechanics, shared allocation logic, Model A. **Python only**: Models B, C, wing/body, sensitivities, reports, chart orchestration. Shared logic has byte-parity tests; Python-only analytics are deterministic and fixture-tested. Analytical uncertainty never enters the deterministic accounting state.

## D6 — Wing/body
Primary candidate set: same underlying, same expiry, same right, **same parent order-entry minute**. Sensitivity: **±60 s on first-fill execution time** (labelled execution-time evidence, not decision-time proximity). Multiple candidates, unmatched quantity and alternatives are kept; no forced one-to-one matching. The ≈7.8 % of `h_` fills with the second app key stay eligible for every method that does not need the app key; the number-block method is `NOT_APPLICABLE` / `UNRESOLVED` for them. TP-02's ±10 s closing wing link stays a separate historical analysis.

## D7 — Demonstration cycles
Frozen in `docs/DEMO_CYCLE_SELECTION.md` (formula) and `reports/DEMO_CYCLE_SELECTION_NOTE.md` (result) **before any grouping output exists**.


## M2-C status (executed vs audited vs not implemented)
* **Executed:** C1 first-fill chaining and C2 last-to-first chaining, thresholds 2/5/10/30/60 s, boundaries underlying × expiry × session, closing portions only (`reports/M2C_CLOSING_BATCH_REPORT.md`, data in `reports/m2c_data/`). Ordering `(first closing second, smallest closing source_row_id, parent_order_id)`; C2 predecessor = immediately preceding parent. Two points the approved text leaves open were **fixed by me and measured, not decided for you**: the tie order and the C2 predecessor reference (result: at most one link differs).
* **Audited, `UNRESOLVED — REVIEW REQUIRED`, not implemented:** `CB_NUMBER_BLOCK_V1` (`reports/M2C_NUMBER_BLOCK_AUDIT.md`; interpretations N1–N5).
* **Not implemented:** wing/body associations, Models A and B, cut/re-entry policies.

**Model C accepted** (see `reports/M2C_ACCEPTANCE_ADDENDUM.md`): C1 PASS; C2 PASS under the implemented tie-break / predecessor reference (identical to C1 only under that convention); outputs are time-connected closing-order clusters, not decisions; the number-block variant stays `UNRESOLVED — REVIEW REQUIRED` and is not implemented.


## M2-D status (executed)
Wing/body association analysis **executed** (`reports/M2D_WING_BODY_REPORT.md`): W1, W1_S60, W2, W2_S60, W3; W4 (number-block) **not implemented**; W5 = unmatched quantity reported per method. Roles are module-tag attribution (wing = long `h_`, body = short `num`; closing by the closing fill's tag) with a direction-based sensitivity. Clarification of the approved text: the ±60 s sensitivity also requires the same IST session. Not started: M2-E, Models A and B, cut/re-entry, M3. (The earlier "Not implemented: wing/body associations" line under *M2-C status* is superseded by this section.)
