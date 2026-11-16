# M2-F — Final independent audit of the Algo 8 reconstruction system

**Audited commit:** `7117bbce` (branch `engineering/position-lifecycle-basket-reconstruction`, clean tree, equal to origin at audit start). Audit evidence commits: `d8ca687d` onward. M1/M2-B/M2-C/M2-D/M2-E artifacts and the raw data were not modified.

# DECISION: **M2 — CONDITIONAL PASS**

**Why not PASS.** One High defect is unresolved and blocks an unconditional PASS under the audit rule (D-A01, with the same root cause visible as B-01 and C-01): the observed position layer (episode identity, reversal count, FIFO/LIFO attribution, and through them closing-batch and wing/body membership) depends on an **unresolved intra-second fill-order convention**. The pipeline uses file order; the raw data cannot decide the order, trade id / order number contradict file order in 2 of 56 mixed-side groups, and the reports disclosed only part of the sensitivity. This is a methodology ambiguity, not a coding error, so the audit did not choose an order or change any output.
**Why not FAIL.** No Critical defect. Every quantity the audit could re-derive from the raw ledger reproduces exactly under the declared convention: all 41,421 fills, 23,684 opening allocations, 17,760 closing portions, 2,667 episodes, all ten C1/C2 views, 36,784 wing/body items and 228,106 links, both frozen cycles, and all figure data (about 24,500 checks in Track D alone, 0 failures). Evidence classes are not upgraded. All deterministic outputs reproduce byte-for-byte across environments.
**Conditions to convert to PASS** (see `M2F_METHODOLOGY_LIMITATIONS.md` section 12): (1) a user decision on the intra-second order convention and a disclosure addendum for M2-B/C/D quantifying the sensitivity; (2) approval of the case-selection wording correction (the M2-E claim "fixed before any case was looked at" is unsupported); (3) a reversal-definition decision (D-16); (4) disposition of the Medium defects. **Until then, downstream work (M3) must treat episode identity, reversal counts, FIFO/LIFO attribution and batch/wing-body membership as conditional on the file-order convention.** M3 was not started.

## 1. Repository state and audited commit
* Branch `engineering/position-lifecycle-basket-reconstruction`; HEAD at audit start `7117bbce`; working tree clean; origin identical; manifests (m2c 6/6, m2d 6/6, m2e 19/19 per cycle) intact; manifest source hashes equal the file hashes (raw csv `86e65ab6ece4…`, TP-01 ledger `3b47c55150d7…`).
* Ancestry verified: frozen cycles `e06a711e` (2026-11-13T15:46:15Z) precede M2-B (15:57), closing-batch code (16:26) and wing/body code (17:52); case-selection code first appears in `10e33962` (2026-11-14T07:08:59Z).
* Baseline before any audit action: 236 fast tests passed (274 total incl. 38 slow). Python 3.13, g++ 13. `stage2_alpha_research/` preserved as found (caches only on disk; sources are on another branch, E-D11).

## 2. Scope actually inspected
Five independent fresh-context tracks (A accounting and lineage; B closing batches; C wing/body; D forensics and visualization; E system and reproducibility), each re-deriving its layer from the raw ledger with its own code and each writing only to `reports/m2f_audit/track_*/`. 124 fresh mutation records, 97 claims, 49 defects. Per-track deliverables: `FINDINGS.md`, `claims.json`, `defects.json`, `mutations.json`, scripts and result JSON.

## 3. Scope not inspected (or not verified)
See `M2F_METHODOLOGY_LIMITATIONS.md` section 11: M2-C/M2-D internals beyond equality and independent re-implementation; 10 case PNGs; mark availability (market bars absent); settlement data; en_US locale and Windows newlines; C++ line coverage; external-market-data tools; the TP-03 E6/E7 artifacts; the audit tracks are the same model family as the author (independence limit).

## 4. Accounting and lineage results (Track A)
* **PASS [RAW][IMPL]** under file order: engine fill fields equal raw columns for all 41,421 rows; parent count 39,874 (column 163; column 4 is recycled: D-A06); OA 23,684 (1,414,545 units); CP 17,760 (1,377,065 units); episodes 2,667; lifecycle events 41,444; closing allocations FIFO 25,023 / LIFO 24,948 / AVG 17,760 row-exact; 26 mixed parents (23 with a reversal fill); 15,889 of 17,760 closing portions convention-sensitive: all equal an independent reference.
* TP-01 reproduced (episodes 2,667/2,667; piece ledger exact; realized 2,100,552.00 / 2,096,874.50 / 2,100,111.63 rupees). FIFO realized recomputed from raw rupee text with Decimal equals the engine exactly in paise; quantities are units (gcd 65 / 20); AVG is fractional-paise float (D-A03).
* Observed layer identical across FIFO/LIFO/AVG: true by construction (the split uses net inventory only), not an empirical finding.
* **Tie order (R1): not invariant** — see limitations section 1. Invariant: total OA/CP units, final inventory, cash, AVG realized. Not invariant: episode ids, reversal count, OA/CP membership, FIFO/LIFO attribution, realized P&L (up to 13 rupees).
* Expired inventory: 81 instruments (37,480 units) with no closing fill; EXPIRED_UNCLOSED is an inference; no settlement P&L inferred; expiry-boundary path unexercised on real data (D-A04).

