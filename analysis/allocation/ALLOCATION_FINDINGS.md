# Algo 8 — Allocation-level reconstruction (phase 1)

Branch `research/algo8-allocation-reconstruction`, stacked on PR #4 (`28739d50`). Every number below comes from scripts in
`analysis/allocation/` that were **executed** on the clean order table (column 163 key), with outputs in `results/`.
Five unit tests pass (`python -m pytest analysis/allocation/tests`). No model was fitted; the only tuned quantity is one
threshold per reference in T3, chosen on DEV and applied unchanged to VAL and TEST. `alpha_freeze/`, existing research code,
model thresholds and raw trade data are untouched.

## 1. Requirement lock

| Item | Locked specification |
|---|---|
| **Question** | Does Algo 8 manage its book as one aggregated position, or as independent allocations, each with its own entry, size, hedge and exit? |
| **Data** | Clean order table (39,874 orders, 35 cycles), Breeze 1-min bars, unit-lot book from the actual fills. **Allocation ids are not in the data.** |
| **Allocation definitions** (all three built, reported separately, none assumed correct) | **(a) Slot:** one allocation per (cycle, date, schedule slot k, right); slot = nearest 09:16 + 15k clock, entry first fill in [clock − 2 s, clock + 180 s); other sells are "extra" (per sale burst). **(b) Chain:** lineage Y's timer-phase chains (`chains.py` algorithm, unchanged) re-run on bursts rebuilt from the clean orders (burst = body sells > 4 s apart; this gap reproduces the legacy cache's 5,481 bursts exactly on the legacy table). Detection is per underlying-day (the legacy cache had no underlying column). **(c) Lot:** every unit lot is its own allocation. |
| **Hedge link** | A wing (long entry) joins the allocation of the nearest same-right body sell within ±10 s (92.8 % linked, 7.2 % `unlinked`). |
| **Closing ownership** | Not observable. Fixed by convention: `cheap` (cheapest entry closes first), `fifo`, `lifo`. All three are reported. |
| **Splits** | DEV 18 / VAL 8 / TEST 9 cycles, unchanged. TEST is not an unseen period (contaminated for hand constants). |
| **Metrics** | T1 closure granularity; T2 hit@1 / hit@3 / mean rank of the contract actually bought back; T3 AP of the raw ratio and precision / recall at a DEV-chosen threshold; T4 wing coupling against 1,000 within-(cycle, right, day) permutations. |
| **Not done** | Replacement / re-entry continuity (Clock-B re-sales are off-grid by construction in (a) and (b), so they cannot be tested with these definitions); no new modelling; no change to any frozen finding. |

## 2. What was built (code written, executed, outputs inspected)

* `alloc.py`: the three definitions, the per-allocation ledger and the lot ledger. Outputs:
  `allocation_ledger_slot.csv` (6,545 short allocations), `allocation_ledger_chain.csv` (4,355), `allocation_lots.csv.gz`
  (32,196 unit lots with both allocation ids) and `allocation_summary.txt`.
* Ledger columns per allocation: **entries** (`n_short_lots`, `n_entry_orders`, strikes, first / last entry, mean entry
  price); **hedge** (`wing_lots`, `wing_lots_released`); **stop and exit history** (`closed_<label>` counts by exit class,
  by the stated lot convention); **re-entry** (`reentry_lots`); **final state** (`n_survive_lots`, `last_exit`, carried
  lots). Quantity changes over time are the lot-level entry and exit rows in `allocation_lots.csv.gz`.
* Shape of the hypotheses: **slot** allocations average 2.26 lots (median 1, p90 4, max 122; 56 % single-lot); **chain**
  allocations average 3.40 (63 % single-lot). 47.6 % of short entry orders fall on a schedule slot and 51.8 % in a
  significant chain. Because most allocations are one or two lots, many allocation-level references equal the lot-level one
  by construction; this limits what the tests can separate (see §4).

## 3. Results

### T1. Closure granularity (cheap convention; fifo and lifo agree within ±0.05)

| Day | Stop orders | Lots closed per order | Allocations holding the contract (slot / chain) | Closes fewer lots than **every** candidate allocation (slot / chain) |
|---|---:|---:|---|---|
| D-1 | 691 | 1.000 | 4.2 / 3.5 | 19 % / 15 % |
| D0 | 2,554 | 1.083 | 10.6 / 8.7 | 6 % / 7 % |

