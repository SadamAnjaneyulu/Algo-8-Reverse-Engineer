"""Generates reports A-E from the computed tables (reports/tables). Run after the scans: python3 -m validation.make_reports"""
import csv, json, os
import pandas as pd
T, OUT = 'reports/tables', 'reports'
N = json.load(open(f'{T}/report_numbers.json')); Q = N['quality']; CV = N['coverage']; INV = N['inventory']; LEG = N['legacy']
cov = {i: pd.read_csv(f'{T}/{i}_expiry_coverage.csv') for i in ('nifty', 'sensex')}; deep = pd.read_csv(f'{T}/deep_scan_sessions.csv'); ex = pd.read_csv(f'{T}/deep_scan_examples.csv'); neg = pd.read_csv(f'{T}/negative_volume_rows.csv')
yv = pd.read_csv(f'{T}/index_vs_yahoo.csv'); post = pd.read_csv(f'{T}/post_cas_spot_1520_anomaly.csv'); o = pd.DataFrame(json.load(open(f'{T}/option_session_scan.json'))); u = pd.DataFrame(json.load(open(f'{T}/underlying_scan.json')))
COMMIT = INV['commit']; STATUS = 'CONDITIONAL PASS (NIFTY) / FAIL against the stated three-year SENSEX objective'
n = lambda x: f'{int(x):,}'
def tab(df, cols=None): 
    df = df if cols is None else df[cols]; return '| ' + ' | '.join(df.columns) + ' |\n|' + '---|' * len(df.columns) + '\n' + '\n'.join('| ' + ' | '.join('' if pd.isna(v) else str(v) for v in r) + ' |' for r in df.itertuples(index=False))
