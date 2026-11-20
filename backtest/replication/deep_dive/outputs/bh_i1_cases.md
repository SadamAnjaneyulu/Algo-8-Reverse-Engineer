# Interaction timelines (cases chosen by pre-registered rules: first instance in cycle order)

## normal
**Rule:** D-1 body short sale, one wing lot 2.5-6 s later, balance restored.  **Cycle:** NIFTY expiry 2026-06-30, right CE, D-1

| time(IST) | module | side | strike | lots | limit | fill | S_after | L_after | gap |
|---|---|---|---|---|---|---|---|---|---|
| 09:24:21.000 | BODY | Sell | 24050 | 1 | 94.45 | 110.8 | 4 | 3 | 1 |
| 09:24:24.196 | HEDGE | Buy | 24700 | 1 | 2.3 | 2.0 | 4 | 4 | 0 |

## body_partial
**Rule:** body order filled in several partial fills (>= 2 lots).  **Cycle:** NIFTY expiry 2026-09-01, right PE, D-1

| time(IST) | module | side | strike | lots | limit | fill | S_after | L_after | gap |
|---|---|---|---|---|---|---|---|---|---|
| 14:46:21.821 | HEDGE | Buy | 23250 | 6 | 1.55 | 1.35 | 45 | 41 | 4 |
| 14:46:25.053 | s_ | Buy | 24050 | 23 | 43.35 | 36.95 | 22 | 41 | -19 |
| 14:46:25.053 | s_ | Buy | 24000 | 12 | 30.2 | 25.95 | 10 | 41 | -31 |
| 14:46:25.053 | s_ | Buy | 24100 | 2 | 61.2 | 52.3 | 8 | 41 | -33 |
| 14:46:25.053 | s_ | Buy | 23950 | 1 | 20.8 | 17.95 | 7 | 41 | -34 |
| 14:46:25.053 | s_ | Buy | 24150 | 7 | 85.05 | 72.31 | 0 | 41 | -41 |
| 14:46:25.054 | s_ | Sell | 23050 | 2 | 0.8 | 0.95 | 0 | 39 | -39 |
| 14:46:25.054 | s_ | Sell | 23100 | 1 | 0.85 | 1.0 | 0 | 38 | -38 |
| 14:46:25.054 | s_ | Sell | 23400 | 2 | 1.4 | 1.65 | 0 | 36 | -36 |
| 14:46:25.054 | s_ | Sell | 23300 | 1 | 1.15 | 1.3 | 0 | 35 | -35 |
| 14:46:25.054 | s_ | Sell | 23200 | 10 | 0.9 | 1.0 | 0 | 25 | -25 |
| 14:46:25.054 | s_ | Sell | 23450 | 5 | 1.55 | 1.75 | 0 | 20 | -20 |
| 14:46:25.054 | s_ | Sell | 23350 | 1 | 1.25 | 1.45 | 0 | 19 | -19 |
| 14:46:27.420 | HEDGE | Buy | 23300 | 4 | 1.55 | 1.4 | 0 | 23 | -23 |
| 14:46:29.000 | BODY | Sell | 23400 | 2 | 1.4 | 1.65 | 2 | 23 | -21 |
| 14:46:29.000 | BODY | Sell | 23250 | 16 | 1.15 | 1.3 | 2 | 7 | -5 |
| 14:46:29.000 | BODY | Sell | 23300 | 5 | 1.2 | 1.35 | 3 | 3 | 0 |
| 14:46:29.000 | BODY | Sell | 23150 | 2 | 0.8 | 0.95 | 3 | 1 | 2 |
| 14:46:29.000 | BODY | Sell | 23450 | 5 | 1.55 | 1.85 | 8 | 1 | 7 |
| 14:46:29.000 | BODY | Sell | 22050 | 1 | 0.3 | 0.35 | 8 | 0 | 8 |
| 14:46:29.000 | BODY | Sell | 23350 | 1 | 1.3 | 1.5 | 9 | 0 | 9 |
| 14:46:29.000 | BODY | Sell | 23050 | 2 | 0.8 | 0.95 | 11 | 0 | 11 |
| 14:46:31.000 | BODY | Sell | 23200 | 10 | 0.95 | 1.05 | 21 | 0 | 21 |
| 14:46:31.000 | BODY | Sell | 23100 | 1 | 0.85 | 1.0 | 22 | 0 | 22 |
| 14:46:36.114 | s_ | Buy | 23200 | 10 | 1.25 | 1.05 | 12 | 0 | 12 |
| 14:46:36.114 | s_ | Buy | 23450 | 5 | 2.05 | 1.8 | 7 | 0 | 7 |
| 14:46:36.114 | s_ | Buy | 23300 | 1 | 1.5 | 1.3 | 6 | 0 | 6 |
| 14:46:36.114 | s_ | Buy | 23050 | 2 | 1.25 | 0.95 | 4 | 0 | 4 |
| 14:46:36.114 | s_ | Buy | 23400 | 2 | 1.85 | 1.6 | 2 | 0 | 2 |
| 14:46:36.114 | s_ | Buy | 23100 | 1 | 1.3 | 1.0 | 1 | 0 | 1 |
| 14:46:36.114 | s_ | Buy | 23350 | 1 | 1.7 | 1.45 | 0 | 0 | 0 |

