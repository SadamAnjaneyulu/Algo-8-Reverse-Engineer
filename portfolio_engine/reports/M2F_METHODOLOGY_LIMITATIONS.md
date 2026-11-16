# M2-F — Methodology limitations and unresolved assumptions

Facts below come from the five audit tracks (`reports/m2f_audit/track_*/FINDINGS.md`, scripts and `*_result.json`). Nothing here makes a methodology decision on the user's behalf; where a choice is needed it is listed in section 12. Earlier reports are **not** edited: this document and the defect register are the addenda.

## 1. Intra-second fill order is an unresolved convention (root cause R1; defects D-A01 High, B-01, C-01 Medium)

**Fact.** Raw timestamps are whole seconds, so the order of same-second fills is not decidable from the file. The pipeline uses file (source-row) order. Only same-instrument fills in the same second can matter: 4,464 groups over 824 instruments, of which 56 mix buy and sell (46 instruments). Trade id and order number agree with file order in 54 / 55 of 56 mixed-side groups and **contradict it in two** (NIFTY|2026-06-23|CE|24100 rows 726-728; NIFTY|2026-07-07|CE|24450 rows 9688-9689). No order was chosen by the audit.

**Measured sensitivity (Track A, full ledger, FIFO; LIFO and AVG show the same identity changes):**

| Alternative order | Instruments changed | Episode identities changed | Fills with changed open/close split | Reversal fills | Realized delta |
|---|---:|---:|---:|---:|---|
| file order (as delivered) | 0 | 0 | 0 | 23 mixed parents with a reversal fill (M2-B; the other rows count reversal fills as measured by Track A) | 0 |
| sells first | 1 | 1 | 2 | 23 | 0 |
| buys first | 5 | 12 | 4 | 23 | 0 |
| reversed file order | 18 | 33 | 49 | 22 | -400 paise FIFO, -1,300 LIFO |
| random (5 seeds) | 10-17 | 15-28 | 23-40 | 20-23 | 0 to -400 paise FIFO |
| trade id ascending | 2 | 4 | 4 | 21 | 0 |
| order number ascending | 2 | 4 | 4 | 21 | 0 |

**Invariant under every order tested:** total opening units (1,414,545), total closing units (1,377,065), final signed inventory per instrument, cash flow, AVG realized total.
**Not invariant:** which fills are opening/closing portions, episode ids, reversal count (20-23), opening-allocation row count, FIFO/LIFO attribution (13k-18k allocation pairs under global reshuffles), realized P&L (up to 13 rupees).

**Downstream effects measured:** closing-batch membership (Track B): 1-2 batches replaced at every threshold under sells-first / buys-first (2 / 4 fills change their split; 9-322 closing portions sit in changed batches); wing/body (Track C): opening body units 626,765 / 626,830 / 626,680 and closing body units 540,250 / 540,315 / 540,165 under file / sells-first / buys-first; items move by up to 4, W1 links by up to 2, W1_S60 links by up to 7. M2-B disclosed only the sells-first/buys-first case (20 fills, 5 instruments; reproduced exactly).

**Consequence.** Every episode id, reversal count, FIFO/LIFO attribution and batch/wing-body membership is conditional on the file-order convention. The accounting is correct under that convention; it is not tie-order-invariant. M3 must not treat episode identity or reversal counts as order-free facts.

## 2. Number-block grouping stays UNRESOLVED
Documented as unresolved and not implemented (Track B: no hits in code, tests or outputs; W4 not implemented; Track C). The audit introduced no interpretation.

## 3. Wing/body: what the data can and cannot support (Track C)
* A W1 candidate is a **temporal co-submission** relation. 86.9 % of opening wings have a same-minute body candidate versus 17.8-25.6 % at +-2..5 minute shifts, so co-timing is non-random. That fits a protective link and equally fits one scheduler submitting several legs. Protective intent is NOT_TESTABLE. 6 W1 links join the same contract and 24 are not further OTM (kept unflagged: C-04).
* A W2 weight is arithmetic, not an allocation: for 1,798 of 2,651 multi-candidate wings with a unique nearest body the largest weight is not on the nearest body; 9.1 % of bodies exceed weight 1.
* A W3 FIFO queue match is not ownership: median |dt| 1,007 s, wing before body in 7.9 %; reversing the body queue keeps only 136 of 12,096 pairs.
* A closing position without a role-labelled wing is not shown to lack a hedge (not testable). Scope exclusions are 336,040 closing units and 170,650 opening units outside the tag roles, plus origin-based exclusions of 59,065 (short-`num` episodes stopped by `s_`) and 114,645 (`h_`-only long episodes closed by `num`/`s_`/`v_`) units (C-03). Denominators reconcile to the full unit universe: no excluded population disappears.
* A body and a wing in one cycle do not demonstrably belong to one original basket (the 35 cycles have 51-279 distinct entry minutes).
* Wording: the "second app key 7.8 %" is a share of `h_` fills (7.84 %), not of wing units (8.43 % of opening wing units); "equal to TP-03 E6" is NOT VERIFIED (C-06).

