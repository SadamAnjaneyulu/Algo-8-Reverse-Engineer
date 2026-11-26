# Algo 8 — D0 step 1b: scheduled selling in depth

*Plan `D0_SCHEDULED_PLAN.md`, written before the tests. In-sample: D0 of the 30 cycles with both logs. Figure: `figures/bl_d0q_summary.png`.*

## 0. Result
* **What it is.** A clock. At fixed seconds the system sells **1 CE + 1 PE lot at the ATM strike**, a straddle. The clock is different for each underlying × version and identical across the days of a group, to within 1–3 s.
  * 1,044 pairs, 2,088 lots (25% of D0 sell lots).
* **When it starts and ends:**

| group | cycles_with_sales | waves | first | last | waves_per_15min_median | lots_per_wave | share_in_block_min_0_or_1 |
|---|---|---|---|---|---|---|---|
| NIFTY V1 | 7 | 76 | 09:15:59 | 14:30:00 | 3.500 | 1 CE + 1 PE | 0.553 |
| NIFTY V2 | 4 | 66 | 09:15:59 | 13:59:59 | 2.500 | 1 CE + 1 PE | 0.727 |
| SENSEX V1 | 9 | 12 | 09:32:01 | 13:49:01 | 1.000 | 1 CE + 1 PE | 0.000 |
| SENSEX V2 | 5 | 71 | 09:16:00 | 14:44:00 | 3.000 | 1 CE + 1 PE | 0.606 |


* **What ends it.** Every cycle sells until its group's last wave unless the cycle stop fires first. Two exceptions, both SENSEX V1:
  * one cycle skipped only the last wave; it had the highest MTM of its group (+₹4.2 L);
  * one cycle stopped scheduled selling at 10:32 with nothing unusual in its MTM or book.
  * *Unresolved* (one case each).
* **Trigger.**
  * The trigger is the clock. While the cycle is active, 95% of waves are executed (out-of-fold timetable).
  * No state variable explains the few skips: MTM, book size, spot move, distance to the strike midpoint, straddle premium and recent buy-backs all fall short of AUC 0.70 in both halves.
* **Strike chosen: the ATM of the live spot price.**
  * It is the strike nearest the previous minute's close in **96.0%** of pairs.
  * In **100%** it was the ATM strike at some moment inside the sale minute.
  * A premium-based ATM is ruled out. Where the straddle ATM (|CE − PE| smallest) or the synthetic forward picks a different strike, the real strike follows the spot ATM in 90% / 90% of cases.
  * The 4% that differ from the previous close happen when spot sits near the midpoint between two strikes (median 0.46 step from ATM, against 0.24 overall). There the spot crossed the midpoint inside the minute. This fits an ATM taken from the live price at the second of the sale. *Inferred.*
* **Same scheduler as D-1, for NIFTY.**
  * 88% (V1) and 88% (V2) of the D-1 NIFTY waves recur on D0 at the same second.
  * D0 adds about twice as many waves on top, mostly at the 15-minute block boundary (block minutes 0 and 1) and at +5, +7, +10 and +13/14 minutes of a block.
  * SENSEX runs a different D0 clock: V1 sells once per block at +60 s and shares 6% of its waves with D-1; V2 shares 34%.

## 1. The timetable (every wave = 1 CE + 1 PE lot at ATM)
Times are mm:ss within each 15-minute slot.

**NIFTY V1** (76 waves): 09:01: 15:59; 09:16: 16:18 30:57; 09:31: 31:00 31:06 31:10 32:00; 09:46: 46:00 46:06 46:31 47:06 00:58; 10:01: 01:10 15:58; 10:16: 16:00 16:57 17:00 17:58 26:04 26:04 29:58; 10:31: 31:02 31:10 32:00; 10:46: 46:31 47:31 56:04; 11:01: 01:10 01:58 11:28 15:58; 11:16: 16:58 17:01; 11:31: 31:01 31:09; 11:46: 46:31 47:00 47:31 56:04; 12:01: 01:10 02:00 06:00; 12:16: 26:00; 12:31: 31:01 31:09 31:28 32:00 36:01 37:27 37:57; 12:46: 46:00 47:01 56:00 00:00; 13:01: 01:00 01:00 01:28 06:00 15:00; 13:16: 17:00 26:00 30:00; 13:31: 31:28 32:00 36:00 45:00; 13:46: 46:00 49:00 56:01 59:59; 14:01: 01:01 01:01 07:28 15:00; 14:16: 27:57 30:00

