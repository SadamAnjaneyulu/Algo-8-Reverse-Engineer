# Track D — M2-E historical forensics and visualizations: independent audit

Scope: NIFTY 2026-06-30 and SENSEX 2026-07-16 (HEAD 7117bbce, read-only). Verification classes: **[RAW]** raw-source, **[IMPL]** independent re-implementation, **[INV]** internal invariant, **[REPRO]** reproducibility. Labels: VERIFIED / INSPECTED / SUSPECTED / NOT VERIFIED. All scripts are in this directory; none import pe.* (anti-circularity). Scratch mirrors lived under the session scratchpad (`m2f_d/`).

## 0. Bottom line
* **Numbers: justified.** Every dataset row, V1/V2/V3 CSV row, V4 aggregate and conservation total, V5/V6 value, coverage-report number and quoted full-ledger scope number that was re-derived from the raw ledger agrees (about 24,500 independent checks: 13,564 dataset/V1-V3 + 9,344 V4-V6/coverage/scope + 1,382 case + 225 manifest; 0 failures). No mark, interpolated price or unrealized P&L exists anywhere.
* **Case-selection narrative: NOT justified as written.** Cycle freeze (e06a711e) is timestamp-supported; individual case selection is *not* shown to be fixed before inspection, yet one heading and every case block say "fixed before any case was looked at / predefined, outcome-free". Selection is nevertheless price-independent (executed perturbation) and fully reproducible, but concentrates every case on D-1 session-start positions.
* **Visuals: two real presentation defects** (legend hides the widest batch in all four V4 figures; case PNGs carry no case-specific information) plus several Low items. No figure implies ownership, hedging or intent beyond the evidence labels.
* **Test suite (89 tests) is weaker than it looks for presentation artefacts**; see section 6: 7 of 21 new mutants survive the existing tests.

## 1. Raw recomputation (task 1)
| Check | Script | Class | Result |
|---|---|---|---|
| Column semantics (4,11,12,14,15,16,18,19,23,27,33,137,161,163,166); col137 vs col18; UTC epoch; session-time window | verify_raw_columns.py | [RAW] | VERIFIED. col137 != col18 on 431 raw rows (20 NIFTY / 13 SENSEX cycle fills), so the price-column choice is discriminated. 337 full-ledger raw fills lie outside 09:14-15:31 IST (not in the two cycles; not investigated). |
| fills, V1 series, carry, lifecycle, episodes, opening items vs independent signed replay | verify_datasets.py | [RAW]+[IMPL] | VERIFIED (1146 + 729 fills; 85 + 70 episodes; 1147 + 729 events; 699 + 452 items) |
| V1 CSV (incl. CARRY_IN rows, signs, D-1/D0), V2 CSV, V3 CSV, entry-minute cohorts | verify_datasets.py | [RAW] | VERIFIED |
| TP-03 window IST conversion | verify_tp03_windows.py | [RAW] | VERIFIED: 44/44 windows per cycle reproduce the published body-short fill counts only under IST (6 / 19 under a UTC reading); m2e start timestamps = label - 19800 s |
| V4 conservation and aggregates (C1, C2, 5 thresholds) | verify_v4v5v6.py | [RAW]+[IMPL] | VERIFIED. (M2-C gap rules not audited.) |
| W1 / W1_S60 candidate sets re-implemented from raw; V5 multiplicity, units, histograms, W3 overlap; V6 panels | verify_v4v5v6.py | [RAW]+[IMPL] | VERIFIED. W3 queue values and W2 weights only aggregated from the slice. |
| Full-ledger scope numbers (8,399 / 7,301 / 3,501 / 3,800 / 1,098 / 133,640 / 8,204 / 195 / 68,720 / 336,040) | verify_v4v5v6.py | [RAW]+[IMPL] | VERIFIED; 107,530 (mixed-module closing wing units) NOT VERIFIED |
| Coverage report numbers | verify_v4v5v6.py | [RAW] | VERIFIED |
| Price units / no marks | header + key scan (103 files), PNG footers | [INV]+INSPECTED | VERIFIED: paise execution prices only (fills.tsv exec_price_paise, items avg_exec_price_paise); only "unrealized P&L = NA" text. |
All outputs: verify_*.out.