oi_n = Q['nifty']['oi']; oi_s = Q['sensex']['oi']
D = [  # id, severity, instrument, session, evidence, root cause, resolution, blocks research
 ('D01', 'High', 'SENSEX', '2024-11-22, 2025-02-25, 2025-04-01, 2025-08-26, 2026-03-12 (D-1 and D0 of each)', 'Five regular weekly expiries (Tuesday/Friday/Thursday, all trading days in the independent calendar) have no data. The dataset calendar lists them as NOT FOUND, yet the delivered reports say "sessions missing 0" and "expiries planned 124, done 124".', 'Expiry discovery failed for those weeks (probe outcome not recorded; scripts not committed).', 'Re-probe with credentials; fetch the 10 sessions; amend the reports.', 'No for NIFTY; partially for SENSEX expiry-complete studies'),
 ('D02', 'High', 'SENSEX', '2023-11-03 .. 2024-05-24 (30 expected weekly expiries)', 'No SENSEX data before 2024-05-30. 30 expected Friday expiries are absent (the reports say 35 weeks; the calendar file shows 30 plus the 5 in D01). The cause (vendor has no F&O history) is the acquirer\'s claim; I cannot re-probe without credentials.', 'Claimed Breeze limitation (UNVERIFIED).', 'Re-probe; if confirmed, SENSEX has only 2.45 years and cannot support 2 years in-sample + 1 year out-of-sample.', 'Yes, for the stated three-year SENSEX design'),
 ('D03', 'High', 'SENSEX', 'all 248 sessions', f'open_interest = 0 in 12,928,723 of 12,928,723 rows ({oi_s["contract_sessions_oi_all_zero"]:,} of {oi_s["contract_sessions_oi_all_zero"]:,} contract-sessions). Of these rows 10,348,960 carry volume > 0, so zero is "unavailable", not real.', 'API does not return SENSEX open interest (or returns a placeholder).', 'Treat SENSEX OI as missing (NaN), never 0; do not use it.', 'Yes for OI-based research; no for price/volume research'),
 ('D04', 'High', 'NIFTY / SENSEX', 'NIFTY expiry 2026-11-09; SENSEX expiry 2025-10-23', 'D-1 was taken as the previous day that has Breeze data, which selected Diwali Muhurat special sessions (NIFTY Sunday 2026-11-08: 76 spot bars, 11,190 option rows; SENSEX Tuesday 2025-10-21: 204 spot bars, 8,344 option rows). The regular previous sessions (2026-11-06, 2025-10-20) are absent. NIFTY ATM centre 25,050 and SENSEX 84,400 were then computed from the regular session before the special one.', 'D-1 defined from data presence, not from a regular-session calendar.', 'Fetch regular D-1; tag Muhurat/special sessions; exclude them from D-1/D0.', 'No (2 expiries), but they must be excluded or repaired'),
 ('D05', 'High', 'NIFTY / SENSEX', 'all 30 sessions from 2026-08-03 (closing-auction era), 15:20 to about 15:29', f'NIFTY spot bar 15:20 deviates from the 15:14 close in both directions (-173 to +160 bp; {int((post[post["index"]=="nifty"].jump_pct.abs()>0.5).sum())} of 30 sessions beyond 0.5% at the open of the bar) and decays over the following minutes. SENSEX is affected too, though less: the spot-minus-futures basis moves by more than 25 bp at 15:20 on 4 of 30 post-era sessions and up to 269 bp (90th percentile 112 bp vs 9 bp before the change; NIFTY 123 bp vs 5 bp; 21 of 30 NIFTY sessions beyond 25 bp, 0 of 218 before). Futures are clean. The earlier exact-trade dataset shows the same artefact. It distorts day high/low (12 NIFTY sessions differ from Yahoo by more than 0.3%), spot-vs-option checks after 15:19 (1,278 NIFTY / 733 SENSEX intrinsic-value breaches) and the SENSEX option spikes of 2026-09-10 15:21 and 2026-10-01 15:26. Spot also has no bars for 15:16-15:19 on the 10 later post-era NIFTY days.', 'Index values published during the closing-auction window are not valid prints.', 'Use spot only up to 15:14 on post-2026-08-03 sessions, or take the closing level from another source.', 'Partly: spot-based features after 15:15 in post-2026-08 sessions'),
 ('D06', 'High', 'NIFTY / SENSEX', '20 NIFTY rows (10 negative, 10 positive) and 3 negative SENSEX rows', 'Signed 32-bit wrap-around in the volume field. NIFTY: 10 negative rows (-4.25e9 .. -4.29e9, e.g. -4,259,883,546 -> true 35,083,750 after adding 2^32; 2024-01-04 .. 2025-04-30) and 10 POSITIVE rows of about 4.31e9-4.33e9 (true value plus 2^32; 2023-12-07 .. 2024-11-07), all late on expiry day. A sign check finds only the negative ones; the positive ones silently inflate minute-level volume sums to ~4.3e9. The 3 SENSEX rows (-27,280 / -111,280 / -1,166,230) also have OI 0 and implausible prices.', 'Vendor int32 overflow; not repaired. (Found by the independent reviewer for the positive rows; recount confirmed 10 + 10 + 3.)', 'Treat volume outside [0, 2^31) as invalid; NIFTY values can be repaired by +/- 2^32 after review.', 'No, but silent if unfiltered'),
 ('D07', 'Low', 'SENSEX', '2024-10-03 11:25, 2024-10-17 10:28 and 12:29, 2026-09-10 15:21 (2 rows), 2026-10-01 15:26', f'{int(ex[ex.kind=="spike"].shape[0])} isolated price spikes flagged by a >5x neighbour test: e.g. 85,200 PE open 1,951 / close 132.45 at spot 83,070; 78,400 PE close 1,582.05 at spot 81,203. Three (2024) look like bad ticks; the three 2026 ones lie in the closing-window artefact (D05). The reviewer\'s wider scan finds 8, and one 2024 case (2024-09-20 14:24) may be a real move. OHLC consistency passes, so the plain OHLC test does not catch them.', 'Bad ticks / closing-window artefact.', 'Spike filter in research loaders; do not delete in the source.', 'No'),
 ('D08', 'Medium', 'NIFTY', '2024-06-26 (D-1 of expiry 2024-06-27)', 'Only 8,337 option rows against ~55,000 typical; 146 of 182 planned contracts have no rows, including all 22 within +-5 strikes of the centre (the data report\'s "min 20 strikes" is this session). Expiry 2024-06-27 D0 is normal.', 'Probable failed or truncated download (cannot be distinguished from "no trades" because the manifest records no per-contract outcome).', 'Re-download the session.', 'No (one session)'),
 ('D09', 'Medium', 'both', 'manifests/checkpoint.csv', f'The checkpoint lists attempted contracts only (103,776 rows, no status, byte count, hash or timestamp). {n(Q["nifty"]["contracts_without_rows"])} NIFTY and {n(Q["sensex"]["contracts_without_rows"])} SENSEX planned contracts have no data and cannot be classed as unlisted / no trades / failed. The download scripts named in the README are not in the repository.', 'Manifest design; scripts not committed.', 'Commit the scripts; add per-contract outcome and hash to the manifest.', 'No, but limits reproducibility'),
 ('D10', 'Medium', 'both', 'two sessions named in the README', 'The README says two sessions held ~25.3k duplicate rows removed "before this was moved here". The committed raw JSON for them has 0 duplicates and equals the normalized CSV, so the raw files are not the exact API response for those sessions (the "immutable raw" claim does not hold).', 'Raw files were edited.', 'Document; keep the original responses if they still exist.', 'No'),
 ('D11', 'Medium', 'NIFTY', 'expiry 2026-11-17', 'Last NIFTY weekly expiry excluded as "in-progress" although the run started 2026-11-17 21:16 (after the close). The summary also gives the last NIFTY expiry as 2026-11-10; the real one is Monday 2026-11-09 (2026-11-10 is a holiday).', 'Exclusion rule applied one day early; report error.', 'Fetch 2026-11-16/17; correct the summary.', 'No'),
 ('D12', 'Medium', 'both', 'all pre-2026-08-03 sessions', f'Bars after the last regular minute: NIFTY {n(deep[deep["index"]=="nifty"].post_close_rows.sum())} rows ({n(deep[deep["index"]=="nifty"].post_close_with_volume.sum())} with volume), SENSEX {n(deep[deep["index"]=="sensex"].post_close_rows.sum())} ({n(deep[deep["index"]=="sensex"].post_close_with_volume.sum())}): a 15:30 bar per contract plus sparse later minutes; 145 option rows at 09:14 (NIFTY 2024-01-10/11); spot files hold pre-open rows 09:00/09:09-09:14 (NIFTY 1,826, SENSEX 1,440). The earlier validated pipeline dropped these.', 'Normalizer keeps everything the API returns.', 'Filter to 09:15-15:29 (15:39 from 2026-08-03) in research code and label the rest.', 'No'),
 ('D13', 'Medium', 'both', 'all', f'About a third of NIFTY option bars (6,312,819 of 18,978,233) and a fifth of SENSEX bars (2,579,706 of 12,928,723) are flat zero-volume bars: the vendor repeats the last price for minutes without trades. They are not trades. NIFTY also has {n(deep[deep["index"]=="nifty"].oi_zero_with_volume.sum())} bars with volume but OI 0 (241 sessions) and 338 open-interest jumps of more than 5x.', 'Vendor behaviour.', 'Treat volume == 0 bars as "no trade"; never as an executable price.', 'No'),
 ('D14', 'Medium', 'both', 'SENSEX 2025-08-04 (71 minutes missing), 2025-10-16 (24), 2025-10-21 (171, Muhurat); NIFTY 2026-11-08 (299, Muhurat) and 10 + 13 sessions with 4-6 missing minutes', f'Spot sessions with missing regular minutes: NIFTY {Q["nifty"]["underlying"]["spot_sessions_with_missing_minutes"]} sessions / {Q["nifty"]["underlying"]["spot_missing_minutes"]} minutes, SENSEX {Q["sensex"]["underlying"]["spot_sessions_with_missing_minutes"]} / {Q["sensex"]["underlying"]["spot_missing_minutes"]}. Most are the 15:16-15:19 auction-transition minutes after 2026-08-03; two SENSEX sessions are genuinely incomplete.', 'Vendor gaps.', 'Do not fill; flag sessions in research code.', 'No'),
 ('D15', 'Medium', 'both', 'contracts with no row', 'Presence of a contract in a session file requires at least one record that day. Using "contracts present in the files" as the tradable universe at time t leaks future information (a contract that only trades later is still present all day).', 'Files omit contracts without rows.', 'Define the universe from the planned grid (ATM rule + checkpoint) and treat missing as unknown.', 'Yes, if misused'),
 ('D16', 'Medium', 'both', 'proposed split', 'Not a data defect but a research-independence defect: the last 12 months include 2026-06-22..2026-10-22 (18 expiries per index) that were studied while reverse-engineering Algo 8. SENSEX in-sample would be only ~17 months.', 'Reuse of inspected data.', 'See report D.', 'Yes for the stated split'),
 ('D17', 'Medium', 'both', 'calendar CSV and README', 'The calendar column atm_ref is the ATM of the close of the last trading day of the ISO week (re-verified against Yahoo: 151/160 NIFTY, 119/160 SENSEX), i.e. information from after the expiry; it differs from the window centre (matches 3.8% NIFTY, 2.4% SENSEX). The atm_ref stored inside each raw file is the window centre (564/564). Using the calendar column for strike selection would be look-ahead. README errors: SENSEX first usable expiry is 2024-05-31 (first session 2024-05-30), not 2024-06-06; "35 weeks" excluded is 30 pre-boundary + 5 unreported mid-period weeks; the raw files have no `status` key.', 'Undocumented column meaning; documentation errors.', 'Rename or drop the column; correct the README.', 'Yes if the column is misused'),
 ('D18', 'Low', 'both', 'ATM centre', 'The strike-window centre equals ATM(D-2 close) with the independent Yahoo close for 306/316 NIFTY and 206/248 SENSEX sessions (two sessions per expiry share one centre, so 153/158 and 103/124 expiries), within one step for 312 and 244 sessions. The pipeline uses the Breeze close, which differs from the official close by a median of about 11 / 28 index points. Larger gaps are explained by special sessions (NIFTY 2026-02-03: Sunday Budget session; 2026-11-09 and SENSEX 2025-10-23: the D-1 problem in D04). The window was left by the opening spot by more than 10 steps in 7 NIFTY and 34 SENSEX sessions (reviewer), never leaving the +-45 window.', 'Rounding / source-of-close difference.', 'None needed.', 'No'),
 ('D19', 'Low', 'both', 'timestamps', 'Timestamps are naive local strings (no timezone). The convention (bar start, IST) matches the earlier exact-trade files (identical minutes), which verified it against Algo 8 fills, but it is not stated in this dataset.', 'Format.', 'Document; convert to IST-aware on load.', 'No'),
 ('D20', 'Medium', 'both', 'all', 'Lot size history is not supplied: NIFTY 50 -> 25 -> 75 -> 65 and SENSEX 10 -> 20 over the period (dates from memory, unverified here), so volume and OI units are not comparable over time and P&L per lot changes. Strike-listing windows and tick history are also not supplied, and option prices cannot be checked against an independent source (only the same vendor).', 'Out of scope of acquisition.', 'Source lot sizes and listing rules from exchange circulars before P&L work.', 'Yes for cross-period volume/OI and P&L studies'),
 ('D21', 'High', 'NIFTY / SENSEX', 'NIFTY D-1 2026-05-11; SENSEX D-1 2024-10-17, D0 2024-08-02, D0 2025-10-16', 'Intraday outages inside sessions that a presence check calls complete: NIFTY 2026-05-11 has volume 0 for every contract from 09:15 to 11:11 (117 minutes) while prices and OI move, and the 11:12 bar carries the accumulated volume; SENSEX 2024-10-17 has no option data after 13:13 (136 minutes; futures also truncated); SENSEX 2024-08-02 has a 35-minute hole (09:57-10:31) and 2025-10-16 a 24-minute hole (09:45-10:08) on expiry day. The first three change the expiry status to Partial.', 'Vendor outages; not flagged anywhere in the delivered reports.', 'Refetch if the vendor can supply them; otherwise flag sessions in research loaders.', 'No (4 sessions), but minute-level volume studies must exclude them'),
 ('D22', 'Medium', 'both', 'all sessions', 'Closing level: the 15:29 spot bar differs from the official close by a median of about 11 (NIFTY) / 28 (SENSEX) points, up to 120 / 290; the official close sits in the 15:30-15:39 bars, present in about 284 of 286 pre-auction NIFTY sessions but only about 100 of 248 SENSEX sessions, so using the last row of a file leaks the closing print into earlier decisions. There is no settlement price: the last D0 option bar is a last trade, not intrinsic value at the official close (90th-percentile gap 80-100 points for in-the-money contracts). (Reviewer-reported; the Yahoo comparison in report C is consistent with the 11 / 35-point close gap.)', 'Vendor data content.', 'Compute settlement from an official closing level; never use bars after 15:29 as decision-time data.', 'No'),
 ('D23', 'Low', 'both', 'sessions where the near-month future expires that day', 'On 35 NIFTY and 27 SENSEX sessions the near-month future in the file is the contract expiring that same day (recount confirmed), so futures-based forward prices and parity are unusable there.', 'Near-month definition.', 'Use the next contract on monthly expiry days.', 'No')
]
with open(f'{OUT}/E_DEFECT_REGISTER.csv', 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['defect_id', 'severity', 'instrument', 'affected_sessions', 'evidence', 'root_cause', 'recommended_resolution', 'blocks_research']); w.writerows(D)
sev = pd.Series([d[1] for d in D]).value_counts().to_dict()
E = f'''# E. Defect register
Pinned commit `{COMMIT}`. {len(D)} defects: {sev}. Rated after an independent review (see report A); several ratings were raised or lowered on its evidence. Severity: Critical = data cannot be trusted at all; High = blocks a stated use or a whole segment; Medium = needs a filter or documentation; Low = cosmetic or context. No Critical defects were found: every raw row equals its normalized row, and no OHLC, duplicate, timezone or expiry-identity error exists.

''' + '\n\n'.join(f'### {d[0]} ({d[1]}): {d[2]}\n* **Sessions:** {d[3]}\n* **Evidence:** {d[4]}\n* **Root cause:** {d[5]}\n* **Resolution:** {d[6]}\n* **Blocks research:** {d[7]}' for d in D)
open(f'{OUT}/E_DEFECT_REGISTER.md', 'w').write(E)