**NIFTY V2** (66 waves): 09:01: 15:59; 09:16: 16:02 16:02 16:02 16:02 16:02 16:02 16:04 16:06 16:19 30:57 30:59 30:59 30:59 30:59; 09:31: 31:06 31:09 45:59; 09:46: 46:05 46:30 47:06 52:59 00:57; 10:01: 01:09 15:58; 10:16: 16:00 16:58 17:57 29:58; 10:31: 31:00 31:00; 10:46: 46:30 47:30; 11:01: 01:09 01:57 11:27 15:58; 11:16: 16:00 16:57 30:59 30:59; 11:31: 31:09; 11:46: 46:30 47:30 53:00; 12:01: 01:09 11:00; 12:16: 16:00 30:59; 12:31: 31:00 31:09 31:27 37:27 37:57; 12:46: 53:00 59:59; 13:01: 01:01 01:27 11:00 14:59; 13:16: 16:00 29:59; 13:31: 31:00 31:27 44:59; 13:46: 59:59

**SENSEX V1** (12 waves): 09:31: 32:01; 10:16: 17:00; 10:31: 32:01; 11:01: 02:01; 11:16: 17:00; 11:46: 47:01; 12:01: 02:01; 12:31: 32:01; 12:46: 47:00; 13:16: 17:01; 13:31: 32:01; 13:46: 49:01

**SENSEX V2** (71 waves): 09:16: 16:00 16:02 16:03 16:03 16:04 16:04 16:05 16:06 16:31 29:00 30:58; 09:31: 31:00 31:06; 09:46: 46:06 53:00 59:00 00:58; 10:16: 16:00 16:00 29:00 29:58; 10:31: 31:00 31:00 32:01; 10:46: 46:00 46:00 59:00; 11:01: 01:58 11:28; 11:16: 16:00 16:00 16:00 16:00 29:00; 11:31: 31:00 31:00 32:00 32:00; 11:46: 46:00 46:00 53:00 59:00; 12:01: 11:00; 12:16: 16:00 29:00; 12:31: 31:00 31:01 31:28 32:01 37:28; 12:46: 46:00 53:01 59:00; 13:01: 01:00 01:01 01:28 11:00 14:00; 13:16: 16:00 29:00; 13:31: 31:00 31:28 44:00; 13:46: 59:00; 14:01: 01:00 01:01 07:28 14:00; 14:16: 16:00 29:00; 14:31: 44:00

**Stability.** For each group, the share of waves learned on one cycle half that are also found on the other (±3 s):

| group | waves_half_a | waves_half_b | a_in_b | b_in_a |
|---|---|---|---|---|
| NIFTY V1 | 78 | 73 | 0.923 | 1.000 |
| NIFTY V2 | 0 | 63 | — | — |
| SENSEX V1 | 11 | 12 | 1.000 | 0.917 |
| SENSEX V2 | 69 | 63 | 0.928 | 0.984 |


NIFTY V2 has only two usable cycles (two others stopped at the open), and both are in the same half. Its timetable can only be learned in-sample.

