# M2-D report — wing / body association analysis

Branch `engineering/position-lifecycle-basket-reconstruction`; implementation `f1b3f974`, review fixes in the following commit (starting head `b48b0e68`). Mode `HISTORICAL_OBSERVED_REPLAY`; source `Trades_GKOHNP140.csv` sha256 `86e65ab6…f528`. Data: `reports/m2d_data/` (gzip TSVs per method + items, `manifest.json`, `m2d_summary.json`); charts: `reports/m2d_figures/` (each with its CSV).
**Decision: PASS for M2-D as an association analysis, with the scope limits in §6.** Nothing below proves lot ownership or protective intent: a successful association algorithm does not prove original strategy intent. M2-E and M3 are not started.

## 1. What was implemented (approved D6)
| Method | Rule | Level | Kind |
|---|---|---|---|
| **W1 (primary)** | same underlying, expiry, CE/PE right **and parent-order entry minute** (candidate set; `nearest` flag by \|Δ first fill\|, ties flagged) | opening (OA) and closing (CP) | candidate relationships |
| **W1_S60** | same underlying, expiry, right, **IST session** and \|first-fill gap\| ≤ 60 s (inclusive) — execution-time evidence, **not** decision-time proximity | both | sensitivity |
| W2 / W2_S60 | wing units spread over the W1 / W1_S60 candidates in proportion to body units (fractional **weights**, column `weighted_wing_units`) | both | arithmetic weights |
| W3 | FIFO queue arithmetic within (underlying, expiry, right, session) | opening only | arithmetic pairing, no timing claim (`queue_matched_units`) |
| W4 number-block | **NOT implemented** (semantics `UNRESOLVED`; no new evidence) | — | — |
| W5 | unmatched / unresolved quantity, reported per method | — | — |
Unit = parent order × instrument (partial fills of one parent are one item; 3 fills of one parent never inflate candidates). Roles are **module-tag attribution only**: wing = long `h_`, body = short `num`; at the closing level the tag is that of the closing fill. Nothing is forced one-to-one; many-to-many links, ties and unmatched units are kept. App keys influence nothing (see §4). Documented clarification of the approved text: the ±60 s sensitivity also requires the same IST session.

