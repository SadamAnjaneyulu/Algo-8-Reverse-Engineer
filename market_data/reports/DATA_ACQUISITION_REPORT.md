# NIFTY options data: audit, feasibility and three-year acquisition plan

Date of work: 2026-11-17. Scope: NIFTY index options (plus the underlying index and, optionally, futures). Code: `market_data/acquisition/` (16 offline tests pass). Evidence labels: **VERIFIED** (observed in files or by a request I made), **DOCUMENTED** (public broker text, not tested), **INFERRED**, **UNRESOLVED**.

## Answers to the three questions

| Question | Answer |
|---|---|
| 1. What do we already have? | **NIFTY index 1-minute: 85 sessions (2026-06-22 to 2026-10-22). NIFTY options 1-minute: 1,445 contract-days (545,979 bars), 33 sessions (2026-06-23 to 2026-10-19), 18 weekly expiries, only the contracts Algo 8 traded (775 distinct contracts, 17-54 strikes per session).** No futures, no earlier history, no bid/ask, no IV/Greeks. That is about 11 % of the three-year calendar (119 of 1,096 days) and about 10 % of the ~314 option sessions needed (33). |
| 2. What more do we need? | Index for the other ~700 sessions; confirmed weekly-expiry calendar for ~139 more expiries; for each expiry the sessions D-1 and D0 over a fixed ATM +-45-strike band, CE and PE (about 182 contracts per expiry): about **12.3 k requests for the core band (+-20 strikes) and 15.5 k more for the wings**; optional near/next-month futures (~314 requests). |
| 3. Can Breeze give the full three years, and how much today? | **Unproven.** The endpoint works for expired NIFTY options in Jun-Oct 2026 (VERIFIED, 1,445 contract-days). Whether it reaches back to 2023-10-23 is **UNRESOLVED**: ICICI's FAQ says 3 years (so about 2023-11-17 from today), another source says up to 10. **Today I could download nothing:** no Breeze credentials exist in this environment, and earlier cloud attempts were rejected by the broker edge (see section 2). The pipeline is built and tested offline; a first run on your machine needs a 6-request lookback probe, then ~4,500 requests per day (about 1.6 h of request time). |

## 1. Existing data inventory (all figures recomputed from the files; `reports/existing_audit/`)

Source: branch `data/local-breeze-fetch` (identical tree on `research/ml-decision-engine` and `research/strong-findings`, tree hash `a6b0881c`). Every cache in the repo (`analysis/_cache`, `ohlcv_research/_cache`, `stage2_alpha_research/_cache`) is derived from this same set. Futures: none found in any branch.

| Item | Result | Status |
|---|---|---|
| Index NIFTY | 31,839 bars, 85 sessions, 77 with 375 bars and 8 with 370-371 (the 15:16-15:19 auction-transition minutes are absent from 12 Oct onward), no duplicates, no nulls, 0 inconsistent OHLC. **Index volume is 0 in every row.** | VERIFIED |
| Weekdays without a session | 26 Jun, 14 Sep, 2 Oct, 20 Oct 2026 (holidays per the earlier calendar notes) | VERIFIED data, holiday reason from earlier notes |
| Options NIFTY | 545,979 bars; 1,445 contract-days; 775 contracts; expiries 2026-06-23 ... 10-19 (17 Tuesdays + one Monday holiday shift); DTE 0 (775), 1 (628), 3 (42 weekend) | VERIFIED |
| Fields | timestamp (IST, +05:30), underlying, expiry, strike, CE/PE, OHLC, volume, **open interest**. No bid/ask, IV, Greeks, VWAP. | VERIFIED |
| Open interest (NIFTY) | non-zero in 100 % of rows and it changes in 82 % of minutes (so it is an intraday series, not one daily number). Its exact timing semantics are **UNRESOLVED**. (One SENSEX raw file I opened shows OI = 0.0; SENSEX is out of scope and was not audited.) | VERIFIED / UNRESOLVED |
| Volume | per bar (not cumulative); zero in 19,224 rows (3.5 %) which are mostly carried prices, not trades; kept as observed | VERIFIED |
| Quality | 0 duplicates, 0 nulls, 0 inconsistent OHLC, 0 zero prices, 100 % on the 0.05 tick, 100 % of strikes on the 50-point grid | VERIFIED |
| Session coverage | 1,380 contract-days have the full grid (375, or 385 from 3 Aug 2026), 39 have 300-374 bars, 26 have fewer than 300 (illiquid wings). Missing bars are **left missing** (never filled). 9,079 bars sit at 15:30-15:39 (derivatives auction-transition session, from 3 Aug). | VERIFIED |
| Chain completeness | **Not a chain.** 17-54 strikes per session (mean 37), only what Algo 8 traded. CE and PE print in the same minute for only 17.6 % of contract-minutes. Strikes lie from -42.6 to +44.4 steps (50 points) of the day's open, 1 %-99 % within -40.5 to +40.6. | VERIFIED |
| Sessions with option data | 33 of the 85 index sessions: only D-1 and D0 of each weekly expiry | VERIFIED |
| Provenance | each file has raw bytes, a hash and a metadata record in the branch | VERIFIED |