## 2. Start and end per cycle
| cid | und | version | expiry | first_sched | last_sched | group_last_wave | stop | end_reason | sched_lots |
|---|---|---|---|---|---|---|---|---|---|
| 0 | NIFTY | V1 | 2026-06-30 | 09:30:58 | 14:15:00 | 14:30:00 | 14:25:13 | cycle stop | 146 |
| 1 | NIFTY | V1 | 2026-07-07 | 09:16:19 | 14:30:01 | 14:30:00 | - | group's last wave | 154 |
| 2 | NIFTY | V1 | 2026-07-14 | - | - | 14:30:00 | 09:15:17 | no scheduled sale (stopped at the open) | 0 |
| 3 | NIFTY | V1 | 2026-07-21 | 09:15:59 | 14:30:01 | 14:30:00 | - | group's last wave | 144 |
| 4 | NIFTY | V1 | 2026-07-28 | 09:15:59 | 14:30:00 | 14:30:00 | - | group's last wave | 166 |
| 5 | NIFTY | V1 | 2026-08-04 | 09:30:57 | 14:30:00 | 14:30:00 | - | group's last wave | 144 |
| 6 | NIFTY | V1 | 2026-08-18 | - | - | 14:30:00 | 09:15:07 | no scheduled sale (stopped at the open) | 0 |
| 7 | NIFTY | V1 | 2026-08-25 | 09:15:59 | 14:29:59 | 14:30:00 | - | group's last wave | 150 |
| 9 | NIFTY | V1 | 2026-09-08 | 09:16:02 | 14:29:59 | 14:30:00 | - | group's last wave | 154 |
| 10 | NIFTY | V2 | 2026-09-22 | 09:15:59 | 13:59:59 | 13:59:59 | 14:14:29 | group's last wave | 136 |
| 12 | NIFTY | V2 | 2026-10-06 | 09:15:58 | 13:59:59 | 13:59:59 | - | group's last wave | 132 |
| 13 | NIFTY | V2 | 2026-10-13 | 09:15:59 | 09:16:18 | 13:59:59 | 09:18:01 | cycle stop | 18 |
| 14 | NIFTY | V2 | 2026-10-19 | 09:15:59 | 09:16:02 | 13:59:59 | 09:26:19 | cycle stop | 12 |
| 15 | SENSEX | V1 | 2026-06-25 | 09:32:00 | 13:49:01 | 13:49:01 | - | group's last wave | 22 |
| 16 | SENSEX | V1 | 2026-07-02 | 09:32:01 | 13:49:01 | 13:49:01 | - | group's last wave | 24 |
| 17 | SENSEX | V1 | 2026-07-09 | 09:32:01 | 13:49:01 | 13:49:01 | - | group's last wave | 22 |
| 18 | SENSEX | V1 | 2026-07-16 | 09:32:01 | 10:32:01 | 13:49:01 | 11:00:46 | cycle stop | 6 |
| 19 | SENSEX | V1 | 2026-07-23 | 09:32:01 | 13:49:00 | 13:49:01 | - | group's last wave | 22 |
| 20 | SENSEX | V1 | 2026-07-30 | 09:32:01 | 13:49:01 | 13:49:01 | - | group's last wave | 24 |
| 21 | SENSEX | V1 | 2026-08-06 | - | - | 13:49:01 | 09:22:40 | no scheduled sale (stopped at the open) | 0 |
| 22 | SENSEX | V1 | 2026-08-13 | 09:32:00 | 13:49:01 | 13:49:01 | - | group's last wave | 24 |
| 23 | SENSEX | V1 | 2026-08-20 | - | - | 13:49:01 | 09:14:13 | no scheduled sale (stopped at the open) | 0 |
| 24 | SENSEX | V1 | 2026-08-27 | 09:32:01 | 13:32:01 | 13:49:01 | - | early end: skipped waves 13:49:01 | 22 |
| 25 | SENSEX | V1 | 2026-09-10 | 09:32:01 | 10:32:01 | 13:49:01 | - | early end: skipped waves 11:02:01, 11:47:01, 12:02:01, 12:47:00, 13:17:01, 13:32:01,  | 4 |
| 26 | SENSEX | V2 | 2026-09-17 | 09:16:02 | 14:44:00 | 14:44:00 | - | group's last wave | 142 |
| 27 | SENSEX | V2 | 2026-09-24 | - | - | 14:44:00 | 09:15:00 | no scheduled sale (stopped at the open) | 0 |
| 28 | SENSEX | V2 | 2026-10-01 | 09:16:01 | 14:44:00 | 14:44:00 | - | group's last wave | 130 |
| 29 | SENSEX | V2 | 2026-10-08 | 09:16:00 | 14:44:00 | 14:44:00 | - | group's last wave | 140 |
| 30 | SENSEX | V2 | 2026-10-15 | 09:16:00 | 09:16:04 | 14:44:00 | 09:16:28 | cycle stop | 6 |
| 31 | SENSEX | V2 | 2026-10-22 | 09:15:59 | 14:44:02 | 14:44:00 | - | group's last wave | 144 |