## 2. OBSERVED relationships (facts about recorded fills; no assignment needed)
| Opening level | Value |
|---|---|
| wing items / units | 8,399 / 617,130 |
| body items / units | 13,325 / 626,765 |
| groups (underlying, expiry, right, entry minute) | 7,958: **5,446 with both sides**, 1,000 wing-only (133,640 wing units), 1,512 body-only (128,430 body units) |
| wing/body unit ratio exactly 1:1 | **81.2 % of groups with both sides**; 55.6 % of all groups; 53.1 % of wing units; ratio < 1 in 9.8 %, > 1 in 9.1 % |
| Closing level (same groups, closing parent's entry minute) | wing 4,306 items / 500,775 units; body 10,754 / 540,250; 2,381 groups with both sides, **71.5 % exactly 1:1**; 180 wing-only (105,750 units), 686 body-only (105,060) |
**The 81.2 % is a group-level observed ratio (TP-03 E7 reported 79.7 % per window-right); it is not evidence that any specific wing lot protects any specific body lot.** Per-link observed properties (W1, opening): wing executed within 5 s of the body in 49.3 % of links (median \|Δ\| 6 s, p90 34 s, max 383 s); wing strike further OTM than the body strike in 99.9 % (median 800 index points, p10 300, p90 2,000); wing price / body price median 0.0247 (90 % ≤ 0.05) — descriptive only, no budget rule assumed; wing unit / body unit per link median 1.0 (p10 1.0, p90 4.0, range 0.125–27).

## 3. INFERRED candidate relationships (opening level; closing in `m2d_summary.json`)
| | W1 (same entry minute) | W1_S60 (±60 s) | W3 (queue arithmetic) |
|---|---:|---:|---:|
| wings with ≥ 1 candidate (of 8,399) | 7,301 (3,501 unique, 3,800 multiple) | 8,204 (2,631 unique, 5,573 multiple) | 8,176 |
| wings with no candidate | 1,098 | 195 | 223 |
| **unmatched wing units** | 133,640 (21.7 %) | 68,720 | 56,420 (queue residual) |
| bodies without a wing candidate (items / units) | 2,412 / 128,430 | 873 / 65,845 | 66,055 units (queue residual) |
| links | 18,823 | 29,079 | 12,096 |
| candidates per wing (median · p90 · max) | 2 · 5 · 32 | 2 · 8 · 49 | 1 · 2 · 27 |
| wings per body (median · p90 · max) | 1 · 3 · 9 | 2 · 4 · 11 | 1 · 1 · 3 |
| \|Δ first fill\| median · p90 (s) | 6 · 34 | 11 · 51 | 1,007 · 3,624 |
W1 pairs 7,301 of 8,399 wing parents — **independently equal** to the pairing TP-03 Phase 1 E6 used (same minute, same right). 2,887 W1 links are nearest-ties (kept ambiguous). 35 % of W1_S60 links fall outside the same-entry-minute set. **Closing level:** W1 gives 3,981 of 4,306 wings a candidate (939 unique, 3,042 multiple); unmatched wing units 105,750; bodies without wing 105,060 units; W1_S60 4,146 / 83,180 / 79,530; W3 is not defined at the closing level.
**W2 weights are not allocations:** weighted wing units per body exceed the body's own quantity for 9.1 % of opening bodies (max 31.5×) because each wing is spread over all its candidates.

## 4. Cases where methods disagree (counted, never resolved; opening wings)
W1 nearest body = W1_S60 nearest body: 6,848; **differ: 453**; W1 has none but ±60 s has candidates: 903; none in both: 195. W3's queue body lies **outside** the W1 candidate set for 6,689 wings and inside it for only 437 (+ 1,050 with a W3 body but no W1 candidate): the arithmetic pairing is a different object from co-submission and must not be read as the same relationship. At the closing level 131 wings differ between W1 and W1_S60 nearest and 165 gain a candidate only in the sensitivity.
**Second app key (`F88187`, 687 wing items, 8.2 % of items / 8.4 % of wing units):** eligible and matched — W1 item match 89.5 % vs 86.7 % for the main key (unit match 70.7 % vs 79.0 %), ±60 s 97.1 % vs 97.7 %. Removing every app key leaves every link id of every method unchanged (tested): app keys do not enter any rule.

## 5. Evidence classification
| Statement | Class |
|---|---|
| item quantities, group-level wing/body ratios, co-submission and execution-proximity facts | CONFIRMED_OBSERVATION |
| module tags as roles | CONFIRMED_ATTRIBUTION (tag only; not intent) |
| W1 candidate relationship ("this wing may protect this body") | **WEAKLY_SUPPORTED** (ceiling for `INFERRED:WING_BODY`) |
| W1_S60 candidate relationship; W3 pairing | **UNRESOLVED** |
| lot-to-lot ownership / protective intent | **UNRESOLVED / NOT_TESTABLE** (no leg identifiers in the export) |
| window-level 1:1 quantity finding (TP-03 E7) | STRONGLY_SUPPORTED **as a window-level observation only** |
Each link row carries `membership_provenance INFERRED:WING_BODY:<method>`, `observation_basis` (the observed fact), `evidence_class` (the inferred relationship) and `protective_link UNRESOLVED`; never `EXPLICIT`.

## 6. Scope limits that matter (all reported, none hidden)
* **Tag-based roles exclude real units** (`scope_exclusions_TAGGED_units`): opening — long `num` 61,470, long `v_` 67,635, long `s_` 3,255, long `m_` 1,040 (seed wings tagged `num` are **not** wings here), short `s_` 37,120, short `h_` 130; closing — long episodes closed by `num` 132,235, `s_` 44,530, `v_` 41,575, `m_` 1,040 (≈ 219k units) and short episodes closed by `s_` 95,485 and `h_` 21,175. Opening bodies are 626,765 units but closing bodies only 540,250 because stop-closed bodies carry the `s_` tag: **closing-level "bodies without a wing" omits stop-closed bodies.**
* A wider **direction-based sensitivity** (wing = any long-side item, body = any short-side item) is in `coverage_direction_scope_sensitivity`: opening wings 9,669 (750,530 units) of which 8,288 have a W1 candidate; closing wings 5,728 (720,155 units), 5,177 with a candidate.
* The closing "wing" is defined by the tag of the closing fill: of its 500,775 units, 387,985 sit in episodes opened only by `h_`, **107,530 in episodes opened by mixed modules** and 5,260 in episodes opened without any `h_`.
* Whole-second timestamps; entry minute is minute precision and is not an execution time; first-fill gaps are execution evidence.

## 7. Tests and independent review
`python3 -m pytest portfolio_engine/tests -q` → **185 passed** (fast subset `-m "not slow"`: 149); `tests/test_wing_body.py`: 30 fast + 3 slow real-ledger tests; C++ 24/24; earlier-stage artifacts unchanged. Tests cover false matches (right, expiry, underlying, minute, ±60 vs 61 s, IST midnight), multiple candidates and ties, proportional weights, partial quantities, unmatched positions on both sides, missing entry minute / metadata / app key, second app key, many-to-many, W3 conservation and sessions, closing level, disagreement, parent aggregation, PE strike sign, first-fill times, provenance/evidence labels, observed-layer immutability, and corrupted-result rejection by an independent checker (which also compares candidate sets with a brute-force reference).
A separate read-only agent re-implemented W1, W1_S60, W2, W3 on the full ledger (both levels, both scopes) and 200 random scenarios: **0 differences**; it reproduced 7,301 / 8,399, the 81.18 % group result and all output hashes. **Defects found and fixed:** (1) W3 "unmatched" counted whole items (51,740 / 63,520) instead of queue units (56,420 / 66,055) — now the residual; (2) inferred links were labelled `CONFIRMED_OBSERVATION` — now the observed fact is a separate column and the relationship is WEAKLY_SUPPORTED / UNRESOLVED; (3) scope exclusions were unreported — now listed by module; (4) `allocated_wing_units` suggested ownership — renamed `weighted_wing_units` / `queue_matched_units`, with the weighted-coverage distribution reported; (5) the 81.2 % headline lacked its denominators; W3 tie fields now `NA`; docs refreshed. **Seven mutants that survived the first tests** (PE strike sign, last-fill timestamp, last-fill session, S60 primary flag, S60 app-key filter, closing wing by any module, W3 item-count coverage) are **all killed** by tests added for them.
Remaining weakness: my independent checker and the reviewer's code share the same written rule set; a misreading of the specification would not be caught.

## 8. Remaining uncertainty
Which wing (if any) protects which body — needs leg or allocation identifiers or decision logs; the intent of the entry-minute coincidence; the number-block semantics (unresolved); stop-closed bodies and non-`h_` long items are outside the tagged scope by design.