## body_partial_no_stop
**Rule:** same rule, first instance not within 120 s of a stop-module order.  **Cycle:** NIFTY expiry 2026-10-19, right CE, D-1

| time(IST) | module | side | strike | lots | limit | fill | S_after | L_after | gap |
|---|---|---|---|---|---|---|---|---|---|
| 15:15:03.000 | BODY | Buy | 24000 | 54 | 2.0 | 1.25 | 35 | 89 | -54 |
| 15:15:12.000 | BODY | Sell | 24500 | 54 | 0.3 | 0.35 | 89 | 89 | 0 |

## delayed_hedge
**Rule:** wing decision more than 10 s after the body fill.  **Cycle:** NIFTY expiry 2026-06-23, right PE, D0

| time(IST) | module | side | strike | lots | limit | fill | S_after | L_after | gap |
|---|---|---|---|---|---|---|---|---|---|
| 09:46:00.000 | BODY | Buy | 24150 | 2 | 72.45 | 63.25 | 50 | 52 | -2 |
| 09:46:00.000 | BODY | Buy | 24100 | 2 | 40.1 | 34.95 | 48 | 52 | -4 |
| 09:46:01.000 | BODY | Sell | 24100 | 2 | 29.4 | 34.4 | 50 | 52 | -2 |
| 09:46:06.000 | BODY | Sell | 24100 | 2 | 29.25 | 34.27 | 52 | 52 | 0 |
| 09:46:08.141 | HEDGE | Sell | 23650 | 2 | 0.8 | 0.9 | 52 | 50 | 2 |
| 09:46:20.997 | HEDGE | Buy | 23500 | 2 | 1.0 | 0.85 | 52 | 52 | 0 |
| 09:46:32.000 | BODY | Sell | 24100 | 2 | 27.9 | 32.75 | 54 | 52 | 2 |
| 09:46:36.870 | HEDGE | Buy | 23450 | 2 | 0.9 | 0.8 | 54 | 54 | 0 |

## quantity_differs
**Rule:** wing signed lots differ from S-L at decision (sign right).  **Cycle:** NIFTY expiry 2026-06-30, right PE, D0

| time(IST) | module | side | strike | lots | limit | fill | S_after | L_after | gap |
|---|---|---|---|---|---|---|---|---|---|
| 09:25:01.000 | BODY | Buy | 23950 | 1 | 103.65 | 91.1 | 7 | 23 | -16 |
| 09:25:02.000 | BODY | Buy | 23950 | 1 | 105.3 | 92.25 | 6 | 23 | -17 |
| 09:25:06.889 | HEDGE | Sell | 23250 | 2 | 0.7 | 0.85 | 6 | 21 | -15 |
| 09:25:06.889 | HEDGE | Sell | 23300 | 2 | 0.8 | 0.95 | 6 | 19 | -13 |
| 09:25:06.889 | HEDGE | Sell | 23350 | 12 | 0.9 | 1.0 | 6 | 7 | -1 |
| 09:25:06.889 | HEDGE | Sell | 23400 | 1 | 1.0 | 1.2 | 6 | 6 | 0 |

## missing_hedge
**Rule:** non-responding body burst, book stays imbalanced (unexplained class).  **Cycle:** NIFTY expiry 2026-06-30, right CE, D0

| time(IST) | module | side | strike | lots | limit | fill | S_after | L_after | gap |
|---|---|---|---|---|---|---|---|---|---|
| 09:19:14.000 | BODY | Buy | 23900 | 1 | 103.35 | 90.1 | 66 | 150 | -84 |

## existing_inventory
**Rule:** burst containing a new short sale answered by no hedge because L >= S already.  **Cycle:** NIFTY expiry 2026-07-28, right PE, D0