# ----------------------------------------------------------------------------- B coverage
rows = []
for i, U in (('nifty', 'NIFTY'), ('sensex', 'SENSEX')):
    c = CV[U]; z = N[i]; q = Q[i]
    rows.append({'': U, 'Expected expiries': c['expected'], 'Complete': c['complete'], 'Partial': c['partial'], 'Missing': c['missing'], 'Unverified': c['unverified'], 'D-1 usable': z['usable_d1'], 'D0 usable': z['usable_d0'], 'Planned contracts': n(q['planned_contracts']), 'Contracts with rows': n(q['contracts_with_rows']), 'Share': f"{q['share_with_rows']:.1%}"})
B = f'''# B. Coverage report
Pinned commit `{COMMIT}`; expected expiries come from an independent rule + trading-calendar construction (not from the dataset's calendar), 2023-11-01 to the last complete session 2026-11-17.

{tab(pd.DataFrame(rows))}

"D-1 usable" counts sessions that are the true previous regular session and have data near the money; D0 counts expiry sessions with data.

## Expiry calendar evidence
* NIFTY (NSE): Thursday weekly expiry until 2025-08-28, Tuesday from 2025-09-02 (public sources: [Moneylife](https://www.moneylife.in/article/nse-equity-fo-contracts-to-expire-on-tuesdays-bse-on-thursdays-from-1st-september/77434.html), [Business Today](https://www.businesstoday.in/markets/stocks/story/nse-bse-fo-expiry-days-what-has-changed-for-stock-investors-history-more-480781-2025-06-18); the NSE circular text itself was not found, one source gives 29 Aug for the switch). {sum(cov['nifty'].holiday_shifted)} expiries are holiday shifts (Tuesday/Thursday holiday: previous trading day).
* SENSEX (BSE): Friday from May 2023, Tuesday from January 2025 (month stated by sources; the dataset shows Friday 2025-01-03 and Tuesday 2025-01-07, so the switch date rests on the data only), Thursday from 2025-09-01. The two transition weeks (2024-12-30, 2025-01-06) are marked *unconfirmed* and were accepted only because the data and the rule agree.
* Trading days: Yahoo daily index series (^NSEI, ^BSESN; different vendor) restricted to weekdays and excluding Diwali Muhurat sessions (2026-11-08 confirmed by several reports; 2023-11-12, 2024-11-01, 2025-10-21 not confirmed by my search, supported by the data and by regular-holiday dates). Without removing Muhurat days my first pass misjudged three expiries, which is why this list matters.
* Expiry identification in the data: on D0 the median last close of options 300+ points out of the money is the 0.05 minimum tick in all 158 NIFTY and 123 of 124 SENSEX present D0 sessions (exception: 2024-09-20, 0.125). This supports that the contracts really expired that day (DATA evidence).

## Non-complete expiries
{tab(pd.concat([cov['nifty'][cov['nifty'].status != 'Complete'].assign(index='NIFTY'), cov['sensex'][(cov['sensex'].status != 'Complete') & (cov['sensex'].expected_expiry >= '2024-05-31')].assign(index='SENSEX')])[['index', 'expected_expiry', 'status', 'notes']])}

SENSEX Missing before 2024-05-31: 30 expiries, 2023-11-03 to 2024-05-24 (full list in `reports/tables/sensex_expiry_coverage.csv`). Full per-expiry tables: `reports/tables/nifty_expiry_coverage.csv`, `sensex_expiry_coverage.csv`.

## Contract, CE/PE and strike coverage
Every session has both CE and PE (316/316 NIFTY, 248/248 SENSEX). The plan is 91 strikes x CE/PE = 182 contracts per session at a 50 (NIFTY) / 100 (SENSEX) step, symmetric around the centre in all 564 sessions. Share of planned contracts with data by distance from the centre (steps): NIFTY 99.7% within 20, 94% at 30, 58-77% at 40, 43-62% at 45; SENSEX 100% within 5, 88-93% at 20, 68-70% at 30, 52-57% beyond 40. Far strikes without rows are consistent with "no trades", but the manifest cannot prove it. CE strikes without a PE of the same strike in the same session: NIFTY {Q['nifty']['ce_strikes_without_pe_same_session']}, SENSEX {Q['sensex']['ce_strikes_without_pe_same_session']}; PE without CE: NIFTY {Q['nifty']['pe_strikes_without_ce_same_session']}, SENSEX {Q['sensex']['pe_strikes_without_ce_same_session']}.

## Underlying coverage
Spot and futures files exist for all 316 NIFTY and 248 SENSEX sessions (every checkpoint entry). Spot raw == normalized for all files. Index volume is zero in all but 60 (NIFTY) and 136 (SENSEX) spot rows: index volume is unusable. Futures expiry field is always on or after the session date; futures-to-spot basis is between -0.52% and +1.51% (plausible).
'''
open(f'{OUT}/B_COVERAGE_REPORT.md', 'w').write(B)

