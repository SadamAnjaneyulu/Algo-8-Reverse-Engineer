# E. Defect register
Pinned commit `eb4097308d47ccc75078ab73ba76d33bb1c7030b`. 20 defects: {'Medium': 11, 'High': 5, 'Low': 4}. Severity: Critical = data cannot be trusted at all; High = blocks a stated use or a whole segment; Medium = needs a filter or documentation; Low = cosmetic or context. No Critical defects were found: every raw row equals its normalized row, and no OHLC, duplicate, timezone or expiry-identity error exists.

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

### D05 (High): NIFTY
* **Sessions:** all 30 sessions from 2026-08-03 (closing auction era), bar 15:20 onward
* **Evidence:** Spot bar 15:20 opens up to +1.99% from the 15:14 close (6 of 30 sessions beyond 0.5%, 3 beyond 1%) and decays over the next minutes; SENSEX is unaffected. The earlier exact-trade dataset shows the same artefact (2026-10-21, 2026-10-22), so it is a vendor artefact present in both pipelines. It distorts day high/low (12 sessions differ from Yahoo by more than 0.3%) and spot-vs-option checks after 15:19.
* **Root cause:** Index values published during the closing-auction window are not valid prints.
* **Resolution:** Truncate spot at 15:14 for post-2026-08-03 sessions in research, or source official closes elsewhere.
* **Blocks research:** Partly: spot-based features after 15:15 in NIFTY post-2026-08

### D06 (Medium): NIFTY / SENSEX
* **Sessions:** 10 NIFTY rows (2024-01-04 .. 2025-04-30), 3 SENSEX rows (2024-10-17/18, 2024-10-24)
* **Evidence:** Negative volume. NIFTY values (-4.25e9 .. -4.29e9) equal the true volume minus 2^32 (signed 32-bit wrap-around; add 4,294,967,296 to recover, e.g. -4,259,883,546 -> 35,083,750). The 3 SENSEX rows have volume -27,280 / -111,280 / -1,166,230, OI 0 and implausible prices.
* **Root cause:** Vendor int32 overflow; not repaired in the dataset.
* **Resolution:** Flag, do not use; NIFTY rows can be repaired by +2^32 after review.
* **Blocks research:** No

### D07 (Medium): SENSEX
* **Sessions:** 2024-10-03 11:25, 2024-10-17 10:28 and 12:29, 2026-09-10 15:21 (2 rows), 2026-10-01 15:26
* **Evidence:** 6 isolated price spikes: e.g. 85,200 PE open 1,951 / close 132.45 at spot 83,070; 78,400 PE close 1,582.05 at spot 81,203 (3 points one minute earlier). OHLC consistency passes, so the plain OHLC test does not catch them.
* **Root cause:** Bad ticks in vendor data.
* **Resolution:** Exclude flagged bars; add a spike filter to research loaders.
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

### D17 (Low): both
* **Sessions:** calendar CSV
* **Evidence:** Column atm_ref does not equal the strike-window centre (matches 3.8% NIFTY, 2.4% SENSEX); its meaning is undocumented. README says SENSEX first usable expiry 2024-06-06 (actual first expiry 2024-05-31, first session 2024-05-30) and "35 weeks" excluded (30 + 5 unreported).
* **Root cause:** Documentation errors.
* **Resolution:** Correct the README / calendar header.
* **Blocks research:** No

### D18 (Low): both
* **Sessions:** ATM centre
* **Evidence:** The strike-window centre equals ATM(D-2 close) with the independent Yahoo close for 306/316 NIFTY and 206/248 SENSEX sessions, +-1 step for most of the rest (the pipeline uses the Breeze close, which differs from the official close by about 11 / 35 index points). Larger gaps are explained by special sessions (NIFTY 2026-02-03: Sunday Budget session; 2026-11-09 and SENSEX 2025-10-23: the D-1 problem in D04).
* **Root cause:** Rounding / source-of-close difference.
* **Resolution:** None needed; +-45 strikes absorb it.
* **Blocks research:** No

### D19 (Low): both
* **Sessions:** timestamps
* **Evidence:** Timestamps are naive local strings (no timezone). The convention (bar start, IST) matches the earlier exact-trade files (identical minutes), which verified it against Algo 8 fills, but it is not stated in this dataset.
* **Root cause:** Format.
* **Resolution:** Document; convert to IST-aware on load.
* **Blocks research:** No

### D20 (Low): both
* **Sessions:** all
* **Evidence:** Lot size, strike-listing windows and tick-size history are not part of the dataset; volume units (contracts or units) are not stated. Option prices cannot be checked against an independent source (only the same vendor).
* **Root cause:** Out of scope of acquisition.
* **Resolution:** Source from exchange circulars before P&L work.
* **Blocks research:** No