# Demonstration-cycle selection note (frozen)

Criteria: `docs/DEMO_CYCLE_SELECTION.md`, committed before this script was run. Inputs: source availability and reconstruction quality only. Eligibility: fills on D-1 and D0. Score = mean of C1–C6; tie-break earlier expiry. No grouping output, P&L or chart was examined.

## NIFTY: SELECTED `NIFTY|2026-06-30` (score 1.0000, 1146 fills)

Runner-ups: `NIFTY|2026-08-18` (1.0000); `NIFTY|2026-09-22` (0.9997); `NIFTY|2026-07-07` (0.9993)

| cycle | fills | C1_fill_coverage | C2_parent_metadata | C3_reconciliation | C4_option_marks | C5_classification | C6_d1_d0 | score |
|---|---|---|---|---|---|---|---|---|
| NIFTY|2026-06-30 | 1146 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| NIFTY|2026-08-18 | 568 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| NIFTY|2026-09-22 | 1303 | 0.9985 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.9997 |
| NIFTY|2026-07-07 | 1811 | 0.9956 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.9993 |

## SENSEX: SELECTED `SENSEX|2026-07-16` (score 1.0000, 729 fills)

Runner-ups: `SENSEX|2026-08-06` (1.0000); `SENSEX|2026-08-27` (1.0000); `SENSEX|2026-09-10` (1.0000)

| cycle | fills | C1_fill_coverage | C2_parent_metadata | C3_reconciliation | C4_option_marks | C5_classification | C6_d1_d0 | score |
|---|---|---|---|---|---|---|---|---|
| SENSEX|2026-07-16 | 729 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| SENSEX|2026-08-06 | 543 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| SENSEX|2026-08-27 | 1326 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| SENSEX|2026-09-10 | 935 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |

Ineligible (missing D-1 or D0 fills): NIFTY|2026-06-23, NIFTY|2026-08-11, NIFTY|2026-09-01, NIFTY|2026-09-15, NIFTY|2026-09-29

**Both selections are decided by the pre-registered tie-break (earlier expiry): several cycles per underlying score exactly 1.0000, so the score barely discriminates; it excludes only the five ineligible cycles and the lower-quality ones.** Not editing the formula after seeing this.

Full table: `demo_cycle_scores.csv`. **Frozen: not to be rerun after grouping results exist.**
