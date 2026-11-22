# Algo 8 — D0 counter-sells: what they are

*Plan `D0_COUNTER_PLAN.md`, written before the tests. In-sample: D0 of 30 cycles, 1,395 stop-loss buy-back events, solo sales of the other right. Figure: `figures/bl_d0k_summary.png`. Script `bl_d0k_counter.py`.*

## 0. Result: no sign that the buy-back itself triggers the counter-sell
* **Stop-loss buy-backs go together with other-right sales.** Around a stop-loss, 6.8 solo sale orders land on the other right within ±90 s per event, against 1.5 for times shifted by 15 minutes (4.6×). 63% of events have a sale in the next 60 s (null 19%).
  * By the plan's rule (at least 1.5× both chance levels) the reasons that go with sales are: **stop-loss, cycle-stop window, burst member, roll-out and "other"** (3.8/4.6×, 6.3/10.4×, 2.7/3.6×, 2.6/2.4×, 1.7/2.0×, against the two chance levels).
  * **Take-profit (0.8×), partner (0.9/1.3×) and clearance do not** (clearance 15:10–15:13 passes one chance level and fails the other). *Observed.*
* **But the sales are not shown to be caused by the buy-back.** They come as often before it as after: 2,104 orders in the 30 s before and 2,029 in the 30 s after (null 283–357). A trigger would show them after. *Observed.*
* **The spot move accounts for much of it.** When the other right's short is at a fresh 60-minute favourable extreme (spot making new lows for a CE short, new highs for a PE short), it sells 3.3 lots in the minute, against 0.39 without it.
  * A stop-loss on the first right goes with that move: 62% of stop minutes in the biggest adverse bin are also fresh extremes for the other right, against 18% of other minutes.
  * The stop adds a smaller lift: stop-only minutes sell 1.74 lots against 0.39 (neither); extreme-only 3.26; both together 4.38. The "fresh extreme" gate is my 60-minute definition, so stop-only minutes may contain other spot moves it misses.
  * Within the same size of adverse move, stop-loss minutes still sell more in the larger-move bins, with a CI that excludes zero in 4 of the 6 bins that have enough stop minutes. **That does not meet my 8-of-10-bin bar**, so I keep it as a common cause with a possible extra effect of the stop, not as a trigger.
* **The quantity does not follow the lots bought.** Sold lots in the next 60 s are about 2 to 2.6 whatever the number of lots bought back (Spearman -0.02). The median is 1 lot. It is not a one-for-one replacement.
* **The strike is the live ATM, not the stopped strike.** 38% are at the ATM of the previous minute's close and 87% within one step. Only 13% are at the stopped strike. The premium sold is a median 0.58× the premium bought back.
* **Which stop events lead to a sale cannot be predicted** from lots bought, hour or time of day (AUC 0.49, 0.49, 0.49, all CIs include 0.5); the buy-back ratio is weak (AUC 0.58).

**So the "counter-sell" lots (20% of D0 sell lots) look largely like the fresh-extreme solo ladder firing in the same minutes as stop-losses, with a smaller possible extra effect of the stop itself.** *Inferred; the share is not quantified.*

## 1. C1 — which buy-backs go with other-right sales
| reason | events | sales_per_event | null_10min | null_15min_clock_kept | ratio_vs_10 | ratio_vs_15 | share_events_with_sale_0_60s | null_share_15min |
|---|---|---|---|---|---|---|---|---|
| 1 cycle-stop window | 30 | 4.87 | 0.77 | 0.47 | 6.35 | 10.43 | 0.57 | 0.05 |
| 2a clearance 15:10-15:13 | 160 | 1.03 | 2.64 | 0.36 | 0.39 | 2.87 | 0.16 | 0.08 |
| 2b clearance 15:14 | 83 | 0.30 | 1.23 | 0.56 | 0.24 | 0.54 | 0.08 | 0.08 |
| 2c clearance 15:15+ | 382 | 0.45 | 0.68 | 2.69 | 0.66 | 0.17 | 0.08 | 0.18 |
| 3 stop-loss | 1395 | 6.78 | 1.77 | 1.46 | 3.82 | 4.63 | 0.63 | 0.19 |
| 4 take-profit | 612 | 1.24 | 1.21 | 1.48 | 1.03 | 0.84 | 0.18 | 0.18 |
| 5 partner | 191 | 1.02 | 1.18 | 0.78 | 0.86 | 1.31 | 0.18 | 0.16 |
| 6 roll-out | 789 | 4.11 | 1.59 | 1.73 | 2.59 | 2.38 | 0.50 | 0.36 |
| 7 burst member | 409 | 4.68 | 1.71 | 1.28 | 2.74 | 3.65 | 0.41 | 0.14 |
| 8 other | 606 | 2.46 | 1.49 | 1.24 | 1.65 | 1.98 | 0.22 | 0.17 |

Rates are solo sale orders on the other right within ±90 s per event. Why roll-out, burst and "other" buy-backs also sit above chance was not tested here.

