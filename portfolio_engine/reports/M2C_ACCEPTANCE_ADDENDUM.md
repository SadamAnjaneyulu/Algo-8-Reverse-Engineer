# M2-C acceptance addendum (final acceptance recorded; no committed M2-C output changed)

Committed primary C1/C2 outputs, code, tests and the original `M2C_*` reports are **unchanged**. This addendum records the acceptance decisions and completes the documentation checklist. Data: `m2c_addendum.json` (`tools/m2c_addendum.py`, read-only).

## 1. Acceptance decisions (reviewer)
1. **C1 first-fill chaining: PASS.** 2. **C2 last-to-first chaining: PASS**, retaining the implemented deterministic tie-break and predecessor reference. 3. Primary C1/C2 outputs are not changed. 4. The measured alternatives are **sensitivities** (§3). 5. **C1 and C2 are identical only under the selected convention; they are not universally equivalent.** 6. Reconstructed batches are **time-connected closing-order clusters**, not confirmed original portfolio decisions (identifiers keep the existing `CLOSING_BATCH` token; the wording in prose is "cluster"). 7. Whole-second precision and single-linkage chaining limitations are retained. 8. The number-block audit is complete; its conclusion stays **`UNRESOLVED — REVIEW REQUIRED`**. 9. The number-block variant is **not** implemented without new direct evidence or explicit stakeholder confirmation.
**Not claimed anywhere:** that a cluster is a recovered Algo 8 decision, that the registered 10-second parameter is a recovered strategy rule, or that a cluster is an opening basket.

## 2. Documentation checklist (where each item lives)
| Required item | Location |
|---|---|
| Exact primary ordering and tie-break | `M2C_CLOSING_BATCH_REPORT.md` §1: parents ordered by `(first closing-fill second, smallest closing source_row_id, parent_order_id)`; single linkage over **adjacent** parents in that order; implemented in `closing_batches.py: build_view` (default arguments) and re-implemented independently in `reference_partition` |
| Exact C2 predecessor reference | same §1: gap = `first(next) − last(previous)`, previous = the **immediately preceding parent in the primary order** (not the running maximum of earlier last fills) |
| Alternative conventions and their membership differences | `M2C_CLOSING_BATCH_REPORT.md` §3 (counts) and §3 below (exact members) |
| Chaining-duration distribution, longest-chain examples | report §2 (median / p99 / max per threshold) and §4 below |
| Inclusive threshold semantics | `gap ≤ threshold` (inclusive); pairs exactly at the threshold are counted in report §2 (e.g. 661 at 2 s) |
| Timestamp-precision limitation | whole-second timestamps; report §2 (1,633 pairs one second beyond the 2 s threshold) and `m2c_figures/m2c_precision_sensitivity.png` |
| Number-block interpretations and unresolved conclusion | `M2C_NUMBER_BLOCK_AUDIT.md` §3–4 (N1–N5), verdict `UNRESOLVED — REVIEW REQUIRED` |
| Reviewer findings and mutation evidence | report §6 (defects, fixes, six mutations killed) and `tests/test_closing_batches.py` |

## 3. Exact membership differences under the alternative conventions (sensitivities only)
Under **either** alternative (tie-break by parent id, or C2 reference = running-max last fill) C2 has one batch fewer at 2, 5 and 10 s and no difference at 30 and 60 s. At 2 s the difference is exactly this (SENSEX, 2026-07-02): approved rule gives the batches `[10853054]` and `[10853055, 10853056, 10853057]`; the alternatives give one batch `[10853055, 10853056, 10853057, 10853054]`. Parent `10853057` is the single closing parent whose fills span 57 s (first/last 1782986253 / 1782986310); parent `10853054` starts at 1782986283, i.e. inside that interval. The same parents are involved at 5 and 10 s. No other parent is affected at any threshold.

## 4. Chaining durations (C1; the 10 s primary view in bold) and longest chains
| g (s) | longest cluster (session) | parents | closing portions | contracts | units | time (IST) | duration (s) | largest link gap (s) |
|---:|---|---:|---:|---:|---:|---|---:|---:|
| 2 | 533 (2026-07-02) | 3 | 4 | 3 | 400 | 15:27:33–15:28:30 | **57** | 0 |
| 5 | 090 (2026-08-04) | 75 | 78 | 11 | 8,060 | 14:58:15–14:59:21 | **66** | 5 |
| 10 | 036 (2026-06-23) | 52 | 70 | 5 | 8,450 | 11:46:23–11:48:28 | **125** | 10 |
| 30 | 091 (2026-06-25) | 115 | 115 | 21 | 3,200 | 14:10:54–14:18:55 | **481** | 27 |
| 60 | 031 (2026-07-07) | 112 | 112 | 17 | 7,865 | 14:10:01–14:29:36 | **1175** | 59 |
Second and third longest clusters: 
| g (s) | 2nd session | parents | duration (s) | 3rd session | parents | duration (s) |
|---:|---|---:|---:|---|---:|---:|
| 2 | 2026-07-08 | 11 | 14 | 2026-06-23 | 12 | 12 |
| 5 | 2026-07-07 | 33 | 57 | 2026-07-02 | 3 | 57 |
| 10 | 2026-08-12 | 83 | 118 | 2026-07-30 | 89 | 102 |
| 30 | 2026-07-02 | 100 | 461 | 2026-07-07 | 42 | 363 |
| 60 | 2026-06-25 | 198 | 988 | 2026-07-30 | 109 | 748 |
Single-linkage chaining lets a cluster grow beyond its threshold (up to ≈ 28× at 2 s and 20× at 60 s, e.g. 198 parents over 988 s at 60 s); a long cluster is a chain of time-adjacent parents, not a single simultaneous event.

## 5. Terminology rule for later reports
Use "time-connected closing-order cluster" (C1/C2, threshold g) for these objects; never "decision", "basket" or "recovered rule".
