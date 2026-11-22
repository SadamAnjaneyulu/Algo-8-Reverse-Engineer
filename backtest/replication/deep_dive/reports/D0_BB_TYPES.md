# Algo 8 — D0 buy-backs: every reason, open to close

*Plan `D0_BB_TYPES_PLAN.md` (written before the classification; one post-hoc addendum on the chance level). In-sample: D0 of the 30 cycles, 9,656 body buy-back lots. Figure: `figures/bl_d0y_summary.png`. Scripts `bl_d0y_types.py`, `bl_d0y_other.py`.*

## 0. Result: five reasons explain about two thirds of D0 buy-backs; about a third has no firm reason
| reason | share of buy-back lots | what identifies it | market at that minute | status |
|---|---|---|---|---|
| Stop-loss | 27% | premium high ≥ 1.4× the lot's own entry; median 1.64×, 88% at or above 1.4×, 99% at or above 1.2× | spot moved against the short 0.58 steps in 5 min (random minutes 0.08) | Observed (the D-1 stop, refit lower) |
| Take-profit | 9% | premium low ≤ 0.1× entry; median 0.03×; 52% are lots carried from D-1 | spot moves slightly the lot's way | Observed (new on D0) |
| Clearance | 24% | from 15:10; mostly in profit (median 0.36×); 15:14 alone 11% | time only | Observed |
| Cycle-stop window | 3% | body buy-backs at or after the cycle stop | the cycle loss limit | Observed (chunk 4) |
| Partner | 4% | other right, same strike, within ±60 s of a stop-loss; 3.1× chance (3.1× with the clock kept) | the partner leg of a stopped straddle | Observed |
| Burst member | 12% | in a burst of ≥ 5 lots on one right; median ratio 0.99×, mixed profit and loss | mild: 0.22 steps against (random 0.03) | Unresolved trigger |
| Roll-out | 13% | a body sale on the same right within 60 s after; 2.0× chance by ±10 min shift but only 1.4× with the clock kept | weak | Not kept (below the 1.5× bar) |
| Other | 9% | none of the above; ratio 0.28–1.29× (10–90%); only 0.2% reach 1.4× | mild: 0.09 steps against (random 0.01) | Unresolved |


* **The 1.2× question.** On D-1 the stop sits at about 1.6×. On D0:
  * the stop-loss type starts at **1.4×** (the fitted threshold). 99% of stop-loss lots are at or above 1.2×, and 57% at or above 1.6×;
  * a stop at 1.2× would label 3,307 lots as stop-loss, against 2,584 at 1.4× and 1,861 at 1.6×;
  * lots bought back between 1.0× and 1.4× with no stop-loss reason are the "burst", "roll-out" and "other" lots. They are not a pile-up at 1.0×: 14% are within ±5% of entry, against 11% and 13% in the neighbouring bins.
* **About half of all buy-back lots are not stops.** 51% are bought back below their entry price (in profit), and 23% below a quarter of it.
  * The reasons are the clearance (24%), the take-profit (9%) and the partner legs.
* **No fixed holding time.** For the 1,786 lots that entered in a scheduled pair on D0, no holding duration stands out.
  * Exactly 5 / 10 / 15 / 30 / 60 minutes are each below 1% of lots.
  * Only buy-backs within 0–2 minutes of the sale are above chance (55 lots, 3%).
* **Buy-backs are not tied to the 5-minute marks.** 43% fall in the 133 s after a 5-minute mark, against 45% expected by chance.
  * Outside the clearance and the stop window, the last and first minute of each 15-minute block hold 11% and 12% of lots, against 6.7% if uniform.

