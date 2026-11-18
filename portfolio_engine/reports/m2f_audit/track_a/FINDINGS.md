# TRACK A - Accounting and position lineage: final audit findings (M2-F)

Scope: schema, ledger, replay, invariants, lineage, lineage_set, parents, tsvio, provenance, generators/historical, C++ core, parity tools, lineage rules docs, M1/M2B reports.
Repo HEAD 7117bbce, read-only. All outputs here and in scratch only. Labels: VERIFIED = executed and seen; INSPECTED = read only; SUSPECTED; NOT VERIFIED.
Verification classes: [RAW] raw-source check, [IMPL] independent re-implementation, [XLANG] cross-language consistency only, [INV] internal invariant only, [REPRO] reproducibility only.

## 1. Independent reference (ref_model.py) - VERIFIED [RAW]+[IMPL]
Built from Trades_GKOHNP140.csv with csv.reader (no pandas, no pe.*, no TP-01 parquet): signed net position per instrument (underlying|expiry|right|strike), opening vs closing quantity per fill (reversing fills split), episodes, lifecycle events, closing allocations for FIFO, LIFO (lot list) and AVG (exact Fractions); FIFO also implemented a second way (cumulative-interval overlap) and the two agree. Raw columns verified: 4 order no, 11 side, 12 underlying, 14 strike, 15 expiry, 16 right, 19 order qty, 20 remaining, 27 status, 33 fill qty (units), 137 per-fill price, 161 UTC epoch, 163 parent id, 166 app key. Col 18 is the running order average (not used).
Exclusions: none. 41,421 rows, 0 invalid (side, qty>0, 5-paise price grid, qty multiple of lot, timestamps non-decreasing); 0 identical rows; 0 flagged duplicates; 561 same (parent,qty,price,second) groups all with distinct trade ids.

### Comparison with committed engine outputs (compare_ref_vs_engine.py; engine only LOADED) - VERIFIED
| item | reference | engine | exact matches / mismatches |
|---|---|---|---|
| fills vs raw (8 fields) | 41,421 | 41,421 | 41,421 / 0 |
| opening allocations (OA) | 23,684 (1,414,545 units) | 23,684 | 23,684 / 0 |
| closing portions (CP) | 17,760 (1,377,065 units) | 17,760 | 17,760 / 0 |
| episodes | 2,667 | 2,667 | 2,667 / 0 (direction, opened, closed, n fills, ended_by, reversal flag, first/last ts) |
| lifecycle events | 41,444 | 41,444 | identical |
| per-fill roles (close, open, inventory_after, reversal, episodes) | 41,421 | 41,421 | 41,421 / 0 |
| CA rows FIFO / LIFO / AVG | 25,023 / 24,948 / 17,760 | same | all rows exact (AVG within 1e-5) |
| realized paise FIFO / LIFO | 210,055,200 / 209,687,450 | same | exact integers |
| realized AVG paise | 210,011,162.714088 (exact rational) | float 210,011,162.7140885 | diff 9.0e-9 |
| remaining slices FIFO/LIFO/AVG | 526 lots / 501 lots / 81 pools | same | identical |
| final inventory, cash | 37,480 abs units; cash 278,748,200 paise | same | identical |
| parent roles | 39,874 parents: 23,057 OPENING_ONLY, 16,791 CLOSING_ONLY, 26 MIXED | same | identical; 26 = 23 with a reversal fill + 3 without |
| FIFO vs LIFO convention-sensitive CPs | 15,889 | 15,889 | same set |
Observed layer identical across FIFO/LIFO/AVG in the reference too (structural: the split uses only net inventory).
TP-01 comparison (compare_ref_vs_tp01.py): position_episodes 2,667/2,667 per method; reconstructed_position_ledger pieces FIFO 25,023 and LIFO 24,948 equal as sorted (close_row, open_row, qty, pnl paise); AVG per-close max diff 3.6e-11 rupees; fill_roles 0 mismatches x 3; reconciliation_summary realized 2,100,552.00 / 2,096,874.50 / 2,100,111.63. Class: reproduction of an earlier implementation by the same project, not independent economics.