## 5. C1/C2 results (Track B)
* **PASS [RAW][IMPL]:** an independent reference reproduces all ten views over the full ledger with 0 differences (partitions, counts, sizes, start/end/duration, join gaps, overlap flags, portion quantities, batch ids); 14 synthetic boundary cases plus 600 fuzz scenarios x 10 views: 0 disagreements. Unit conservation and exactly-once membership hold in all views. Batch counts 7,127 / 3,777 / 3,065 / 2,171 / 1,502; longest chains 57 / 66 / 125 / 481 / 1,175 s at 2/5/10/30/60 s.
* Frozen cycles: NIFTY 107/63/53/45/36 batches (382 parents), SENSEX 79/33/25/22/14 (264 parents).
* Ambiguities measured not decided (limitations section 7); the exclusive-threshold reading changes 1,214 / 840 / 153 / 50 / 63 batches. Number-block unresolved and unimplemented. Replay tie order changes 1-2 batches (B-01, not disclosed in M2-C reports).

## 6. Wing/body results (Track C)
* **PASS [RAW][IMPL]:** independent reference (different W3 algorithm) equals all 36,784 items and 228,106 links (W1 42,777; W1_S60 65,228; W2 42,777; W2_S60 65,228; W3 12,096). Headline numbers reproduced exactly (8,399 wings; 7,301 with candidate; 3,501 unique; 3,800 multiple; 1,098 none; 133,640 unmatched units = 21.65 %; W1_S60 8,204/195/68,720; W3 residuals 56,420/66,055; 336,040 closing units and 170,650 opening units outside tag roles; 107,530 mixed-module closing wing units). Denominators reconcile to the full unit universe. App keys are not used as a filter (code inspection; engine perturbation [REPRO]).
* Frozen-cycle coverage: all 125 cycle-level fields equal for both cycles. 29 mutants: existing tests killed 28 (W3-weight survivor now pinned), reference killed 29. Assumption challenges: candidate != hedge, weight != allocation, queue match != ownership (limitations section 3).

## 7. Historical-cycle results (Track D)
* Both cycles reproduce from raw: 1,146 + 729 fills, 85 + 70 episodes, 1,147 + 729 lifecycle events (the extra NIFTY event is the reversal), 699 + 452 opening items; TP-03 windows correct only under IST (44/44); 17 case records re-derived (1,382 checks) including the reversal fill split 390/130 and the SENSEX mixed parent. No marks, interpolated prices or unrealized P&L anywhere.
* Case-selection audit: cycles supported; individual selection outcome-free (executed) but not shown to be prospectively fixed (limitations section 4).

## 8. Visualization findings
All 20 figures and 7 case PNGs inspected (10 case PNGs not viewed). No figure implies ownership, hedging, basket identity or intent. Defects: D-01 (V4 legend hides the widest-batch marker, Medium), D-04 (case charts carry no case-specific content, Medium), D-10 (W3 shown in candidate vocabulary), D-05..D-09, D-13, D-14 (Low). Regeneration in scratch: all 103 non-PNG files and 37 PNGs byte-identical to committed (matplotlib 3.11.2).

## 9. Independent raw-source verification
Raw-source verification [RAW] was performed by Tracks A, B, C and D (not E). Verification classes are stated per claim in the register. [XLANG] (Python vs C++) and [REPRO] (reruns, snapshots) are never presented as independent validation.

## 10. Python/C++ verification (Track E and A)
* Fresh C++ build (warning-free); 15/15 full-ledger and frozen-cycle x convention x tie-order combinations byte-identical on 7 files each; Track A: 63 comparisons on raw-derived input, 0 differences; 245 + 400 random sequences (about 4,800 runs): 0 differing except documented overflow rejections and 7 extreme AVG runs (E-D06). **Class: shared-logic consistency, not independent validation.** Parser differences (E-D05) exist for malformed tokens.

