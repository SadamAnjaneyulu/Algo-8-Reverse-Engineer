# Ordering semantics of whole-second fills (N1)

**Rule.** The source timestamps have one-second resolution. The system therefore *observes* the order of events only **between** seconds. Anything finer is a convention.
A deterministic output order is never described as historical chronology.

## What is promised, by layer

| Layer | What the system orders | Status |
|---|---|---|
| Events at different timestamps | by timestamp | **observed** |
| Fills of the **same instrument** inside one second | by the scenario policy: baseline = source-file row; sensitivity policies = a per-contract key, then source row | **convention** (`SOURCE_ROW_ORDER_CONVENTION` or a sensitivity-only policy); not verified chronology |
| Fills of **different instruments** inside one second | the baseline serialization (source-file row) under **every** scenario | **serialization only**; the project uses no cross-instrument order and claims none. (For SENSEX the embedded nanosecond time agrees with file order for 87 % of adjacent cross-instrument same-second pairs, so it may carry cross-instrument information; whether it is a venue-wide clock was not shown and no result depends on it.) |
| Portfolio (aggregate) state after a fill | after the **last** fill of a second, **inventory (aggregate and per instrument), cash and cumulative gross opened/closed units** are identical under any ordering of that second's fills. **Not invariant even at second end** (they depend on same-instrument order): cumulative FIFO/LIFO realized P&L, per-module (tag) opened/closed units, reversal counts. Every earlier state inside a second with more than one fill depends on an unobservable order | `SECOND_END_INVENTORY_CASH_INVARIANT` vs `UNORDERED_WITHIN_SECOND` |

## The defect (N1) and its measurement

Before this fix the keyed policies (`trade_id`, `order_no`, `sensex_trade_id_time`, `per_contract_id_sequence`) sorted the whole second's events by one tuple `(timestamp, key, source row)`.
The keys have per-contract meaning (a NIFTY trade id is a per-contract counter; a SENSEX key is an embedded nanosecond time), so the sort compared a NIFTY key such as `3109390` with a SENSEX key such as `1782272760351084326`: a comparison with no meaning.

Hand-calculated example (rows 10-13, one second; baseline serialization 10, 11, 12, 13): NIFTY rows 10 and 12 have keys 300 and 100; SENSEX rows 11 and 13 have keys 900000 and 800000.
Local ordering gives **12, 13, 10, 11** (each instrument reordered inside its own slots). The old global sort gave **12, 10, 13, 11**. Test: `test_keyed_order_never_compares_keys_across_instruments_hand_calculated`.

Measured on the full ledger (`reports/m2f_audit/n1/n1_measure.py`, result in `n1_measure_result.json`), old global sort vs local ordering:

| Policy | Stream positions that differ | Intermediate aggregate gross states that differ | Max difference (units) | Per-instrument sequences equal |
|---|---:|---:|---:|---|
| `per_contract_id_sequence` | 8,196 of 41,421 | 2,532 | 7,150 | yes |
| `trade_id` | 8,199 | 2,534 | 7,150 | yes |
| `order_no` | 1,734 | 1,218 | 3,250 | yes |
| `sensex_trade_id_time` | 2,296 | 644 | 740 | yes |

* **Per-instrument accounting was never affected** (every instrument sees the same fill sequence under both sorts), so every R1 / R1-C accounting number stands.
* **The global event stream and every intermediate portfolio state of a sensitivity scenario were affected.** Under the baseline nothing changed (the baseline has no key).
* Even the *local* ordering moves intermediate aggregate states: local vs baseline, 681 stream positions and 509 intermediate aggregate gross states differ for the hybrid (66 and 9 for `sensex_trade_id_time`).
* The **inventory, cash and gross opened/closed units at the end of every second are identical** under the baseline, the local ordering and the old global sort (verified for all four policies). Cumulative realized P&L, per-module opened/closed units and reversal counts are **not**: under the hybrid, cumulative FIFO realized differs at 1,514 second-ends, LIFO at 1,155, per-module units at 6,527 (780 units, the 626,765 vs 625,985 body-unit difference) and the reversal count at 6,527 (independent review, CR-01, from the raw CSV). **Cross-instrument interleaving alone changes none of them** (0 differences in 12 random interleavings that keep every instrument's order).

**Severity: Medium.** No delivered output was affected; sensitivity-scenario portfolio paths (not accounting) were.

## Event-processing designs compared

| Criterion | A. global keyed sort (old) | B. local (instrument, second) order + baseline serialization (**adopted**) | C. atomic second: per-instrument transitions inside the second, portfolio state only at the end of the second (**usage rule**) |
|---|---|---|---|
| Per-instrument accounting | correct | correct (same sequences) | correct (same as B) |
| Aggregate inventory at second end | invariant | invariant | invariant, and the only state published |
| Cash | invariant at second end | invariant at second end | invariant at second end |
| Intermediate portfolio states | arbitrary (meaningless cross-key order) | deterministic but **not chronology** | not published; flagged `UNORDERED_WITHIN_SECOND` |
| Same-second risk decisions | ill-defined | ill-defined (depends on the serialization) | defined only on the second-end state |
| Python / C++ | Python only | Python only for keyed policies; baseline unchanged and byte-parity-tested | needs second-boundary snapshots in the engine (M3) |
| Reproducibility | deterministic | deterministic | deterministic |
| Invents an unobservable chronology? | yes | no claim is made, but a reader could mistake the serialization for one | **no**: it assumes less than B |

**Decision recorded (engineering, within the owner's directive):** B is implemented in `replay.order_events` (`_local_keyed_order`) as the *serialization*; C is the *rule for use*: portfolio-level analysis of any scenario may use per-instrument position transitions and **second-end** portfolio states only. Scenario outputs carry `inventory_series_intra_second_flags.tsv` (`SINGLE_FILL_SECOND`, `SECOND_END_INVENTORY_CASH_INVARIANT`, `UNORDERED_WITHIN_SECOND`); every scenario manifest carries `ordering_semantics`.

## Accepted limitation (formal)

Until the engine takes snapshots only at second boundaries (M3), **no portfolio-level event-path interpretation (intra-second exposure, peak intraday inventory inside a second, same-second risk decision) is authorized for any scenario**, baseline included. This is not specific to the hybrid: the baseline's intra-second aggregate path is also only a serialization.

## Verification
* Hand-calculated and bucket-boundary tests: `tests/test_tie_order_policy.py` (N1 section); scenario and flag tests: `tests/test_scenario.py`.
* Mutation harness `reports/m2f_audit/r1/mutation_harness_N1.py`: 9 of 9 mutants killed by the intended assertion (global sort, reversed source-row tie-break, policy name ignored, SENSEX keyed like a NIFTY counter, SENSEX time rule on NIFTY, bucket widened to two seconds, bucket without the second, bucket without the instrument, one policy left global); results in `mutation_results_N1.json`, with the assertion message of each kill.

## Independent-review notes (closure review, 2026-11-16)
* **CR-01 (Medium, fixed here):** the invariance claim is limited to inventory, cash and gross opened/closed units (see the table and the flag name above); a counterexample test is in `tests/test_scenario.py`.
* **CR-04:** C2 closing-batch membership depends on the tie-break among equal-first-second parents (C1 does not): 60 random tie-breaks give C2 counts of 7,126-7,127 / 3,776-3,777 / 3,064-3,065 at 2 / 5 / 10 s, constant at 30 / 60 s. This is the same serialization dependence as in `M2F_METHODOLOGY_LIMITATIONS.md` section 7.
