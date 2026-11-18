# Algo 8 — Allocation reconstruction, phase 3: replacement and re-entry continuity

Branch `research/algo8-allocation-reconstruction` (PR #5, draft). Code: [`replacement.py`](replacement.py); unit tests:
[`tests/test_replacement.py`](tests/test_replacement.py) (5 tests; 14 in the allocation suite, all passing). Every number below comes from
outputs **executed** on the clean order table (column-163 key) and written to [`results/`](results/). No model was fitted. The stop
models, the frozen alpha, TEST thresholds, PR #1 / PR #2 findings and raw data are untouched, and the phase-2 conclusion (stop constant and
reference UNKNOWN) is not reopened.

## Short answers

| Question | Answer |
|---|---|
| **Can we reconstruct the position lifecycle?** | **At contract and lot level: yes.** Every model × convention ledger reproduces the observed short inventory after all 39,874 orders (0 mismatches, 0 negative inventories). **At allocation level: no.** The same order flow fits several ownership stories equally well. |
| **Can we identify replacement versus independent re-entry?** | **Partly.** Re-sales within **60 s** of a buy-back are 1.3–4.1× more frequent than under a time-shifted null for Clock-B rebalances, lot stops, basket reductions and partial buy-backs. Beyond 1 minute, observed pairs are mostly at or **below** the null, so later "replacements" are not distinguishable from independent entries. Scheduled-window sales (44.5 % of sold lots) are independent by construction. |
| **Can we infer allocation ownership?** | **No.** Of 3,611 replacement / re-entry lot pairs, 73 % have competing antecedent reductions on ≥ 2 contracts within 15 min (and 44 % of the fast, ≤ 60 s links have competitors within 60 s), a further 23 % change owner with the ownership convention, and only **3.5 %** are identified. Slot and chain models almost never treat a re-sale as a continuation (0.4–0.8 % and 2.6–3.6 %). |
| **Which parts of the state machine are recovered?** | OPEN (schedule), ADD (ladder), REDUCE (mostly one lot), CARRY, FINAL CLOSE, and a REPLACE transition within ≈ 1 minute after Clock-B rebalances and some reductions, mostly at a **different strike**. RE-ENTER after full closure is rare (31 lots within 60 s). **Triggers** for replace vs not, the replacement strike rule and the replacement quantity rule are **not recovered**. |
| **What information is still missing?** | Allocation / parent-order ids; order lifecycle (submit, ack, cancel, pending); sub-minute decision times for body orders; decision logs; and a quote-based ATM definition (full chain), to test the "re-sold at ATM" claim exactly. |

## 1. Data and event definitions

| Event | Definition | Count |
|---|---|---|
| Reduction **R** | Every closing short buy-back (any module / label) | 11,007 orders, **15,327 lots** |
| Sale **S** | Every short-opening sell (label `open`, side Sell; module tag kept) | 13,410 orders, **15,312 lots** |
| Hedge **H** | Every wing order: long-opening buy, or wing close labelled `L-…` | — |
| Inventory | Short lots per contract and per right **before and after every order**, from one running pass in replay order (`prepare()`) | 39,874 orders |
| ATM | Sale or reduction strike within ± 0.5 strike step (NIFTY 50, SENSEX 100) of the index close of the **last completed minute** | — |
| Schedule window | First fill in [09:16 + 15k − 2 s, + 180 s) (the phase-1 slot definition) | — |

Times are **first-fill times at 1-second resolution**. Body orders are only stamped to the minute, so decision times inside a minute are not
known (the phase-2 limitation applies).

## 2. Linker and classification (pre-registered in the `replacement.py` header)

**Linking (association only, not ownership).**
- A sale links only to **earlier** reductions of the same underlying, expiry, right and date. Earlier means earlier in replay order **and** with a first fill not after the sale's first fill.
- **Capacity:** each reduction can supply at most the lots it bought back. A sale's lots are assigned greedily and may be **split** across reductions, one row per split. No reduction is over-replaced and no sale lot is used twice; both are asserted in code.
- Scheduled-window sales are *independent scheduled entries* and do not consume capacity (primary rule).
- Priority: the **most recent** reduction first, with same contract breaking ties.