| time(IST) | module | side | strike | lots | limit | fill | S_after | L_after | gap |
|---|---|---|---|---|---|---|---|---|---|
| 15:10:48.000 | BODY | Buy | 24000 | 1 | 42.8 | 37.2 | 42 | 43 | -1 |
| 15:10:48.000 | BODY | Buy | 24000 | 1 | 42.8 | 37.2 | 41 | 43 | -2 |
| 15:10:48.000 | BODY | Buy | 24000 | 1 | 42.8 | 37.25 | 40 | 43 | -3 |
| 15:10:52.571 | HEDGE | Sell | 23700 | 3 | 0.05 | 0.05 | 40 | 40 | 0 |
| 15:11:06.000 | BODY | Sell | 23900 | 1 | 0.15 | 0.15 | 41 | 40 | 1 |
| 15:11:06.000 | BODY | Sell | 23900 | 1 | 0.15 | 0.15 | 42 | 40 | 2 |
| 15:11:13.000 | BODY | Buy | 24000 | 1 | 45.6 | 39.95 | 41 | 40 | 1 |
| 15:11:13.000 | BODY | Buy | 24000 | 1 | 45.6 | 39.95 | 40 | 40 | 0 |
| 15:11:17.000 | BODY | Buy | 23950 | 1 | 0.7 | 0.6 | 39 | 40 | -1 |
| 15:11:17.000 | BODY | Buy | 24000 | 1 | 45.2 | 39.5 | 38 | 40 | -2 |
| 15:11:17.000 | BODY | Buy | 24050 | 1 | 102.85 | 89.8 | 37 | 40 | -3 |
| 15:11:24.999 | HEDGE | Sell | 23700 | 3 | 0.05 | 0.05 | 37 | 37 | 0 |

## body_exits_hedge_stays
**Rule:** quiet-time over-hedge: shorts gone, longs remain.  **Cycle:** NIFTY expiry 2026-06-30, right CE, D0

| time(IST) | module | side | strike | lots | limit | fill | S_after | L_after | gap |
|---|---|---|---|---|---|---|---|---|---|
| 09:19:14.000 | BODY | Buy | 23900 | 1 | 103.35 | 90.1 | 66 | 150 | -84 |

## hedge_exits_first
**Rule:** wing SELL while S >= L (no excess longs).  **Cycle:** NIFTY expiry 2026-07-07, right CE, D0

| time(IST) | module | side | strike | lots | limit | fill | S_after | L_after | gap |
|---|---|---|---|---|---|---|---|---|---|
| 09:16:15.000 | BODY | Buy | 24650 | 1 | 3.0 | 2.65 | 49 | 50 | -1 |
| 09:16:15.000 | BODY | Sell | 24450 | 1 | 38.7 | 45.7 | 50 | 50 | 0 |
| 09:16:19.000 | BODY | Sell | 24450 | 1 | 38.7 | 47.6 | 51 | 50 | 1 |
| 09:16:19.000 | BODY | Sell | 24450 | 1 | 38.7 | 49.4 | 52 | 50 | 2 |
| 09:16:20.000 | BODY | Buy | 24650 | 1 | 3.0 | 3.0 | 52 | 51 | 1 |
| 09:16:23.333 | HEDGE | Buy | 24800 | 1 | 1.2 | 1.05 | 52 | 52 | 0 |
| 09:16:24.000 | BODY | Sell | 24450 | 1 | 39.85 | 45.0 | 53 | 52 | 1 |
| 09:16:24.000 | BODY | Buy | 24650 | 1 | 3.2 | 2.8 | 53 | 53 | 0 |
| 09:16:24.000 | BODY | Buy | 24650 | 1 | 3.2 | 2.8 | 53 | 54 | -1 |
| 09:16:27.374 | HEDGE | Sell | 24950 | 1 | 0.6 | 0.65 | 53 | 53 | 0 |
| 09:16:32.000 | BODY | Buy | 24650 | 1 | 3.2 | 2.8 | 53 | 54 | -1 |
| 09:16:34.000 | BODY | Sell | 24450 | 1 | 39.85 | 44.1 | 54 | 54 | 0 |
| 09:16:34.000 | BODY | Buy | 24650 | 1 | 3.2 | 2.85 | 54 | 55 | -1 |
| 09:16:34.000 | BODY | Buy | 24650 | 1 | 3.2 | 2.85 | 54 | 56 | -2 |
| 09:16:34.000 | BODY | Sell | 24450 | 1 | 39.85 | 44.1 | 55 | 56 | -1 |
| 09:16:34.000 | BODY | Sell | 24450 | 1 | 39.85 | 44.0 | 56 | 56 | 0 |
| 09:16:34.723 | HEDGE | Sell | 24900 | 1 | 0.6 | 0.7 | 56 | 55 | 1 |
| 09:16:35.000 | BODY | Sell | 24450 | 1 | 37.55 | 44.15 | 57 | 55 | 2 |
| 09:16:35.000 | BODY | Sell | 24450 | 1 | 37.55 | 44.05 | 58 | 55 | 3 |
| 09:16:36.000 | BODY | Sell | 24450 | 1 | 37.55 | 44.35 | 59 | 55 | 4 |
| 09:16:36.000 | BODY | Buy | 24350 | 1 | 126.05 | 109.4 | 58 | 55 | 3 |
| 09:16:40.432 | HEDGE | Buy | 24800 | 3 | 1.2 | 1.05 | 58 | 58 | 0 |
