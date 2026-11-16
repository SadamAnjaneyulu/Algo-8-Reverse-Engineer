# Track B - closing-batch methodology audit (M2-C: C1 first-fill, C2 last-to-first)
HEAD 7117bbce. Read-only on repo; outputs only in this folder; mutation mirror in scratch. Classes: [RAW] raw-source, [IMPL] own re-implementation, [INV] invariant, [REPRO] reproducibility. Labels VERIFIED / INSPECTED / SUSPECTED / NOT VERIFIED. No XLANG verification was performed (NOT VERIFIED).

## Method
Approved text read first (tp03/config.yaml exit.batch, BASKET_GROUPING_METHODOLOGY.md D2, ontology, M2C report and addendum), own reading derived, then `ref_closing.py` written (stdlib only, no pe import): own position replay of the raw 41,421 fills, parent units via closing portions, stream = underlying x expiry x IST session, order (first closing second, smallest closing row, parent id), inclusive gap, single linkage over adjacent parents, C2 previous-parent last fill. Implementation read afterwards.

## 1. Reference vs committed outputs (all ten views, full ledger) - VERIFIED [IMPL]/[RAW]
0 differences in: batch partitions, counts, n_parents, portions, quantities, start/end/duration, n_links, max_link_gap, member join gaps, overlap/strict-overlap flags, portion membership (row, quantity), batch id numbering (`compare_committed.py`, `compare_links_committed.py`). Closing units 1,377,065 from a raw-only minimal loop equal the batch sums in all views. Committed gz files match manifest hashes [REPRO]. Source row ids are 0-based (documented in SCHEMAS.md; CSV line = id + 1).
No interpretation difference arose between my reading and the author's for the approved convention.

## 2. Ambiguity of the approved method - measured ([IMPL], `ambiguity_measure.py`, `ambiguity_result.json`)
Columns: g = 2/5/10/30/60 s. "Changed" = batches only in the alternative / only in base.
| Ambiguity | Alternative | Impact (C1 and C2 unless stated) |
|---|---|---|
| Tie order among equal first-second parents | parent-id only, last-then-row, min-row-any-fill, numeric-aware id, reversed id | C1: 0 (provably invariant). C2: 0 for min-row-any/numeric/reversed; parent-id-only and last-then-row: 1 batch fewer at 2/5/10 s (4 parents), 0 at 30/60 |
| C2 reference | running max over chain / over stream | 1 fewer batch at 2/5/10 s (changed 1/2, 4 parents), 0 at 30/60; max chain length unchanged |
| Inclusive vs exclusive threshold | gap < g | changed 1,214/553, 840/399, 153/74, 50/25, 63/30; batches 7,788/4,218/3,144/2,196/1,535 vs 7,127/3,777/3,065/2,171/1,502; max parents 78/95/122/128/198 (base 78/96/122/128/198) |
| Mixed parents (26) | exclude | batches 7,122/3,774/3,063/2,171/1,502; 150/447/584/760/1,350 parents in changed batches; max parents 78/92/118/127/197 |
| Timestamp of a mixed parent | any fill instead of closing only (first and/or last) | 0 (no mixed parent has an opening fill before its first closing fill) |
| Stream boundary | underlying only; und x session; und x expiry (D-1/D0 merged) | 0 on this data (no parent spans sessions/instruments; no cross-expiry adjacency within 60 s) |
| Unit | order number (col 4, 16,435 units) instead of tag (col 163, 16,817) | 0 changed partitions |
| Replay tie order of same-second opposite fills | sells_first / buys_first | 2 / 4 fills change open/close split; 1 / 2 batches replaced at every g; 9-171 / 10-322 portions in changed batches (see B-01) |
| Linkage (context, not approved) | anchor-based non-transitive | batches 7,464/4,732/3,816/2,779/2,195; max parents 30/50/78/106/122 (single linkage 78/96/122/128/198) |
Baseline max chain: parents 78/96/122/128/198; duration 57/66/125/481/1,175 s (matches report, all thresholds). None of these choices was decided here.

## 3. Synthetic boundaries (`synthetic_lib.py`, `synthetic_boundaries.py`) - VERIFIED [IMPL]
14 hand-built cases (gap == g and g+1 at each threshold, equal timestamps with shuffled ids/input order, multi-fill parents, overlapping intervals, mixed parents, parents across instruments/expiries/underlyings, IST midnight and UTC midnight, 30-link chains with gap == g, C2 prev vs running-max, reversal) + 6 hand-derived expectations + 600 fuzz scenarios x 10 views: engine == reference everywhere (175 fuzz scenarios have C1 != C2). Missing/NaN timestamp: engine raises incidental TypeError/ValueError (B-05).

## 4. Chains, cycles, C1/C2 - VERIFIED [IMPL]
Longest clusters, pair counts, nesting and identical-batch counts reproduce the reports. Frozen cycles (each spans D-1 and D0 sessions, so two streams): NIFTY 2026-06-30: 107/63/53/45/36 batches, 382 parents, 66,170 units; SENSEX 2026-07-16: 79/33/25/22/14 batches, 264 parents, 14,180 units (C1; C2 identical). C2 == C1 holds only under the implemented convention (section 2).

## 5. Number block - VERIFIED [INSPECTED]
Documented UNRESOLVED (D2, M2C_NUMBER_BLOCK_AUDIT.md); no implementation in code/outputs; the diagnostics tool is descriptive only. Not interpreted by me.

## 6. Mutation testing (`run_mutations.py`, `mut_detector.py`, `mutations.json`)
28 mutants on a scratch mirror. Existing 25 tests kill 27; survivor **M22** (summarize `pairs_linked` `<`). Own reference kills 25; own survivors **M13** (parent qty attribution; caught only by [REPRO] hash), **M23** (nested forced True; equivalent on real data), **M28** (missing parent-id handling; no scenario in my detector). M14, M25, M26 are killed by existing tests only via the committed-manifest hash snapshot. Real-data-invisible mutants (M04/M05 C2 collapse; M07-M09, M19 boundary merges) are killed only on synthetic input. Failures inspected: assertion failures, no unrelated crashes. Baseline detector run: 0 mismatches.

## Defects
B-01 Medium (closing identification tie sensitivity undisclosed), B-04 Medium (test gaps / snapshot-only kills), B-02, B-03, B-05, B-06, B-07 Low. No Critical or High defects found. Details in defects.json.

## Not inspected
C++ side; M1 replay internals beyond agreement of outputs (my replay agrees exactly); wing/body, M2-D/E; figures and C1/C2 plots; the numeric content of M2C_UNIT_AUDIT; full pytest suite beyond test_closing_batches.py; the claim texts of tp_reconstruction beyond the batch spec; cross-language verification.