## 2. C2 — timing
| lag_from_s | lag_to_s | orders | null_15min |
|---|---|---|---|
| -60 | -55 | 274 | 55 |
| -55 | -50 | 254 | 56 |
| -50 | -45 | 280 | 60 |
| -45 | -40 | 324 | 60 |
| -40 | -35 | 394 | 47 |
| -35 | -30 | 384 | 46 |
| -30 | -25 | 278 | 52 |
| -25 | -20 | 346 | 49 |
| -20 | -15 | 303 | 40 |
| -15 | -10 | 282 | 49 |
| -10 | -5 | 305 | 49 |
| -5 | 0 | 590 | 44 |
| 0 | 5 | 676 | 80 |
| 5 | 10 | 283 | 51 |
| 10 | 15 | 222 | 58 |
| 15 | 20 | 245 | 50 |
| 20 | 25 | 291 | 67 |
| 25 | 30 | 269 | 48 |
| 30 | 35 | 194 | 42 |
| 35 | 40 | 217 | 46 |
| 40 | 45 | 207 | 35 |
| 45 | 50 | 200 | 44 |
| 50 | 55 | 186 | 56 |
| 55 | 60 | 150 | 57 |
| 60 | 65 | 192 | 73 |
| 65 | 70 | 200 | 53 |
| 70 | 75 | 157 | 61 |
| 75 | 80 | 159 | 42 |
| 80 | 85 | 132 | 47 |
| 85 | 90 | 154 | 56 |


## 3. C3 — cause or common cause
Minute panel, within bins of the adverse 5-minute spot move (the lowest bins have too few stop minutes):

| adverse_move_bin | adv_lo | adv_hi | cells_with_stop | cells_without | sold_with_stop | sold_without | difference | ci_lo | ci_hi | fav_ext_share_with | fav_ext_share_without |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 4 | -0.07 | 0.00 | 12 | 1392 | 1.00 | 0.29 | 0.71 | -0.09 | 1.49 | 0.17 | 0.01 |
| 5 | -0.00 | 0.07 | 20 | 1384 | 1.40 | 0.31 | 1.09 | 0.49 | 2.15 | 0.35 | 0.02 |
| 6 | 0.07 | 0.14 | 39 | 1364 | 1.03 | 0.51 | 0.52 | -0.02 | 1.10 | 0.26 | 0.05 |
| 7 | 0.14 | 0.25 | 67 | 1337 | 1.87 | 0.63 | 1.24 | 0.51 | 2.20 | 0.54 | 0.07 |
| 8 | 0.25 | 0.43 | 113 | 1291 | 3.02 | 0.87 | 2.15 | 1.43 | 2.87 | 0.58 | 0.11 |
| 9 | 0.43 | 3.28 | 302 | 1102 | 4.15 | 1.55 | 2.59 | 2.02 | 3.43 | 0.62 | 0.18 |


Sold lots, split by stop and by fresh extreme:

| sl | fe | cells | sold |
|---|---|---|---|
| False | False | 12913 | 0.39 |
| False | True | 552 | 3.26 |
| True | False | 265 | 1.74 |
| True | True | 308 | 4.38 |


## 4. C4 — quantity, C5 — strike, C6 — which events lead to a sale
| bin | events | bought_mean | sold_mean | sold_median | share_with_sale | sold_over_bought |
|---|---|---|---|---|---|---|
| 1 | 849 | 1.00 | 2.63 | 1.00 | 0.64 | 2.63 |
| 2 | 290 | 2.00 | 2.62 | 1.00 | 0.62 | 1.31 |
| 3 | 102 | 3.00 | 2.07 | 1.00 | 0.62 | 0.69 |
| 4-5 | 89 | 4.34 | 2.34 | 1.00 | 0.58 | 0.54 |
| 6-8 | 42 | 6.67 | 2.12 | 1.00 | 0.64 | 0.32 |
| 9-15 | 23 | 9.57 | 2.00 | 1.00 | 0.65 | 0.21 |


| variable | AUC | ci_lo | ci_hi |
|---|---|---|---|
| lots | 0.490 | 0.450 | 0.534 |
| ratio | 0.581 | 0.533 | 0.627 |
| hour | 0.492 | 0.429 | 0.539 |
| j | 0.488 | 0.420 | 0.540 |


## 5. What is not known
* **The exact trigger of the ladder.** The step size and gate were fitted in `D0_SELLS.md` (0.05 step, fresh 60-minute extreme, F1 about 0.38). Nothing here improves that.
* **Whether the stop has its own effect.** The stop-only lift is modest and cannot be separated from intraminute extremes with one-minute bars.
* **Order inside the minute.** Minute bars cannot say whether the sale or the buy-back came first; the 5 s histogram shows the sales spread on both sides.

## Caveats
* **In-sample.** One-minute market bars. Cycle-bootstrap CIs.
* The 8-of-10-bin acceptance bar in the plan was not met (4 of 6 evaluable bins).

## Run order
`bl_d0s_label.py` → `bl_d0y_types.py` → `bl_d0k_counter.py` (~1 min) → `make_d0k_report.py`.