## 4. M2-E case-study selection: limitation and ADDENDUM (D-02, D-03, D-04, D-15)
**What is supported.** The two demonstration cycles were frozen in `e06a711e` (2026-11-13T15:46:15Z), before the first lineage commit (15:57:05Z), the closing-batch code (16:26:17Z) and the wing/body code (17:52:42Z). Case selection is **outcome-free**: all fill prices were scrambled and the lineage, closing-batch, wing/body engines and the full build re-run, and all 20 selections were unchanged (Track D); an independent re-implementation reproduces all 10 rules and all selections.

**What is NOT supported.** The individual case-selection procedure (`pe/cases.py`, `tools/m2e_cases.py`, the case-study report) first appears in commit `10e33962` (2026-11-14T07:08:59Z), the same commit as the datasets, figures and case JSON; its rule text was edited again in `7117bbce` (07:48:29Z). There is no timestamped evidence that the rule was fixed before the cases were inspected. It must **not** be described as prospectively preregistered or proven outcome-blind. **Addendum:** the statements below in earlier reports are superseded by this paragraph.

| Location | Statement | Verdict |
|---|---|---|
| `reports/M2E_POSITION_CASE_STUDIES.md:5` (generated by `tools/m2e_cases.py:42`) | "Selection method (fixed before any case was looked at)" | **Not supported** |
| same file, per-case headers (lines 45, 67, 88, 115, 137, 162, 187, 212, 237, 261, 282, 303, 336, 361, 386, 411, 436; `tools/m2e_cases.py:16`) | "predefined, outcome-free" | "outcome-free" supported; "predefined" not shown |
| `python/pe/cases.py:1-3` | "PREDEFINED and structural" | structural and price-free supported; predefined not shown |
| `reports/M2E_HISTORICAL_FORENSICS_REPORT.md:7`; `reports/m2e_data/review_dispositions.json:3` | "10 predefined case types" | not shown |
| M2E final report section H | "git history can only show it from the checkpoint commit" | correct; contradicts the case-study heading |