A stop buy-back closes one lot. In 81–86 % of D-1 cases some candidate allocation has exactly one lot left, so a
whole-allocation close cannot be excluded for them. In **14–19 % of D-1 stops no candidate allocation is a single lot**, so
those stops are **inconsistent with an allocation-sized stop** under that definition. T1 alone is weakly discriminating
because single-lot allocations are common.

### T2. Which contract is bought back (D-1, 691 orders; random hit@1 = 0.115)

| Reference (previous close ÷ reference, highest ratio first) | hit@1 | hit@3 | Paired hit@1 difference vs lot-level (90 % cycle-bootstrap) |
|---|---:|---:|---|
| **Lot level:** cheapest open lot | **0.560** | 0.986 | — |
| Slot-allocation average entry (min over slots) | 0.551 | 0.988 | −0.009 [−0.023, +0.005] |
| Chain-allocation average entry (min over chains) | 0.556 | 0.984 | −0.004 [−0.024, +0.015] |
| **Aggregate:** contract average entry | 0.493 | 0.977 | **−0.067 [−0.099, −0.034]** |
| Newest open lot | 0.496 | 0.961 | −0.064 [−0.110, −0.017] |
| Most expensive open lot (negative control) | 0.433 | 0.948 | −0.127 [−0.166, −0.086] |

