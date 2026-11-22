# Algo 8 — D0 chunk 1: body sells

*Plan `D0_SELLS_PLAN.md` (written before the tests; addenda 1b and 1c were written after T1 and T3 and before their own tests). In-sample: D0 of the 30 cycles with both D-1 and D0 logs (29 have D0 sells). Out-of-fold = cycle halves by parity. Figure: `figures/bl_d0s_summary.png`.*

## 0. Result
* **D0 selling ranks at AUC 0.932** (CI 0.905–0.957) from market data and the decoded rules, with leave-one-cycle-out fits.
  * With completed bars only (causal) the AUC is **0.893**.
  * Adding the real buy-back history from earlier minutes gives **0.944**. *Observed.*
* **D0 has a fixed pair timetable, like D-1, but per underlying and version.**
  * Pair start seconds repeat across cycles to within 1–2 s: NIFTY V1 76 waves, NIFTY V2 66 waves, SENSEX V1 12 waves, SENSEX V2 71 waves.
  * Learned on one half and scored on the other, it gives pair-lot **F1 0.805** (precision 96%, recall 69%), with the strike nearest the previous close 99% exact. *Observed.*
  * **This corrects `D0_INVENTORY.md`.** Its "no D0 timetable" came from pooling NIFTY and SENSEX.
* **All body selling stops at the first stop-module order** (11 cycles). In 4 of them the stop fires before 09:16. Here the stop time is taken from the real orders; chunk 4 decodes it.
* **Solo sells (70% of D0 sale lots) are the weak part, as on D-1.**
  * The D-1 ladder carries over and is precise (84%) but finds only 8% of the lots.
  * Refit for D0 (finer 0.05-step ladder, lots = steps crossed, fresh 60-minute extreme), it reaches **F1 0.377**, against a placebo of 0.095.
  * Adding a counter-sell on the real other-right buy-backs gives 0.395.
* **Solo sells are tied to buy-backs on the other right.**
  * 64% of solo lots are sold within ±60 s of one, against a 33% null.
  * The tie is partly a common cause, the same spot move. Inside each spot-move quintile the buy-back still ranks solo minutes at AUC 0.59–0.65.
  * There is no fixed lot ratio (median 0.50, IQR 0.25–1.00).

## 1. What D0 selling is made of
| label | definition | lots | share |
|---|---|---|---|
| grid pair | CE + PE at the same strike within 3 s, starting in minute-of-hour 1–3 / 16–18 / 31–33 / 46–48 | 1,536 | 18.4% |
| off-grid pair | the same pairing, any other minute | 956 | 11.5% |
| solo | unpaired sale | 5,844 | 70.1% |

These are 8,336 lots in the 30 decodable cycles. The inventory's 10,190 also counts 3 cycles with no D-1 log, which are left out here.

## 2. The pair timetable
**The pooled slot view (T1)** shows the windows exist but mixes groups:
* grid windows hold 1,539 pair lots, against 196 / 206 in windows shifted by 5 / 10 minutes;
* a pooled rule of one pair per slot scores only 0.446.

**Per underlying and version (T1b),** learned out-of-fold:

| test | F1 | ci_lo | ci_hi | precision | recall | real_lots | sim_lots |
|---|---|---|---|---|---|---|---|
| T1b timetable (OOF) vs all pair lots | 0.805 | 0.726 | 0.865 | 0.964 | 0.691 | 2492 | 1786 |
| T1b timetable (OOF) vs grid-pair lots only | 0.661 | 0.615 | 0.700 | 0.615 | 0.715 | 1536 | 1786 |


Waves found on all cycles (descriptive):

| und | version | cycles | waves | lots_per_right |
|---|---|---|---|---|
| NIFTY | V1 | 9 | 76 | 76 |
| NIFTY | V2 | 4 | 66 | 66 |
| SENSEX | V1 | 11 | 12 | 12 |
| SENSEX | V2 | 6 | 71 | 71 |


* The NIFTY timetables have several pairs per slot. SENSEX V1 has one pair per slot, about 60 s after the slot start, and sells in fewer slots.
* 69% of real pairs fall within 3 s of a wave of their own group (out-of-fold).

## 3. Pairs the timetable does not explain (385)
* **123 are in the 09:xx hour,** 92 of them between 09:15 and 09:18: an opening burst whose size varies by cycle.
* **41% follow a body buy-back within 60 s,** against 21% for timetable pairs. They look like re-centring pairs after a stop (*Inferred*).
* **The D-1 breakout machine, run unchanged, explains part of the rest (10:30–15:15):**

| test | F1 | ci_lo | ci_hi | precision | recall | real_lots | sim_lots |
|---|---|---|---|---|---|---|---|
| T2b breakout machine vs residual pair minutes 10:30-15:15 | 0.375 | 0.280 | 0.492 | 0.431 | 0.331 | 178 | 137 |
| T2b placebo: cycle-permuted spot | 0.095 | 0.061 | 0.125 | 0.109 | 0.084 | 178 | 138 |
| T2b placebo: fires +15 min | 0.063 | 0.014 | 0.110 | 0.073 | 0.056 | 178 | 137 |


