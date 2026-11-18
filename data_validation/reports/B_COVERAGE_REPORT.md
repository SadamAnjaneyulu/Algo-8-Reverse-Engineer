# B. Coverage report
Pinned commit `eb4097308d47ccc75078ab73ba76d33bb1c7030b`; expected expiries come from an independent rule + trading-calendar construction (not from the dataset's calendar), 2023-11-01 to the last complete session 2026-11-17.

|  | Expected expiries | Complete | Partial | Missing | Unverified | D-1 usable | D0 usable | Planned contracts | Contracts with rows | Share |
|---|---|---|---|---|---|---|---|---|---|---|
| NIFTY | 160 | 156 | 2 | 2 | 0 | 156 | 158 | 57,512 | 52,134 | 90.6% |
| SENSEX | 159 | 123 | 1 | 35 | 0 | 123 | 124 | 45,136 | 36,404 | 80.7% |

"D-1 usable" counts sessions that are the true previous regular session and have data near the money; D0 counts expiry sessions with data.

## Expiry calendar evidence
* NIFTY (NSE): Thursday weekly expiry until 2025-08-28, Tuesday from 2025-09-02 (public sources: [Moneylife](https://www.moneylife.in/article/nse-equity-fo-contracts-to-expire-on-tuesdays-bse-on-thursdays-from-1st-september/77434.html), [Business Today](https://www.businesstoday.in/markets/stocks/story/nse-bse-fo-expiry-days-what-has-changed-for-stock-investors-history-more-480781-2025-06-18); the NSE circular text itself was not found, one source gives 29 Aug for the switch). 10 expiries are holiday shifts (Tuesday/Thursday holiday: previous trading day).
* SENSEX (BSE): Friday from May 2023, Tuesday from January 2025 (month stated by sources; the dataset shows Friday 2025-01-03 and Tuesday 2025-01-07, so the switch date rests on the data only), Thursday from 2025-09-01. The two transition weeks (2024-12-30, 2025-01-06) are marked *unconfirmed* and were accepted only because the data and the rule agree.
* Trading days: Yahoo daily index series (^NSEI, ^BSESN; different vendor) restricted to weekdays and excluding Diwali Muhurat sessions (2026-11-08 confirmed by several reports; 2023-11-12, 2024-11-01, 2025-10-21 not confirmed by my search, supported by the data and by regular-holiday dates). Without removing Muhurat days my first pass misjudged three expiries, which is why this list matters.
* Expiry identification in the data: on D0 the median last close of options 300+ points out of the money is the 0.05 minimum tick in all 158 NIFTY and 123 of 124 SENSEX present D0 sessions (exception: 2024-09-20, 0.125). This supports that the contracts really expired that day (DATA evidence).

## Non-complete expiries
| index | expected_expiry | status | notes |
|---|---|---|---|
| NIFTY | 2023-11-02 | Missing |  |
| NIFTY | 2024-06-27 | Partial | D-1 session 2024-06-26 is incomplete: only 0 of 22 contracts within +-5 steps of the centre have data |
| NIFTY | 2026-11-09 | Partial | dataset D-1 2026-11-08 differs from expected previous regular session 2026-11-06 (dataset D-1 is a special Muhurat session) |
| NIFTY | 2026-11-17 | Missing |  |
| SENSEX | 2024-11-22 | Missing |  |
| SENSEX | 2025-02-25 | Missing |  |
| SENSEX | 2025-04-01 | Missing |  |
| SENSEX | 2025-08-26 | Missing |  |
| SENSEX | 2025-10-23 | Partial | dataset D-1 2025-10-21 differs from expected previous regular session 2025-10-20 (dataset D-1 is a special Muhurat session) |
| SENSEX | 2026-03-12 | Missing |  |

SENSEX Missing before 2024-05-31: 30 expiries, 2023-11-03 to 2024-05-24 (full list in `reports/tables/sensex_expiry_coverage.csv`). Full per-expiry tables: `reports/tables/nifty_expiry_coverage.csv`, `sensex_expiry_coverage.csv`.

## Contract, CE/PE and strike coverage
Every session has both CE and PE (316/316 NIFTY, 248/248 SENSEX). The plan is 91 strikes x CE/PE = 182 contracts per session at a 50 (NIFTY) / 100 (SENSEX) step, symmetric around the centre in all 564 sessions. Share of planned contracts with data by distance from the centre (steps): NIFTY 99.7% within 20, 94% at 30, 58-77% at 40, 43-62% at 45; SENSEX 100% within 5, 88-93% at 20, 68-70% at 30, 52-57% beyond 40. Far strikes without rows are consistent with "no trades", but the manifest cannot prove it. CE strikes without a PE of the same strike in the same session: NIFTY 906, SENSEX 3896; PE without CE: NIFTY 860, SENSEX 4262.

## Underlying coverage
Spot and futures files exist for all 316 NIFTY and 248 SENSEX sessions (every checkpoint entry). Spot raw == normalized for all files. Index volume is zero in all but 60 (NIFTY) and 136 (SENSEX) spot rows: index volume is unusable. Futures expiry field is always on or after the session date; futures-to-spot basis is between -0.52% and +1.51% (plausible).
