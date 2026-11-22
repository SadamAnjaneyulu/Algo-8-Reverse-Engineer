# Algo 8 — how was scheduled selling actually scheduled? A bank of timers

*Plan `D0_SCHED_RULE_PLAN.md` (written before the validation tests; addendum A, gapped timers with a skip penalty, is post-hoc). Descriptive, consensus clock times of every group. Figures: `figures/bl_d0r_timers_NIFTY_V1.png`, `figures/bl_d0r_bank.png`. Scripts `bl_d0r_ilp.py`, `bl_d0r_val.py`, `bl_d0r_bank.py`, `bl_d0r_gap.py`.*

## 0. Result
* **D-1 is ATM straddle selling at 15-minute marks, as established. This page is about what is inside the marks, and how D0 differs.**
  * **D-1:** every cycle sells 1 CE + 1 PE at the ATM strike after 17 of the 21 marks between 09:30 and 14:30 (12:15, 12:45, 13:00 are skipped). 93% of the 1,061 straddles are at the ATM of the previous minute's close. Each mark gets between 1 and 3.7 straddles per cycle on average, at different seconds (table in §1).
  * **Inside the marks, the clock times are built from a bank of independent timers.** Each timer fires every N minutes at a fixed second offset, between a start and an end, and may skip a slot.
    * D-1 NIFTY (before 16 Sep): 5 timers explain 79% of the 33 clock times.
    * Their periods (15, 30, 45, 60 minutes) are multiples of 15 minutes, consistent with the 15-minute marks (inferred).
  * **D0:** the same 15-minute marks plus more marks, and more straddles per mark. 10 timers explain 80% of the 76 clock times. **D0 runs more timers, and several start earlier.**
  * Null (clock times shifted by up to ±150 s): 7% covered. *Observed.*
* **The timers are real, not a fitting artefact.** Timers fitted only on the morning (before 12:00) predict clock times after 12:00 to the second:

| day | group | targets | afternoon times predicted | null mean | null 95th pct |
|---|---|---|---|---|---|
| D-1 | NIFTY V1 | 9 | 0.444 | 0.006 | 0.000 |
| D-1 | NIFTY V2 | 9 | 0.556 | 0.004 | 0.000 |
| D-1 | SENSEX V1 | 9 | 0.444 | 0.003 | 0.000 |
| D-1 | SENSEX V2 | 10 | 0.500 | 0.004 | 0.000 |
| D0 | NIFTY V1 | 37 | 0.108 | 0.003 | 0.027 |
| D0 | NIFTY V2 | 21 | 0.238 | 0.002 | 0.000 |
| D0 | SENSEX V2 | 29 | 0.483 | 0.006 | 0.036 |


  * Predicted shares are 0.11–0.56 against null means of 0.003–0.007. All 7 group-days beat the 95th percentile of the null.
  * The result holds in 38 of 40 settings of the timer cost and tolerance.
  * With skipped slots allowed, the same forward test gives recall 24%–45% (null at most 0.9%) and precision 21%–79% (null at most 1.4%); all 7 of 7 beat the null's 95th percentile.
  * *Observed.*
* **The same timer bank serves NIFTY and SENSEX.** The NIFTY D0 timers, extended over the day, explain 74% of NIFTY V2 D0 times, 56% of SENSEX V2 and 92% of SENSEX V1 (null about 3%).
* **D0 reuses D-1's timers.** D-1 timers extended over the day explain 38%–50% of the D0 times of NIFTY and SENSEX V2 (null 1%). The D0 timers explain 82% of D-1 times. SENSEX V1 on D0 shares none of its own D-1 timers (it runs two 45-minute timers only).
* **Why D0 looks unorganised: more timers run at once, and they start and stop at different times.**

| time | D-1 timers running | D0 timers running |
|---|---|---|
| 10:00 | 1 | 4 |
| 11:00 | 3 | 7 |
| 12:00 | 2 | 4 |
| 13:00 | 1 | 6 |
| 14:00 | 1 | 2 |


  * D0 has 10 timers against 5 on D-1, and about twice as many running at most hours.
  * Timers that start after 10:00 on D0: 30 min @ :04-06 from 10:26:04, 30 min @ :00 from 10:31:02, 45 min @ :00 from 10:32:00, 10 min @ :00 from 12:06:00, 30 min @ :27-28 from 12:31:28, 15 min @ :00 from 13:00:00.
  * The afternoon 15-minute timer starts at 13:00:00 on D0 and 13:29:59 on D-1.
  * Overlapping timers of different periods and second offsets are what make the pattern hard to see by eye.
