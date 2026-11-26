# Algo 8 — D0 scheduled selling: why 83 pairs on D0 against 33 on D-1

*One cycle: NIFTY expiring 2026-07-28 (D-1 = 2026-07-27). Scripts `bl_d0q_detail.py`, `bl_d0q_why.py`. Figures `figures/bl_d0q_why.png` (all NIFTY cycles side by side) and `figures/bl_d0q_cycle4.png`. Descriptive; the recurrence test is leave-one-cycle-out.*

## 0. Answers
1. **Is it really 83 scheduled pairs? Yes, as a clock.**
   * 78 of the 83 fall at the same second in the **other** NIFTY cycles. Across all 30 cycles, 87% of D0 pairs recur at the same second in other cycles; the same test with the times shifted by 137 s gives 0%.
   * The 5 that do not recur are the burst at 09:16:19–21, whose size changes from cycle to cycle.
2. **Lots per scheduled pair: exactly 1 CE lot + 1 PE lot.** All 83 pairs are 1 + 1. They are 166 lots out of this cycle's 325 D0 body sell lots (51%).
   * Several pairs can fire in the same second: 4 at 09:16:19, 2 at 10:26:04, 2 at 13:01:01, 2 at 14:01:01.
3. **How it executes.**
   * The CE order and the PE order are sent within the same second (median gap 0 s) at the same strike, 1 lot each.
   * So each pair is one short straddle at that strike.