**Early ends, compared with the cycles of the same group that sold the same wave:**

| cid | expiry | first_skipped | mtm_lakh | book_lots | sells_so_far | others_n | others_mtm_range | others_book_range | others_sells_range |
|---|---|---|---|---|---|---|---|---|---|
| 24 | 2026-08-27 | 13:49:01 | 4.17 | 220 | 271 | 6 | 0.26..2.02 | 152..207 | 217..415 |
| 25 | 2026-09-10 | 11:02:01 | 1.79 | 173 | 109 | 7 | 0.18..3.60 | 102..195 | 96..146 |


## 3. Attendance and skips (out-of-fold waves, active cycles)
* Attendance by group: NIFTY V1 96%, NIFTY V2 100%, SENSEX V1 85%, SENSEX V2 96%.

**Single-variable AUC for skipping a wave:**

| variable | AUC_skip | ci_lo | ci_hi | AUC_half_even | AUC_half_odd |
|---|---|---|---|---|---|
| mtm_lakh | 0.459 | 0.293 | 0.615 | 0.387 | 0.484 |
| book_lots | 0.457 | 0.295 | 0.593 | 0.392 | 0.499 |
| spot_move_since_prev_wave | 0.560 | 0.401 | 0.669 | 0.397 | 0.676 |
| dist_to_strike | 0.462 | 0.360 | 0.567 | 0.447 | 0.468 |
| straddle_over_step | 0.611 | 0.492 | 0.746 | 0.601 | 0.601 |
| bb_lots_prev5 | 0.664 | 0.534 | 0.836 | 0.731 | 0.624 |


## 4. Strike candidates
| candidate | exact_share | n |
|---|---|---|
| prev_close | 0.960 | 1044 |
| minute_open | 0.951 | 1044 |
| minute_close | 0.844 | 1044 |
| any_atm_in_minute | 1.000 | 1038 |
| straddle_min_abs_ce_pe | 0.836 | 1044 |
| synthetic_forward | 0.830 | 1044 |
| previous_sched_strike | 0.807 | 1019 |


**Where the candidates disagree:**

| alternative | pairs_where_they_disagree | real_equals_prev_close | real_equals_alternative | neither |
|---|---|---|---|---|
| straddle_min_abs_ce_pe | 163 | 0.896 | 0.104 | 0.000 |
| synthetic_forward | 172 | 0.895 | 0.105 | 0.000 |
| minute_open | 35 | 0.629 | 0.371 | 0.000 |


**The 42 pairs not at the previous-close ATM:**
* every one was ATM at some point inside the minute;
* 57% match the minute-close ATM;
* 31% repeat the previous scheduled strike.

## 5. D-1 vs D0 waves
| group | D0_waves | D1_waves | D0_waves_matching_a_D1_wave | D1_waves_matching_a_D0_wave | D1_first_last | D0_first_last |
|---|---|---|---|---|---|---|
| NIFTY V1 | 76 | 33 | 0.368 | 0.879 | 09:16:01–14:29:59 | 09:15:59–14:30:00 |
| NIFTY V2 | 66 | 32 | 0.621 | 0.875 | 09:16:01–14:31:01 | 09:15:59–13:59:59 |
| SENSEX V1 | 12 | 33 | 0.167 | 0.061 | 09:16:02–14:30:00 | 09:32:01–13:49:01 |
| SENSEX V2 | 71 | 32 | 0.324 | 0.344 | 09:16:01–14:45:00 | 09:16:00–14:44:00 |


## 6. Caveats
* **In-sample.** The timetable in §1–2 and §4 is learned on all cycles (descriptive). The out-of-fold version gives the same picture (§1 stability) except for NIFTY V2.
* **Minute bars.** The strike rule is checked on minute bars. The exact second-level spot at the sale is not observed, so "live ATM" is inferred from the midpoint cases.
* **One case each** for the two early ends.

## Run order
`bl_d0q_sched.py` → `make_d0q_report.py` (needs chunk 1–4 outputs).