## 1. All types
| type | lots | share | cycles | ratio 10% | 25% | median | 75% | 90% | share_in_loss | held (min), median | carried from D-1 | CE_share | median_time |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 cycle-stop window | 319 | 0.03 | 10 | 0.25 | 0.44 | 0.98 | 1.24 | 2.34 | 0.45 | 0.68 | 0.34 | 0.62 | 11:01 |
| 2a clearance 15:10-15:13 | 378 | 0.04 | 18 | 0.01 | 0.04 | 0.46 | 0.90 | 1.19 | 0.21 | 131.08 | 0.19 | 0.61 | 15:11 |
| 2b clearance 15:14 | 1101 | 0.11 | 17 | 0.03 | 0.10 | 0.36 | 0.76 | 1.13 | 0.14 | 159.72 | 0.27 | 0.60 | 15:14 |
| 2c clearance 15:15+ | 800 | 0.08 | 9 | 0.00 | 0.00 | 0.16 | 0.67 | 1.16 | 0.14 | 19.72 | 0.32 | 0.52 | 15:19 |
| 3 stop-loss | 2584 | 0.27 | 25 | 1.37 | 1.49 | 1.64 | 1.80 | 2.02 | 1.00 | 41.24 | 0.12 | 0.48 | 12:32 |
| 4 take-profit | 853 | 0.09 | 18 | 0.01 | 0.02 | 0.03 | 0.07 | 0.10 | 0.00 | 208.51 | 0.52 | 0.63 | 14:44 |
| 5 partner | 386 | 0.04 | 23 | 0.15 | 0.33 | 0.62 | 0.89 | 1.05 | 0.14 | 49.57 | 0.12 | 0.66 | 14:15 |
| 6 roll-out | 1259 | 0.13 | 26 | 0.37 | 0.85 | 1.01 | 1.23 | 1.55 | 0.52 | 7.10 | 0.18 | 0.54 | 12:37 |
| 7 burst member | 1128 | 0.12 | 24 | 0.31 | 0.61 | 0.99 | 1.17 | 1.32 | 0.49 | 75.11 | 0.26 | 0.47 | 14:06 |
| 8 other | 848 | 0.09 | 24 | 0.28 | 0.69 | 1.01 | 1.19 | 1.29 | 0.52 | 32.00 | 0.10 | 0.53 | 14:03 |


*Types are assigned by precedence (stop window, clearance, stop-loss, take-profit, partner, roll-out, burst, other). The overlap of the raw flags is in `bl_d0y_overlap.csv`.*

**Chance levels for the trigger-based types:**

| type | lots_reaching_rule | share_flagged | chance_shift10min | chance_shift15min_clock_kept | ratio_vs_10min | ratio_vs_15min |
|---|---|---|---|---|---|---|
| 5 partner | 3621 | 0.107 | 0.034 | 0.035 | 3.126 | 3.063 |
| 6 roll-out | 3235 | 0.389 | 0.198 | 0.272 | 1.969 | 1.429 |


* **Partner passes** (3× chance under both shifts).
* **Roll-out does not.** It is 2.0× chance with the ±10-minute shift, but 1.4× once the shift keeps the 15-minute clock. Counting only sales that are not scheduled pairs it is 32% against 21% chance (1.5×, borderline).

## 2. The market at the buy-back minute
Mean adverse spot move over the previous 5 / 15 minutes, in strike steps (CE short: spot up; PE short: spot down), against random minutes of the same cycle and hour:

| type | window_min | lots | adverse_move_steps_mean | null_mean | share_adverse | null_share_adverse | difference |
|---|---|---|---|---|---|---|---|
| 3 stop-loss | 5 | 2584 | 0.583 | 0.084 | 0.943 | 0.742 | 0.499 |
| 3 stop-loss | 15 | 2584 | 0.822 | 0.252 | 0.920 | 0.799 | 0.569 |
| 4 take-profit | 5 | 853 | -0.069 | -0.039 | 0.426 | 0.386 | -0.030 |
| 4 take-profit | 15 | 853 | -0.282 | -0.100 | 0.265 | 0.363 | -0.182 |
| 5 partner | 5 | 386 | -0.407 | -0.068 | 0.073 | 0.228 | -0.338 |
| 5 partner | 15 | 386 | -0.577 | -0.210 | 0.220 | 0.218 | -0.367 |
| 6 roll-out | 5 | 1259 | 0.094 | -0.017 | 0.537 | 0.444 | 0.111 |
| 6 roll-out | 15 | 1259 | 0.096 | -0.048 | 0.530 | 0.442 | 0.144 |
| 7 burst member | 5 | 1128 | 0.221 | 0.031 | 0.645 | 0.569 | 0.190 |
| 7 burst member | 15 | 1128 | 0.266 | 0.067 | 0.610 | 0.584 | 0.199 |
| 8 other | 5 | 848 | 0.087 | 0.006 | 0.580 | 0.512 | 0.081 |
| 8 other | 15 | 848 | 0.107 | 0.027 | 0.554 | 0.518 | 0.080 |


* **Stop-loss lots follow an adverse move**: 94% of them, against 74% for random minutes.
* **Burst and "other" lots show a mild adverse move**, about a fifth of a step. That is too weak to call a trigger.
* **Partner lots follow a favourable move for their own right**, as expected for the other leg of a stopped straddle.

