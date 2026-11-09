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

## 5. Consequences for the audit

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
