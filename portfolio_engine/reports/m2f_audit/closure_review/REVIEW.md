# M2 closure: fresh-context adversarial review

Reviewed head `49f86e88`. The branch tip moved to `3d52b8cf` during the review; the two later commits add only three mutation-result JSON files under `reports/m2f_audit/r1/` and change no code, test or document, so every number below stands for the tip as well. Labels: **[RAW]** derived by me from `Trades_GKOHNP140.csv` with my own code (`rawload.py`, `replay_mine.py`, no `pe` imports); **[IMPL]** produced by project code that I ran; **[DOC]** read only. Nothing in the repo outside this directory was edited; the raw CSV and `tp_reconstruction/` were only read. All scripts are in this directory (run each from here with `python3 <script>`); `defects.json` has the machine-readable findings.

**Verdict.** No Critical or High finding. Every headline number I re-derived was reproduced exactly. Two documentation claims are stronger than the data (CR-01 Medium, CR-02 Low); the rest are Low or Info. No delivered output is wrong.

## Findings

| ID | Sev | Item | One line |
|---|---|---|---|
| CR-01 | Medium | 1 | "second-end aggregate state is order-invariant" is true for inventory, cash, gross opened/closed only; the `SECOND_END_ORDER_INVARIANT` flag sits on rows whose cumulative realized P&L, per-tag opened/closed units and reversal count depend on the order |
| CR-02 | Low | 1 | "no cross-instrument order is observable" is untested for SENSEX (embedded ns agrees with file order for 87 percent of cross-instrument adjacent same-second pairs) |
| CR-03 | Low | 3 | inclusive `gap <= g` on whole seconds links pairs whose ns-resolved gap exceeds g (SENSEX: 157 of 340 boundary links at 2 s); "1,214 ..." counts one direction only |
| CR-04 | Low | 3 | C2 membership depends on the tie-break among equal-first-second parents (C1 does not) |
| CR-05 | Low | 2 | 3 of the 26 baseline parent-level flips are produced by other parents' fills (0 of 22 hybrid) |
| CR-06 | Low | 4 | the price-scrambling test is blind to price read from outside `px_fill` (executed mutant survives) |
| CR-07 | Low | sample | B-04 evidence cites a non-existent directory |
| CR-08 | Low | 6 | "evidence-class labels verified stable" is vacuous (constants); W2 label note |
| CR-I1 | Info | all | long list of exact reproductions (below) |

## 1. Same-second event semantics

**Soundness of `_local_keyed_order` [IMPL, read and exercised].** It takes the baseline sort `(timestamp, source row, fill id)` and refills the slots of each `(timestamp, instrument)` group with that group sorted by `(tie key, source row, fill id)`. This is a permutation that never moves a fill across seconds or across instruments' slot sets, so per-instrument sequences are the sorted ones and cross-instrument interleaving stays the baseline one. I found no mathematical flaw. My independent implementation (`rawload.order_hybrid`) gives identical totals: 172 of 4,464 same-instrument-second groups differ from baseline (2 mixed-side), reversal fills 23 to 21, [RAW] `item1e_group_counts.py`. I also reproduced the N1 measure exactly: 8,196 stream positions, 2,532 intermediate gross states, max 7,150 units (old global sort vs local); local vs baseline 681 positions / 509 gross states [RAW] `item1f_n1_measure.py`.

**The "second-end state is identical" claim [RAW] `item1_second_end.py`.** I replayed 21,882 seconds under baseline, hybrid, 12 random permutations of all fills of each second (X), 12 random permutations inside each (instrument, second) group (I) and 12 random cross-instrument interleavings that keep every instrument's order (C). At every second-end:

| Quantity | hybrid | X | I | C |
|---|---|---|---|---|
| aggregate CE/PE long/short inventory, open instruments | 0 diffs | 0 | 0 | 0 |
| cash | 0 | 0 | 0 | 0 |
| inventory of every instrument touched | 0 | 0 | 0 | 0 |
| cumulative opened units, cumulative closed units | 0 | 0 | 0 | 0 |
| cumulative FIFO realized (seconds differing) | 1,514 | 8,906-14,958 | 9,305-14,427 | **0** |
| cumulative LIFO realized | 1,155 | 11,354-13,924 | 11,033-14,031 | **0** |
| cumulative reversal count | 6,527 | 8,100-18,406 | 6,527-18,434 | **0** |

Gross opened and closed units are invariant by an identity (opened + closed = sum of quantities; opened - closed = change of |inventory|). So cross-instrument interleaving alone (C) changes no second-end quantity of any kind, per-instrument realized P&L included: that part of the project's position is confirmed. Same-instrument order does change realized P&L, per-tag attribution and reversal counts at second-end.