## 3. Scheduled straddles
Reason, for the lots that entered in a scheduled pair or a D0 pair (grid or off-grid):

| reason | lots | share |
|---|---|---|
| 1 cycle-stop window | 87 | 0.027 |
| 2a clearance 15:10-15:13 | 135 | 0.042 |
| 2b clearance 15:14 | 378 | 0.118 |
| 2c clearance 15:15+ | 212 | 0.066 |
| 3 stop-loss | 994 | 0.310 |
| 4 take-profit | 369 | 0.115 |
| 5 partner | 152 | 0.047 |
| 6 roll-out | 242 | 0.075 |
| 7 burst member | 370 | 0.115 |
| 8 other | 272 | 0.085 |


Entry mix of every reason (columns = how the lot was sold):

| reason | deep | grid_pair | late | offgrid_pair | reactive | scheduled | solo |
|---|---|---|---|---|---|---|---|
| 1 cycle-stop window | 0 | 28 | 11 | 18 | 30 | 41 | 191 |
| 2a clearance 15:10-15:13 | 0 | 55 | 9 | 51 | 8 | 29 | 226 |
| 2b clearance 15:14 | 0 | 167 | 39 | 117 | 30 | 94 | 654 |
| 2c clearance 15:15+ | 0 | 47 | 6 | 14 | 36 | 151 | 546 |
| 3 stop-loss | 0 | 556 | 37 | 279 | 38 | 159 | 1515 |
| 4 take-profit | 0 | 105 | 14 | 33 | 49 | 231 | 421 |
| 5 partner | 0 | 67 | 8 | 62 | 7 | 23 | 219 |
| 6 roll-out | 5 | 96 | 60 | 79 | 39 | 67 | 913 |
| 7 burst member | 1 | 160 | 73 | 111 | 44 | 99 | 640 |
| 8 other | 4 | 123 | 14 | 115 | 13 | 34 | 545 |


## 4. Holding time of scheduled-pair lots
| hold_min | lots | null_mean | null_p95 | ratio |
|---|---|---|---|---|
| 0-1 | 19 | 7.65 | 13.00 | 2.48 |
| 1-2 | 36 | 8.17 | 13.00 | 4.40 |
| 2-3 | 5 | 9.24 | 14.00 | 0.54 |
| 3-5 | 25 | 20.24 | 28.00 | 1.24 |
| 5-7 | 36 | 21.99 | 29.00 | 1.64 |
| 7-10 | 50 | 37.48 | 47.00 | 1.33 |
| 10-15 | 82 | 73.17 | 86.00 | 1.12 |
| 15-20 | 69 | 78.81 | 92.00 | 0.88 |
| 20-30 | 162 | 142.90 | 161.05 | 1.13 |
| 30-45 | 181 | 183.51 | 201.00 | 0.99 |
| 45-60 | 144 | 145.67 | 161.00 | 0.99 |
| 60-90 | 292 | 271.92 | 288.00 | 1.07 |
| 90-120 | 166 | 183.58 | 196.00 | 0.90 |
| 120-180 | 193 | 203.64 | 213.00 | 0.95 |
| 180-300 | 248 | 248.08 | 255.00 | 1.00 |
| 300-500 | 78 | 80.09 | 84.00 | 0.97 |


Only the 1–2 minute bin sits clearly above chance (the quick exits). Everything else is within the null.

## 5. What is not known
* **The trigger of the burst lots** (12%) and of the "other" lots (9%). They are lots bought back at ratios from about 0.3× to 1.3× in groups, with no price level, holding time or clock that identifies them.
  * "Other" is concentrated in the 14:00 hour (340 of 848 lots), and 64% entered as solo sales.
* **Why the stop-loss threshold is 1.4× on D0 and about 1.6× on D-1.** It is a fitted value, with a graded hazard rather than a wall.
* **Lots carried from D-1.** Their buy-backs are mostly take-profit and clearance, and barely follow their own price (chunk 2).

## Caveats
* **In-sample.** All 30 cycles. Types are assigned lot by lot, so a lot with several possible reasons gets the first by precedence.
* **Ratios use the decision price.** The minute-high and minute-low tests use one-minute bars; the true intraminute path is not observed.
* **Post-hoc.** The clock-preserving chance level, and the near-1.0 and spot-move checks.

## Run order
`bl_d0b_ledger.py` → `bl_d0b_tests.py` (panel) → `bl_d0y_types.py` (~1 min) → `bl_d0y_other.py` → `make_d0y_report.py`.