* **Not explained:** 20% of the D0 NIFTY times, 14% for NIFTY V2 and 11% for SENSEX V2.
  * These are not noise. Of the 26 NIFTY times that the strict (no-skip) model left out, 65% also appear at the same second in NIFTY V2 and 42% in SENSEX V2 (null 1%). They are fixed clock times without a periodic rule I can see.

## 1. D-1 at the 15-minute marks (all 32 cycles)
Straddles per cycle in the 3 minutes after each mark. Each straddle is 1 CE + 1 PE at ATM. 1,061 straddles in total; all of them fall in these windows.

| 15-min mark | share of cycles selling | avg straddles per cycle | min | max | straddles (all cycles) |
|---|---|---|---|---|---|
| 09:15 | 0.97 | 2.94 | 0 | 5 | 94 |
| 09:30 | 1.00 | 1.88 | 1 | 3 | 60 |
| 09:45 | 1.00 | 3.03 | 3 | 4 | 97 |
| 10:00 | 1.00 | 1.00 | 1 | 1 | 32 |
| 10:15 | 1.00 | 3.69 | 3 | 4 | 118 |
| 10:30 | 1.00 | 1.44 | 1 | 4 | 46 |
| 10:45 | 1.00 | 2.00 | 2 | 2 | 64 |
| 11:00 | 1.00 | 1.69 | 1 | 3 | 54 |
| 11:15 | 1.00 | 2.00 | 2 | 2 | 64 |
| 11:30 | 1.00 | 1.38 | 1 | 3 | 44 |
| 11:45 | 1.00 | 2.66 | 2 | 3 | 85 |
| 12:00 | 1.00 | 1.03 | 1 | 2 | 33 |
| 12:30 | 1.00 | 2.06 | 2 | 3 | 66 |
| 13:15 | 0.66 | 0.66 | 0 | 1 | 21 |
| 13:30 | 1.00 | 1.00 | 1 | 1 | 32 |
| 13:45 | 1.00 | 1.00 | 1 | 1 | 32 |
| 14:00 | 1.00 | 1.09 | 1 | 2 | 35 |
| 14:15 | 1.00 | 1.00 | 1 | 1 | 32 |
| 14:30 | 1.00 | 1.44 | 1 | 3 | 46 |
| 14:45 | 0.19 | 0.19 | 0 | 1 | 6 |


* **17 marks are sold after in every cycle:** 09:30, 09:45, 10:00, 10:15, 10:30, 10:45, 11:00, 11:15, 11:30, 11:45, 12:00, 12:30, 13:30, 13:45, 14:00, 14:15, 14:30.
* **Not sold after:** 12:15, 12:45, 13:00.
* **Partly:**
  * 09:15 is the opening (97% of cycles);
  * 13:15 only in the cycles before 16 Sep (66%);
  * 14:45 only in a few (19%).

## 2. The method in plain words
1. Take the clock times at which the system sells (the consensus list of each group, `D0_SCHEDULED_ALLTIMES.md`).
2. Look for sets of times that are spaced by a whole number of 5 minutes, at the same second, between a start and an end. Such a set is a **timer**.
3. An integer program picks the smallest set of timers that explains the most times.
4. The null: shift every time randomly by ±150 s and repeat. A timer set that explains the real times and not the shifted ones is real.
5. The key test is forecasting. Learn the timers from the morning only and ask whether they predict the afternoon to the second.

## 3. The timer bank
| timer family (period @ second offset) | period_min | timers found | group-days where it appears | fires |
|---|---|---|---|---|
| every 15 min @ :00 | 15 | 12 | 7 | 97 |
| every 30 min @ :09-10 | 30 | 6 | 6 | 37 |
| every 60 min @ :30-31 | 60 | 6 | 6 | 18 |
| every 45 min @ :00 | 45 | 6 | 4 | 39 |
| every 60 min @ :00 | 60 | 7 | 4 | 28 |
| every 30 min @ :00 | 30 | 4 | 4 | 23 |
| every 30 min @ :27-28 | 30 | 3 | 3 | 9 |
| every 15 min @ :04-06 | 15 | 2 | 2 | 11 |
| every 10 min @ :00 | 10 | 1 | 1 | 10 |
| every 75 min @ :00 | 75 | 1 | 1 | 10 |
| every 20 min @ :00 | 20 | 1 | 1 | 7 |
| every 30 min @ :04-06 | 30 | 1 | 1 | 4 |
| every 15 min @ :57 | 15 | 1 | 1 | 3 |


A *group-day* is one of the eight cases D-1 / D0 × NIFTY / SENSEX × cycles before / from 16 Sep. Timers with the same period and second offset recurring in several group-days are the strongest evidence.

