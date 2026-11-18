# E. Defect register
Pinned commit `eb4097308d47ccc75078ab73ba76d33bb1c7030b`. 23 defects: {'Medium': 12, 'High': 7, 'Low': 4}. Rated after an independent review (see report A); several ratings were raised or lowered on its evidence. Severity: Critical = data cannot be trusted at all; High = blocks a stated use or a whole segment; Medium = needs a filter or documentation; Low = cosmetic or context. No Critical defects were found: every raw row equals its normalized row, and no OHLC, duplicate, timezone or expiry-identity error exists.

### D01 (High): SENSEX
* **Sessions:** 2024-11-22, 2025-02-25, 2025-04-01, 2025-08-26, 2026-03-12 (D-1 and D0 of each)
* **Evidence:** Five regular weekly expiries (Tuesday/Friday/Thursday, all trading days in the independent calendar) have no data. The dataset calendar lists them as NOT FOUND, yet the delivered reports say "sessions missing 0" and "expiries planned 124, done 124".
* **Root cause:** Expiry discovery failed for those weeks (probe outcome not recorded; scripts not committed).
* **Resolution:** Re-probe with credentials; fetch the 10 sessions; amend the reports.
* **Blocks research:** No for NIFTY; partially for SENSEX expiry-complete studies

### D02 (High): SENSEX
* **Sessions:** 2023-11-03 .. 2024-05-24 (30 expected weekly expiries)
* **Evidence:** No SENSEX data before 2024-05-30. 30 expected Friday expiries are absent (the reports say 35 weeks; the calendar file shows 30 plus the 5 in D01). The cause (vendor has no F&O history) is the acquirer's claim; I cannot re-probe without credentials.
* **Root cause:** Claimed Breeze limitation (UNVERIFIED).
* **Resolution:** Re-probe; if confirmed, SENSEX has only 2.45 years and cannot support 2 years in-sample + 1 year out-of-sample.
* **Blocks research:** Yes, for the stated three-year SENSEX design

### D03 (High): SENSEX
* **Sessions:** all 248 sessions
* **Evidence:** open_interest = 0 in 12,928,723 of 12,928,723 rows (36,404 of 36,404 contract-sessions). Of these rows 10,348,960 carry volume > 0, so zero is "unavailable", not real.
* **Root cause:** API does not return SENSEX open interest (or returns a placeholder).
* **Resolution:** Treat SENSEX OI as missing (NaN), never 0; do not use it.
* **Blocks research:** Yes for OI-based research; no for price/volume research

### D04 (High): NIFTY / SENSEX
* **Sessions:** NIFTY expiry 2026-11-09; SENSEX expiry 2025-10-23
* **Evidence:** D-1 was taken as the previous day that has Breeze data, which selected Diwali Muhurat special sessions (NIFTY Sunday 2026-11-08: 76 spot bars, 11,190 option rows; SENSEX Tuesday 2025-10-21: 204 spot bars, 8,344 option rows). The regular previous sessions (2026-11-06, 2025-10-20) are absent. NIFTY ATM centre 25,050 and SENSEX 84,400 were then computed from the regular session before the special one.
* **Root cause:** D-1 defined from data presence, not from a regular-session calendar.
* **Resolution:** Fetch regular D-1; tag Muhurat/special sessions; exclude them from D-1/D0.
* **Blocks research:** No (2 expiries), but they must be excluded or repaired

### D05 (High): NIFTY / SENSEX
* **Sessions:** all 30 sessions from 2026-08-03 (closing-auction era), 15:20 to about 15:29
* **Evidence:** NIFTY spot bar 15:20 deviates from the 15:14 close in both directions (-173 to +160 bp; 6 of 30 sessions beyond 0.5% at the open of the bar) and decays over the following minutes. SENSEX is affected too, though less: the spot-minus-futures basis moves by more than 25 bp at 15:20 on 4 of 30 post-era sessions and up to 269 bp (90th percentile 112 bp vs 9 bp before the change; NIFTY 123 bp vs 5 bp; 21 of 30 NIFTY sessions beyond 25 bp, 0 of 218 before). Futures are clean. The earlier exact-trade dataset shows the same artefact. It distorts day high/low (12 NIFTY sessions differ from Yahoo by more than 0.3%), spot-vs-option checks after 15:19 (1,278 NIFTY / 733 SENSEX intrinsic-value breaches) and the SENSEX option spikes of 2026-09-10 15:21 and 2026-10-01 15:26. Spot also has no bars for 15:16-15:19 on the 10 later post-era NIFTY days.
* **Root cause:** Index values published during the closing-auction window are not valid prints.
* **Resolution:** Use spot only up to 15:14 on post-2026-08-03 sessions, or take the closing level from another source.
* **Blocks research:** Partly: spot-based features after 15:15 in post-2026-08 sessions