# ----------------------------------------------------------------------------- C quality
rawn, raws = Q['nifty']['raw_vs_norm'], Q['sensex']['raw_vs_norm']
C = f'''# C. Data quality report
Pinned commit `{COMMIT}`. Every figure is recomputed from the committed files (`reports/tables/`).

| Check | NIFTY | SENSEX |
|---|---|---|
| Option rows scanned | {n(Q["nifty"]["rows"])} | {n(Q["sensex"]["rows"])} |
| Duplicate (datetime, strike, right) rows | 0 | 0 |
| Missing / NaN OHLC | 0 | 0 |
| Invalid OHLC (high < low/open/close, low > open/close, price <= 0, off the 0.05 tick) | 0 | 0 |
| Volume outside [0, 2^31) (int32 wrap-around) | 20 (10 negative, 10 positive) | 3 (negative, with bad prices) |
| Missing or negative open interest | 0 | 0 (but all values are 0, see below) |
| Open interest equal to 0 | {oi_n["share_rows_oi_zero"]:.1%} of rows; {oi_n["contract_sessions_oi_all_zero"]:,} contract-sessions | 100% of rows |
| Timestamp unparseable / weekend / other date | 0 / 11,190 (Muhurat Sunday) / 0 | 0 / 0 / 0 |
| Out-of-order or repeated timestamps within a contract | 0 | 0 |
| Expiry field mismatch with file name; right not CE/PE; strike off the step grid; rows outside the plan | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 |
| Cross-contract identical price series (>= 20 bars, non-constant) | 0 | 0 |
| Contract-sessions with data | {n(Q["nifty"]["contracts_with_rows"])} | {n(Q["sensex"]["contracts_with_rows"])} |
| Contract-sessions with a full 375/385-minute grid | {n(Q["nifty"]["candle"]["full_grid"])} ({Q["nifty"]["candle"]["full_grid"]/Q["nifty"]["contracts_with_rows"]:.1%}) | {n(Q["sensex"]["candle"]["full_grid"])} ({Q["sensex"]["candle"]["full_grid"]/Q["sensex"]["contracts_with_rows"]:.1%}) |
| Contract-sessions with < 50% of the grid | {n(Q["nifty"]["candle"]["coverage_lt_50"])} | {n(Q["sensex"]["candle"]["coverage_lt_50"])} |
| Contract-sessions with a gap > 30 minutes | {n(Q["nifty"]["candle"]["max_gap_gt_30min"])} | {n(Q["sensex"]["candle"]["max_gap_gt_30min"])} |
| Flat zero-volume (carried-price) bars | 6,312,819 (33.3%) | 2,579,706 (19.9%) |
| Isolated price spikes (>5x vs both neighbours) | 0 | 6 |
| Volume > 0 bars priced below intrinsic value by > 0.5% of spot | 1,378 of 12.6M (1,278 after 2026-08-03) | 903 of 10.3M (733 after 2026-08-03) |
| Bars after the last regular minute | 23,793 (6,757 with volume) | 29,395 (5,918 with volume) |
| Option minutes with no spot bar in the session | 17,374 | 33,235 |
| Spot sessions with missing regular minutes | {Q["nifty"]["underlying"]["spot_sessions_with_missing_minutes"]} ({Q["nifty"]["underlying"]["spot_missing_minutes"]} min) | {Q["sensex"]["underlying"]["spot_sessions_with_missing_minutes"]} ({Q["sensex"]["underlying"]["spot_missing_minutes"]} min) |

## Put-call parity (CE/PE labels and spot alignment)
At 11:00 and 14:00, strikes within 2 steps of spot with volume > 0: median |C - P - (S - K)| is {pd.read_csv(f'{T}/put_call_parity.csv').query("`index`=='nifty'").median_err_pct.median():.3f}% of spot (NIFTY) and {pd.read_csv(f'{T}/put_call_parity.csv').query("`index`=='sensex'").median_err_pct.median():.3f}% (SENSEX); no session exceeds 0.3% (max {pd.read_csv(f'{T}/put_call_parity.csv').median_err_pct.max():.2f}%). Two NIFTY sessions have no testable strikes (the Muhurat session and the incomplete 2024-06-26). This supports correct CE/PE labelling and option/spot minute alignment; it is a plausibility test (carry and early-exercise-free European parity), not a price verification.

## Missing candles are not all "missing"
The vendor repeats the previous price (volume 0) for no-trade minutes of contracts that have traded, so a missing minute is rarer than a no-trade minute. A contract-minute with no row at all can be a true gap or a minute before the first trade; the data cannot distinguish them. Treat volume 0 as no trade and an absent row as unknown.

## Raw versus normalized
| | NIFTY | SENSEX |
|---|---|---|
| Option sessions compared | {rawn["sessions_compared"]} | {raws["sessions_compared"]} |
| Raw rows / normalized rows | {n(rawn["raw_rows"])} / {n(rawn["norm_rows"])} | {n(raws["raw_rows"])} / {n(raws["norm_rows"])} |
| Rows only in raw / only in normalized / value mismatches | {rawn["raw_only"]} / {rawn["norm_only"]} / {rawn["value_mismatch"]} | {raws["raw_only"]} / {raws["norm_only"]} / {raws["value_mismatch"]} |
| Underlying files (spot + futures): raw-only / norm-only / mismatching values | {Q["nifty"]["underlying"]["raw_only"]} / {Q["nifty"]["underlying"]["norm_only"]} / {Q["nifty"]["underlying"]["raw_mismatch_rows"]} | {Q["sensex"]["underlying"]["raw_only"]} / {Q["sensex"]["underlying"]["norm_only"]} / {Q["sensex"]["underlying"]["raw_mismatch_rows"]} |

Normalization does not change any OHLC, volume or OI value. Caveat: this proves the normalizer is faithful, not that the raw files are the original API responses (defect D10).

## Index versus an independent vendor (Yahoo daily)
{tab(yv.round(1))}

Pre-auction-era closes differ by a median of 11 (NIFTY) / 35 (SENSEX) points because the vendor close is the 15:29 print and Yahoo carries the official close; highs/lows agree within a few points. After 2026-08-03 the NIFTY day high/low differ in 12/7 sessions because of the 15:20 artefact (D05).

## Cross-check with the earlier exact-contract files (same vendor, different pipeline and time)
{LEG["contract_days_compared"]:,} contract-days / {LEG["minutes_both"]:,} overlapping minutes: **0** mismatches in open, high, low, close, volume and open interest; {LEG["index_days_compared"]} index days with **0** mismatching OHLC values. The broad data hold {LEG["minutes_broad_only"]:,} extra minutes (post-close 15:30+ rows the earlier pipeline dropped) and omit 20 legacy contract-days, all of them strikes outside the +-45 window. This shows both pipelines treat the vendor data identically; it is **not** independent proof that the vendor data are correct.

## Anomaly list
Negative-volume rows: `reports/tables/negative_volume_rows.csv`. Spikes and intrinsic-value breaches: `reports/tables/deep_scan_examples.csv`. Planned contracts without rows: `reports/tables/planned_contracts_without_rows.csv`. Session-level scan: `reports/tables/option_session_scan.json`, `deep_scan_sessions.csv`, `underlying_scan.json`.
'''
open(f'{OUT}/C_DATA_QUALITY_REPORT.md', 'w').write(C)