**Classes (exclusive, in this order).**
- dt > 15 min → **unresolved association**.
- Same contract with zero inventory before the sale → **same-contract re-entry after full closure**.
- Same contract, the whole buy-back re-sold → **same-contract replacement**; part of it → **partial position replenishment**.
- Different strike, sale at ATM and original not ATM → **ATM re-centering**; otherwise → **same-right, different-strike replacement**.
- Unlinked sales → independent scheduled entry / independent off-grid entry (no eligible antecedent, or antecedent capacity exhausted).
- Wing orders within 0–60 s after a same-right reduction → **hedge adjustment** (wings never consume short capacity).

**Ambiguity.** At the sale time, if reductions with capacity exist on ≥ 2 different contracts within 15 min, the link is flagged
`ownership_ambiguous`. The 60-s version is reported as a sensitivity.

**Association test.** Observed (reduction → later off-grid same-right sale) pairs per window are compared against 200 draws of a null that
shifts every reduction by a random ± 20–120 min inside the same session.

**Ownership models.** Each linked lot pair (closed lot → new lot) is built under the cheapest-first, FIFO and LIFO conventions.
- **A (slot):** the new lot keeps its own slot allocation.
- **B (chain):** continuation if and only if the two lots share a timer-phase chain.
- **C (event):** the new lot **inherits** the closed lot's allocation (non-ambiguous links of ≤ 15 min only). Ambiguous links go to an explicit `AMB|<sale>` thread.
- The owner is *identified* only if all three conventions give the closed lot the same slot allocation.

**Revisions made while building (disclosed).**
- The first version linked "same contract first", which tied Clock-B re-sales to older same-strike reductions. The primary rule became "most recent first", and the old rule is kept as a variant.
- 17 links whose sale filled before its reduction were then excluded.

## 3. Association: what really follows a buy-back?

Observed pairs ÷ time-shifted null (excess ratio; p < 0.05 shown in **bold**). Source: [`replacement_association_null.csv`](results/replacement_association_null.csv).

| Reduction group | 0–30 s | 30–60 s | 1–5 min | 5–15 min | > 15 min |
|---|---|---|---|---|---|
| Clock-B rebalance | **3.31** | **4.13** | 0.56 | **1.29** | 0.76 |
| Clock-B, no replacement | 0 pairs | 0 pairs | 0.51 | 0.88 | 0.71 |
| Individual lot stop | **3.58** | **1.30** | 0.70 | 0.74 | 0.93 |
| Same-contract partial buy-back | **1.76** | 1.05 | 0.99 | 0.80 | 0.83 |
| Side-level reduction | 0.87 | 0.62 | 0.86 | 0.70 | 0.73 |
| Basket reduction | **2.00** | **2.19** | **1.45** | **1.36** | 0.70 |
| Grid rebalance (A / :00) | **2.13** | 0.38 | 1.05 | **1.60** | 0.86 |
| Scheduled / liquidation / other | **2.88** | **1.28** | 0.99 | 0.65 | 0.17 |

* The **Clock-B** labels behave as their names say. Rebalances are followed by re-sales within a minute at 3–4× the null. The "no replacement" class has **zero** same-right off-grid sales within 60 s.
* **Side-level reductions are never followed by re-sales** above chance, so they look like genuine de-risking.
* For most groups, association beyond 1 minute is at or below chance (activity elsewhere in the session is higher than right after a buy-back). Links in those windows are not evidence of replacement.
* This is association, and partly co-scheduling: Clock-B ticks fix both the buy-back and the re-sale times. It is **not** evidence of allocation ownership.

## 4. Link classes by window (primary rule; lots)