## 2. Claim verdicts (details in claims.json)
41,421 fills VERIFIED. Parent count 39,874 VERIFIED but definition-dependent (col 163; col 4 gives 37,258 and is recycled across parents). 23,684 OA / 17,760 CP / 2,667 episodes / 26 mixed parents / 23 reversals VERIFIED under src (file) tie order only. 15,889 convention-sensitive VERIFIED. Observed layer identical across conventions VERIFIED (structural). TP-01 totals reproduced VERIFIED. Integer paise, no hidden multiplier VERIFIED for FIFO/LIFO ([RAW]: FIFO realized recomputed from raw rupee text with Decimal = 2,100,552.00, x100 equals paise exactly; qty gcd NIFTY 65, SENSEX 20, so quantities are units, no lot multiplier). AVG is fractional paise held as float. Remaining expired inventory: 81 instruments, 37,480 units (71 long, 10 short); no settlement P&L inferred VERIFIED (realized = sum of closing allocations; no settlement field in pe/). NOT VERIFIED by me: M1 claim that 6 tie-ambiguous fills equal TP-01 role_ambiguity_fills.csv; TP-02 timeline row equality; M2C number-block, wing/body, M2D/E content (outside scope).

## 3. Tie-order dependency (task 3) - VERIFIED [IMPL] on [RAW]
Only fills of the same (instrument, second) can change state: 4,464 such groups (824 instruments); 56 groups mix sides (46 instruments); 2,685 same-side groups have different prices; 765 involve a single parent.
Measured against src order (FIFO; LIFO/AVG have the same identity changes), tie_order_result.json and tie_alt_keys_result.json:
| alternative order | instruments changed | episode identities changed | fills with changed open/close split | reversal fills | realized delta (paise) |
|---|---|---|---|---|---|
| sells_first | 1 | 1 | 2 | 23 | 0 |
| buys_first | 5 | 12 | 4 | 23 | 0 |
| reversed src | 18 | 33 | 49 | 22 | -400 FIFO / -1300 LIFO / 0 AVG |
| random seeds 0-4 | 12, 17, 10, 14, 15 | 20, 28, 15, 26, 24 | 33, 40, 23, 30, 37 | 22, 23, 20, 21, 21 | 0 to -400 FIFO, 0 to -1300 LIFO |
| trade id (col 28) ascending | 2 | 4 | 4 | 21 (OA 23,682) | 0 |
| order number (col 4) ascending | 2 | 4 | 4 | 21 (OA 23,682) | 0 |
M2B's disclosed figure (sells_first/buys_first: 20 fills, 5 instruments) reproduces exactly (union over the two orders). Invariant in every variant: total OA units 1,414,545, total CP units 1,377,065, final signed inventory per instrument, cash flow, number of episodes under trade-id/order-no (2,667), AVG realized total. Not invariant: which fills are OA/CP, episode ids and membership, reversal count (20-23), OA row count, FIFO/LIFO attribution (13k-18k CA pairs under global reshuffles), and realized P&L (up to 13 rupees).
Raw evidence on intra-second order: timestamps are only to the second; trade id (SENSEX ids embed a nanosecond timestamp) and order number agree with file order in 54/56 and 55/56 mixed-side groups, and DISAGREE in two (NIFTY|2026-06-23|CE|24100 rows 726-728; NIFTY|2026-07-07|CE|24450 rows 9688-9689). Which order is true cannot be decided from the file; I do not choose. See D-A01.

## 4. Other challenges (task 3)
Duplicate opening allocations: none in engine output (row-list length 41,444 = 23,684 + 17,760; unique ids). Missing CPs: none (17,760 exact). Wrong direction: all 2,667 episode directions match. Reversal allocation: all 23 reversal fills yield one CP in the closed episode and one OA in a new started_by_reversal episode (episode ids match). Partial closes: 41,444 lifecycle events identical incl. quantities. Remaining inventory: identical. Expiry boundary: no fills after expiry day; 31,293 fills on expiry day; 81 instruments non-flat (54 last-filled on expiry day, 27 the day before; 13 last fills at/after 15:30 IST, max 15:39:27); last data day = max expiry = 2026-10-22 and nothing non-flat expires that day, so the `<=` boundary and OPEN_AT_END_OF_DATA are not exercised on real data (D-A04). Duplicate flags: none exist in the data; handling exercised only synthetically and in my fuzz (892 flagged rows, 0 mismatches). Partially filled orders: col 20 = order qty - cumulative fills for every parent; 3 parents end PartiallyFilled with unfilled remainder (40/340, 40/160, 65/1755 units); 1,059 parents have multiple fills; no parent spans dates.