**Usable?** The files are internally clean and usable for replaying Algo 8's own trades. They are **not** usable for strategy validation because they are 4 months long, selection-biased toward contracts Algo 8 chose, and contain no index sessions before June 2026.

## 2. ICICI Breeze feasibility

| Constraint | Finding | Status |
|---|---|---|
| Endpoint | `GET https://breezeapi.icicidirect.com/api/v2/historicalcharts` (`interval=1minute`, `from_date`, `to_date`, `stock_code`, `exch_code`, `product_type`, `expiry_date`, `right`, `strike_price`); session exchange at `.../breezeapi/api/v1/customerdetails`. Reachable from this container (HTTP 401 / 415 unauthenticated). | VERIFIED |
| Expired option contracts | returned for 2026-06-23 ... 10-19 weekly expiries (1,445 contract-days via this endpoint, identity fields checked). Request form: expiry, right, strike. | VERIFIED for those months |
| Interval | 1-minute used and delivered | VERIFIED |
| Max span per request | SDK example documents **1,000 candle intervals**; existing code stays under it. I plan two sessions per request (750-770 candles). Whether two-session spans are accepted is **UNRESOLVED** until the first sample. | DOCUMENTED / UNRESOLVED |
| Rate limit | ICICI FAQ: **100 calls/minute, 5,000 calls/day**. The existing downloader spaces calls 1.25 s (48/min) with no throttling observed. Default cap here: 4,500/day. The day boundary and whether failed calls count are **UNRESOLVED**. | DOCUMENTED |
| Lookback | ICICI FAQ: "3 years of data"; a comparison article: "10 years". **Unknown for 1-minute options.** `plan-lookback` probes six dates (2023-10-23 ... 2025-06-02). | UNRESOLVED |
| Futures (expired) | request form `product_type=futures` is untested. | UNRESOLVED |
| Cloud access | Earlier notes: cloud login worked but the history endpoint returned an HTML "Request Rejected" page (support ID recorded), then on 2026-10-26 the key/session pair was rejected at session exchange. All completed downloads came from a Windows machine with native TLS. | VERIFIED (history in repo) |
| Credentials | none in this environment (checked environment names only; no values printed). The pipeline reads `BREEZE_API_KEY` and `BREEZE_API_SESSION` or hidden prompts and never writes them; a test greps the store for the secrets. | VERIFIED |