# ----------------------------------------------------------------------------- D research readiness
ns, ss = N['nifty']['split'], N['sensex']['split']
D_ = f"""# D. Research readiness report
Pinned commit `{COMMIT}`. Two separate questions: (1) is the dataset technically valid, (2) is the proposed research split independent.

## 1. Technical readiness
| Use | NIFTY | SENSEX | Reason and evidence |
|---|---|---|---|
| Historical market replay of D-1/D0 minute marks | CONDITIONAL | CONDITIONAL (124 of 159 expiries) | Raw = normalized for every file; 0 duplicates, 0 invalid OHLC, expiry identity verified; prices equal the earlier pipeline on 1.22M overlapping minutes. Conditions: restrict to 09:15-15:29 (15:39 from 2026-08-03); treat volume 0 as no trade; drop volumes outside [0, 2^31) and the flagged spikes; mask the outage sessions (D21); do not use spot after 15:14 from 2026-08-03. Prices are trade candles only: no bid/ask. |
| Expiry-session analysis | YES (D0 {N["nifty"]["usable_d0"]}/160, D-1 {N["nifty"]["usable_d1"]}/160) | PARTIAL (D0 {N["sensex"]["usable_d0"]}/159) | 35 SENSEX expiries missing (30 before 2024-05-31, 5 unreported); NIFTY: 3 partial, 2 missing. |
| Options portfolio reconstruction | CONDITIONAL | CONDITIONAL | Window is ATM +-45 around the D-2 close; the earlier exact-trade data contain 20 SENSEX contract-days outside it (strikes 46-61 steps away) so wings beyond +-45 are not covered; far strikes without rows cannot be classed as unlisted or failed. For reconstructing Algo 8 fills use the exact-trade dataset. |
| Portfolio-construction research | CONDITIONAL | NO for the stated 3-year design | SENSEX has {N["sensex"]["span_years"]} years of history and no open interest. NIFTY has {N["nifty"]["span_years"]} years. |
| Backtesting | CONDITIONAL, relative comparisons only | CONDITIONAL, shorter | Only D-1/D0 sessions exist (no other days to expiry); no bid/ask or spread, so fills and costs must be assumed; lot-size history not supplied; far strikes thin. |

## 2. Chronological split on the actual data
Only whole expiries are assigned (D-1 and D0 stay together); no expiry crosses the boundary.

| | NIFTY | SENSEX |
|---|---|---|
| First / last session | {N["nifty"]["first_session"]} / {N["nifty"]["last_session"]} | {N["sensex"]["first_session"]} / {N["sensex"]["last_session"]} |
| Last 12 months (out-of-sample) from | after {ns["proposed_oos_from_exclusive"]}; first expiry D0 {ns["oos_first_d0"]}; {ns["oos_expiries"]} expiries | after {ss["proposed_oos_from_exclusive"]}; first expiry D0 {ss["oos_first_d0"]}; {ss["oos_expiries"]} expiries |
| In-sample | {ns["is_first"]} to {ns["is_last_d0"]}: {ns["is_expiries"]} expiries ({ns["is_months"]} months) | {ss["is_first"]} to {ss["is_last_d0"]}: {ss["is_expiries"]} expiries ({ss["is_months"]} months, **less than the 24 requested**) |
| Out-of-sample expiries that fall inside the already-inspected Algo 8 window (2026-06-22 to 2026-10-22) | {ns["oos_expiries_inside_algo8_window"]} of {ns["oos_expiries"]} | {ss["oos_expiries_inside_algo8_window"]} of {ss["oos_expiries"]} |
| Out-of-sample expiries before that window (clean) | {ns["oos_expiries_before_algo8_window"]} (about 8 months) | {ss["oos_expiries_before_algo8_window"]} |
| Out-of-sample expiries after that window (2026-10-23 on) | {ns["oos_expiries_after_algo8_window"]} | {ss["oos_expiries_after_algo8_window"]} |

**The final year is not independent.** The expiries of 2026-06-22 to 2026-10-22 ({ns["algo8_window_expiries"]} per index) were used to reverse-engineer Algo 8 (PRs #1-#5; the exact-trade files cover the same sessions, 67 of them overlap this dataset). Any idea or parameter that came from Algo 8's behaviour is contaminated there. Treat only the {ns["oos_expiries_before_algo8_window"]} NIFTY expiries before the window and the {ns["oos_expiries_after_algo8_window"]} after it as clean, and report the exposed block separately. The in-sample / out-of-sample information boundary also needs an embargo: the first out-of-sample expiry's strike centre uses a D-2 close that lies in the in-sample period, which is legitimate, but a strategy that carries state across the boundary would not be independent.

## 3. Leakage review
* **Strike selection:** the window centre is ATM of the D-2 close, verified against an independent close (306/316 NIFTY and 206/248 SENSEX sessions exact, the rest within one step or explained by special sessions). The D-2 close is known before D-1 opens, so there is no look-ahead in the centre. The calendar column `atm_ref` is not the centre and must not be used.
* **Contract selection:** the universe was fixed ex ante (91 strikes x 2) and does not depend on the day's range. But a contract appears in a file only if it had at least one record that day: using "present in the file" as eligibility at time t is look-ahead (D15). Use the planned grid.
* **Preprocessing:** normalization is per-session and value-preserving (0 changed values); the only removals are the documented duplicates (D10). Nothing in the files uses information from later periods, but the scripts are not committed, so this cannot be confirmed from code.
* **Same expiry/contract in both periods:** none (whole expiries).
* **Day selection:** two special-session D-1 choices (D04) and the exclusion of the latest NIFTY week (D11) were rule artefacts, not performance based.
"""
open(f'{OUT}/D_RESEARCH_READINESS_REPORT.md', 'w').write(D_)