### D06 (High): NIFTY / SENSEX
* **Sessions:** 20 NIFTY rows (10 negative, 10 positive) and 3 negative SENSEX rows
* **Evidence:** Signed 32-bit wrap-around in the volume field. NIFTY: 10 negative rows (-4.25e9 .. -4.29e9, e.g. -4,259,883,546 -> true 35,083,750 after adding 2^32; 2024-01-04 .. 2025-04-30) and 10 POSITIVE rows of about 4.31e9-4.33e9 (true value plus 2^32; 2023-12-07 .. 2024-11-07), all late on expiry day. A sign check finds only the negative ones; the positive ones silently inflate minute-level volume sums to ~4.3e9. The 3 SENSEX rows (-27,280 / -111,280 / -1,166,230) also have OI 0 and implausible prices.
* **Root cause:** Vendor int32 overflow; not repaired. (Found by the independent reviewer for the positive rows; recount confirmed 10 + 10 + 3.)
* **Resolution:** Treat volume outside [0, 2^31) as invalid; NIFTY values can be repaired by +/- 2^32 after review.
* **Blocks research:** No, but silent if unfiltered

### D07 (Low): SENSEX
* **Sessions:** 2024-10-03 11:25, 2024-10-17 10:28 and 12:29, 2026-09-10 15:21 (2 rows), 2026-10-01 15:26
* **Evidence:** 6 isolated price spikes flagged by a >5x neighbour test: e.g. 85,200 PE open 1,951 / close 132.45 at spot 83,070; 78,400 PE close 1,582.05 at spot 81,203. Three (2024) look like bad ticks; the three 2026 ones lie in the closing-window artefact (D05). The reviewer's wider scan finds 8, and one 2024 case (2024-09-20 14:24) may be a real move. OHLC consistency passes, so the plain OHLC test does not catch them.
* **Root cause:** Bad ticks / closing-window artefact.
* **Resolution:** Spike filter in research loaders; do not delete in the source.
* **Blocks research:** No