Source: [`replacement_transition_matrix.csv`](results/replacement_transition_matrix.csv) (table `class x window`). 4,654 link rows, 5,560 lots.

| Class | 0–30 s | 30–60 s | 1–5 min | 5–15 min | > 15 min |
|---|---:|---:|---:|---:|---:|
| Same-right, different-strike replacement | 1,284 | 182 | 436 | 457 | 1 |
| ATM re-centering | 185 | 69 | 191 | 231 | 2 |
| Same-contract replacement | 120 | 77 | 143 | 183 | 1 |
| Same-contract re-entry after full closure | 18 | 12 | 19 | 8 | 0 |
| Partial position replenishment | 0 | 0 | 0 | 0 | 0 |
| Unresolved association | — | — | — | — | 1,941 |

Unlinked sale lots: 6,813 independent scheduled entries (44.5 %), 2,847 off-grid with no eligible antecedent, 88 with exhausted
antecedent capacity.

**How much of each buy-back is re-sold, and how fast** ([`replacement_by_reduction_label.csv`](results/replacement_by_reduction_label.csv)):

| Reduction label | Lots | Re-sold ≤ 30 s | ≤ 60 s | ≤ 15 min |
|---|---:|---:|---:|---:|
| Clock-B rebalance | 744 | 21.2 % | **31.5 %** | 49.9 % |
| Clock-B, no replacement | 419 | 0 % | **0 %** | 8.4 % |
| Individual lot stop | 3,456 | 3.6 % | 4.1 % | 11.7 % |
| Same-contract partial | 811 | 16.2 % | 20.0 % | 45.5 % |
| Side-level reduction | 871 | 5.1 % | 6.2 % | 15.2 % |
| Basket reduction | 1,804 | 12.0 % | 18.1 % | 36.8 % |
| Grid rebalance | 698 | 5.6 % | 6.2 % | 38.8 % |
| Final flatten | 2,005 | 0.8 % | 1.1 % | 1.8 % |
| Expiry-day salvage | 2,067 | 8.6 % | 11.3 % | 27.5 % |
| Cycle stop & liquidation | 2,111 | 27.9 % | 28.6 % | 28.6 % |

**Clock-B, in detail.**
- With the capacity-constrained, most-recent-first rule, 31.5 % of Clock-B rebalance lots get a re-sale within 60 s.
- If each Clock-B buy-back is instead allowed to claim **any** same-right off-grid sale within 60 s, ignoring competing reductions, the share is **69.8 %**.
- The gap is ownership competition, not missing re-sales: 55 % of Clock-B buy-backs have another same-right buy-back within the next 60 s.
- Linked Clock-B re-sales are fast: 10th / 25th / 50th percentile 3 / 15 / 48 s, against the earlier ≈ 28 s median.
- They are **not mostly at ATM** under the strike-distance definition: 66 of 203 lots ≤ 60 s are at 0 steps, the rest 1–3 steps either side. The strike change is 0 for 52 lots, ± 1 step for 76, ± 2–3 for 52.
- So the earlier "re-sold at ATM" description holds only loosely. An exact test needs a quote-based ATM.

**Observation flagged for review (no conclusion changed).** In 7 of 12 cycle-stop cycles, short-opening fills arrive shortly after the `s_`
liquidation begins: 603 lots link to a liquidation buy-back 0–38 s earlier, and open sells are seen up to ≈ 140 s after the stop starts (e.g. NIFTY 30 Jun: 18 sells 2–15 s after the stop). They may be in-flight body orders; order lifecycle is not in
the data. This sits awkwardly with register RSK-01's wording "no new entries afterwards in the cycle", which this phase did not re-test.

**Hedge adjustments** within 60 s of a same-right reduction ([`replacement_hedge_links.csv`](results/replacement_hedge_links.csv)), in wing lots:

| Wing order | Lots |
|---|---:|
| Wing sold as salvage | 6,074 |
| Hedge released (same-side short closed within 60 s) | 4,727 |
| New wing bought | 2,916 |
| Final-flatten wing sale | 531 |
| Lump disposal | 277 |

Wing actions accompany reductions closely. This is association; which allocation a wing belongs to is not identified (phase 1, T4).

## 5. Stability across linkage definitions

Linked lots with dt ≤ 60 s, by variant ([`replacement_variant_stability.csv`](results/replacement_variant_stability.csv)):

| Class (≤ 60 s) | Primary (most recent) | Horizon 15 min | Scheduled consume | Same-contract first | Earliest first |
|---|---:|---:|---:|---:|---:|
| Different-strike replacement | 1,472 | 1,472 | 1,433 | 1,148 | 667 |
| ATM re-centering | 265 | 265 | 262 | 185 | 74 |
| Same-contract replacement | 199 | 199 | 199 | 275 | 32 |
| Re-entry after full closure | 31 | 31 | 31 | 40 | 3 |

* The three **recency-based** definitions agree within 3 %. Same-contract-first moves about 20 % of the ≤ 60 s lots between classes.
* Earliest-first links sales to old reductions and keeps less than half of the fast links. It is shown only as a deliberately implausible bound.
* Over **all** windows, class shares are definition-dependent (unresolved 0–25 % of sold lots; different-strike 8–16 %). Only the ≤ 60 s structure is stable.
* Link classes do not depend on the ownership convention (cheapest-first / FIFO / LIFO); ownership does (§6).

## 6. Ownership: competing linkage models

Replacement / re-entry lot pairs (3,611; [`replacement_ownership_pairs.csv.gz`](results/replacement_ownership_pairs.csv.gz)). Shares are
identical to 0.001 across the three conventions:

| Outcome | Share |
|---|---:|
| Cannot distinguish: competing antecedents on ≥ 2 contracts within 15 min | 73.1 % |
| Cannot distinguish: owner allocation changes with the convention | 23.4 % |
| A and B both say "new allocation"; C says "continuation" | 3.2 % |
| B and C agree (same chain); A disagrees | 0.2 % |
| A, B and C all agree | 0.0 % |

* **Agreement between models is essentially nil.** Under A (slot), a Clock-B or post-reduction re-sale always starts a new "extra" allocation. Under B (chain), it continues the old chain only 2.6–3.6 % of the time. Under C (event), it continues by assumption.
* The data cannot tell which is right: **ownership is identified for 3.5 % of pairs**, and only relative to definitions that are themselves unvalidated.
* With a 60-s ambiguity window instead of 15 min, 21 % of replacement links still have competing antecedents on ≥ 2 contracts.
* All ambiguous and unresolved links are listed with their reasons in [`unresolved_position_links.csv`](results/unresolved_position_links.csv): 4,550 rows = 1,910 competing antecedents + 1,870 associations > 15 min + 770 convention-dependent only. The convention-dependent flag is set on 4,109 of them.

## 7. State machine (lifecycle ledgers)

Ledgers: [`position_lifecycle_ledger.csv`](results/position_lifecycle_ledger.csv) (model C, cheapest-first) and `.csv.gz` (all nine model ×
convention ledgers). Metrics: [`state_transition_metrics.csv`](results/state_transition_metrics.csv). Event types come only from observed
orders:
- **OPEN**: first entry of a thread.
- **ADD**: further entry with inventory > 0.
- **REDUCE**: exit leaving inventory > 0.
- **CLOSE**: inventory → 0 and the thread later re-opens.
- **REPLACE / RE-ENTER**: model-C linked entry, or a re-opening after CLOSE.
- **CARRY**: open at the first D0 minute.
- **FINAL CLOSE**: the last close.