**CR-01 (Medium), counterexample (a), executed.** The wording "the state after the last fill of a second is identical under any ordering" (ORDERING_SEMANTICS table; "the state at the end of every second is identical", line 35) and the flag `SECOND_END_ORDER_INVARIANT` are over-broad:
* [RAW] cumulative per-module opened/closed units differ at 6,527 second-ends (780 units, e.g. `num` short opened 395,240 vs 394,460 at ts 1788167791; this is the 626,765 vs 625,985 body-unit difference).
* [IMPL] `pe.forensics.inventory_series` / `intra_second_flag_table` on the real ledger for cycle NIFTY 2026-09-01 (contains rows 27906-27917), baseline vs hybrid: 3 second-end rows labelled `SECOND_END_ORDER_INVARIANT` differ in `cum_opened_num_short`, `cum_opened_other`, `cum_closed_by_tag_num`, `cum_closed_by_tag_s_` (8,970 vs 8,190, 1,235 vs 2,015, 7,670 vs 8,450, 5,395 vs 4,615) (`item1d_flag_overclaim.py`).
* [IMPL, synthetic, `counterexamples_ab.py`] inventory +10 at 100.00; in one second buy 10 @ 120.00 and sell 10 @ 110.00 on the same instrument. Under `src` and `sells_first`: gross 10 and cash -110,000 identical; FIFO realized +10,000 in both; LIFO realized -10,000 vs +10,000 and book value -100,000 vs -120,000.
* Not a delivered-output defect: in the two delivered cycles (NIFTY 2026-06-30, SENSEX 2026-07-16) the regenerated hybrid inventory series has 0 differing second-end columns (`item7_compare_inventory.py`).
* Fix: name the invariant quantities in the docs, narrow or rename the flag, add a test on a cycle with a mixed-tag reordered group.

**CR-02 (Low).** [RAW] `item1c_ids.py`, `item1g_sensex_cross.py`: NIFTY trade ids are per contract (22 ids shared by different instruments; 6,392 day-level decreases in file order; 0 decreases across seconds within an instrument-day, 212 inside a second). SENSEX embedded ns: 0 decreases across seconds within an instrument-day, 33 inside a second. But for different SENSEX instruments in one second the ns agrees with file order in 6,482 of 7,447 adjacent pairs (87 percent; same instrument 98.7 percent). The project did not test whether the ns is a venue-wide clock, yet states no cross-instrument order is observable. Results do not depend on it (previous table), so Low. Row 8079 is the only SENSEX row using the epoch fallback and is alone in its group; 130 SENSEX groups have tied ns keys and fall back to source row. [DOC] claim "epoch = round-half-up(ns/1e9)" holds for all but row 8079.

## 2. Reversal measures

Recomputed with my own code (`item2_reversals.py`): full ledger baseline per-fill 23 / parent-level 26; hybrid 21 / 22; NIFTY 2026-06-30 1 / 1 (both scenarios); SENSEX 2026-07-16 0 / 1 (both). All claimed numbers reproduced. The definitions are unambiguous in code. Overlap [RAW]: all 23 baseline per-fill crossings lie inside a parent-level flip group, 3 parent-level flips have none (parent ends flat, then opens the other side), no parent has two flip groups. So on this ledger per-fill is a subset of parent-level, although the docs correctly say this is not true in general.

**CR-05 (Low), counterexample (b), executed** (`item2b_attribution.py`, `counterexamples_ab.py`, project `pe.reversals.measures` on synthetic rows):
* Order dependence: +10, then parents A sells 10 and B sells 5 in one second: A-then-B gives per-fill 0 / parent-level 0; B-then-A gives 1 / 1.
* Attribution: +5; A buys 1, B sells 11, A buys 1: per-fill 1 (B), parent-level 2 (A: +5 to -4 although A only bought; B: +6 to -5). One crossing counted twice, one assigned to a parent that only bought.
* Two fills of one parent (+10 to 0 to -10): per-fill 0, parent-level 1.
* [RAW] real data: 3 of 26 baseline parent-level flips (rows 27906/27916 PE23200; 27908/27917 CE24600; parent `s_22084429338804` rows 33690-33717) exist only because other parents' fills interleave; the parent alone ends at zero. Hybrid: 0 of 22. The 26 vs 22 difference is therefore an ordering artefact. All within the documented caveat, but the headline count does not say so.

## 3. Closing batches