## 2. Visual inspection (task 2; INSPECTED with the Read tool)
All 10 figures for both cycles (V1, V2, V3, V4_C1, V4_C2, V5_W1, V5_W1_S60, V5_W2, V5_W3, V6 = 20 PNGs) and 7 case PNGs (NIFTY CT1, CT2, CT5 reversal, CT9; SENSEX CT3, CT7, CT9). A legend-overlap probe was also run on a scratch re-render (legend_overlap_probe.py).
* **D-01 (Medium)** V4 legend hides the widest batch (NIFTY 92 parents, SENSEX 75) in all four V4 figures.
* **D-04 (Medium)** case PNGs are generic V2 charts; CT6-CT9 show nothing about wing/body candidates or batches; CT1/CT5 NIFTY identical episode.
* D-05..D-13 Low: C1 = C2 shown twice; W2 scatter overplot (379 items -> 12 points) with y = x line; V5 legends over bars; V3 cohort bars 1 px with no legend; "Red" vs orange; W3 "candidate" wording and "matched"; TP-03 NOT_LISTED label on wings; boundary-links note.
* Good: evidence-class text on every V5/V6 figure; scope warning explicitly says full-ledger, not this cycle; times labelled IST; footer states execution prices only / marks missing / unrealized P&L NA; V1 panels state "CSV columns are unsigned"; no figure implies ownership, basket identity or protective intent. Net-inventory spikes at the 14:25 close-out are real sequential fills (53 s unwind), not an artefact.

## 3. Regeneration and manifests (task 3)
Scratch copy of the repo (portfolio_engine without build/, raw CSV, tp_reconstruction), tools m2e_build, m2e_charts, m2e_cases, m2e_catalog, m2e_coverage_report, m2e_report re-run: **103 non-PNG files byte-identical, 37 PNGs byte-identical**; the only differences are runtime metadata: `generated_at_head` ("UNAVAILABLE" in a non-git copy vs committed 10e33962) in two manifests and m2e_summary.json, and the "Base commit" string in the final report (regen_compare.out). [REPRO] Committed manifests record 10e33962, not HEAD (D-12; data unchanged). Manifest verification (225 checks: files, hashes, rows, sources exist, no unlisted figure file, case manifests) passes; figure manifests lack source-dataset hashes.