**Selection effects (Track D).** 13 of 17 picks are the chronologically first candidate (the rest skip earlier candidates already used; NIFTY CT5 reuses CT1's episode, which is the single reversal). 16 of 17 selected episodes start 09:16-09:46 on D-1 and none on D0 (D-03): "no candidate wing" cases largely describe session-start staging, and case charts carry no case-specific content (D-04). Proposed correction (not applied): reword the generator text and add a D0 case rule; requires approval.

## 5. "Reversal" is definition-dependent (D-16)
Under the per-fill rule NIFTY has one REVERSED event and SENSEX none. One SENSEX parent (`s_16053046299662`) closes CE77600 #1 (160 units) and opens #2 (20 units) within a second without a net sign flip in one fill; NIFTY PE23850 shows a similar pattern across different parents. Whether that is a "reversal" is a definition decision; both definitions should be reported. No choice was made.

## 6. Expired and open inventory (D-A04)
81 instruments (71 long, 10 short; 37,480 units) have no closing fill. The EXPIRED_UNCLOSED label is an **inference** from missing closing fills: for 27 the last fill is the day before expiry; 13 last fills are at or after 15:30 IST. No settlement data exist, none is inferred, realized P&L equals the sum of closing allocations. The last data day equals the maximum expiry and no instrument expiring that day is non-flat, so the expiry-boundary and OPEN_AT_END_OF_DATA branches are never exercised on real data. In the two frozen cycles no position expired unclosed.

## 7. Closing batches: ambiguities in the approved text (Track B; measured, not decided)
* Tie order among equal-first-second parents: C1 provably invariant; C2 changes by 1 batch at 2/5/10 s under two orderings (4 parents), 0 at 30/60 s.
* C2 reference (running max over chain or stream instead of previous parent): 1 fewer batch at 2/5/10 s.
* **Exclusive threshold (gap < g) instead of inclusive:** changes 1,214 / 840 / 153 / 50 / 63 batches at 2/5/10/30/60 s. This is the largest wording-sensitive choice.
* Stream definition (underlying only; underlying x session; underlying x expiry): no effect on this data. Stream boundary is stricter than the approved D2 text and unrecorded (B-02); tie-break wording differs from code (B-03).
* Maximum chain length: 78/96/122/198 parents (baseline) vs 78/95/122/198 under the exclusive threshold; longest chains 57/66/125/481/1,175 s at 2/5/10/30/60 s. Chaining is single-linkage by design.
* Reproduction: an independent reference reproduces all ten views with 0 differences; it shares the written text with the author, so a misreading of the text would not appear.

## 8. Parent-order identity (D-A06)
Parent id = raw column 163 (39,874 parents). Column 4 (order number) gives 37,258 and is recycled across different parents, so it is not an identity. Column 163 never mixes side, instrument, quantity or app key. The alternative count is not stated in the reports.

## 9. Data and coverage limits
* Historical option marks are absent here: no mark-to-market, unrealized P&L or price-context analysis exists.
* AVG realized P&L is IEEE-754 float, not integer paise (D-A03); FIFO/LIFO are exact integers.
* The generator trusts the TP-01 parquet for content; the audit verified every row equals the raw csv (D-A02).
* 337 full-ledger raw fills lie outside 09:14-15:31 IST (none in the two cycles; not investigated).
* The two frozen cycles only; nothing is claimed for other cycles beyond the full-ledger numbers M2-D computed.
* `stage2_alpha_research/` holds only caches/pickles on disk; its sources are on branch `research/stage2-independent-alpha`, not an ancestor of HEAD (E-D11).

## 10. Independence limits of this audit and of Python/C++ parity
* All auditors, the author and earlier reviewers are the same model family; tracks received no author conclusions but share background assumptions. References for batches, wing/body and lineage were written from the same written specifications as the originals.
* Python/C++ parity (15/15 full-ledger/frozen-cycle combinations; 1,043 of 1,221 random runs byte-identical, 171 near-overflow C++ rejections, 7 extreme AVG runs) is shared-logic consistency, **not** independent economic or historical validation. Parser differences (E-D05) and overflow/float-sum semantics (E-D06) differ at extreme inputs only.
* Reproducibility: all deterministic outputs are byte-identical across clones, hash seeds, timezones and Python 3.11-3.13; dependencies are unpinned and PNG bytes match only under matplotlib 3.11.2 (E-D09).

## 11. Not inspected / not verified
M2-C chaining internals beyond equality and the independent reference; W2 weights and W3 queue arithmetic in the figures (aggregated from slices only); the absolute 107,530 mixed-module closing-wing figure beyond Track C's recomputation; 10 case PNGs (NIFTY CT3, CT6, CT6b, CT7, CT8; SENSEX CT1, CT2, CT6, CT6b, CT8); the claim that 6 tie-ambiguous fills equal `role_ambiguity_fills.csv`; TP-02 timeline row equality; the int64-overflow guard internals; en_US locale; Windows newlines; C++ line coverage; tools that need external market data; exchange lot-size circulars (lot sizes are data-derived: quantity gcd 65 NIFTY, 20 SENSEX).

## 12. Decisions required from the user (none were taken by the audit)
1. **Intra-second fill-order convention** (R1): keep file order as a declared convention and disclose sensitivity everywhere, or choose another order (trade id / order number / other), or require all downstream work to be tie-order-conditional.
2. **Case-selection wording:** accept this addendum, or approve changing the generator text and re-issuing the M2-E report.
3. **Reversal definition** for reporting (per-fill vs net sign flip across parents).
4. **Exclusive vs inclusive closing-batch threshold:** confirm the inclusive reading (the approved text), or record the exclusive reading as an alternative sensitivity.
5. Whether to approve the proposed Medium-defect fixes (legend placement, manifest coverage, pinned dependencies, additional tests) listed in `M2F_DEFECT_REGISTER.md`.

## R1 ADDENDUM — corrections to section 1 (2026-11-15; earlier text unchanged)
1. **"Trade id and order number contradict file order in two [mixed-side] groups."** True as stated (rows 726-728 and 9688-9689 for trade id; one of them for order number) but incomplete: those groups do not change any allocation. The accounting-relevant disagreements are two **same-side** groups at a position flip (NIFTY 2026-09-01 CE24600 rows 27911/27917 and PE23200 rows 27912/27916). Populations (order differs / allocation changes / episode identity / batches / wing-body) are reported separately in `reports/R1_TIE_ORDER_CONVENTION.md`.
2. **"M2-B disclosed ... (20 fills, 5 instruments; reproduced exactly)."** Only the 5-instrument count matches R1's `buys_first` result; the "20 fills / 42 rows" count was **not** reproduced under R1's populations (2 and 4 fills whose open/close split changes). The "reproduced exactly" wording was not verified and is withdrawn.
3. **Stress orders** (reversed, seeded random) in the table above remain valid as stress tests, not candidate chronologies. The sensitivity-only policies approved in R1 (including `sensex_trade_id_time`) are quantified in R1 section 3.

## R1-C DECISION — intra-second fill-order convention (2026-11-15; earlier text unchanged)

**Formal project decision (owner, 2026-11-15): OPTION C.** `SOURCE_ROW_ORDER_CONVENTION` remains the primary convention of the existing historical reconstruction; the delivered M2-B to M2-E outputs are **not** regenerated or replaced. Downstream research must evaluate **both** ordering assumptions: the baseline `SOURCE_ROW_ORDER_CONVENTION` and the sensitivity scenario `PER_CONTRACT_ID_SEQUENCE` (NIFTY numeric trade id; SENSEX embedded nanosecond trade-id time with epoch fallback for the exceptional row 8079; source-row order as the final tie-break), which is kept distinct from the individual `trade_id`, `order_no` and `sensex_trade_id_time` policies. Both result sets are preserved, and conclusions are labelled ordering-stable or ordering-dependent. **Neither ordering is claimed to be verified exchange execution chronology; the true intra-second sequence is UNRESOLVED.** Evidence and comparison: `reports/R1C_DUAL_SCENARIO_COMPARISON.md`.

**Limitation that remains.** Episode identity, reversal counts, opening/closing allocation, FIFO/LIFO lot attribution, closing-batch membership and wing/body membership are conditional on the ordering convention; the size of the dependence under the hybrid scenario is quantified in the comparison document (4 episodes in 2 instruments, 4 allocation splits, 3.7 to 3.8 % of closing fills' lot attribution, 1 batch per view, 6 W1/W2 links). Totals (units, inventory, cash, realized P&L, episode count) are stable under both.

## DECISION STATUS LEDGER (2026-11-16; section 12 above is the original list and is unchanged)

| # | Decision (section 12) | Status |
|---|---|---|
| 1 | Intra-second fill-order convention | **DECIDED**: Option C (2026-11-15): baseline `SOURCE_ROW_ORDER_CONVENTION` + sensitivity `PER_CONTRACT_ID_SEQUENCE`; N1 fixed, accepted limitation on intra-second portfolio paths |
| 2 | Case-selection wording | **DECIDED and IMPLEMENTED** (Decision A): corrected wording, case records unchanged, D-1 concentration disclosed |
| 3 | Reversal definition | **DECIDED and IMPLEMENTED** (Decision B): per-fill primary, parent-level diagnostic, never merged |
| 4 | Inclusive vs exclusive threshold | **DECIDED and IMPLEMENTED** (Decision C): inclusive primary; exclusive artifact separate |
| 5 | Medium-defect fixes | see `M2F_DEFECT_REGISTER.md` (closure dispositions per defect) |
| — | Other methodology choices (C2 predecessor, stream boundary, tie-break, parent identity, EXPIRED_UNCLOSED, number-block, W-classes, tag scope) | **RECORDED** (Decision D): `docs/BASKET_GROUPING_METHODOLOGY.md` |

**New findings of the closure:** N1 (Medium, fixed): keyed orders compared keys across instruments; measured on the full ledger (hybrid): 8,196 of 41,421 stream positions and 2,532 intermediate aggregate states differed (max 7,150 units), per-instrument sequences and every second-end state unaffected. N2 (Medium, resolved): hybrid M2-D/M2-E evidence reproduced from committed code; the earlier 167/139/29 file counts were wrong and are superseded by the reconciled inventory (170 paths).

**Accepted limitation:** no portfolio-level event-path interpretation inside a second is authorized for any scenario until the engine snapshots only at second boundaries (M3). **Owner decisions of 2026-11-16 (approved in the M2 closure directive):** Decision A (case-selection wording), Decision B (two reversal measures, never merged), Decision C (inclusive closing-batch threshold; exclusive reading as a sensitivity artifact), Decision D (recorded interpretations of the remaining methodology choices). Each was implemented with tests and scratch-mutant runs; delivered M2-B..M2-E outputs were not regenerated or replaced (only approved wording lines in four documents changed; every generated data file is byte-identical).