## 4. Solo sells
**Descriptive tests (T3)**

| test | value | ci_lo | ci_hi | null | n |
|---|---|---|---|---|---|
| T3a solo lots after a favourable 5-min spot move | 0.632 | 0.596 | 0.668 | 0.549 | 5844 |
| T3a solo lots after a favourable 15-min spot move | 0.595 | 0.528 | 0.650 | 0.590 | 5844 |
| T3b D-1 solo ladder on D0 vs solo lots | 0.154 | 0.126 | 0.187 | — | 5844 |
| T3b placebo: cycle-permuted spot | 0.051 | 0.037 | 0.066 | — | 5844 |
| T3c replacement: same-right buy-back within 60 s before the sale | 0.342 | 0.240 | 0.440 | 0.225 | 5844 |
| T3d counter-sell: other-right buy-back within 60 s before or after | 0.643 | 0.585 | 0.698 | 0.333 | 5844 |


* **Bursts.** 2,032 bursts (gap ≤ 30 s). The median burst is 1 lot, the 90th percentile 6. Bursts of 5+ lots carry 50% of solo lots, and 76% of them come with a favourable spot move.
* **Coupling with other-right buy-backs (±90 s).**
  * 72% of solo lots are in such bursts.
  * The buy-back comes -62 s to 16 s around the burst start (IQR).
  * Sold lots / bought lots: median 0.50. There is no fixed ratio.

**Machines, fitted on one half and scored on the other (addendum 1c)**

| machine | F1 | ci_lo | ci_hi | precision | recall | sim_lots | real_lots | chosen |
|---|---|---|---|---|---|---|---|---|
| M1 spot ladder | 0.377 | 0.329 | 0.420 | 0.459 | 0.320 | 4071 | 5844 | (0.05, 60, True) / (0.05, 60, True) |
| M2 premium ladder | 0.340 | 0.298 | 0.379 | 0.310 | 0.376 | 7089 | 5844 | (0.05, True) / (0.05, True) |
| M3 counter-sell on real buy-backs | 0.314 | 0.274 | 0.352 | 0.284 | 0.352 | 7245 | 5844 | 0.5 / 1.0 |
| M4 union ladder + counter-sell | 0.395 | 0.354 | 0.432 | 0.367 | 0.429 | 6837 | 5844 | ('M1', (0.05, 60, True), 0.25) / ('M1', (0.1, 60, True), 0.5) |
| D-1 ladder unchanged (X 0.2, gate 60, 1 lot) | 0.154 | 0.124 | 0.196 | 0.842 | 0.085 | 589 | 5844 | (0.2, 60, False) / (0.2, 60, False) |
| placebo M1 (0.05, 60, True) on cycle-permuted spot (all cycles) | 0.095 | 0.079 | 0.114 | 0.123 | 0.077 | 3653 | 5844 | placebo |
| M1 (0.05, 60, True) real spot (all cycles, same config, for the placebo comparison) | 0.377 | 0.331 | 0.419 | 0.459 | 0.320 | 4071 | 5844 | reference |
| placebo M1 (0.1, 60, True) on cycle-permuted spot (all cycles) | 0.090 | 0.072 | 0.109 | 0.168 | 0.061 | 2136 | 5844 | placebo |
| M1 (0.1, 60, True) real spot (all cycles, same config, for the placebo comparison) | 0.330 | 0.280 | 0.383 | 0.559 | 0.234 | 2449 | 5844 | reference |
| placebo M3 r 0.5, buy-backs shifted +600 s | 0.152 | 0.109 | 0.197 | 0.175 | 0.135 | 4524 | 5844 | placebo |
| placebo M3 r 0.5, buy-backs shifted -600 s | 0.194 | 0.142 | 0.243 | 0.214 | 0.177 | 4813 | 5844 | placebo |
| M3 r 0.5 real buy-back times (all cycles, reference) | 0.325 | 0.286 | 0.360 | 0.366 | 0.292 | 4657 | 5844 | reference |
| post-hoc: M1 extended grid (X 0.02-0.05, gate 60-120) | 0.378 | 0.331 | 0.421 | 0.421 | 0.343 | 4755 | 5844 | (0.05, 60, True) / (0.03, 60, True) |


* The finer ladder is the best single rule. The grid boundary (0.05 step) does not bind: the extended grid gives the same F1.
* Counter-sell is a real coupling (2× its shifted placebo), but adds little on top of the ladder.

**Common-cause check (T5).** The same-minute other-right buy-back as a score for solo minutes, inside quintiles of the favourable spot move:

| quintile | mv_lo | mv_hi | cells | solo_rate | AUC_bb_other_now | AUC_bb_other_prev5 |
|---|---|---|---|---|---|---|
| 0 | -14.467 | -0.078 | 2835 | 0.117 | 0.594 | 0.577 |
| 1 | -0.078 | 0.027 | 2834 | 0.071 | 0.592 | 0.572 |
| 2 | 0.028 | 0.138 | 2835 | 0.091 | 0.616 | 0.577 |
| 3 | 0.138 | 0.335 | 2834 | 0.166 | 0.594 | 0.607 |
| 4 | 0.335 | 31.954 | 2835 | 0.298 | 0.653 | 0.617 |


