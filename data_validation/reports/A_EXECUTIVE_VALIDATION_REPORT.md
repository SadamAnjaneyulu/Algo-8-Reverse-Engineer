# A. Executive validation report
**Dataset:** `data/market_context_3yr_broad/` on branch `data/local-breeze-fetch`, **commit `eb4097308d47ccc75078ab73ba76d33bb1c7030b`** (3,391 files, 12.2 GB). Validated 2026-11-18 by recomputation from git objects; nothing was modified or re-downloaded.

## Verdict: CONDITIONAL PASS (NIFTY) / FAIL against the stated three-year SENSEX objective
| | NIFTY | SENSEX |
|---|---|---|
| Status | **CONDITIONAL PASS** | **CONDITIONAL PASS for 2024-05-31 onward (price data only); FAIL for the stated three-year objective** |
| Expected weekly expiries (independent calendar) | 160 | 159 |
| Complete / Partial / Missing / Unverified | 155 / 3 / 2 / 0 | 121 / 3 / 35 / 0 |
| Span | 2023-11-08 to 2026-11-09 (3.0 y) | 2024-05-30 to 2026-11-12 (2.45 y) |

**Why it is not a plain PASS.** The dataset is internally clean: every raw row equals its normalized row, there are no duplicates, no invalid OHLC, no timezone or expiry-identity errors, the strike window is centred on the D-2 close as intended, and prices equal the earlier exact-trade Breeze files on 1.22 million overlapping minutes. But (1) SENSEX lacks 35 expected expiries and all open interest, so the three-year SENSEX design cannot be satisfied; (2) two D-1 sessions are special Muhurat sessions, one NIFTY D-1 session is largely empty and three more sessions have intraday outages; (3) spot after the closing-auction change (2026-08-03) contains invalid prints around 15:20 in NIFTY and, less so, SENSEX; (4) vendor errors: 23 int32 wrap-around volumes (13 negative, 10 positive and therefore invisible to a sign check) and a few bad price ticks; (5) the final year is not an independent out-of-sample period.

## What was verified and how independent it is
* **Independent of the dataset's own files:** expiry calendar (public exchange-rule reports + Yahoo trading days), D-2 closes and index daily OHLC (Yahoo), strike-grid and CE/PE logic, raw-to-normalized equality recomputed with my own code.
* **Same vendor, different pipeline:** the earlier exact-trade files (identical on all overlapping minutes). This catches pipeline bugs, **not** vendor errors.
* **Not independently verifiable here:** option prices, volume and open interest against an exchange source; the Breeze "no SENSEX history before 2024-05" claim (needs credentials); special-session dates for 2023-2025.

## Acceptance criteria (section 11)
| # | Criterion | Result |
|---|---|---|
| 1 | Every expected expiry accounted for | MET: all 319 classified; 5 NIFTY and 38 SENSEX are not Complete |
| 2 | D-1 and D0 quantified separately | MET: NIFTY D-1 155 / D0 158; SENSEX D-1 122 / D0 123 |
| 3 | Contract and strike coverage verified | MET with limits: plan symmetric and correct; unlisted vs failed contracts cannot be separated (D08, D09) |
| 4 | OHLC integrity | MET: 0 OHLC failures; volume wrap-arounds (23), bad ticks (6) and outages documented (D06, D07, D21) |
| 5 | Timestamp and timezone integrity | MET with exceptions: naive timestamps, bars after close and pre-open rows documented (D12, D19) |
| 6 | Underlying correctly aligned | PARTLY: aligned and consistent with Yahoo; NIFTY post-2026-08-03 15:20+ invalid (D05); special-session D-1 (D04) |
| 7 | Raw vs normalized consistency | MET (0 differences) but raw edited for two sessions (D10) |
| 8 | Manifest matches actual records | MET for files (0 differences); manifest lacks per-contract outcomes and the scripts are missing (D09) |
| 9 | Known gaps documented | MET in this report; the dataset's own reports understate SENSEX gaps (D01, D02, D17) |
| 10 | Validation reproducible | MET: `data_validation/run_validation.sh`, 25 tests (18 check/corruption tests in `tests/test_checks.py`, 7 invariants over the produced tables in `tests/test_outputs.py`) |