| Metric | A slot | B chain | C event |
|---|---:|---:|---:|
| Threads | 6,547 | 4,357 | 6,527 (1,752 of them explicit `AMB` threads) |
| Inventory mismatches vs orders (all 39,874 orders) | **0** | **0** | **0** |
| Negative thread inventory | 0 | 0 | 0 |
| REPLACE / RE-ENTER events | 0 / 31 | 0 / 333 | 2,584 / 62 |
| Threads carried into D0 | 1,655 | 1,228 | 1,650 |
| Thread back at its previous peak after REPLACE | — | — | 88–93 % |

(Cheapest-first shown. FIFO and LIFO are within ± 2 % for threads, CARRY and REPLACE; RE-ENTER counts move more: A 17–43, B 213–352, C 53–72.)

**Model C transitions (cheapest-first)**, from → to (share of the "from" state):
- OPEN → ADD 47 %, FINAL CLOSE 31 %, CARRY 18 %.
- ADD → ADD 61 %, REDUCE 27 %, CARRY 10 %.
- REDUCE → REDUCE 55 %, FINAL CLOSE 35 %, REPLACE 6 %.
- REPLACE → FINAL CLOSE 74 %, REDUCE 13 %, CLOSE 7 %.
- CARRY → FINAL CLOSE 67 %, REDUCE 29 %.
- CLOSE → REPLACE 94 % (by construction, CLOSE requires a later re-opening).

**Conservation holds by construction:** threads partition the unit lots of an exact replay. It is therefore a software check, not evidence
for any model. What separates the models is ownership agreement (§6), and there they disagree.

## 8. Acceptance criteria

| Criterion | Status |
|---|---|
| 1. All transitions conserve inventory | **Met**: 0 mismatches over 39,874 orders under 9 model × convention ledgers; asserted capacity and sale-lot conservation. |
| 2. No event double-counted | **Met**: each sale lot is linked at most once; each reduction supplies at most its bought-back lots (asserted). Splits are explicit rows (`split_index`). |
| 3. Clock-B replacements represented | **Met**: off-grid Clock-B re-sales are linked (383 links); "no replacement" has 0 re-sales within 60 s. |
| 4. Ambiguous links explicit | **Met**: `ownership_ambiguous`, `AMB|` threads, `unresolved_position_links.csv`. |
| 5. Stable across reasonable definitions | **Met for ≤ 60 s links** (recency-based variants within 3 %). **Not met beyond 1 minute**, where shares move with the definition; those windows also lack association evidence. |
| 6. Association separated from ownership | **Met**: §3–5 (association, null-tested) versus §6 (ownership: 3.5 % identified). |
| 7. No exact allocation claim without ids | **Met**: no exact allocation reconstruction is claimed. |

## 9. Limits

* Sub-minute order of body decisions is unknown; "subsequent" relies on first-fill times at 1 s.
* The ATM definition is strike distance to the last completed minute's index close, not a quote-based ATM.
* The time-shifted null preserves session and right but not intraday activity clustering; excess ratios near 1–1.5 should not be over-read.
* Allocation definitions (slot, chain) are hypotheses carried over from phase 1; model C's inheritance is an assumption.
* All dates were inspected in earlier phases; this is descriptive reconstruction, not out-of-sample validation.

## 10. Consequences

* **Readiness row 13 (re-entry and replacement)** stays **Approximate – low**. The replacement association within 60 s is now quantified (Clock-B 3–4× null; ≈ 70 % of Clock-B lots re-sold within 60 s if competition is ignored), but the replace / don't-replace trigger, the strike rule and allocation ownership are not recovered. The 34 % index is unchanged.
* **Recovered state machine (observed, not causal):** OPEN → ADD … → REDUCE (one lot) → [REPLACE within ≈ 1 min, usually at another strike, or nothing] → … → CARRY → REDUCE / FINAL CLOSE. Side-level reductions do not lead to replacement; Clock-B rebalances and basket reductions often do.
* **What would resolve ownership:** allocation or parent-order ids; failing that, order-lifecycle logs (which order was pending when the re-sale was decided) and sub-minute decision times.