## 11. Mutation tests and survivors
123 mutants (+1 control): existing tests killed 108 and **15 survived** (A: M11 timestamp +19800 s; B: M22; C: M19 W3 weight; D: M-D-04/05/06/08/11/12/17; E: E05/E07/E08/E14/E17). The auditors' own independent checks missed 5 (B: M13, M23, M28; D: M-D-11; E: E01, which the existing suite did kill). M11 and M19 now have regression tests (not re-run against the mutants). Full lists: `M2F_TEST_COVERAGE.md`.

## 12. Claim-to-evidence register
`M2F_CLAIM_EVIDENCE_REGISTER.md` — 97 claims: Independently verified fact: 39, Reproduced result with limited independent verification: 17, Method-dependent result: 17, Unresolved: 8, Internal consistency only: 8, Not testable with available data: 7, Inferred association: 1. 18 Track D classes were derived mechanically by the lead and are marked.

## 13. Defect register
`M2F_DEFECT_REGISTER.md` — 49 defects: Critical 0, High 1, Medium 19, Low 29.

**High (blocks PASS):**
* **D-A01** — Observed layer (OA/CP/episodes/reversal counts) depends on an unresolved intra-second tie order; raw sequence keys contradict file order in 2 mixed-side groups; M2B limit disclosure understates the dependence

**Medium:**
* D-A02 — Historical generator trusts the TP-01 parquet; only the raw CSV hash is checked, never the parquet content against the raw file
* D-A04 — EXPIRED_UNCLOSED is an inference from absent closing fills, and the OPEN_AT_END_OF_DATA branch is unexercised on real data
* D-A08 — Existing test suite has a surviving mutant and several detectors that are not independent of the code under test
* B-01 — Closing identification (hence C1/C2 membership) depends on the order of same-second opposite-side fills in one instrument; not disclosed or measured in the M2-C reports
* B-04 — Existing test suite lets a reporting-layer mutation survive and kills three others only through a committed-output hash snapshot
* C-01 — M2-D headline counts are conditional on the same-second tie order of the replay and this is not disclosed in the M2-D report
* C-02 — W3 weight column is not pinned by any existing test (mutant M19 survives all 33 tests)
* D-01 — V4 (C1 and C2) legend hides the widest-batch marker in both cycles
* D-02 — Case-study section claims the selection method was "fixed before any case was looked at" and each case says "predefined, outcome-free"; timestamped evidence does not supp
* D-03 — Every selected case sits in the first part of D-1; rule structurally favours opening-minute (seed) structures and no D0 case exists
* D-04 — Case-study PNGs are generic single-episode V2 charts with no case-specific content (no case type, quantities, anchor item, counterpart, batch or price)
* D-15 — Existing selection tests are weak: test_case_selection_ignores_prices_and_outcomes perturbs only dataset columns that the datasets carry; it cannot detect an upstream dep
* D-16 — "SENSEX has no reversal" is definition-dependent: one parent flips a short into a long within a second but is not a REVERSED event
* E-D01 — coverage.json key order depends on PYTHONHASHSEED (byte-nondeterministic output, unhashed)
* E-D02 — Provenance heads in committed manifests do not identify the generating code; run_id depends on git HEAD; dirty check is partial
* E-D03 — Output manifests do not cover every output file; hash bases differ between stages
* E-D07 — Infrastructure code is untested: pe.cli 0 %, provenance.manifest, tool scripts, cases.record
* E-D09 — Dependencies unpinned; reproducibility asserted only for the present environment
* E-D12 — Surviving system mutants: C++ IST offset, Python schema_version check, git sha, manifest writers are pinned by no test

Low defects (29) are listed in the register with proposed corrections; none was applied. **Fixed in this audit:** only tests were added (`tests/test_m2f_regressions.py`: raw-ledger generator check, W3 weight pin, m2c/m2d manifest hashes). No delivered artifact was modified.

## 14. Unresolved methodological assumptions
Intra-second fill order (R1); exclusive vs inclusive batch threshold; C2 predecessor reference; stream boundary wording; reversal definition (per-fill vs net flip); parent identity column; EXPIRED_UNCLOSED as inference; case-selection history; number-block (unresolved by design); all inferred wing/body relations (W1 WEAKLY_SUPPORTED, W1_S60 / W3 UNRESOLVED, ownership and protective intent NOT_TESTABLE). Details and required decisions: `M2F_METHODOLOGY_LIMITATIONS.md`.

## 15. Acceptance conditions (section 8 of the audit brief)