# ----------------------------------------------------------------------------- A executive
REVIEW = open(f'{OUT}/REVIEWER_NOTES.md').read() if os.path.exists(f'{OUT}/REVIEWER_NOTES.md') else '_Reviewer notes not yet attached._'
cn, cs_ = CV['NIFTY'], CV['SENSEX']
A = f"""# A. Executive validation report
**Dataset:** `data/market_context_3yr_broad/` on branch `data/local-breeze-fetch`, **commit `{COMMIT}`** (3,391 files, 12.2 GB). Validated 2026-11-18 by recomputation from git objects; nothing was modified or re-downloaded.

## Verdict: {STATUS}
| | NIFTY | SENSEX |
|---|---|---|
| Status | **CONDITIONAL PASS** | **CONDITIONAL PASS for 2024-05-31 onward (price data only); FAIL for the stated three-year objective** |
| Expected weekly expiries (independent calendar) | {cn["expected"]} | {cs_["expected"]} |
| Complete / Partial / Missing / Unverified | {cn["complete"]} / {cn["partial"]} / {cn["missing"]} / {cn["unverified"]} | {cs_["complete"]} / {cs_["partial"]} / {cs_["missing"]} / {cs_["unverified"]} |
| Span | {N["nifty"]["first_session"]} to {N["nifty"]["last_session"]} ({N["nifty"]["span_years"]} y) | {N["sensex"]["first_session"]} to {N["sensex"]["last_session"]} ({N["sensex"]["span_years"]} y) |

**Why it is not a plain PASS.** The dataset is internally clean: every raw row equals its normalized row, there are no duplicates, no invalid OHLC, no timezone or expiry-identity errors, the strike window is centred on the D-2 close as intended, and prices equal the earlier exact-trade Breeze files on 1.22 million overlapping minutes. But (1) SENSEX lacks 35 expected expiries and all open interest, so the three-year SENSEX design cannot be satisfied; (2) two D-1 sessions are special Muhurat sessions, one NIFTY D-1 session is largely empty and three more sessions have intraday outages; (3) spot after the closing-auction change (2026-08-03) contains invalid prints around 15:20 in NIFTY and, less so, SENSEX; (4) vendor errors: 23 int32 wrap-around volumes (13 negative, 10 positive and therefore invisible to a sign check) and a few bad price ticks; (5) the final year is not an independent out-of-sample period.

## What was verified and how independent it is
* **Independent of the dataset's own files:** expiry calendar (public exchange-rule reports + Yahoo trading days), D-2 closes and index daily OHLC (Yahoo), strike-grid and CE/PE logic, raw-to-normalized equality recomputed with my own code.
* **Same vendor, different pipeline:** the earlier exact-trade files (identical on all overlapping minutes). This catches pipeline bugs, **not** vendor errors.
* **Not independently verifiable here:** option prices, volume and open interest against an exchange source; the Breeze "no SENSEX history before 2024-05" claim (needs credentials); special-session dates for 2023-2025.

## Acceptance criteria (section 11)
| # | Criterion | Result |
|---|---|---|
| 1 | Every expected expiry accounted for | MET: all {cn["expected"] + cs_["expected"]} classified; {cn["expected"] - cn["complete"]} NIFTY and {cs_["expected"] - cs_["complete"]} SENSEX are not Complete |
| 2 | D-1 and D0 quantified separately | MET: NIFTY D-1 {N["nifty"]["usable_d1"]} / D0 {N["nifty"]["usable_d0"]}; SENSEX D-1 {N["sensex"]["usable_d1"]} / D0 {N["sensex"]["usable_d0"]} |
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

Details: B coverage, C quality, D readiness, E defect register ({len(D)} defects: 0 Critical, {sev.get('High', 0)} High, {sev.get('Medium', 0)} Medium, {sev.get('Low', 0)} Low).

## Independent review
{REVIEW}
"""
open(f'{OUT}/A_EXECUTIVE_VALIDATION_REPORT.md', 'w').write(A)