## 4. Case-study selection audit (task 4)
**(i) Cycles.** e06a711e 2026-11-13T15:46:15Z "frozen before any grouping"; criteria doc committed in 41ecbbb0 15:45:26Z; first M2 lineage 9de52d9e 15:57:05Z, first grouping code (closing batches) 9b6a496e 16:26:17Z, wing/body f1b3f974 17:52:42Z. VERIFIED timestamps. Nuance: the score used TP-02 mechanisms and the count of TP-03 window rows (pre-M2 entry-window analysis, itself a grouping) and script + output were committed together, so non-iteration cannot be proved; both underlyings had several score-1.0 cycles, the tie-break (earlier expiry) decided.
**(ii) Case rules.** `pe/cases.py` RULES + `select` re-implemented from raw (verify_cases.py): all 20 selections and anchors reproduce (1,382 checks).
**(iii) Evidence of prior freezing: none.** pe/cases.py, tools/m2e_cases.py and M2E_POSITION_CASE_STUDIES.md first appear in 10e33962 (2026-11-14T07:08:59Z) together with the datasets, figures and case JSON; rule text/disclosure edited in 7117bbce (07:48:29Z) after review, selected episodes/anchors unchanged. Not prospectively preregistered; not proven outcome-blind by history.
**Claim sentences** (file:line; supported?):
| Location | Sentence | Supported |
|---|---|---|
| reports/M2E_POSITION_CASE_STUDIES.md:5 (generated by tools/m2e_cases.py:42) | "Selection method (fixed before any case was looked at)" | NO (no earlier timestamp) |
| M2E_POSITION_CASE_STUDIES.md:45,67,88,115,137,162,187,212,237,261,282,303,336,361,386,411,436 (tools/m2e_cases.py:16) | "Selection rule (predefined, outcome-free; ...)" | "outcome-free": YES (executed); "predefined": NOT shown |
| python/pe/cases.py:1-3 | "Selection is PREDEFINED and structural ... Profit, loss, price and any outcome are never consulted" | structural + price-free YES; "predefined" not shown |
| M2E_HISTORICAL_FORENSICS_REPORT.md:7, review_dispositions.json:3 | "10 predefined case types per cycle" | types listed in RULES; timing not shown |
| M2E_HISTORICAL_FORENSICS_REPORT.md:42, review_dispositions.json:10 | "Case selection is chronological and outcome-free; the reviewer verified it by brute force" | YES (chronological / price-free verified here too) |
| M2E_HISTORICAL_FORENSICS_REPORT.md section H last bullet | "written in code before cases were viewed, but git history can only show it from the checkpoint" | honest, but contradicts the case-study heading |
| M2E_CYCLE_COVERAGE_REPORT.md:3, tools/m2e_coverage_report.py:9, forensics.py:11 | "selected before any grouping, e06a711e" | YES for M2 grouping code; TP-03 windows predate |
| tests/test_forensics.py:206-221 | "outcome-free" / "ignores prices and outcomes" | weak: perturbs dataset columns only |
**Executed perturbation (IMPL).** All fill prices scrambled (x7/5 + row offset, tick-aligned) *before* the lineage, M2-C and M2-D engines; full m2e_build re-run in scratch (reconciliation PASS); `K.select` on the rebuilt datasets: **all 20 selections identical** (perturbation_selection_result.log). So selection is structural; limitation: structure itself (timing of fills, tags) is what the cases are chosen on, and rules were visible to the author when written.
**Selection effects.** Rule = first qualifying candidate not already used. 13 of 17 picks equal the chronological first; 4 do not (NIFTY CT5 reuses CT1's episode - the only reversal; NIFTY CT7 rank 2, CT9 rank 5; SENSEX CT9 rank 6). 16 of 17 episodes start 09:16-09:46 on D-1; none on D0 (D-03). Type order matters (earlier types consume episodes).

## 5. Case records (task 5)
All 17 available cases re-derived from raw (fills, per-episode opening/closing quantities, opening/closing parents, lifecycle, wing/body membership = items with an opening allocation in the episode, in/out of M2-D tagged scope, W1/W1_S60 counterparts and dt, related reversal episodes), plus case figure CSVs: **VERIFIED**. NIFTY reversing fill row 5681 (parent h_30084825701151, BUY 520): 390 closing in CE24100#1, 130 opening in CE24100#2; the preceding fill 5680 (130) closes #1. SENSEX mixed parent s_16053046299662: fills 12632 (60) and 12638 (100) close CE77600#1, 12641 (20) opens CE77600#2 (no reversing fill: separate fills). ID/episode assignment of reversing fills is consistent in datasets, case JSON and V2/case CSV.

## 6. Mutation testing (task 6)
Method: mutate COPIES only (light mutant trees in scratch; symlinks to the repo-sized inputs, copies of tests/tools/python/m2e_data/m2e_figures), refresh manifest hashes to simulate a generator that writes consistent manifests, run the existing `tests/test_forensics.py` (89 tests, `-x`) and Track D's raw-derived verifiers. 21 new mutants + 1 control (control: 89 passed, all own checks pass). None coincides with the previous reviewer's set (dropped fill, +19800 s, CE/PE swap, +1 lot V3, partial->CLOSED, CONFIRMED label, dropped batch member, V4 sensitivity value, V6 stack move, V1 ts as UTC, TP-03 overlay shift, V2 qty, case JSON qty, V5 multiplicity swap). A crash for another reason is not counted as a kill (no crashes occurred; failure lines recorded in mutations.json).
| id | change | existing tests | Track D checks |
|---|---|---|---|
| m00 | CONTROL: no change, manifests refreshed | control: passes (expected) | control: passes (expected) |
| m01 | V3 entry-minute cohort CSV: body units +65 in one (session, minute) row (wrong per-minute aggregation) | killed | killed |
| m02 | V1 CSV: one FILL row duplicated | killed | killed |
| m03 | V2 CSV: REVERSED event row dropped | killed | killed |
| m04 | V3 CSV: one body item labelled WING_LONG_BY_TAG (role label swap) | SURVIVED | killed |
| m05 | V4_C1 CSV: duration_s +1 for one batch | SURVIVED | killed |
| m06 | V5_W1 CSV: wing units no-candidate (unmatched) set to 0, total unchanged | SURVIVED | killed |
| m07 | V6 CSV: full-ledger scope number wing_items_with_candidate_full_ledger_W1 +1 | killed | killed |
| m08 | V1 CSV: D-1/D0 labels swapped (SENSEX) | SURVIVED | killed |
| m09 | V1 CSV: short_CE sign flipped on 5 rows | killed | killed |
| m10 | fills.tsv: exec_price_paise replaced by raw order running-average column (col 18) for all NIFTY fills | killed | killed |
| m11 | m2e_charts footer drops the execution-price/marks/unit annotation; V1 re-rendered (PNG only) | SURVIVED | SURVIVED |
| m12 | case_studies.json CT6 record: opening_parents[0] replaced by a closing parent | SURVIVED | killed |
| m13 | lifecycle_events.tsv (SENSEX): one event quantity +65 | killed | killed |
| m14 | episodes.tsv (NIFTY): n_parents +1 on one episode | killed | killed |
| m15 | coverage.json (SENSEX): fills.opening_units +65 | killed | killed |
| m16 | session_carry.tsv (NIFTY): D-1 short_CE +65 | killed | killed |
| m17 | V5_W1_S60 CSV: 5 links moved to the adjacent dt_s histogram bin | SURVIVED | killed |
| m18 | m2c_closing_batches_C1.tsv slice (NIFTY): total_closing_qty +65 for one batch | killed | killed |
| m19 | opening_items.tsv (NIFTY): avg_exec_price_paise written in rupees (/100) | killed | killed |
| m20 | cases/CT5_REVERSAL.csv: REVERSED event dropped | killed | killed |
| m21 | V2 CSV (SENSEX): inventory_after sign flipped on one ADDED event | killed | killed |

**Survivors of the existing test-suite (7 of 21): M-D-04 (V3 role label swap), M-D-05 (V4 duration +1), M-D-06 (V5 unmatched units omitted), M-D-08 (V1 D-1/D0 label swap), M-D-11 (footer/price-unit annotation removed), M-D-12 (case record opening parent replaced), M-D-17 (V5 histogram bin shift).** The existing tests check figure CSVs against manifests/hashes and a few recomputations, but not role labels, V4 CSV values, V5 category values, V1 d_label, case-record parents or V5 histogram bins. Detector independence: the existing tests that did kill (e.g. M-D-09, 10, 14, 16, 18, 19) regenerate through the production engine (independent of the mutated file, not of the engine); Track D checks use only the raw CSV and are independent of every mutated path.
**Survivors of Track D checks: M-D-11** (the PNG footer text is not read by any check; the harness's informational PNG-hash mismatch flagged verify_manifests only incidentally and is not counted). Disclosure: my V3 role/side check, V6 section-G check and case-figure-CSV check were added after the first clean run and before the mutation run; the first version of my V3 figure check would have missed M-D-04 (it did not compare tag_role). Caveat: mutants are single-point edits; no mutant touched PNG pixels other than M-D-11.

## 7. Not inspected / limits
* M2-C chaining rules and M2-D matching internals (only equality, conservation and a raw re-implementation of W1 / W1_S60 candidate sets); W3 queue arithmetic and W2 weights not re-derived; 107,530 mixed-module closing-wing units NOT VERIFIED.
* Individual PNG pixel content beyond the 20 figures + 7 case PNGs inspected (10 case PNGs not viewed: NIFTY CT3, CT6, CT6b, CT7, CT8; SENSEX CT1, CT2, CT6, CT6b, CT8); the M2-E markdown catalog and final report prose was grepped, not proofread line by line.
* No market bars exist in this environment (ALGO8_MARKET_DIR absent): mark coverage NOT VERIFIED either way; C++ parity and slow tests not run beyond tests/test_forensics.py.
* Same-second fill ordering uses raw row order (convention).
* 337 raw fills outside 09:14-15:31 IST in the full ledger (none in the two cycles) not investigated.

## 8. Defects (severity)
Critical: none. High: none. Medium: D-01 (V4 legend hides widest batch), D-02 (case selection "fixed before" claim), D-03 (selection concentrated on D-1 session start), D-04 (case PNGs generic), D-15 (weak existing selection / presentation tests), D-16 (SENSEX "no reversal" definition-dependent). Low: D-05 .. D-14. Details with repro / fix / test in defects.json.