| # | Condition | Result | Basis |
|---|---|---|---|
| 1 | Accounting and position quantities reconcile to source fills | **MET (under file order)** | Track A [RAW]/[IMPL]: all 41,421 fills; units, cash, inventory exact |
| 2 | Lineage does not double-count or omit inventory | **MET** | OA/CP unit totals invariant in every order; reference exact; Track A mutants M01-M03 killed |
| 3 | FIFO/LIFO/AVG differences remain analytical | **MET** | observed layer convention-independent by construction; 15,889 sensitive portions identical to reference |
| 4 | Reversal and partial-close behaviour correct | **MET WITH CONDITION** | correct under file order (390/130 split verified from raw); reversal count 20-23 depends on tie order (R1) |
| 5 | Closing-batch rules implemented as documented | **MET** | Track B: 0 differences vs independent reference, all 10 views; wording nits B-02/B-03 (Low) |
| 6 | C1/C2 sensitivities and tie-order limitations correctly reported | **NOT FULLY MET** | C2 tie sensitivity reported; replay tie-order dependence and exclusive-threshold sensitivity were not (B-01, C-01); addendum provided |
| 7 | Wing/body methods preserve ambiguity and unmatched quantities | **MET** | Track C: items/links exact; multiplicity and unmatched units preserved; denominators reconcile |
| 8 | Evidence classes conservative | **MET** | no upgrade found; wording defects C-06, D-10 recorded |
| 9 | Scope exclusions remain visible | **MET** | Track C denominators; Track D V3/V6 exclusions shown |
| 10 | Both frozen cycles reconcile to raw source | **MET** | Track D: ~24,500 checks, 0 failures |
| 11 | Chart data and displayed figures reproducible | **MET** | Track D/E: regeneration byte-identical; manifests partial (E-D03, D-12) |
| 12 | Python/C++ consistency intact for shared logic | **MET (XLANG only)** | Tracks A/E: byte-identical; edge-case differences E-D05/E-D06 (Low) |
| 13 | Critical and high defects resolved or explicitly block | **BLOCKS PASS** | D-A01 (High) unresolved; requires user decision |
| 14 | Medium/low limitations documented | **MET** | defect register + limitations document; Medium items open pending approval |
| 15 | No unsupported claims of ownership, protective intent, decision triggers or alpha | **MET FOR THESE CLAIMS** | Tracks C/D inspection; but one unsupported methodological claim (M2-E case selection "fixed before") recorded as D-02 |

## 16. Standard applied
The audit asked whether the claims survive an independent attempt to disprove them. The numerical claims do, under a declared convention; the claim that the reconstruction is convention-free does not, and one methodological claim in M2-E (case selection) was overstated. Both are reported here as findings, and neither has been silently corrected.

**Stopped after M2-F for approval. M3 and portfolio-construction work have not begun.**

## R1 ADDENDUM (2026-11-15; earlier text unchanged)
The High finding D-A01 (with B-01 and C-01) has been **remediated by policy and disclosure, not by changing results**: `SOURCE_ROW_ORDER_CONVENTION` was approved as the primary deterministic fill-order convention (not verified chronology), sensitivity-only policies were added, the convention is stamped in the delivered manifests, and the dependence is disclosed in the M2-B/M2-C/M2-D reports and the evidence registry (`reports/R1_TIE_ORDER_CONVENTION.md`). The underlying ambiguity cannot be eliminated with the available source data. **This addendum does not change the M2-F decision (CONDITIONAL PASS)**; the acceptance gate and the remaining Medium/Low findings are still to be processed. Two statements in this report are corrected in the R1 document: the "two mixed-side groups" statement (incomplete as an explanation of accounting sensitivity) and the note that the M2-B figure "20 fills / 42 rows" was reproduced exactly (not verified).

## M2 CLOSURE ADDENDUM (2026-11-16; earlier text unchanged)
The decision of this report (**M2 - CONDITIONAL PASS**, 15 conditions above) is the historical audit conclusion at commit `562d7eb6` and stays as written. Closure work after it is recorded in `reports/M2_CLOSURE_FINAL_REPORT.md`: the four "conditions to convert to PASS" of this report are met (1: Option C decision + disclosure quantifying the sensitivity; 2: case-selection wording corrected, Decision A; 3: reversal definitions, Decision B; 4: every Medium defect has a closure disposition: 12 fixed, 3 accepted with evidence, 4 deferred with reasons). New findings of the closure: N1 (Medium, fixed), N2 (Medium, resolved), review findings CR-01..CR-08 (1 Medium, 7 Low; fixed or dispositioned). The final M2 decision proposed there is again **CONDITIONAL PASS**, with standing conditions for M3, and awaits the owner's approval. The original disposition lines of this audit are preserved verbatim in `reports/m2f_audit/disposition_history.json` and the defect register.