### D08 (Medium): NIFTY
* **Sessions:** 2024-06-26 (D-1 of expiry 2024-06-27)
* **Evidence:** Only 8,337 option rows against ~55,000 typical; 146 of 182 planned contracts have no rows, including all 22 within +-5 strikes of the centre (the data report's "min 20 strikes" is this session). Expiry 2024-06-27 D0 is normal.
* **Root cause:** Probable failed or truncated download (cannot be distinguished from "no trades" because the manifest records no per-contract outcome).
* **Resolution:** Re-download the session.
* **Blocks research:** No (one session)

### D09 (Medium): both
* **Sessions:** manifests/checkpoint.csv
* **Evidence:** The checkpoint lists attempted contracts only (103,776 rows, no status, byte count, hash or timestamp). 5,378 NIFTY and 8,732 SENSEX planned contracts have no data and cannot be classed as unlisted / no trades / failed. The download scripts named in the README are not in the repository.
* **Root cause:** Manifest design; scripts not committed.
* **Resolution:** Commit the scripts; add per-contract outcome and hash to the manifest.
* **Blocks research:** No, but limits reproducibility

### D10 (Medium): both
* **Sessions:** two sessions named in the README
* **Evidence:** The README says two sessions held ~25.3k duplicate rows removed "before this was moved here". The committed raw JSON for them has 0 duplicates and equals the normalized CSV, so the raw files are not the exact API response for those sessions (the "immutable raw" claim does not hold).
* **Root cause:** Raw files were edited.
* **Resolution:** Document; keep the original responses if they still exist.
* **Blocks research:** No

### D11 (Medium): NIFTY
* **Sessions:** expiry 2026-11-17
* **Evidence:** Last NIFTY weekly expiry excluded as "in-progress" although the run started 2026-11-17 21:16 (after the close). The summary also gives the last NIFTY expiry as 2026-11-10; the real one is Monday 2026-11-09 (2026-11-10 is a holiday).
* **Root cause:** Exclusion rule applied one day early; report error.
* **Resolution:** Fetch 2026-11-16/17; correct the summary.
* **Blocks research:** No

### D12 (Medium): both
* **Sessions:** all pre-2026-08-03 sessions
* **Evidence:** Bars after the last regular minute: NIFTY 23,793 rows (6,757 with volume), SENSEX 29,395 (5,918): a 15:30 bar per contract plus sparse later minutes; 145 option rows at 09:14 (NIFTY 2024-01-10/11); spot files hold pre-open rows 09:00/09:09-09:14 (NIFTY 1,826, SENSEX 1,440). The earlier validated pipeline dropped these.
* **Root cause:** Normalizer keeps everything the API returns.
* **Resolution:** Filter to 09:15-15:29 (15:39 from 2026-08-03) in research code and label the rest.
* **Blocks research:** No

### D13 (Medium): both
* **Sessions:** all
* **Evidence:** About a third of NIFTY option bars (6,312,819 of 18,978,233) and a fifth of SENSEX bars (2,579,706 of 12,928,723) are flat zero-volume bars: the vendor repeats the last price for minutes without trades. They are not trades. NIFTY also has 1,994 bars with volume but OI 0 (241 sessions) and 338 open-interest jumps of more than 5x.
* **Root cause:** Vendor behaviour.
* **Resolution:** Treat volume == 0 bars as "no trade"; never as an executable price.
* **Blocks research:** No

### D14 (Medium): both
* **Sessions:** SENSEX 2025-08-04 (71 minutes missing), 2025-10-16 (24), 2025-10-21 (171, Muhurat); NIFTY 2026-11-08 (299, Muhurat) and 10 + 13 sessions with 4-6 missing minutes
* **Evidence:** Spot sessions with missing regular minutes: NIFTY 10 sessions / 342 minutes, SENSEX 13 / 310. Most are the 15:16-15:19 auction-transition minutes after 2026-08-03; two SENSEX sessions are genuinely incomplete.
* **Root cause:** Vendor gaps.
* **Resolution:** Do not fill; flag sessions in research code.
* **Blocks research:** No

### D15 (Medium): both
* **Sessions:** contracts with no row
* **Evidence:** Presence of a contract in a session file requires at least one record that day. Using "contracts present in the files" as the tradable universe at time t leaks future information (a contract that only trades later is still present all day).
* **Root cause:** Files omit contracts without rows.
* **Resolution:** Define the universe from the planned grid (ATM rule + checkpoint) and treat missing as unknown.
* **Blocks research:** Yes, if misused

### D16 (Medium): both
* **Sessions:** proposed split
* **Evidence:** Not a data defect but a research-independence defect: the last 12 months include 2026-06-22..2026-10-22 (18 expiries per index) that were studied while reverse-engineering Algo 8. SENSEX in-sample would be only ~17 months.
* **Root cause:** Reuse of inspected data.
* **Resolution:** See report D.
* **Blocks research:** Yes for the stated split

### D17 (Medium): both
* **Sessions:** calendar CSV and README
* **Evidence:** The calendar column atm_ref is the ATM of the close of the last trading day of the ISO week (re-verified against Yahoo: 151/160 NIFTY, 119/160 SENSEX), i.e. information from after the expiry; it differs from the window centre (matches 3.8% NIFTY, 2.4% SENSEX). The atm_ref stored inside each raw file is the window centre (564/564). Using the calendar column for strike selection would be look-ahead. README errors: SENSEX first usable expiry is 2024-05-31 (first session 2024-05-30), not 2024-06-06; "35 weeks" excluded is 30 pre-boundary + 5 unreported mid-period weeks; the raw files have no `status` key.
* **Root cause:** Undocumented column meaning; documentation errors.
* **Resolution:** Rename or drop the column; correct the README.
* **Blocks research:** Yes if the column is misused

### D18 (Low): both
* **Sessions:** ATM centre
* **Evidence:** The strike-window centre equals ATM(D-2 close) with the independent Yahoo close for 306/316 NIFTY and 206/248 SENSEX sessions (two sessions per expiry share one centre, so 153/158 and 103/124 expiries), within one step for 312 and 244 sessions. The pipeline uses the Breeze close, which differs from the official close by a median of about 11 / 28 index points. Larger gaps are explained by special sessions (NIFTY 2026-02-03: Sunday Budget session; 2026-11-09 and SENSEX 2025-10-23: the D-1 problem in D04). The window was left by the opening spot by more than 10 steps in 7 NIFTY and 34 SENSEX sessions (reviewer), never leaving the +-45 window.
* **Root cause:** Rounding / source-of-close difference.
* **Resolution:** None needed.
* **Blocks research:** No

### D19 (Low): both
* **Sessions:** timestamps
* **Evidence:** Timestamps are naive local strings (no timezone). The convention (bar start, IST) matches the earlier exact-trade files (identical minutes), which verified it against Algo 8 fills, but it is not stated in this dataset.
* **Root cause:** Format.
* **Resolution:** Document; convert to IST-aware on load.
* **Blocks research:** No

### D20 (Medium): both
* **Sessions:** all
* **Evidence:** Lot size history is not supplied: NIFTY 50 -> 25 -> 75 -> 65 and SENSEX 10 -> 20 over the period (dates from memory, unverified here), so volume and OI units are not comparable over time and P&L per lot changes. Strike-listing windows and tick history are also not supplied, and option prices cannot be checked against an independent source (only the same vendor).
* **Root cause:** Out of scope of acquisition.
* **Resolution:** Source lot sizes and listing rules from exchange circulars before P&L work.
* **Blocks research:** Yes for cross-period volume/OI and P&L studies

### D21 (High): NIFTY / SENSEX
* **Sessions:** NIFTY D-1 2026-05-11; SENSEX D-1 2024-10-17, D0 2024-08-02, D0 2025-10-16
* **Evidence:** Intraday outages inside sessions that a presence check calls complete: NIFTY 2026-05-11 has volume 0 for every contract from 09:15 to 11:11 (117 minutes) while prices and OI move, and the 11:12 bar carries the accumulated volume; SENSEX 2024-10-17 has no option data after 13:13 (136 minutes; futures also truncated); SENSEX 2024-08-02 has a 35-minute hole (09:57-10:31) and 2025-10-16 a 24-minute hole (09:45-10:08) on expiry day. The first three change the expiry status to Partial.
* **Root cause:** Vendor outages; not flagged anywhere in the delivered reports.
* **Resolution:** Refetch if the vendor can supply them; otherwise flag sessions in research loaders.
* **Blocks research:** No (4 sessions), but minute-level volume studies must exclude them

### D22 (Medium): both
* **Sessions:** all sessions
* **Evidence:** Closing level: the 15:29 spot bar differs from the official close by a median of about 11 (NIFTY) / 28 (SENSEX) points, up to 120 / 290; the official close sits in the 15:30-15:39 bars, present in about 284 of 286 pre-auction NIFTY sessions but only about 100 of 248 SENSEX sessions, so using the last row of a file leaks the closing print into earlier decisions. There is no settlement price: the last D0 option bar is a last trade, not intrinsic value at the official close (90th-percentile gap 80-100 points for in-the-money contracts). (Reviewer-reported; the Yahoo comparison in report C is consistent with the 11 / 35-point close gap.)
* **Root cause:** Vendor data content.
* **Resolution:** Compute settlement from an official closing level; never use bars after 15:29 as decision-time data.
* **Blocks research:** No

### D23 (Low): both
* **Sessions:** sessions where the near-month future expires that day
* **Evidence:** On 35 NIFTY and 27 SENSEX sessions the near-month future in the file is the contract expiring that same day (recount confirmed), so futures-based forward prices and parity are unusable there.
* **Root cause:** Near-month definition.
* **Resolution:** Use the next contract on monthly expiry days.
* **Blocks research:** No