Sources for the documented items: [ICICI Direct Breeze FAQ](https://icicidirect.com/faqs/f-and-o/breeze-api), [ICICI Direct "what is trading apis"](https://icicidirect.com/faqs/f-and-o/what-is-trading-apis), [SDK package page](https://pypi.org/project/breeze-connect), and the repo's `LOCAL_BREEZE_OPTIONS.md`. No alternative vendor is substituted: if Breeze cannot go back to 2023-10, the shortfall is reported and the source choice is yours.

## 3. Exact NIFTY options data requirements

| Need | Spec | Why | Status |
|---|---|---|---|
| Option bars | 1-minute OHLC, volume, open interest; CE and PE; strike; expiry; contract identity; IST timestamps; source id on every row | what Breeze returns and what simulation needs | VERIFIED fields |
| Sessions | **D-1 and D0 of every weekly expiry** (previous trading day and the expiry day) | the only structure seen in Algo 8 (BTST carried to expiry); other DTEs are not downloaded | INFERRED; reopen if the new strategy trades other DTEs |
| Strikes | ATM of the **close of D-2** (known before D-1 opens) +-45 steps of 50 (91 strikes) x CE/PE = 182 contracts per expiry; tier 1 = +-20 (82 contracts), tier 2 = wings out to +-45. The same set is used for both sessions | covers 99 % of Algo 8's observed offsets (+-40.6 steps) with a causal rule | derived from VERIFIED offsets |
| Optional coverage extension | `plan --stage range` adds strikes the session range actually reached (hindsight coverage). **The backtest must never read band edges or "which contracts exist" as information.** | complete chain on big-move days | design rule |
| Underlying | NIFTY index 1-minute for **all** weekdays in the window (calendar, previous close, realised vol) | trading calendar comes from here; holidays come back empty and are listed for review | VERIFIED request form |
| Futures | near and next monthly NIFTY futures for the same sessions (~314 requests): forward price for implied volatility, basis | required only if IV/Greeks use a forward rather than spot | optional, request form UNRESOLVED |
| Contract metadata | expiry calendar from candles (an expiry is accepted only when an ATM option request returns bars on that date, never from rules alone); lot-size and strike-step history | contract universe | calendar discovered; **lot-size history UNRESOLVED** (the existing files imply 65 in 2026; it was different earlier) |
| Not available from Breeze history | bid/ask, order book, IV, Greeks. IV and Greeks can be **derived** (Black-76 from option close, forward, time, rate) and must be labelled `derived_estimate`; bid/ask cannot be derived. | | VERIFIED absent |

## 4. Acquisition plan (credential-free projection, `python3 -m acquisition.cli estimate`)

Window **2023-10-23 to 2026-10-22** (784 weekdays, 157 nominal weekly expiries). The session-rule snapshot in the repo ends 2026-10-22, so the window ends there; if the start proves unavailable the tail can be extended only after verifying later session rules.

| Block | Requests | Notes |
|---|---:|---|
| Lookback probe (index, 6 dates) | 6 | do first; decides the real start date |
| Index, remaining weekdays | 704 | 789 weekdays+lead-in minus 85 held; empty weekdays = holidays to review |
| Expiry confirmation probes | ~160 | one ATM CE per week, more only when a holiday shifts the date |
| Options tier 1 (ATM +-20), 139 new expiries + 18 partly held | **12,265** | 11,398 new + 867 left in the 18 held expiries (measured with the real store) |
| Options tier 2 (wings to +-45) | **15,457** | 13,900 new + 1,557 in held expiries |
| Futures (optional) | ~314 | unverified form |
| **Core package (index + probes + tier 1 + futures)** | **~13,450** | **3.0 days at 4,500/day; 4.7 h of request time** |
| **Full package (+ tier 2)** | **~28,900** | **6.4 days; 10.0 h** |

How much today: one day = 4,500 requests, roughly the index (704), probes (160) and about 3,600 core-band option requests, i.e. the core band for ~44 of 139 remaining expiries (about a third) in ~1.6 h. This holds only if the 5,000/day cap applies as documented and two-session requests are accepted (otherwise requests double).

Pipeline properties (all tested with a fake Breeze, 16 tests):
reuse legacy files byte-for-byte (`import-legacy`, source id `legacy:<hash>`) and never re-request them; one SQLite manifest (tasks, contract-days, request log); write-once read-only raw JSON; separate normalized CSV per contract-day with `source_id` on every row; restart after interruption sends no request twice, raw present but manifest lost is reused with zero requests; daily cap and `--max-requests`; retries with back-off on 429/5xx, run stops on auth failure, HTML rejection, persistent 429, or five transient failures in a row; a wrong instrument in a response fails the task and keeps the raw file; empty responses stay EMPTY (never zero volume); blank open interest stays blank; bars outside the requested sessions are not kept; no secret ever reaches disk.

```
export BREEZE_API_KEY=...   # or use --prompt-credentials (hidden)
python3 -m acquisition.cli import-legacy --store data_store --branch-root <checkout of data/local-breeze-fetch>
python3 -m acquisition.cli plan-lookback --store data_store && python3 -m acquisition.cli fetch --store data_store --kinds index --max-requests 6
python3 -m acquisition.cli plan --store data_store --stage index        && python3 -m acquisition.cli fetch --store data_store --kinds index
python3 -m acquisition.cli plan --store data_store --stage expiries     && python3 -m acquisition.cli fetch --store data_store --kinds option --max-tier 0   # repeat until no tasks are added
python3 -m acquisition.cli plan --store data_store --stage options --max-tier 1 && python3 -m acquisition.cli fetch --store data_store --kinds option --max-tier 1
python3 -m acquisition.cli qc --store data_store
```
Add `--native-tls` on Windows (needs `truststore`). Run a **small sample first** (`--max-requests 20`), read `qc`, then continue.

## 5. Dataset structure (`data_store/`, git-ignored)

```
manifest.sqlite                      tasks, contract_days, request_log (no credentials)
raw/<kind>/<und>/<expiry|->/<strike><CE|PE>/<from>_<to>.<taskid>.json   immutable provider responses (+ raw/legacy/...)
normalized/<kind>/<und>/<expiry|->/<strike><CE|PE>/<trade_day>.csv       IST timestamps, source_id per row
qc/                                  coverage and quality reports
```
All timestamps are IST (`+05:30`); the provider's naive times are read as IST (bar label = bar start, VERIFIED against Algo 8 fills earlier).

## 6. Data-quality and coverage report

Full-store QC (`qc` command) cannot be produced yet because nothing new was downloaded. The existing 4-month data are covered in section 1. The QC module is tested (duplicates, OHLC, tick, zero price, expected minutes 375/385, missing minutes, split labels, per-expiry task status).

## 7. Chronological split (`config/validation_split.json`, proposed)

| Dataset | Dates | Use |
|---|---|---|
| In-sample | 2023-10-23 to 2025-10-22 (24 months) | research, development, parameters, backtests |
| Out-of-sample | 2025-10-23 to 2026-10-22 (12 months) | opened once, after the strategy is frozen |

**Contamination warning (needs your decision):** 2026-06-22 to 2026-10-22, four of the twelve OOS months, were already inspected while reverse-engineering Algo 8. Anything inspired by Algo 8's behaviour is not out-of-sample there. Options: (a) keep the 12-month OOS and report two OOS results, clean (2025-10-23 to 2026-06-19, about 8 months) and exposed; (b) treat only the clean 8 months as OOS. I recommend (a). **Walk-forward inside the in-sample period: yes**, anchored, four 3-month validation blocks, 5-trading-day embargo (listed in the JSON). The dates must be restated from the real first/last downloaded session.

## 8. Blockers and unresolved items

1. **No Breeze credentials in this environment, and the cloud route was previously rejected: no new data was downloaded.** Run locally (or supply a working session) as above.
2. **Lookback unknown** (3 vs 10 years claim): run the 6-request probe first. If the start is later than 2023-10-23, the three-year claim fails and I will report the actual span.
3. Two-session requests and the 1,000-candle cap: untested for this API; the first sample decides (otherwise ~2x requests).
4. 5,000/day cap and its day boundary: documented, not measured.
5. Expired futures request form: untested; futures are optional.
6. NIFTY weekly-expiry weekday history (Thursday to Tuesday in Sep 2025) and holidays are used only as a probe order, but the pre-2026 part comes from memory, not from a checked circular. Confirmation is by data.
7. Lot-size history (and strike-step changes) for 2023-2025: not in the files; needed to scale volume and P&L. Must be sourced from exchange circulars.
8. Special sessions (Saturday/Muhurat) are excluded by the weekday rule; list to be reviewed from empty/extra days.
9. Open-interest timing semantics, and the 15:30-15:39 bars (derivatives only from 3 Aug 2026; earlier history ends 15:29).
10. The strike band is derived from Algo 8's observed offsets; if the new strategy uses wider strikes or other DTEs, more tasks must be planned.
11. OOS contamination (section 7). No strategy optimisation has been run.
12. The data store is not committed (size); a container restart loses downloads unless they are copied out or pushed to a data branch.