## 5. Python / C++ (task 4)
C++ core built in scratch (cmake, g++ 13.3, Release; 24/24 core checks passed). Raw-derived TSV written by my own script (not via TP-01 parquet).
* [XLANG] C++ vs Python on the raw-derived TSV: 5 lineage files + dump + roles byte-identical for FIFO/LIFO/AVG x src/sells_first/buys_first (63 file comparisons, 0 diffs).
* [RAW]+[IMPL] C++ outputs parsed and compared with the independent reference (src order): OA, CP, lifecycle, episodes, CA, totals all equal; AVG sum of 6-decimal printed CA rows differs from the exact total by 5.8e-5 paise.
* [IMPL]+[XLANG] fresh random fuzz (fuzz_diff.py, seed 20260101): 400 sequences, 40,802 fills (892 flagged duplicates, 2,791 reversals, 15,206 partial reductions, 4,866 same-second mixed-side groups, 1-6 instruments, non-lot quantities, shuffled input order in 15 percent), x 3 tie orders x 3 methods = 3,600 cases: 0 C++-vs-Python byte differences, 0 C++-vs-reference, 0 Python-vs-reference mismatches (strict-mode invariants on).
* Probe [XLANG]: Python tsvio accepts '+1', '1_30', ' 130' and Unicode digits where C++ rejects (D-A05).
Fuzz limits: prices on 5-paise grid and bounded; no int64-overflow cases; same author wrote both implementations.

