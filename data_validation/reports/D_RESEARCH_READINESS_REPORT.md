# D. Research readiness report
Pinned commit `eb4097308d47ccc75078ab73ba76d33bb1c7030b`. Two separate questions: (1) is the dataset technically valid, (2) is the proposed research split independent.

## 1. Technical readiness
| Use | NIFTY | SENSEX | Reason and evidence |
|---|---|---|---|
| Historical market replay of D-1/D0 minute marks | CONDITIONAL | CONDITIONAL (124 of 159 expiries) | Raw = normalized for every file; 0 duplicates, 0 invalid OHLC, expiry identity verified; prices equal the earlier pipeline on 1.22M overlapping minutes. Conditions: restrict to 09:15-15:29 (15:39 from 2026-08-03); treat volume 0 as no trade; drop negative-volume rows and the 6 SENSEX spikes; do not use NIFTY spot after 15:14 from 2026-08-03. Prices are trade candles only: no bid/ask. |
| Expiry-session analysis | YES (D0 158/160, D-1 156/160) | PARTIAL (D0 124/159) | 35 SENSEX expiries missing (30 before 2024-05-31, 5 unreported); 2 NIFTY expiries partial, 2 missing. |
| Options portfolio reconstruction | CONDITIONAL | CONDITIONAL | Window is ATM +-45 around the D-2 close; the earlier exact-trade data contain 20 SENSEX contract-days outside it (strikes 46-61 steps away) so wings beyond +-45 are not covered; far strikes without rows cannot be classed as unlisted or failed. For reconstructing Algo 8 fills use the exact-trade dataset. |
| Portfolio-construction research | CONDITIONAL | NO for the stated 3-year design | SENSEX has 2.45 years of history and no open interest. NIFTY has 3.0 years. |
| Backtesting | CONDITIONAL, relative comparisons only | CONDITIONAL, shorter | Only D-1/D0 sessions exist (no other days to expiry); no bid/ask or spread, so fills and costs must be assumed; lot-size history not supplied; far strikes thin. |

## 2. Chronological split on the actual data
Only whole expiries are assigned (D-1 and D0 stay together); no expiry crosses the boundary.

| | NIFTY | SENSEX |
|---|---|---|
| First / last session | 2023-11-08 / 2026-11-09 | 2024-05-30 / 2026-11-12 |
| Last 12 months (out-of-sample) from | after 2025-11-09; first expiry D0 2025-11-11; 53 expiries | after 2025-11-12; first expiry D0 2025-11-13; 52 expiries |
| In-sample | 2023-11-08 to 2025-11-04: 105 expiries (23.9 months) | 2024-05-30 to 2025-11-06: 72 expiries (17.2 months, **less than the 24 requested**) |
| Out-of-sample expiries that fall inside the already-inspected Algo 8 window (2026-06-22 to 2026-10-22) | 18 of 53 | 18 of 52 |
| Out-of-sample expiries before that window (clean) | 32 (about 8 months) | 31 |
| Out-of-sample expiries after that window (2026-10-23 on) | 3 | 3 |

**The final year is not independent.** The expiries of 2026-06-22 to 2026-10-22 (18 per index) were used to reverse-engineer Algo 8 (PRs #1-#5; the exact-trade files cover the same sessions, 67 of them overlap this dataset). Any idea or parameter that came from Algo 8's behaviour is contaminated there. Treat only the 32 NIFTY expiries before the window and the 3 after it as clean, and report the exposed block separately. The in-sample / out-of-sample information boundary also needs an embargo: the first out-of-sample expiry's strike centre uses a D-2 close that lies in the in-sample period, which is legitimate, but a strategy that carries state across the boundary would not be independent.

## 3. Leakage review
* **Strike selection:** the window centre is ATM of the D-2 close, verified against an independent close (306/316 NIFTY and 206/248 SENSEX sessions exact, the rest within one step or explained by special sessions). The D-2 close is known before D-1 opens, so there is no look-ahead in the centre. The calendar column `atm_ref` is not the centre and must not be used.
* **Contract selection:** the universe was fixed ex ante (91 strikes x 2) and does not depend on the day's range. But a contract appears in a file only if it had at least one record that day: using "present in the file" as eligibility at time t is look-ahead (D15). Use the planned grid.
* **Preprocessing:** normalization is per-session and value-preserving (0 changed values); the only removals are the documented duplicates (D10). Nothing in the files uses information from later periods, but the scripts are not committed, so this cannot be confirmed from code.
* **Same expiry/contract in both periods:** none (whole expiries).
* **Day selection:** two special-session D-1 choices (D04) and the exclusion of the latest NIFTY week (D11) were rule artefacts, not performance based.