D0 (2,554 orders, random 0.088): lot level 0.365, slot 0.363, chain 0.351, **aggregate 0.231** (lot level minus aggregate
+0.134 [0.082, 0.192]). The aggregate reference loses under cheap, fifo and lifo; the allocation-average references never
beat the lot-level one (D-1 differences ≤ 0.014; the fifo-slot interval just excludes zero in the lot level's favour). Table values are
reference minus lot level, cheap convention; the newest-lot gap is not significant under lifo. The negative control still scores far above random, so a high ratio alone ranks contracts well;
the comparison is the paired difference, not the absolute hit rate.

### T3. Reference sharpness at contract-minute level (D-1; AP of the raw ratio, no fitting)

| Reference | DEV (168 events) | VAL (63) | TEST (127) |
|---|---:|---:|---:|
| Lot level (cheapest open lot) | 0.362 | 0.241 | 0.394 |
| Slot-allocation average | 0.347 | 0.231 | 0.372 |
| Chain-allocation average | 0.332 | 0.212 | 0.355 |
| Aggregate contract average | 0.221 | 0.127 | 0.322 |
| Newest lot | 0.212 | 0.119 | 0.304 |
| Most expensive lot (control) | 0.145 | 0.093 | 0.269 |

The ordering is identical on all three splits. At the DEV-best threshold of 1.60, the lot-level reference has TEST
precision 0.31 / recall 0.54; none of the references is a clean rule. **D0 is weak for every reference** (AP 0.05 on VAL and
TEST), consistent with the earlier finding that D0 stops are not a simple price-crossing rule.

### T4. Wing coupling

Of the wings released ('L-hedge release') with a same-side short closing within 60 s, the share whose entry allocation
equals the allocation of a closed short:

| Definition | Observed | Permutation null (mean; 95th pct) | n |
|---|---:|---|---:|
| Slot | 26.6 % | 17.7 %; 18.4 % | 4,365 |
| Chain | 40.6 % | 34.5 %; 35.3 % | 4,365 |

(fifo / lifo within ±2 points.) There is a statistically clear but **modest** excess: 6–12 points above a null that holds
cycle, right and release day fixed. About three quarters (slot) and three fifths (chain) of releases are **not** with their
own allocation's short. An earlier version of this test permuted across rights and overstated the excess (8.0 % null); it
was corrected before reporting.

## 4. Interpretation and limits

| Statement | Status |
|---|---|
| The per-lot stop reference is the individual entry (or a very small allocation), **not an aggregate contract position**. | **Supported** (T2 and T3, all three conventions and all three splits; D-1 aggregate is 6–7 points worse in hit@1 and 0.07–0.14 lower in AP across DEV / VAL / TEST). |
| The book is **also** managed in aggregate at cycle level (cumulative MTM stop). | Supported earlier (≈ −₹1.30–1.35 L); not re-tested here. So "one aggregated position **or** independent allocations" is a false dichotomy: Algo 8 looks like **both**. |
| Schedule-slot or timer-chain **averages** are a better stop reference than the individual lot. | **Not supported** (never better; the difference with the lot level on D-1 is at most 0.014 in hit@1 and indistinguishable from zero for most conventions). |
| Allocation-**sized** stops. | **Partly contradicted**: stops close one lot; 14–19 % of D-1 stops are inconsistent with a slot or chain allocation-sized close. |
| Slot or chain allocations are real, independent decision units. | **Not identified in the available data.** T2 and T3 cannot separate "per lot" from "per small allocation" (56–63 % of allocations are single lots); the allocation ids are hypotheses. |
| Wings follow their own allocation. | **Weakly supported** (T4, +6 to +12 points); not a rule. |
| D0 stops are allocation- or aggregate-driven. | Not supported by any tested reference (AP ≈ 0.05). |

Adversarial notes:

* Ownership of closed lots is a convention. The lot-level result holds under all three, but they are not independent
  checks (they share the same fills).
* Chain detection was re-implemented per underlying-day on clean bursts; it is **not** the legacy chain table.
* A real allocation id (decision log) would settle the definition question; this phase could not.
* 125 unit lots (0.4 %) are opened by close-labelled orders (position flips) and carry the label `nonentry`.

## 5. Consequences for the audit (phase 1; superseded by §10)

* Readiness row 8 (individual stops) stays **Approximate – low**: the reference level is now better characterised
  (lot-level, not aggregate), but the constant, the D0 scope and allocation ownership are still unresolved.
* The 34 % readiness index is unchanged. The allocation question is **not resolved**; it is narrowed.
* Next, in order: (1) **stop-reference constant using the recovered per-order quotes** (limit ÷ 1.15 / 0.85) on the lot-level
  reference; (2) test allocation definitions with a **tighter** discriminator (stops where the cheapest lot and the
  allocation average disagree by more than the band), which needs the quote timing from (1); (3) replacement / re-entry
  continuity with a definition that can represent Clock-B re-sales.

## 6. Files

`alloc.py` · `falsify.py` · `tests/test_allocation.py` · `results/allocation_ledger_{slot,chain}.csv` ·
`results/allocation_lots.csv.gz` · `results/allocation_T1…T4_*.csv` · `results/allocation_T2_paired_bootstrap.csv` ·
`results/allocation_falsification_report.txt` · `results/allocation_summary.txt`.

---

# Phase 2 — the exact per-lot stop reference and constant, and the discriminating allocation test

## 7. Pre-registered design (written into `stop_reference.py`, `stop_select.py`, `stop_discriminator.py` before the results were read)

| Item | Specification |
|---|---|
| **Question** | Does ONE reference-price formula and ONE stop constant *k* explain the actual stop-like buy-backs? |
| **Quotes** | The algo's own decision quote is recovered from each order's limit band (buy: limit ÷ 1.15). It is used (i) to confirm a match (*L<sub>b</sub>* ≥ *k* × reference) and (ii) at exit level (ratio of the recovered quote to the references). **Crossing times are bracketed to the minute only:** Breeze bars are 1-minute and body orders are stamped to the minute; exact intraminute first-crossing timestamps are not identifiable. |
| **Rule simulated** | Unit crossed in minute *m* when the minute **high** ≥ *k* × reference, built only from lots **open at the start of *m*** (entered in an earlier minute and not yet closed under the convention, so already-closed lots are excluded). Event = rising edge; **first** crossing = first edge of the unit on a day, later edges are **repeated**. |
| **References (6)** | own entry (per lot) · cheapest open entry · slot-allocation average · chain-allocation average · lot-weighted contract average · order-average contract (each entry order once). |
| ***k* grid** | 1.40 … 2.00 in steps of 0.05. |
| **Matching** | One actual buy-back ↔ at most one event; each event used once (greedy, time order). Match = same contract, buy-back minute in [crossing minute, +*W*], and own quote ≥ *k* × reference. Primary *W* = 2 min; *W* = 5 and association-only (no quote test) are sensitivities. |
| **Responder pools** | **S** = buy-backs labelled "individual lot stop-loss" (that label uses cheapest-entry ≥ 1.45×, so it is circular for the cheapest reference); **U** = every non-scheduled, non-clock closing short buy-back (label-free). |
| **Segments** | D-1 fresh · D0 fresh (no carried lot open) · D0 carried (all open lots carried) · D0 mixed (reported, not hidden). |
| **Selection** | *k* chosen on **DEV only** (maximum F1): once per segment and once globally per (convention, reference). Applied unchanged to VAL and TEST. No TEST tuning. |
| **Conventions** | cheapest-first, FIFO, LIFO, each reported. |
| **Metrics** | precision, recall, stop-consistent coverage, false triggers, missed exits, first vs repeated precision, 90 % cycle-bootstrap intervals (2,000 resamples of the split's cycles). Segments need ≥ 30 events and ≥ 30 buy-backs to be assessed. |
| **Verdict rule** | A single (reference, global *k*) *explains* the stop-like exits only if precision ≥ 0.80 **and** recall ≥ 0.80 on VAL and TEST in every assessable segment under every convention. Otherwise UNKNOWN is retained. |

## 8. Results (executed; `results/stop_ref_*.csv`, `results/stop_ref_report.txt`; 9 unit tests pass)

### 8.1 Verdict: UNKNOWN retained — 0 of 18 (convention × reference) global rules meet 80 / 80 in any assessable cell

Cheapest-first convention, pool S, *W* = 2 min quote-confirmed, global *k* chosen on DEV, all segments pooled. 90 % cycle-bootstrap intervals in brackets.

| Reference | *k* (DEV) | VAL precision | VAL recall | TEST precision | TEST recall | Coverage VAL / TEST |
|---|---:|---|---|---|---|---|
| Own entry (per lot) | 1.55 | 0.295 [0.21, 0.38] | 0.663 [0.57, 0.75] | 0.268 [0.21, 0.32] | 0.627 [0.58, 0.68] | 0.85 / 0.88 |
| Slot-allocation average | 1.50 | 0.363 [0.29, 0.44] | 0.531 [0.48, 0.59] | 0.277 [0.22, 0.33] | 0.525 [0.47, 0.57] | 0.93 / 0.93 |
| Chain-allocation average | 1.50 | 0.382 [0.32, 0.45] | 0.454 [0.40, 0.52] | 0.292 [0.24, 0.34] | 0.493 [0.46, 0.54] | 0.90 / 0.93 |
| Cheapest open entry | 1.65 | 0.424 [0.38, 0.47] | 0.121 [0.10, 0.15] | 0.346 [0.28, 0.41] | 0.173 [0.14, 0.20] | 0.68 / 0.66 |
| Lot-weighted contract average | 1.45 | 0.272 [0.20, 0.34] | 0.084 [0.05, 0.13] | 0.283 [0.24, 0.31] | 0.171 [0.15, 0.20] | 0.46 / 0.72 |
| Order-average contract | 1.45 | identical to the lot-weighted average (entry orders are almost all one lot) | | | | |

* **Segments (own entry, cheapest-first, TEST):** D-1 fresh 0.30 / 0.57, D0 fresh 0.26 / 0.64, D0 carried 0.09 / 0.49 (precision / recall; carried TEST has only 43 buy-backs). Selecting *k* per segment on DEV gives the same picture.
* **First vs repeated crossings (own entry, TEST):** first-crossing precision 0.31, repeated 0.21. Repeated crossings are answered less often, but both are far from 0.80.
* **False triggers and missed exits (own entry, TEST):** 1,011 of 1,381 events unanswered; 220 of 590 stop buy-backs have no matching event. Cheapest open entry reverses the trade-off (193 false triggers but 488 missed exits).
* **Fifo and lifo** give the same verdict (best DEV *k* between 1.45 and 1.70, depending on reference and convention; best precision, recall in the same range).
* **Oracle ceiling (informational, not a selection):** choosing *k* on each split's own data, the best F1 is 0.56 (own entry, quote-confirmed, pool S), and the best min(precision, recall) over every reference, segment, split and convention is 0.52 for the primary variant and 0.66 for association-only matching. **No constant on this grid could reach the bar.** The label-free pool U is lower still (best F1 0.45 for the primary variant).

### 8.2 What the data do support: a necessary lower edge near 1.50× the lowest individual entry

Recovered decision quote of each actual stop buy-back divided by the lowest open entry price (cheapest-first; DEV / TEST / VAL):

| Segment | 5 % | median | 95 % |
|---|---|---|---|
| D-1 fresh | 1.50 / 1.51 / 1.51 | 1.65 / 1.67 / 1.63 | 1.86 / 1.84 / 1.84 |
| D0 fresh | 1.51 / 1.48 / 1.49 | 1.82 / 1.85 / 1.74 | 3.65 / 2.51 / 2.78 |
| D0 carried | 1.47 / 1.50 / 0.85 | 1.71 / 1.74 / 1.70 | 2.35 / 3.26 / 2.44 |

For the contract-level average the D-1 lower edge is 1.33–1.36 (median 1.52–1.56): wider and further from any round number. So **about 95 % of stop buy-backs happen when the quote is already ≥ 1.5× the lowest individual entry** (D-1 coverage 0.95 on DEV at *k* = 1.50), a stable fact across splits and conventions. But it is **necessary, not sufficient**: crossing it is followed by a matching buy-back with precision of only 0.3–0.46 at the *k* values that keep recall near 0.5, and the response is spread over time (matched pairs, own entry, *k* = 1.55, *W* = 5: 21 % in the crossing minute, 38 % the next, 41 % two to five minutes later; `stop_lag.csv`). A deterministic per-minute rule would respond immediately; this one does not. Why the algo waits or skips is not identified in the available data.

### 8.3 Discriminating allocation test — events where individual entries differ materially (≥ 10 %) from the average

Rows and actual stop buy-backs where the lowest individual entry is at least 10 % below the slot / chain / contract average. Three tests, pre-registered; all splits, three conventions:

| Test | What it asks | D-1 | D0 |
|---|---|---|---|
| **Exit level** (spread of log[recovered quote ÷ reference], 90 % cycle bootstrap) | Which reference gives the tighter ratio at actual stops? | 9 of 9 cells inconclusive (IQR differences ±0.02) | Lot-level tighter vs the **contract average** in 3 cells (e.g. DEV 0.21 vs 0.41), inconclusive in 15; the average is **never** tighter |
| **Matched hazard** (same lot-level ratio; high vs no dispersion) | Does the stop hazard fall when the average is far away at the same lot-level ratio? | 5 cells say the average (all **chain**, ≤ 12 stop minutes in the high group); 6 consistent with lot-level; 5 inconclusive | 0 cells favour the average; for the **contract average**, high-dispersion rows have a **higher** hazard (+0.03 to +0.10) |
| A / B hazard ratio θ (secondary, **confounded**: region B has a higher lot-level ratio by construction) | | θ 0.11–0.24 in 7 fifo / lifo cells; underpowered (≤ 17 stop minutes in B) | θ > 1 in 14 cells |

Reading:

* **The contract-level average is rejected as the stop reference** on D0 (never tighter, and the hazard does not fall as the average moves away) and is not supported on D-1. This agrees with phase 1.
* **Slot- and chain-allocation averages cannot be separated from the individual entry.** Most dispersed rows involve a handful of events, and the **chain** definition shows a weak, underpowered counter-signal on D-1 (hazard 2–6 points lower at 3–12 stop minutes) that is not stable across conventions. Allocation identity therefore remains **not identified in the available data**.
* The test is sensitive to the allocation definitions, which are unvalidated hypotheses.

## 9. Limits and adversarial notes

* **Timestamps:** crossings are bracketed to the minute; sub-minute order of price and order cannot be recovered. The quote test (own LTP at decision) is the only exact price evidence.
* **Matching strictness:** one buy-back ↔ one event penalises per-lot rules (many crossed lots, one closed at a time). The association-only variant, the *W* = 5 variant and the exit-level coverage show the conclusion does not depend on that choice (best min precision / recall 0.52–0.66).
* **Label circularity:** the pool-S label uses a 1.45× cheapest-entry threshold; the label-free pool U gives lower scores, not higher.
* **Ownership convention** is unobservable; all three give the same verdict.
* **TEST** is not an unseen period and carried segments are small (43 TEST buy-backs).
* The cheapest-open reference is also affected by how the stop module closes the cheapest lot first, so its low recall is partly structural.

## 10. Consequences

* **Stop constant and reference: UNKNOWN retained.** Best single formula (own entry per lot, *k* ≈ 1.5–1.65) gives precision ≈ 0.27–0.46 and recall ≈ 0.5–0.7; no rule reaches 80 %.
* **Established:** a stable necessary lower edge ≈ 1.50 × lowest individual entry (D-1 fresh, D0 fresh and, with few observations, D0 carried); the reference is an individual entry or a small allocation, not the contract average.
* **Readiness:** row 8 (individual stops) remains **Approximate – low (0.25)**; the 34 % index is unchanged (see the updated readiness matrix and register in `audit/`).
* **Next:** (1) explain **non-response** (why most 1.5× crossings are not stopped within five minutes): candidates are poll cadence, one-lot-per-cycle throttling and portfolio-state gates; this needs per-order lifecycle data or timestamps finer than a minute; (2) replacement and re-entry continuity with a definition that can represent Clock-B re-sales; (3) additional historical trade data for unseen validation.