4. **"Previous-minute strike selection".** It is my measuring stick, in plain words:
   * at the second of a sale, take the spot index level as of the last **completed** 1-minute candle (for a sale at 09:31:10, the 09:30 candle's close, 24009.0), and find the strike nearest to it (24000);
   * that strike is sold on both CE and PE;
   * it matches 80 of 83 pairs.
   * The system presumably reads the live spot at the exact second. I only have minute candles, so the previous candle's close is the nearest thing I can test.
   * The 3 misses are the cases that support this: the previous candle's close was only 0.4–5.3 points from the midpoint between two strikes, so the live price had probably crossed it. Table in §3.
5. **Why 83 on D0 and 33 on D-1.**
   * D-1 fires after **18 marks on the clock**, all of them 15-minute boundaries (09:30, 09:45, …; the timetable skips a few, such as 12:15, 12:45 and 13:00), about 1.6 pairs after each.
   * D0 fires after **all 18 of those** and **14 more marks**:
     * 12 are 5-minute marks between the 15-minute boundaries: 10:25, 10:55, 11:10, 11:55, 12:05, 12:25, 12:35, 12:55, 13:05, 13:25, 13:35, 13:55;
     * 2 are 15-minute boundaries that D-1 skips: 12:45 and 13:00.
   * D0 also fires more pairs at the shared boundaries (about 2.6 against 1.6).

| the 83 D0 pairs of this cycle | pairs |
|---|---|
| A. same second as a D-1 pair of this cycle | 30 |
| B. at a boundary D-1 also uses, but another second | 23 |
| C. at one of the 14 marks D-1 does not use | 19 |
| E. recur on other days but sit off the 5-minute grid (10:17:58, 12:37:27, 12:37:58, 13:49:01, 14:07:28, 14:27:58) | 6 |
| D. the opening burst at 09:16:19–21 (does not recur) | 5 |
| **total** | **83** |

The raster (`bl_d0q_why.png`) shows it: the same stripes on every day.

## 1. The recurrence test, by group
Learned without the cycle itself (waves from the other cycles of the group, ±3 s).

| group | pairs | recur_in_other_cycles | shifted_null |
|---|---|---|---|
| NIFTY V1 | 529 | 99% | 0% |
| NIFTY V2 | 149 | 21% | 0% |
| SENSEX V1 | 85 | 100% | 0% |
| SENSEX V2 | 281 | 96% | 0% |


NIFTY V2 has only 2 usable cycles, so its recurrence cannot be tested this way (low rates there reflect too little data, not a failure).

## 2. Boundary table (NIFTY, timetable V1)
Share of cycles with a pair in the 133 s after each 5-minute mark. Only marks used by D-1 or D0 are listed. `kind` says whether the mark is a 15-minute boundary.

| boundary | kind | D-1 pairs per cycle | D0 pairs per cycle | D-1: share of cycles | D0: share of cycles |
|---|---|---|---|---|---|
| 09:30 | 15-min boundary | 2.00 | 5.00 | 1.00 | 1.00 |
| 09:45 | 15-min boundary | 3.00 | 4.00 | 1.00 | 1.00 |
| 10:00 | 15-min boundary | 1.00 | 2.00 | 1.00 | 1.00 |
| 10:15 | 15-min boundary | 4.00 | 4.00 | 1.00 | 1.00 |
| 10:25 | extra 5-min boundary | 0.00 | 2.00 | 0.00 | 1.00 |
| 10:30 | 15-min boundary | 1.00 | 4.14 | 1.00 | 1.00 |
| 10:45 | 15-min boundary | 1.00 | 1.00 | 1.00 | 1.00 |
| 10:55 | extra 5-min boundary | 0.00 | 1.00 | 0.00 | 1.00 |
| 11:00 | 15-min boundary | 2.10 | 2.43 | 1.00 | 1.00 |
| 11:10 | extra 5-min boundary | 0.00 | 1.00 | 0.00 | 1.00 |
| 11:15 | 15-min boundary | 2.00 | 3.00 | 1.00 | 1.00 |
| 11:30 | 15-min boundary | 1.00 | 2.00 | 1.00 | 1.00 |
| 11:45 | 15-min boundary | 2.00 | 2.00 | 1.00 | 1.00 |
| 11:55 | extra 5-min boundary | 0.00 | 0.86 | 0.00 | 0.86 |
| 12:00 | 15-min boundary | 1.00 | 1.57 | 1.00 | 0.86 |
| 12:05 | extra 5-min boundary | 0.00 | 1.00 | 0.00 | 1.00 |
| 12:25 | extra 5-min boundary | 0.00 | 1.00 | 0.00 | 1.00 |
| 12:30 | 15-min boundary | 2.00 | 4.00 | 1.00 | 1.00 |
| 12:35 | extra 5-min boundary | 0.00 | 1.00 | 0.00 | 1.00 |
| 12:45 | 15-min boundary | 0.00 | 2.00 | 0.00 | 1.00 |
| 12:55 | extra 5-min boundary | 0.00 | 1.00 | 0.00 | 1.00 |
| 13:00 | 15-min boundary | 0.00 | 3.57 | 0.00 | 1.00 |
| 13:05 | extra 5-min boundary | 0.00 | 1.00 | 0.00 | 1.00 |
| 13:15 | 15-min boundary | 1.00 | 2.00 | 1.00 | 1.00 |
| 13:25 | extra 5-min boundary | 0.00 | 1.00 | 0.00 | 1.00 |
| 13:30 | 15-min boundary | 1.00 | 3.00 | 1.00 | 1.00 |
| 13:35 | extra 5-min boundary | 0.00 | 1.00 | 0.00 | 1.00 |
| 13:45 | 15-min boundary | 1.00 | 2.29 | 1.00 | 1.00 |
| 13:55 | extra 5-min boundary | 0.00 | 0.86 | 0.00 | 0.86 |
| 14:00 | 15-min boundary | 1.00 | 3.00 | 1.00 | 1.00 |
| 14:15 | 15-min boundary | 1.00 | 1.00 | 1.00 | 1.00 |
| 14:30 | 15-min boundary | 1.00 | 0.86 | 1.00 | 0.86 |


## 3. Strike: the 3 pairs not at the previous-candle ATM
| time | strike | spot_prev_min_close | ATM_of_prev_close | midpoint | spot_minus_midpoint |
|---|---|---|---|---|---|
| 10:47:31 | 24050 | 24024.600 | 24000 | 24025.000 | -0.400 |
| 11:01:57 | 24000 | 24030.300 | 24050 | 24025.000 | 5.300 |
| 11:47:30 | 24050 | 24021.700 | 24000 | 24025.000 | -3.300 |


The midpoint between strikes 24000 and 24050 is 24025. In all three the previous close was within 5.3 points of it (see `spot_minus_midpoint`). That is the signature of a strike read from the live price a few seconds later.

## 4. All 83 pairs, in time order
Columns:
* `time`: first order of the pair.
* `px_*`: fill price.
* `spot_prev_min_close`: the spot used for the strike check.
* `on_D1_clock`: same second as a D-1 pair of this cycle (±3 s).
* `recurs`: same second recurs in other cycles.
* Category letters are the table in §0.

| # | time | CE_order | PE_order | strike | lots_CE | lots_PE | px_CE | px_PE | spot_prev_min_close | ATM_of_prev_close | is_ATM | on_D1_clock | recurs | category |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 09:15:59 | 09:15:59 | 09:15:59 | 24000 | 1 | 1 | 47.6 | 43.0 | 24002.2 | 24000 | True | True | True | A |
| 2 | 09:16:01 | 09:16:01 | 09:16:01 | 24000 | 1 | 1 | 45.4 | 41.8 | 24002.2 | 24000 | True | True | True | A |
| 3 | 09:16:02 | 09:16:02 | 09:16:03 | 24000 | 1 | 1 | 47.2 | 41.7 | 24002.2 | 24000 | True | True | True | A |
| 4 | 09:16:19 | 09:16:19 | 09:16:19 | 24000 | 1 | 1 | 48.1 | 40.0 | 24002.2 | 24000 | True | False | False | D |
| 5 | 09:16:19 | 09:16:19 | 09:16:19 | 24000 | 1 | 1 | 48.0 | 40.5 | 24002.2 | 24000 | True | False | False | D |
| 6 | 09:16:19 | 09:16:21 | 09:16:19 | 24000 | 1 | 1 | 46.0 | 40.5 | 24002.2 | 24000 | True | False | False | D |
| 7 | 09:16:19 | 09:16:21 | 09:16:19 | 24000 | 1 | 1 | 46.0 | 40.5 | 24002.2 | 24000 | True | False | False | D |
| 8 | 09:16:21 | 09:16:21 | 09:16:21 | 24000 | 1 | 1 | 46.3 | 41.4 | 24002.2 | 24000 | True | False | False | D |
| 9 | 09:30:57 | 09:30:57 | 09:30:58 | 24000 | 1 | 1 | 51.7 | 36.2 | 24006.8 | 24000 | True | True | True | A |
| 10 | 09:31:00 | 09:31:00 | 09:31:00 | 24000 | 1 | 1 | 51.3 | 36.1 | 24009.0 | 24000 | True | True | True | A |
| 11 | 09:31:06 | 09:31:06 | 09:31:06 | 24000 | 1 | 1 | 50.0 | 37.9 | 24009.0 | 24000 | True | False | True | B |
| 12 | 09:31:10 | 09:31:10 | 09:31:10 | 24000 | 1 | 1 | 48.9 | 38.4 | 24009.0 | 24000 | True | False | True | B |
| 13 | 09:32:00 | 09:32:00 | 09:32:00 | 24000 | 1 | 1 | 42.2 | 44.5 | 23998.2 | 24000 | True | False | True | B |
| 14 | 09:46:00 | 09:46:00 | 09:46:00 | 24000 | 1 | 1 | 47.8 | 33.2 | 24014.8 | 24000 | True | True | True | A |
| 15 | 09:46:06 | 09:46:06 | 09:46:06 | 24000 | 1 | 1 | 47.1 | 34.0 | 24014.8 | 24000 | True | False | True | B |
| 16 | 09:46:31 | 09:46:31 | 09:46:32 | 24000 | 1 | 1 | 47.1 | 34.2 | 24014.8 | 24000 | True | True | True | A |
| 17 | 09:47:06 | 09:47:06 | 09:47:06 | 24000 | 1 | 1 | 44.9 | 35.0 | 24009.2 | 24000 | True | True | True | A |
| 18 | 10:00:58 | 10:00:58 | 10:00:58 | 24000 | 1 | 1 | 41.1 | 34.5 | 24012.2 | 24000 | True | False | True | B |
| 19 | 10:01:10 | 10:01:10 | 10:01:10 | 24000 | 1 | 1 | 42.9 | 32.9 | 24010.7 | 24000 | True | True | True | A |
| 20 | 10:15:58 | 10:15:58 | 10:15:59 | 24000 | 1 | 1 | 34.6 | 40.5 | 23986.2 | 24000 | True | True | True | A |
| 21 | 10:16:00 | 10:16:00 | 10:16:00 | 24000 | 1 | 1 | 34.6 | 40.6 | 23993.8 | 24000 | True | True | True | A |
| 22 | 10:16:57 | 10:16:57 | 10:16:57 | 24000 | 1 | 1 | 35.5 | 38.7 | 23993.8 | 24000 | True | True | True | A |
| 23 | 10:17:01 | 10:17:01 | 10:17:01 | 24000 | 1 | 1 | 34.5 | 39.1 | 23995.3 | 24000 | True | True | True | A |
| 24 | 10:17:58 | 10:17:58 | 10:17:58 | 24000 | 1 | 1 | 40.0 | 34.4 | 23995.3 | 24000 | True | False | True | E |
| 25 | 10:26:04 | 10:26:04 | 10:26:04 | 24000 | 1 | 1 | 34.2 | 38.4 | 23999.2 | 24000 | True | False | True | C |
| 26 | 10:26:04 | 10:26:04 | 10:26:05 | 24000 | 1 | 1 | 34.3 | 38.0 | 23999.2 | 24000 | True | False | True | C |
| 27 | 10:29:58 | 10:29:58 | 10:29:58 | 24000 | 1 | 1 | 29.4 | 43.6 | 23991.1 | 24000 | True | False | True | B |
| 28 | 10:31:02 | 10:31:02 | 10:31:02 | 24000 | 1 | 1 | 34.0 | 38.0 | 23994.0 | 24000 | True | False | True | B |
| 29 | 10:31:09 | 10:31:09 | 10:31:10 | 24000 | 1 | 1 | 35.0 | 36.2 | 23994.0 | 24000 | True | True | True | A |
| 30 | 10:32:00 | 10:32:00 | 10:32:00 | 24000 | 1 | 1 | 34.1 | 38.4 | 23996.7 | 24000 | True | False | True | B |
| 31 | 10:46:31 | 10:46:31 | 10:46:31 | 24050 | 1 | 1 | 24.4 | 50.0 | 24027.3 | 24050 | True | True | True | A |
| 32 | 10:47:31 | 10:47:31 | 10:47:32 | 24050 | 1 | 1 | 22.4 | 52.3 | 24024.6 | 24000 | False | True | True | A |
| 33 | 10:56:04 | 10:56:04 | 10:56:04 | 24050 | 1 | 1 | 26.4 | 44.1 | 24039.3 | 24050 | True | False | True | C |
| 34 | 11:01:10 | 11:01:10 | 11:01:10 | 24050 | 1 | 1 | 22.9 | 47.8 | 24030.3 | 24050 | True | True | True | A |
| 35 | 11:01:57 | 11:01:57 | 11:01:58 | 24000 | 1 | 1 | 42.1 | 26.2 | 24030.3 | 24050 | False | False | True | B |
| 36 | 11:02:00 | 11:02:00 | 11:02:00 | 24000 | 1 | 1 | 43.5 | 25.3 | 24020.3 | 24000 | True | False | True | B |
| 37 | 11:11:28 | 11:11:28 | 11:11:29 | 24000 | 1 | 1 | 40.3 | 26.8 | 24018.2 | 24000 | True | False | True | C |
| 38 | 11:15:58 | 11:15:58 | 11:15:59 | 24000 | 1 | 1 | 42.9 | 23.2 | 24014.6 | 24000 | True | True | True | A |
| 39 | 11:16:58 | 11:16:58 | 11:16:58 | 24000 | 1 | 1 | 41.4 | 24.6 | 24020.3 | 24000 | True | True | True | A |
| 40 | 11:17:01 | 11:17:01 | 11:17:01 | 24000 | 1 | 1 | 42.2 | 24.1 | 24020.0 | 24000 | True | False | True | B |
| 41 | 11:31:01 | 11:31:01 | 11:31:02 | 24000 | 1 | 1 | 37.4 | 25.6 | 24013.3 | 24000 | True | False | True | B |
| 42 | 11:31:10 | 11:31:10 | 11:31:10 | 24000 | 1 | 1 | 38.5 | 24.6 | 24013.3 | 24000 | True | True | True | A |
| 43 | 11:46:31 | 11:46:31 | 11:46:31 | 24000 | 1 | 1 | 42.2 | 20.6 | 24021.0 | 24000 | True | True | True | A |
| 44 | 11:47:00 | 11:47:00 | 11:47:00 | 24000 | 1 | 1 | 43.6 | 20.1 | 24021.7 | 24000 | True | False | True | B |
| 45 | 11:47:30 | 11:47:30 | 11:47:31 | 24050 | 1 | 1 | 20.6 | 41.8 | 24021.7 | 24000 | False | True | True | A |
| 46 | 11:56:04 | 11:56:04 | 11:56:04 | 24000 | 1 | 1 | 33.6 | 24.7 | 24012.0 | 24000 | True | False | True | C |
| 47 | 12:01:10 | 12:01:10 | 12:01:10 | 24000 | 1 | 1 | 34.0 | 23.6 | 24010.7 | 24000 | True | True | True | A |
| 48 | 12:02:00 | 12:02:00 | 12:02:01 | 24000 | 1 | 1 | 32.5 | 25.1 | 24007.0 | 24000 | True | False | True | B |
| 49 | 12:06:00 | 12:06:00 | 12:06:01 | 24000 | 1 | 1 | 37.5 | 20.9 | 24014.7 | 24000 | True | False | True | C |
| 50 | 12:26:01 | 12:26:01 | 12:26:01 | 24000 | 1 | 1 | 36.5 | 20.1 | 24013.2 | 24000 | True | False | True | C |
| 51 | 12:31:02 | 12:31:02 | 12:31:02 | 24000 | 1 | 1 | 41.6 | 17.4 | 24024.4 | 24000 | True | True | True | A |
| 52 | 12:31:10 | 12:31:10 | 12:31:10 | 24000 | 1 | 1 | 41.1 | 17.6 | 24024.4 | 24000 | True | True | True | A |
| 53 | 12:31:28 | 12:31:28 | 12:31:28 | 24000 | 1 | 1 | 42.1 | 17.1 | 24024.4 | 24000 | True | False | True | B |
| 54 | 12:32:01 | 12:32:01 | 12:32:01 | 24050 | 1 | 1 | 17.6 | 41.3 | 24026.5 | 24050 | True | False | True | B |
| 55 | 12:36:01 | 12:36:01 | 12:36:02 | 24000 | 1 | 1 | 34.0 | 20.4 | 24012.2 | 24000 | True | False | True | C |
| 56 | 12:37:27 | 12:37:27 | 12:37:28 | 24000 | 1 | 1 | 36.9 | 18.9 | 24010.8 | 24000 | True | False | True | E |
| 57 | 12:37:58 | 12:37:58 | 12:37:58 | 24000 | 1 | 1 | 35.6 | 19.2 | 24010.8 | 24000 | True | False | True | E |
| 58 | 12:46:01 | 12:46:01 | 12:46:01 | 24000 | 1 | 1 | 35.4 | 19.0 | 24018.0 | 24000 | True | False | True | C |
| 59 | 12:47:01 | 12:47:01 | 12:47:01 | 24000 | 1 | 1 | 36.6 | 18.5 | 24019.1 | 24000 | True | False | True | C |
| 60 | 12:56:01 | 12:56:01 | 12:56:01 | 24000 | 1 | 1 | 34.1 | 20.3 | 24013.3 | 24000 | True | False | True | C |
| 61 | 13:00:00 | 13:00:00 | 13:00:02 | 24000 | 1 | 1 | 27.9 | 25.9 | 24003.9 | 24000 | True | False | True | C |
| 62 | 13:01:01 | 13:01:01 | 13:01:01 | 24000 | 1 | 1 | 28.4 | 23.8 | 24004.8 | 24000 | True | False | True | C |
| 63 | 13:01:01 | 13:01:01 | 13:01:02 | 24000 | 1 | 1 | 28.4 | 23.4 | 24004.8 | 24000 | True | False | True | C |
| 64 | 13:01:27 | 13:01:27 | 13:01:29 | 24000 | 1 | 1 | 28.0 | 23.6 | 24004.8 | 24000 | True | False | True | C |
| 65 | 13:06:00 | 13:06:00 | 13:06:01 | 24000 | 1 | 1 | 28.4 | 23.4 | 24004.7 | 24000 | True | False | True | C |
| 66 | 13:15:02 | 13:15:02 | 13:15:03 | 24000 | 1 | 1 | 16.2 | 38.2 | 23983.0 | 24000 | True | False | True | B |
| 67 | 13:17:02 | 13:17:02 | 13:17:03 | 23950 | 1 | 1 | 39.1 | 15.7 | 23974.5 | 23950 | True | False | True | B |
| 68 | 13:26:00 | 13:26:00 | 13:26:00 | 24000 | 1 | 1 | 17.2 | 32.6 | 23988.8 | 24000 | True | False | True | C |
| 69 | 13:30:01 | 13:30:01 | 13:30:02 | 24000 | 1 | 1 | 15.6 | 37.0 | 23984.8 | 24000 | True | True | True | A |
| 70 | 13:31:28 | 13:31:28 | 13:31:28 | 24000 | 1 | 1 | 15.3 | 34.9 | 23982.0 | 24000 | True | False | True | B |
| 71 | 13:32:00 | 13:32:00 | 13:32:00 | 24000 | 1 | 1 | 14.8 | 36.0 | 23983.0 | 24000 | True | False | True | B |
| 72 | 13:36:01 | 13:36:01 | 13:36:02 | 24000 | 1 | 1 | 16.8 | 29.9 | 23988.3 | 24000 | True | False | True | C |
| 73 | 13:45:00 | 13:45:00 | 13:45:02 | 24000 | 1 | 1 | 13.8 | 33.2 | 23983.3 | 24000 | True | True | True | A |
| 74 | 13:46:01 | 13:46:01 | 13:46:02 | 24000 | 1 | 1 | 14.6 | 31.6 | 23982.2 | 24000 | True | False | True | B |
| 75 | 13:49:01 | 13:49:01 | 13:49:02 | 24000 | 1 | 1 | 11.9 | 37.0 | 23977.7 | 24000 | True | False | True | E |
| 76 | 13:56:01 | 13:56:01 | 13:56:01 | 24000 | 1 | 1 | 18.1 | 22.4 | 24002.8 | 24000 | True | False | True | C |
| 77 | 13:59:59 | 13:59:59 | 14:00:00 | 24000 | 1 | 1 | 18.2 | 22.6 | 23996.0 | 24000 | True | True | True | A |
| 78 | 14:01:01 | 14:01:01 | 14:01:03 | 24000 | 1 | 1 | 17.3 | 22.9 | 23998.4 | 24000 | True | False | True | B |
| 79 | 14:01:01 | 14:01:01 | 14:01:01 | 24000 | 1 | 1 | 17.4 | 23.3 | 23998.4 | 24000 | True | False | True | B |
| 80 | 14:07:28 | 14:07:28 | 14:07:28 | 24000 | 1 | 1 | 16.4 | 21.4 | 23999.6 | 24000 | True | False | True | E |
| 81 | 14:14:59 | 14:14:59 | 14:15:00 | 24000 | 1 | 1 | 14.4 | 23.3 | 23990.5 | 24000 | True | True | True | A |
| 82 | 14:27:58 | 14:27:58 | 14:27:58 | 24000 | 1 | 1 | 12.4 | 22.6 | 23995.3 | 24000 | True | False | True | E |
| 83 | 14:30:00 | 14:30:00 | 14:30:02 | 24000 | 1 | 1 | 11.2 | 26.1 | 23987.5 | 24000 | True | True | True | A |


## 5. Not known yet
* **Why exactly these 14 extra marks**, and why D0 fires more pairs per boundary. The times are fixed and repeat on every day, but I have not found the rule that picks them.
* **The size of the 09:16 burst.** It varies by cycle.
* **Whether the extra D0 waves belong to a separate scheduler** (for example a D0-only timer set) **or are the D-1 timer set running at a finer grid.** The data cannot separate the two.

## Run order
`bl_d0q_sched.py` (first) → `bl_d0q_detail.py 4` → `bl_d0q_why.py` → `make_d0qw_report.py`.