## 6. Mutation testing (task 5) - VERIFIED [REPRO]
26 mutations (23 Python, 3 C++) on scratch mirrors; each run against the 127 existing tests in test_accounting, test_lineage*, test_tp01_reconciliation, test_parity and against my own comparison (compare_ref_vs_engine.py + fuzz; C++ mutants via cpp_raw_run.py + fuzz with the mutated binary). Full records in mutations.json.
| id | change | existing tests | own check | existing detector |
|---|---|---|---|---|
| M01 | duplicate opening allocation [python/pe/lineage.py] | caught (59 failing tests) | [IMPL] reference comparison | independent-reference tests: test_lineage_reference.py, test_lineage_real.py |
| M02 | dropped closing portion on every reversal fill [python/pe/lineage.py] | caught (55 failing tests) | [IMPL] reference comparison | independent-reference tests: test_lineage_reference.py, test_lineage_real.py |
| M03 | dropped closing portion sparse (1 in 997 source rows) [python/pe/lineage.py] | caught (7 failing tests) | [IMPL] reference comparison | independent-reference tests: test_lineage_real.py |
| M04 | sign flip of FIFO/LIFO realized P&L [python/pe/ledger.py] | caught (108 failing tests) | [INV]/crash only | independent-reference tests: test_tp01_reconciliation.py, test_lineage_reference.py, test_lineage_real.py |
| M05 | AVG realized P&L sign flip [python/pe/ledger.py] | caught (88 failing tests) | [INV]/crash only | independent-reference tests: test_tp01_reconciliation.py, test_lineage_reference.py, test_lineage_real.py |
| M06 | price off by one tick on 1 in 1000 historical fills [python/pe/generators/historical.py] | caught (7 failing tests) | [IMPL] reference comparison | independent-reference tests: test_tp01_reconciliation.py, test_lineage_real.py |
| M07 | wrong price column (order running average col 18 instead of per-fill col 137) [python/pe/generators/historical.py] | caught (24 failing tests) | [INV]/crash only | independent-reference tests: test_tp01_reconciliation.py, test_lineage_real.py |
| M08 | buy/sell reversed on 1 in 4001 historical fills [python/pe/generators/historical.py] | caught (18 failing tests) | [IMPL] reference comparison | independent-reference tests: test_tp01_reconciliation.py, test_lineage_real.py |
| M09 | wrong parent id on closing portions (stale parent of previous CP) [python/pe/lineage.py] | caught (49 failing tests) | [IMPL] reference comparison | independent-reference tests: test_lineage_reference.py, test_lineage_real.py |
| M10 | same-second order swap (reverse source-row tie-break) [python/pe/replay.py] | caught (61 failing tests) | [IMPL] reference comparison | independent-reference tests: test_tp01_reconciliation.py, test_lineage_reference.py, test_lineage_real.py |
| M11 | 19800-second timestamp shift in historical generator [python/pe/generators/historical.py] | SURVIVED (127 pass) | [IMPL] reference comparison | none |
| M12 | reversal opening allocation assigned to the OLD (closed) episode [python/pe/ledger.py] | caught (51 failing tests) | [IMPL] reference comparison | independent-reference tests: test_lineage_reference.py, test_lineage_real.py |
| M13 | FIFO consumes the LAST lot (wrong closing source) [python/pe/ledger.py] | caught (51 failing tests) | [IMPL] reference comparison | independent-reference tests: test_tp01_reconciliation.py, test_lineage_reference.py, test_lineage_real.py |
| M14 | remaining slice quantity off by one lot (65) [python/pe/lineage.py] | caught (61 failing tests) | [IMPL] reference comparison | independent-reference tests: test_lineage_reference.py, test_lineage_real.py |
| M15 | remaining expired-unclosed units off by one lot in dump [python/pe/replay.py] | caught (6 failing tests) | [IMPL] reference comparison | independent-reference tests: test_tp01_reconciliation.py |
| M16 | convention leak: AVG observed OA price differs [python/pe/lineage.py] | caught (82 failing tests) | [IMPL] reference comparison | independent-reference tests: test_lineage_reference.py, test_lineage_real.py |
| M17 | LIFO pops the wrong (front) lot when exhausted [python/pe/ledger.py] | caught (87 failing tests) | [INV]/crash only | independent-reference tests: test_tp01_reconciliation.py, test_lineage_reference.py, test_lineage_real.py |
| M18 | reversal opens full fill quantity (close+open != q) [python/pe/ledger.py] | caught (87 failing tests) | [INV]/crash only | independent-reference tests: test_tp01_reconciliation.py, test_lineage_reference.py, test_lineage_real.py |
| M19 | expiry boundary < instead of <= in episode terminal status [python/pe/lineage.py] | caught (1 failing tests) | [IMPL] reference comparison | internal tests only |
| M20 | flagged duplicate fills no longer ignored [python/pe/replay.py] | caught (46 failing tests) | [INV]/crash only | independent-reference tests: test_lineage_reference.py |
| M21 | direction of reversal-created episodes recorded wrong [python/pe/ledger.py] | caught (9 failing tests) | [IMPL] reference comparison | independent-reference tests: test_tp01_reconciliation.py, test_lineage_real.py |
| M22 | tie-order keys sells_first/buys_first swapped (Python only) [python/pe/replay.py] | caught (4 failing tests) | [IMPL] reference comparison | XLANG parity only |
| M23 | cash flow sign flipped [python/pe/ledger.py] | caught (115 failing tests) | [INV]/crash only | independent-reference tests: test_tp01_reconciliation.py, test_lineage_reference.py, test_lineage_real.py |
| C01 | C++ FIFO consumes last lot [cpp/include/pe/ledger.hpp] | caught (5 failing tests) | [IMPL] reference comparison | XLANG parity only |
| C02 | C++ tie keys swapped [cpp/include/pe/replay.hpp] | caught (4 failing tests) | [IMPL] reference comparison | XLANG parity only |
| C03 | C++ AVG pool average floored [cpp/include/pe/ledger.hpp] | caught (4 failing tests) | [XLANG] only | XLANG parity only |
Summary: existing suite killed 25/26; survivor M11. Existing-suite kills with no independent-reference test (parity or internal only): M19, M22, C01, C02, C03. Crash-type kills (not designed discrimination): M17 (IndexError), M07 (generator tick guard); internal-invariant kills ([INV]): M04, M05, M18, M23, M16 guard. My own check: all 26 detected, but M04/M05/M17/M18/M23/M07 only because the engine raised before my comparison could run, M20 only through a harness exception (flagged duplicate role absent in the reference), C03 only as a C++-vs-Python difference (the C++ invariant check rejected it) - these are NOT independent discrimination. Self-corrections recorded: my first comparison was blind to duplicate OA rows (dict keyed by fill id) and to dump TOTAL changes; I added emitted-row-list and dump-total checks and re-ran M01 (65,128 rows vs 41,444) and M15 (mismatch) - the stored M01/M15 JSONs carry the original result, mutations.json applies the rerun.

## 7. Defects (defects.json)
D-A01 High tie-order dependence larger than disclosed, raw keys contradict file order in 2 groups. D-A02 Medium generator trusts TP-01 parquet (only raw hash checked). D-A08 Medium test-suite survivor M11 and non-independent detectors. D-A04 Medium EXPIRED_UNCLOSED is inferential; boundary unexercised on real data. D-A03 Low AVG float. D-A05 Low int-parse parity gap. D-A06 Low parent id definition. D-A07 Low doc nits (instrument_id format, tools write into repo). No Critical defect: no corruption of observed inventory, accounting or position identity was found under the src order.

## 8. Not inspected / not verified
M2C-M2E layers (baskets, number-block, wing/body, forensics), parents.tsv field content beyond roles and counts, TP-01 role_ambiguity_fills equality, TP-02 timelines, int64-overflow guard, cpp/tests/test_core.cpp contents, exchange lot-size circulars (lot sizes are data-derived), charges/settlement (no data), Python 3.12 vs 3.13 float-sum behaviour on other machines (AVG), compilers other than g++ 13.3.