## 4. Every timer in NIFTY (cycles before 16 Sep)
**D-1, NIFTY (cycles before 16 Sep)** — every timer and when it fires:

* **every 15 min @ :00**, 09:16:01 → 09:45:59, 5 fires in 3 slots: 09:16:01, 09:16:02, 09:31:00, 09:31:00, 09:45:59
* **every 60 min @ :30-31**, 09:46:31 → 11:46:30, 3 fires in 3 slots: 09:46:31, 10:46:30, 11:46:30
* **every 30 min @ :09-10**, 10:01:09 → 12:31:10, 6 fires in 6 slots: 10:01:09, 10:31:09, 11:01:10, 11:31:09, 12:01:09, 12:31:10
* **every 45 min @ :00**, 10:15:59 → 13:16:00, 7 fires in 5 slots: 10:15:59, 10:15:59, 10:16:00, 11:01:00, 11:45:59, 12:31:00, 13:16:00
* **every 15 min @ :00**, 13:29:59 → 14:29:59, 5 fires in 5 slots: 13:29:59, 13:45:00, 14:00:00, 14:14:59, 14:29:59
* *not in any timer (7):* 09:16:07, 09:47:05, 10:16:57, 10:47:31, 11:15:58, 11:16:57, 11:47:30

**D0, NIFTY (cycles before 16 Sep)** — every timer and when it fires:

* **every 15 min @ :00**, 09:15:59 → 11:15:58, 8 fires in 9 slots: 09:15:59, 09:30:57, 09:31:00, 09:46:00, 10:00:58, 10:15:58, 10:16:00, 11:15:58
* **every 30 min @ :09-10**, 09:31:10 → 12:31:09, 7 fires in 7 slots: 09:31:10, 10:01:10, 10:31:10, 11:01:10, 11:31:09, 12:01:10, 12:31:09
* **every 45 min @ :00**, 09:32:00 → 13:17:00, 6 fires in 6 slots: 09:32:00, 10:17:00, 11:01:58, 11:47:00, 12:32:00, 13:17:00
* **every 60 min @ :30-31**, 09:46:31 → 11:46:31, 3 fires in 3 slots: 09:46:31, 10:46:31, 11:46:31
* **every 30 min @ :04-06**, 10:26:04 → 11:56:04, 4 fires in 4 slots: 10:26:04, 10:26:04, 10:56:04, 11:56:04
* **every 30 min @ :00**, 10:31:02 → 14:01:01, 7 fires in 8 slots: 10:31:02, 11:31:01, 12:31:01, 13:01:00, 13:01:00, 14:01:01, 14:01:01
* **every 45 min @ :00**, 10:32:00 → 13:32:00, 6 fires in 5 slots: 10:32:00, 11:16:58, 11:17:01, 12:02:00, 12:47:01, 13:32:00
* **every 10 min @ :00**, 12:06:00 → 13:56:01, 10 fires in 12 slots: 12:06:00, 12:26:00, 12:36:01, 12:46:00, 12:56:00, 13:06:00, 13:26:00, 13:36:00, 13:46:00, 13:56:01
* **every 30 min @ :27-28**, 12:31:28 → 13:31:28, 3 fires in 3 slots: 12:31:28, 13:01:28, 13:31:28
* **every 15 min @ :00**, 13:00:00 → 14:30:00, 7 fires in 7 slots: 13:00:00, 13:15:00, 13:30:00, 13:45:00, 13:59:59, 14:15:00, 14:30:00
* *not in any timer (15):* 09:16:18, 09:31:06, 09:46:06, 09:47:06, 10:16:57, 10:17:58, 10:29:58, 10:47:31, 11:11:28, 11:47:31, 12:37:27, 12:37:57, 13:49:00, 14:07:28, 14:27:57

## 5. What is not known
* **Why those periods, offsets and windows.** The timer shapes are measured; the logic that chose them (an expiry-time ramp, separate strategy legs, a hand-written list) needs the configuration.
* **Why a timer skips a slot.** Slots are skipped in 7 of 51 timers. I found no market state that explains it (`D0_SCHEDULED.md` §3 tested several for whole waves).
* **The unexplained 20%.** Fixed times that repeat across days and groups, but not on a periodic chain.
* **The 75-minute and 5-minute timers are the least certain.** They appear in only 2 group-days. Treat them as candidates.
* **The gapped timers were added after the first results** (post-hoc). They pass the same forward test, but they are more flexible than the strict ones.

## Run order
`bl_d0q_sched.py` → `bl_d0r_ilp.py` (exploratory) → `bl_d0r_val.py` → `bl_d0r_bank.py` → `bl_d0r_gap.py` → `make_d0r_report.py`.