## Top actions
1. Re-probe and fetch the 5 unreported SENSEX expiries, the NIFTY 2024-06-26 session, the regular D-1 for NIFTY 2026-11-09 and SENSEX 2025-10-23, and NIFTY 2026-11-16/17 (credentials needed).
2. Do not use SENSEX open interest; decide whether SENSEX stays in a three-year design.
3. In research loaders: 09:15-15:29 only (15:39 post-2026-08-03), volume 0 = no trade, no spot after 15:14 on post-2026-08-03 sessions, drop volumes outside [0, 2^31) and flagged spikes, mask the four outage sessions, define the universe from the planned grid.
4. Decide how to treat the exposed 2026-06-22..10-22 block (report D).

Details: B coverage, C quality, D readiness, E defect register (23 defects: 0 Critical, 7 High, 12 Medium, 4 Low).

## Independent review
A separate reviewer (another model instance, given the dataset, the independent Yahoo series and my headline findings but not my code's results to rely on) recomputed the findings with its own code. This is a second opinion, **not proof of correctness**; I re-verified every point below that changed a conclusion.

| Finding | Reviewer result | My action |
|---|---|---|
| Manifest vs files; option row totals | Reproduced (103,776 rows; 182 contracts per session; 18,978,233 / 12,928,723 rows) | none |
| Raw = normalized | Reproduced on 26 option sessions and 60 underlying files (same row sets, 0 mismatches; row order differs; raw carries two extra fields; the README's raw `status` key does not exist); raw is already deduplicated | D10 kept |
| NIFTY coverage | 160 expected expiries reproduced; the 2024-06-27 D-1 session (36 contracts) is a second Partial. My interim chat message said 157 Complete / 1 Partial; the tables at that time said 156 / 2 / 2; after adding outage detection from the review the final numbers are **155 / 3 / 2** (NIFTY) and **121 / 3 / 35** (SENSEX) | corrected in the final verdict |
| ATM centre | Reproduced (NIFTY 306/316, SENSEX 206/248 sessions exact; two sessions per expiry share one centre, so the true n is 158 and 124). The calendar column `atm_ref` equals ATM of the close of the last trading day of the ISO week (re-verified: 151/160 NIFTY, 119/160 SENSEX), i.e. look-ahead if used; the `atm_ref` stored inside each raw file is the window centre | D17 rewritten |
| OI | Reproduced; zeros concentrate in deep in-the-money contracts | D03/D13 kept |
| Negative volume | **Mis-stated by me**: there are also positive wrap-around values (true + 2^32) | D06 rewritten after a full scan |
| Closing-window spot artefact | NIFTY confirmed in both directions (-173 to +160 bp); **SENSEX is also affected** in the spot-versus-futures basis | D05 widened after a full scan |
| Bars after the last regular minute; flat bars carry the previous close | Reproduced | none |
| Legacy cross-check | Reproduced on 200 random contract-days (75,039 minutes, 0 mismatches); the 20 absent legacy contract-days lie outside the planned window, not fetch failures; **it shows repeatability, not accuracy** | wording kept |

**Blind spots the reviewer raised (all added to defect register or readiness report):** intraday outages inside sessions labelled Complete (NIFTY 2026-05-11 D-1 zero volume for 117 minutes; SENSEX 2024-10-17 options end 13:13; SENSEX 2024-08-02 and 2025-10-16 holes); official close lives in 15:30-15:39 bars that exist for almost all NIFTY but about 100 of 248 SENSEX pre-auction sessions, so using the last row leaks the closing print; no settlement price on D0; lot-size history (NIFTY 50/25/75/65, SENSEX 10/20) makes volume and OI non-comparable over time; "contract present" is a look-ahead filter (13.7% of planned contracts have no rows, mostly deep in the money); near-month futures equals the same-day-expiring contract on 35 NIFTY / 27 SENSEX monthly-expiry sessions; Yahoo is a weak independent source (NaN rows on real trading days, no Sunday sessions, index only); the fixed window was left by the opening spot by more than 10 steps in 7 NIFTY and 34 SENSEX sessions (never exited).

**Severity changes accepted:** raised: wrap-around volumes, intraday outages, calendar `atm_ref`, closing-window artefact (both indices); lowered: the SENSEX "spikes" (2024-09-20 may be a real move; the 2026 ones belong to the closing-window artefact). Not accepted without evidence: the 2026-11-17 exclusion rationale is plausible if the run's 21:16 timestamp is IST; I could not verify the timezone, so D11 is rated on that uncertainty.