My own closing portions (min(q, |inv|) against the instrument's inventory), parent unit = (parent, underlying, expiry, IST session), 16,817 units baseline (16,815 hybrid), sort (first closing second, smallest closing row, parent id) [RAW] `item3_batches.py`:
* Inclusive counts for C1 and C2: 7,127 / 3,777 / 3,065 / 2,171 / 1,502 at 2/5/10/30/60 s (hybrid identical; 1 batch per view differs each way).
* Exclusive view: 7,788 / 4,218 / 3,144 / 2,196 / 1,535; batches only in the exclusive view **1,214 / 840 / 153 / 50 / 63 (reproduced exactly)**; inclusive-only 553 / 399 / 74 / 25 / 30; pairs at exactly g 661 / 441 / 79 / 25 / 33. Boundary behaviour is correct: gap == g links (inclusive), gap == g+1 never links, no off-by-one found.

**CR-03 (Low), counterexample (c), executed** (`item3b_boundary_counterexamples.py`). Using the SENSEX embedded ns for the first closing fill of each parent: C1 links at reported gap exactly g whose true gap exceeds g: 157/340 (g=2), 103/290 (5), 18/45 (10), 7/12 (30), 6/11 (60); no non-link at gap g+1 has true gap <= g. The inclusive rule is effectively "true gap < g+1", the exclusive "true gap < g"; the pair brackets, but neither equals "<= g seconds". "Changes 1,214 / ... batches" describes only the exclusive-only side; the net change is +661 / +441 / +79 / +25 / +33.

**CR-04 (Low).** Synthetic A(10-100), B(10-11), C(50-60), C2, g=30: tie order A,B gives {A,B},{C}; B,A gives {A,B,C}. [RAW] 60 random tie-breaks among equal-first-second parents: C2 7,126-7,127 at 2 s, 3,776-3,777 at 5 s, 3,064-3,065 at 10 s, constant at 30/60 s; C1 constant at all thresholds. This is a dependence of a published view on a cross-parent serialization, already in limitations section 7.

## 4. Case selection

* **Price-free [IMPL, code reading + experiment].** `cases.select` reads no price column (column list in `item4_cases_result.json`: episode/event/item/link/batch fields only). `wing_body` carries average prices only as output columns of links; membership never uses them. Claim supported for the committed code.
* **"Outcome-free"** means P&L-free. Selection conditions on trajectory outcomes (terminal status CLOSED vs not, REVERSED events, partial-reduction counts). Fair wording; worth saying.
* **D-1 statement [RAW] `item4_cases.py`:** 17 of 17 records begin on D-1; 16 at 09:xx IST, 1 at 11:xx (SENSEX CT9, 11:15:06); I re-derived start times from raw rows (all 17 match `episodes.tsv`). 16 distinct positions (NIFTY CT1 and CT5 share `CE24100#1`), so "17 case records" is exact and "17 positions" would not be. The paragraph in `M2E_POSITION_CASE_STUDIES.md` matches.
* **CR-06 (Low), counterexample (d), executed** in scratch copies under the session scratchpad (`item4b_make_mutants.py`). Mutant A re-ranks CT1 by the RAW-CSV price of each candidate's first fill and the scratch's delivered outputs are regenerated with it. Slow test `test_case_selection_is_invariant_under_upstream_price_scrambling`: **PASSED** (188 s). The non-slow pins (hash pin, wording diff) then failed (3 failed), but only because delivered files changed, not because of price dependence. Mutant B: same ranking using `fills.tsv` `exec_price_paise`: slow test **FAILED** (killed). So the test detects price taken through the scrambled column only, and (comparing against the delivered JSON) also fails for any rule change. The recorded DA01/DA02 kills are real (same class as mutant B).

## 5. Historical preservation

[IMPL] `item5_6_register_check.py` against `git show 562d7eb6:`: `M2F_FINAL_AUDIT_REPORT.md` and `M2F_METHODOLOGY_LIMITATIONS.md` are byte prefixes of their current versions (addenda only appended); the decision line "M2 — CONDITIONAL PASS" is intact in the original part. The six original dispositions (D-A01, D-A08, B-01, C-01, C-02, E-D03) are present verbatim (string equality with the 562d7eb6 text, label renamed to "Original disposition (...verbatim)"). Observation: the final report's header was never updated to say closure completed; closure status lives only in the register and ledger (Info).

## 6. Evidence classes

[IMPL] `pe/wing_body.py`: W1 WEAKLY_SUPPORTED, W1_S60 UNRESOLVED, W2 WEAKLY_SUPPORTED (weights arithmetic), W2_S60 UNRESOLVED, W3 UNRESOLVED; protective intent NOT_TESTABLE and EXPIRED_UNCLOSED "inference" appear consistently in Decision D and the R1-C text; grep of the new documents found no ownership, hedge or chronology claim. **CR-08 (Low):** "evidence-class labels verified stable under the hybrid" is vacuous because labels are constants per method; the real stability results were reproduced (next section). W2 inherits W1's label although its weights are arithmetic; defensible, noted.

## 7. Baseline vs hybrid reproduction

[IMPL] `r1c_scenario_run.py --scenario=baseline` and `--scenario=per_contract_id_sequence` into empty roots, then `r1c_inventory.py --control --scenario --out=<tmp>`: control 167 IDENTICAL / 0 DIFFERENT / 0 MISSING / 2 NEW / 1 EXCLUDED = 170; hybrid 134 / 33 / 0 / 2 / 1 = 170; the `summary` equals the committed `file_inventory.json` exactly; per-path entries equal for 165 of 170 (the 5 differing are manifest/summary JSONs whose raw sha differs only through provenance fields). Wing/body [IMPL] (`item5d_links.py`): W1, W1_S60, W2, W2_S60 each lose 6 links (42,777 to 42,771; 65,228 to 65,222), W3 0 (12,096), opening body units 626,765 to 625,985, 2 items differ. Portfolio metrics [RAW]: fills 41,421, opening 1,414,545, closing 1,377,065, cash 278,748,200, FIFO/LIFO realized 210,055,200 / 209,687,450 (both orders), episodes 2,667 (both).

## Closure-disposition sample (twelve checked)

| Defect | Claim checked | Result |
|---|---|---|
| D-A02 FIXED | verifier exists; 21 tests; commit 2a511c25 | exists; 21 collected; commit resolves (the quoted `26a0da63...` / `90c9c7ee...` are sha256 prefixes, not commits) |
| D-A04 FIXED | 15 tests; 81 instruments (71 long, 10 short, 37,480 units); none expires on last data day | 15 collected; [RAW] 81 / 71 / 10 / 37,480, last day = max expiry 2026-10-22, 0 non-flat expiring that day |
| D-A08 FIXED | independent raw test exists | file exists (21 tests); mutant claims recorded, not re-run |
| B-04 FIXED | 35 tests; 12 mutants; result dir `medium_remediation/` | 35 collected; **directory absent** (CR-07) |
| C-02 FIXED | 5 engine tests | 5 collected |
| D-02 FIXED | slow test kills price/outcome mutants; results JSON | DA01/DA02 recorded as killed; my mutant B killed, mutant A not (CR-06) |
| D-16 FIXED | 23/26, 21/22, 1/1, 0/1; files exist | all reproduced; `reversals.py`, tool, JSON present |
| D-A06 FIXED | 39,874 parents; col 4 gives 37,258, up to 6 parents, 2,224 shared | all reproduced [RAW]; no parent has two order numbers |
| B-01 ACCEPTED | 1 batch per view differs | reproduced [RAW] (1 each way, all ten views) |
| C-01 ACCEPTED | 626,765 vs 625,985; 6 links; 2 items | reproduced [IMPL] |
| N1 (mutation file) | 9 of 9 mutants | N1 results list: 1 baseline + 9 mutants |
| Cited paths/tests | 69 path refs, 20 hash-like refs across all 49 dispositions | all resolve except B-04's directory (the two "unresolved commits" are sha256 prefixes) |

Limits of this review: mutation kill claims were checked only where I re-executed them (mutants A/B above); the three result JSONs added after 49f86e88 were not examined beyond the B-04/C-02 file's entry count (21); closure dispositions beyond the twelve sampled were checked only for resolvable references; the reviewer is the same model family as the authors.

## Reproduction

```
cd portfolio_engine/reports/m2f_audit/closure_review
python3 item1_second_end.py; python3 item1b_tag_columns.py; python3 item1c_ids.py; python3 item1e_group_counts.py; python3 item1f_n1_measure.py; python3 item1g_sensex_cross.py
python3 item1d_flag_overclaim.py <empty_dir>          # project code, NIFTY 2026-09-01
python3 item2_reversals.py; python3 item2b_attribution.py; python3 counterexamples_ab.py
python3 item3_batches.py; python3 item3b_boundary_counterexamples.py
python3 item4_cases.py; python3 item4b_make_mutants.py <scratch> <worktree>   # then run the slow test in each scratch portfolio_engine
python3 item5_6_register_check.py; python3 item5c_sample_checks.py
python3 ../../../tools/r1c_scenario_run.py --scenario=baseline --out-root=<empty>      # and --scenario=per_contract_id_sequence
python3 ../../../tools/r1c_inventory.py --control=<dir> --scenario=<dir> --out=<tmp>
python3 item7_compare_inventory.py <my_inventory.json> ../../r1c_dual_scenario/file_inventory.json <base_out> <hyb_out>; python3 item5d_links.py <base_out> <hyb_out>
```
