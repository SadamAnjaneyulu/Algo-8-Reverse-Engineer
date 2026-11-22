# Algo 8 — D0 (expiry day): inventory and what carries over from D-1

*Step 1 of `D0_PLAN.md`. In-sample, D0 of 32 live cycles. One-minute spot and option OHLC for all 32 D0 sessions were built (`bl_d0_data.py`).*

## 0. Result
* **D0 is the busy day.** 49,997 lots on D0, against 13,655 on D-1. The main flows:
  * body sells 10,190 and body buy-backs 11,498;
  * hedge wing buys 9,370 and wing sells 9,941;
  * body-stream long buys and sells 1,216 / 2,496;
  * stop module 3,515 lots in 11 cycles;
  * lump salvage (`v_` sells) 843.
* **Carried into D0 (median per cycle):** 52 CE and 45 PE short lots, 56 / 48 long lots, the lump being the long excess.
* **What carries over from D-1:**
  * **The hedge controller does.** Long lots equal short lots at 95% of quiet moments (D-1: 99%; the 15:00 hour drops to 75% with the clearance).
  * **The D-1 timetable does not.** On D0 only 3 (V1) and 2 (V2) minutes have a sale in at least 80% of cycles, against 33 fixed waves on D-1. D0 selling is not a fixed minute timetable.
  * **Buy-backs are not minute-clocked on D0:** 11% at second :00, against 48% on D-1.
* **Buy-backs mostly close lots sold during D0** (8,819 lots), not the carried book alone (837 lots on contracts held only from D-1). D0 is an active intraday sell / buy-back cycle on top of the carried position.
* **15:14 clearance:** 2,629 lots in the 15:14 minute (body buy-backs and body-stream long sales). Only 1,911 lots trade after 15:15.

## 1. Lots by module and role
| module | role | orders | lots | cycles |
|---|---|---|---|---|
| h_ | close_long | 3670 | 9941 | 31 |
| h_ | cover_short | 116 | 485 | 13 |
| h_ | open_long | 5242 | 9370 | 29 |
| h_ | open_short | 37 | 302 | 5 |
| m_ | close_long | 6 | 16 | 1 |
| m_ | open_long | 1 | 16 | 1 |
| num | close_long | 831 | 2496 | 29 |
| num | cover_short | 9335 | 11498 | 33 |
| num | open_long | 1067 | 1216 | 33 |
| num | open_short | 8955 | 10190 | 32 |
| s_ | close_long | 169 | 1548 | 11 |
| s_ | cover_short | 213 | 1904 | 11 |
| s_ | open_short | 5 | 63 | 1 |
| v_ | close_long | 304 | 843 | 18 |
| v_ | open_long | 1 | 14 | 1 |
| v_ | open_short | 7 | 95 | 4 |


## 2. Lots by hour
| ('hour', '') | ('h_', 'close_long') | ('h_', 'cover_short') | ('h_', 'open_long') | ('h_', 'open_short') | ('m_', 'close_long') | ('m_', 'open_long') | ('num', 'close_long') | ('num', 'cover_short') | ('num', 'open_long') | ('num', 'open_short') | ('s_', 'close_long') | ('s_', 'cover_short') | ('s_', 'open_short') | ('v_', 'close_long') | ('v_', 'open_long') | ('v_', 'open_short') |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 9 | 1872 | 240 | 1372 | 300 | 0 | 0 | 282 | 1099 | 829 | 2444 | 1204 | 1412 | 63 | 112 | 0 | 95 |
| 10 | 618 | 0 | 1282 | 0 | 0 | 0 | 123 | 665 | 9 | 1179 | 0 | 0 | 0 | 48 | 0 | 0 |
| 11 | 746 | 2 | 1346 | 0 | 0 | 16 | 135 | 975 | 57 | 1457 | 98 | 122 | 0 | 67 | 14 | 0 |
| 12 | 1231 | 9 | 1692 | 0 | 0 | 0 | 103 | 967 | 25 | 1300 | 0 | 0 | 0 | 67 | 0 | 0 |
| 13 | 1245 | 24 | 1793 | 0 | 0 | 0 | 312 | 1274 | 27 | 1475 | 0 | 0 | 0 | 107 | 0 | 0 |
| 14 | 2477 | 80 | 1383 | 2 | 16 | 0 | 273 | 3047 | 92 | 1591 | 246 | 370 | 0 | 338 | 0 | 0 |
| 15 | 1752 | 130 | 502 | 0 | 0 | 0 | 1268 | 3471 | 177 | 744 | 0 | 0 | 0 | 104 | 0 | 0 |


## 3. Timetable test (share of cycles with a sale in a given D0 minute)
| version | cycles | minutes_share_ge_0p8 | minutes_share_ge_0p6 | minutes_with_any_sell | lots_in_ge0p8_minutes |
|---|---|---|---|---|---|
| V1 | 21 | 3 | 36 | 344 | 0.095 |
| V2 | 11 | 2 | 2 | 239 | 0.178 |


## Next (plan phases 2–4)
Test whether the D-1 sell triggers drive D0 selling: the reactive two-candle breakout, the solo ladder at fresh extremes, and wider time windows (grid A in `d0_reconstruction`). Test whether the D-1 own-premium stop (about 1.6×) and the fast-move exits drive D0 buy-backs. Then build the D0 free-running reconstruction from the carried book and score it like D-1.