## 5. Strikes (T4)
* **Pairs:** at the strike nearest the previous minute's close 89% exact, 98% within one step.
* **Solo:** nearest ATM 27% exact, 83% within one step. The D-1 rule (the premium nearest the last sale's premium on that right) scores 50%.
  * Solo sells sit around ATM, often at 2 strikes in one burst. Neither rule is exact.

## 6. One ranking number for D0 selling (T5)
| variant | AUC | ci_lo | ci_hi | AUC_no_wave_minutes | cells | positives |
|---|---|---|---|---|---|---|
| A same-minute market + rules | 0.932 | 0.905 | 0.957 | 0.896 | 15670 | 3605 |
| B causal (market lagged 1 min) | 0.893 | 0.859 | 0.927 | 0.830 | 15670 | 3605 |
| C A + real buy-back history (earlier minutes) + book | 0.944 | 0.928 | 0.959 | 0.918 | 15670 | 3605 |
| C0 C + same-minute buy-backs (teacher-forced) | 0.952 | 0.940 | 0.963 | 0.931 | 15670 | 3605 |
| timetable + clock only | 0.834 | 0.804 | 0.863 | 0.740 | 15670 | 3605 |


`AUC_no_wave_minutes` leaves out the cells within one minute of a timetable wave (out-of-fold waves).

**By sell label (that label's cells against all no-sale cells):**

| sell_label | cells_with_sale | A same-minute market + rules | B causal (market lagged 1 min) | C A + real buy-back history (earlier minutes) + book | C0 C + same-minute buy-backs (teacher-forced) | timetable + clock only |
|---|---|---|---|---|---|---|
| grid_pair | 876 | 0.974 | 0.972 | 0.973 | 0.977 | 0.974 |
| offgrid_pair | 815 | 0.962 | 0.957 | 0.967 | 0.969 | 0.926 |
| solo | 2108 | 0.907 | 0.843 | 0.926 | 0.938 | 0.742 |


## 7. Kept and rejected
| rule | result | null / comparison | decision | evidence |
|---|---|---|---|---|
| D0 pair timetable per underlying x version (fixed seconds) | OOF lot F1 0.805 (precision 96%, recall 69%); strike exact 99% | pooled slot rule 0.446 | kept | Observed |
| D-1 breakout machine on pairs the timetable leaves | F1 0.375 (CI 0.28–0.49) | placebos 0.095 / 0.063 | kept (weak recall) | Observed |
| D-1 solo ladder unchanged | F1 0.154 (precision 84%, recall 8%) | placebo 0.051 | carries over, but covers 9% of D0 solo lots | Observed |
| M1 spot ladder refit for D0 (0.05 step, fresh 60-min extreme, lots = steps crossed) | F1 0.377 (CI 0.33–0.42) | placebo 0.095 | kept | Observed |
| M2 premium ladder | F1 0.340 | below M1 | rejected (M1 better) | Observed |
| M3 counter-sell r × real other-right buy-back lots | F1 0.314; all-cycle r 0.5 0.325 | shifted buy-backs 0.152–0.194 | kept as coupling (teacher-forced) | Observed |
| M4 union ladder + counter-sell | F1 0.395 | M1 alone 0.377 | kept (+0.02) | Observed |
| Solo direction after a favourable 5-min move | 63% | null 55% | descriptive only (< 1.5× null) | Observed |
| Replacement: same-right buy-back ≤ 60 s before | 34% of solo lots | null 22% | kept (1.5×, CI clears null) | Observed |
| Counter-sell: other-right buy-back within ±60 s | 64% of solo lots | null 33% | kept | Observed |


## 8. Caveats
* **In-sample.** All 30 cycles were used to find the structure. Scores are out-of-fold over cycle halves only. The timetable groups are small (NIFTY V2: 4 cycles).
* **Teacher-forced parts:** the stop time, the ladder resets at real pair sales, and M3 (real buy-backs). Chunk 5 replaces them with simulated ones.
* **Two matchers.** T3b (descriptive) uses the one-to-one matcher without the stop gate; the machine table uses a minute histogram matcher with the stop gate. The D-1 ladder scores F1 0.154 under both.
* **Solo machines are scored on the minute only.** Strike is not used in their F1 (Section 5 covers strikes). The minute matcher takes exact minutes first, then ±1.
* **Same-minute alignment (AUC A)** uses the bar the sale falls in. B is the causal number.
* **Post-hoc steps:**
  * addenda 1b and 1c were written after seeing T1 and T3;
  * the extended ladder grid and the all-cycle wave table are labelled where they appear.

## Run order
`src/bl_d0_data.py` → `bl_d0s_label.py` → `bl_d0s_tests.py` → `bl_d0s_tt.py` → `bl_d0s_solo.py` → `bl_d0s_auc.py` → `make_d0s_report.py`. Outputs `outputs/bl_d0s_*`, `bl_summary_d0s0…4.json`.
