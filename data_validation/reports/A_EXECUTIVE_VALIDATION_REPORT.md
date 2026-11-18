# A. Executive validation report
**Dataset:** `data/market_context_3yr_broad/` on branch `data/local-breeze-fetch`, **commit `eb4097308d47ccc75078ab73ba76d33bb1c7030b`** (3,391 files, 12.2 GB). Validated 2026-11-18 by recomputation from git objects; nothing was modified or re-downloaded.

## Verdict: CONDITIONAL PASS (NIFTY) / FAIL against the stated three-year SENSEX objective
| | NIFTY | SENSEX |
|---|---|---|
| Status | **CONDITIONAL PASS** | **CONDITIONAL PASS for 2024-05-31 onward (price data only); FAIL for the stated three-year objective** |
| Expected weekly expiries (independent calendar) | 160 | 159 |
| Complete / Partial / Missing / Unverified | 156 / 2 / 2 / 0 | 123 / 1 / 35 / 0 |
| Span | 2023-11-08 to 2026-11-09 (3.0 y) | 2024-05-30 to 2026-11-12 (2.45 y) |

**Why it is not a plain PASS.** The dataset is internally clean: every raw row equals its normalized row, there are no duplicates, no invalid OHLC, no timezone or expiry-identity errors, the strike window is centred on the D-2 close as intended, and prices equal the earlier exact-trade Breeze files on 1.22 million overlapping minutes. But (1) SENSEX lacks 35 expected expiries and all open interest, so the three-year SENSEX design cannot be satisfied; (2) two D-1 sessions are special Muhurat sessions and one NIFTY D-1 session is incomplete; (3) NIFTY spot after the closing-auction change contains invalid prints at 15:20+; (4) a few vendor errors (13 negative volumes, 6 SENSEX price spikes); (5) the final year is not an independent out-of-sample period.

## What was verified and how independent it is
* **Independent of the dataset's own files:** expiry calendar (public exchange-rule reports + Yahoo trading days), D-2 closes and index daily OHLC (Yahoo), strike-grid and CE/PE logic, raw-to-normalized equality recomputed with my own code.
* **Same vendor, different pipeline:** the earlier exact-trade files (identical on all overlapping minutes). This catches pipeline bugs, **not** vendor errors.
* **Not independently verifiable here:** option prices, volume and open interest against an exchange source; the Breeze "no SENSEX history before 2024-05" claim (needs credentials); special-session dates for 2023-2025.

## Acceptance criteria (section 11)
| # | Criterion | Result |
|---|---|---|
| 1 | Every expected expiry accounted for | MET: all 319 classified; 4 NIFTY and 36 SENSEX are not Complete |
| 2 | D-1 and D0 quantified separately | MET: NIFTY D-1 156 / D0 158; SENSEX D-1 123 / D0 124 |
| 3 | Contract and strike coverage verified | MET with limits: plan symmetric and correct; unlisted vs failed contracts cannot be separated (D08, D09) |
| 4 | OHLC integrity | MET: 0 failures; 13 negative volumes and 6 spikes documented |
| 5 | Timestamp and timezone integrity | MET with exceptions: naive timestamps, bars after close and pre-open rows documented (D12, D19) |
| 6 | Underlying correctly aligned | PARTLY: aligned and consistent with Yahoo; NIFTY post-2026-08-03 15:20+ invalid (D05); special-session D-1 (D04) |
| 7 | Raw vs normalized consistency | MET (0 differences) but raw edited for two sessions (D10) |
| 8 | Manifest matches actual records | MET for files (0 differences); manifest lacks per-contract outcomes and the scripts are missing (D09) |
| 9 | Known gaps documented | MET in this report; the dataset's own reports understate SENSEX gaps (D01, D02, D17) |
| 10 | Validation reproducible | MET: `data_validation/run_validation.sh`, 25 tests (18 check/corruption tests in `tests/test_checks.py`, 7 invariants over the produced tables in `tests/test_outputs.py`) |

## Top actions
1. Re-probe and fetch the 5 unreported SENSEX expiries, the NIFTY 2024-06-26 session, the regular D-1 for NIFTY 2026-11-09 and SENSEX 2025-10-23, and NIFTY 2026-11-16/17 (credentials needed).
2. Do not use SENSEX open interest; decide whether SENSEX stays in a three-year design.
3. In research loaders: 09:15-15:29 only (15:39 post-2026-08-03), volume 0 = no trade, no NIFTY spot after 15:14 post-2026-08-03, drop the 13 + 6 bad bars, define the universe from the planned grid.
4. Decide how to treat the exposed 2026-06-22..10-22 block (report D).

Details: B coverage, C quality, D readiness, E defect register (20 defects: 0 Critical, 5 High, 11 Medium, 4 Low).

## Independent review
_Reviewer notes not yet attached._
