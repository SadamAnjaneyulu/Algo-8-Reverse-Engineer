# Algo 8 — D0 step 1: how many kinds of selling, and which strikes (09:15 → close)

*Plan `D0_SELL_TYPES_PLAN.md`, written before the tests. A post-hoc addendum (far-OTM type) was written after the first run. In-sample: D0 of the 30 cycles with both logs, 8,336 body sell lots. Figure: `figures/bl_d0t_summary.png`.*

## 0. Result: D0 has 9 kinds of selling, plus an unexplained remainder
| # | Kind | Share of D0 sell lots | What triggers it | Strike sold | Evidence |
|---|---|---|---|---|---|
| 1 | **Scheduled pair** (CE + PE) | 21% | Fixed timetable per underlying × version (seconds repeat across cycles) | ATM 96% exact | Observed |
| 2 | **Opening pair** | 2% | 09:15–09:18, before the timetable starts | ATM 95%; at a carried strike 98% | Observed |
| 3 | **Opening solo burst** | 8% | 09:15–09:18: sells the side the opening gap favours | median offset CE -1 / PE +0 steps (− = ITM); at a carried strike 69% | Observed |
| 4 | **Counter-sell** | 20% | A buy-back on the other right within ±60 s (51% vs 25% chance) | ATM ±1 82%; same strike as the other side's buy-back 30% | Observed (about half above chance) |
| 5 | **Far-OTM roll-out** (post-hoc) | 9% | After buying back a nearer strike on the same right, sell further OTM (64% vs 16%–31% chance) | 3–7 steps OTM, median ₹23 | Observed; mostly SENSEX V1 |
| 6 | **Re-centre pair** | 3% | A body buy-back within 60 s before (41% vs 17% chance) | ATM 62%, ±1 94% | Observed |
| 7 | **Fresh-extreme solo** (the D-1 ladder) | 5% | The minute makes a 60-minute favourable extreme (26% vs 10% chance) | ATM ±1 92%, leaning ITM | Observed |
| 8 | **Breakout pair** (D-1 two-candle breakout) | 1% | First break of the previous two 30-min candles | ATM ± 1 step (85% within one) | Observed |
| 9 | **Late solo** | 0.5% | From 15:00 | around ATM | Observed (small) |
| — | **Unexplained**: "replacement" + other solo + other pair | 30% | "Replacement" (same-right buy-back before) is barely above chance after removing roll-outs (27.5% vs 23.5%) | ATM ±1 mostly | Unresolved |

**Strikes overall:**
* **Strike vs ATM:** 44% of D0 sell lots are at the ATM strike (nearest the previous minute's close) and 82% within one step.
* **Mostly strikes already held, not new ones.**
  * **58%** go to strikes already short from D-1;
  * **33%** to strikes opened earlier on D0;
  * only **9%** to new strikes.
* D0 selling **adds to the book they already carry**.

**At the opening (09:15–09:30, 1,455 lots, 17% of D0 selling):** the carried book drives the first decisions.
* **The gap side.**
  * The side sold is the one the overnight gap favours: after a gap up they sell more PE, after a gap down more CE.
  * Spearman -0.62 (p 0.0004); against the gap in 20 of 28 cycles (p 0.036).
* **Carried strikes.** 62% of opening lots are added at strikes carried from D-1.
* **The heavier side.** The heavier carried side gets more: median 63% of opening lots; more than half in 19 of 28 cycles (p 0.09). This is weaker than the gap effect.

## 1. Pre-registered taxonomy (primary)
| type | lots | orders | cycles | share_lots | ci_lo | ci_hi | lots_per_order | CE_share | median_time |
|---|---|---|---|---|---|---|---|---|---|
| scheduled pair | 1722 | 1722 | 22 | 0.207 | 0.124 | 0.287 | 1.000 | 0.500 | 11:46 |
| opening pair | 184 | 184 | 15 | 0.022 | 0.013 | 0.034 | 1.000 | 0.500 | 09:16 |
| re-centre pair | 240 | 240 | 17 | 0.029 | 0.016 | 0.046 | 1.000 | 0.500 | 13:00 |
| breakout pair | 120 | 120 | 12 | 0.014 | 0.007 | 0.023 | 1.000 | 0.500 | 12:05 |
| other pair | 226 | 226 | 11 | 0.027 | 0.004 | 0.063 | 1.000 | 0.500 | 11:31 |
| opening solo | 690 | 687 | 28 | 0.083 | 0.067 | 0.103 | 1.004 | 0.519 | 09:15 |
| replacement solo | 1770 | 1428 | 25 | 0.212 | 0.125 | 0.303 | 1.239 | 0.602 | 14:11 |
| counter-sell solo | 1788 | 1713 | 25 | 0.214 | 0.179 | 0.254 | 1.044 | 0.559 | 12:42 |
| extreme solo | 410 | 410 | 22 | 0.049 | 0.038 | 0.060 | 1.000 | 0.659 | 11:38 |
| late solo | 39 | 39 | 7 | 0.005 | 0.001 | 0.010 | 1.000 | 0.436 | 15:02 |
| other solo | 1147 | 1136 | 23 | 0.138 | 0.100 | 0.188 | 1.010 | 0.503 | 11:01 |


**Chance levels along the precedence chain:**

| group | rule | lots_reaching_rule | share_flagged | chance_share | excess_lots |
|---|---|---|---|---|---|
| pair | wave | 2492 | 0.691 | — | — |
| pair | opening | 770 | 0.239 | — | — |
| pair | recentre | 586 | 0.410 | 0.174 | 138.000 |
| pair | breakout | 346 | 0.347 | — | — |
| solo | opening | 5844 | 0.118 | — | — |
| solo | replacement | 5154 | 0.343 | 0.250 | 481.000 |
| solo | counter | 3384 | 0.528 | 0.266 | 887.000 |
| solo | extreme | 1596 | 0.257 | 0.096 | 256.000 |
| solo | late | 1186 | 0.033 | — | — |


**After the far-OTM refinement:**

| rule | lots_reaching_rule | share_flagged | chance_share | excess_lots |
|---|---|---|---|---|
| replacement | 4393 | 0.275 | 0.235 | 175 |
| counter | 3187 | 0.515 | 0.248 | 850 |
| extreme | 1546 | 0.260 | 0.096 | 253 |


**Overlap of solo flags** (lots carrying both):

| flag | opening | replacement | counter | extreme | late |
|---|---|---|---|---|---|
| opening | 690 | 193 | 492 | 117 | 0 |
| replacement | 193 | 1963 | 1658 | 817 | 362 |
| counter | 492 | 1658 | 3776 | 2062 | 508 |
| extreme | 117 | 817 | 2062 | 2563 | 290 |
| late | 0 | 362 | 508 | 290 | 587 |


## 2. Refined taxonomy (post-hoc: far-OTM roll-out as its own type)
| type2 | lots | orders | cycles | share_lots |
|---|---|---|---|---|
| scheduled pair | 1722 | 1722 | 22 | 0.207 |
| counter-sell solo | 1641 | 1641 | 24 | 0.197 |
| replacement solo | 1206 | 1206 | 24 | 0.145 |
| other solo | 1105 | 1105 | 22 | 0.133 |
| far-OTM solo | 761 | 333 | 12 | 0.091 |
| opening solo | 690 | 687 | 28 | 0.083 |
| extreme solo | 402 | 402 | 22 | 0.048 |
| re-centre pair | 240 | 240 | 17 | 0.029 |
| other pair | 226 | 226 | 11 | 0.027 |
| opening pair | 184 | 184 | 15 | 0.022 |
| breakout pair | 120 | 120 | 12 | 0.014 |
| late solo | 39 | 39 | 7 | 0.005 |


**Far-OTM roll-out:**
* 761 lots in 12 cycles. By underlying × version: NIFTY_V1 141, NIFTY_V2 169, SENSEX_V1 451.
* Time 10/50/90%: 11:04, 13:00, 14:45.
* After a same-right buy-back at a nearer strike within 60 s: 64% of lots, against 31% / 16% with buy-backs shifted +10 / −10 min. Sold premium / bought premium, median 0.35.

## 3. Strikes by type
| type | lots | exact_atm | within1 | off_median | off_q10 | off_q90 | carried_strike | D0_strike | new_strike | same_as_last_sale | d1_premium_rule | repl_same_strike_as_bb | counter_same_strike_as_other_bb | px_median | px_over_atm_median |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| scheduled pair | 1722 | 0.956 | 0.999 | 0.000 | 0.000 | -0.000 | 0.754 | 0.232 | 0.013 | 0.690 | 0.705 | 0.438 | 0.423 | 50.600 | 0.998 |
| opening pair | 184 | 0.951 | 1.000 | 0.000 | 0.000 | 0.000 | 0.984 | 0.016 | 0.000 | 0.792 | 0.781 | 0.255 | 0.232 | 52.175 | 0.984 |
| re-centre pair | 240 | 0.617 | 0.942 | 0.000 | -1.000 | 1.000 | 0.633 | 0.312 | 0.054 | 0.575 | 0.579 | 0.253 | 0.301 | 46.400 | 0.996 |
| breakout pair | 120 | 0.225 | 0.850 | 0.000 | -1.000 | 1.000 | 0.592 | 0.300 | 0.108 | 0.358 | 0.358 | — | 0.200 | 47.875 | 0.998 |
| other pair | 226 | 0.912 | 0.973 | 0.000 | 0.000 | 0.000 | 0.655 | 0.332 | 0.013 | 0.841 | 0.823 | 0.000 | 0.381 | 48.700 | 0.997 |
| opening solo | 690 | 0.230 | 0.780 | -1.000 | -2.000 | 1.000 | 0.688 | 0.245 | 0.067 | 0.600 | 0.468 | 0.212 | 0.208 | 125.675 | 1.060 |
| replacement solo | 1770 | 0.184 | 0.546 | 1.000 | -1.000 | 9.000 | 0.364 | 0.398 | 0.237 | 0.372 | 0.338 | 0.164 | 0.233 | 40.550 | 0.594 |
| counter-sell solo | 1788 | 0.338 | 0.823 | 0.000 | -1.000 | 2.000 | 0.514 | 0.399 | 0.087 | 0.510 | 0.493 | — | 0.305 | 76.925 | 0.954 |
| extreme solo | 410 | 0.371 | 0.917 | -1.000 | -1.000 | 1.000 | 0.502 | 0.466 | 0.032 | 0.585 | 0.571 | — | — | 91.600 | 1.155 |
| late solo | 39 | 0.077 | 0.692 | -1.000 | -2.000 | 1.000 | 0.615 | 0.359 | 0.026 | 0.538 | 0.538 | — | — | 79.800 | 2.136 |
| other solo | 1147 | 0.183 | 0.910 | 1.000 | -1.000 | 1.000 | 0.625 | 0.346 | 0.029 | 0.554 | 0.566 | — | — | 84.500 | 0.698 |
| ALL | 8336 | 0.439 | 0.825 | 0.000 | -1.000 | 2.000 | 0.580 | 0.333 | 0.086 | 0.550 | 0.532 | 0.203 | 0.278 | 66.350 | 0.973 |


Columns:
* `off_*`: strike offset from ATM in steps; + = OTM for the sold right.
* `carried_strike` / `D0_strike` / `new_strike`: whether the strike was already short from D-1, opened earlier on D0, or new.
* `same_as_last_sale`: the same strike as the previous sale on that right.
* `d1_premium_rule`: the strike whose premium is nearest the last sale's premium, the D-1 solo rule.
* Chance for an exact-strike rule ≈ 1/7.

## 4. Opening window per cycle
| cid | gap_steps | open_sell_lots | CE_share | carried_S_CE | carried_S_PE | heavier | share_on_heavier | carried_strike_share | new_strike_share | types |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 1.06 | 0 | — | 76 | 23 | CE | — | — | — | — |
| 1 | 0.81 | 57 | 0.25 | 49 | 74 | PE | 0.75 | 1.00 | 0.00 | counter-sell solo 5; opening pair 18; opening solo 33; other solo 1 |
| 2 | -2.37 | 18 | 0.83 | 16 | 54 | PE | 0.17 | 0.06 | 0.39 | opening solo 18 |
| 3 | -0.47 | 54 | 0.37 | 29 | 63 | PE | 0.63 | 0.98 | 0.02 | counter-sell solo 6; opening pair 24; opening solo 16; other solo 4; replacement solo 4 |
| 4 | -0.61 | 43 | 0.35 | 33 | 88 | PE | 0.65 | 0.86 | 0.02 | extreme solo 5; opening pair 12; opening solo 15; other solo 5; scheduled pair 6 |
| 5 | -2.15 | 42 | 0.24 | 63 | 69 | PE | 0.76 | 1.00 | 0.00 | opening pair 20; opening solo 12; other solo 10 |
| 6 | -1.29 | 0 | — | 26 | 68 | PE | — | — | — | — |
| 7 | -0.69 | 61 | 0.57 | 82 | 34 | CE | 0.57 | 1.00 | 0.00 | counter-sell solo 15; opening pair 20; opening solo 24; other solo 1; replacement solo 1 |
| 9 | -0.65 | 58 | 0.83 | 85 | 48 | CE | 0.83 | 0.57 | 0.03 | counter-sell solo 6; opening pair 16; opening solo 36 |
| 10 | 0.80 | 63 | 0.48 | 42 | 70 | PE | 0.52 | 0.92 | 0.02 | extreme solo 9; opening pair 18; opening solo 36 |
| 12 | 1.04 | 42 | 0.31 | 23 | 35 | PE | 0.69 | 0.88 | 0.02 | opening pair 18; opening solo 20; other solo 4 |
| 13 | 0.08 | 58 | 0.52 | 76 | 29 | CE | 0.52 | 0.98 | 0.02 | counter-sell solo 1; extreme solo 1; opening pair 4; opening solo 34; replacement solo 2; scheduled pair 16 |
| 14 | -0.09 | 235 | 0.64 | 278 | 50 | CE | 0.64 | 0.28 | 0.67 | counter-sell solo 20; opening pair 18; opening solo 27; replacement solo 170 |
| 15 | 4.08 | 41 | 0.22 | 18 | 67 | PE | 0.78 | 0.34 | 0.10 | counter-sell solo 5; opening solo 31; other solo 4; replacement solo 1 |
| 16 | 2.12 | 55 | 0.15 | 40 | 54 | PE | 0.85 | 0.55 | 0.07 | counter-sell solo 17; extreme solo 2; opening solo 32; other solo 3; replacement solo 1 |
| 17 | 2.20 | 30 | 0.27 | 93 | 6 | CE | 0.27 | 0.80 | 0.07 | counter-sell solo 7; extreme solo 3; opening solo 18; replacement solo 2 |
| 18 | 1.71 | 34 | 0.24 | 86 | 11 | CE | 0.24 | 0.76 | 0.06 | counter-sell solo 4; opening solo 27; other solo 3 |
| 19 | -3.19 | 41 | 0.71 | 70 | 43 | CE | 0.71 | 0.02 | 0.15 | counter-sell solo 4; opening solo 35; other solo 2 |
| 20 | -0.02 | 65 | 0.54 | 50 | 57 | PE | 0.46 | 1.00 | 0.00 | counter-sell solo 23; opening solo 39; other solo 2; replacement solo 1 |
| 21 | 1.91 | 75 | 0.43 | 43 | 19 | CE | 0.43 | 0.19 | 0.77 | counter-sell solo 31; opening solo 18; other solo 12; replacement solo 14 |
| 22 | -1.34 | 22 | 0.68 | 19 | 60 | PE | 0.32 | 0.86 | 0.05 | counter-sell solo 3; extreme solo 3; opening solo 15; other solo 1 |
| 23 | 5.57 | 19 | 0.21 | 73 | 47 | CE | 0.21 | 0.05 | 0.32 | opening solo 19 |
| 24 | 1.02 | 53 | 0.85 | 91 | 17 | CE | 0.85 | 0.94 | 0.04 | counter-sell solo 5; extreme solo 4; opening solo 42; other solo 1; replacement solo 1 |
| 25 | 0.21 | 49 | 0.71 | 93 | 9 | CE | 0.71 | 0.71 | 0.06 | counter-sell solo 4; extreme solo 13; opening solo 21; other solo 3; replacement solo 8 |
| 26 | -1.48 | 54 | 0.48 | 43 | 49 | PE | 0.52 | 0.87 | 0.04 | counter-sell solo 3; opening pair 6; opening solo 26; other solo 1; re-centre pair 2; scheduled pair 16 |
| 27 | -6.31 | 4 | 1.00 | 55 | 69 | PE | 0.00 | 0.00 | 0.25 | opening solo 4 |
| 28 | -2.74 | 54 | 0.70 | 64 | 6 | CE | 0.70 | 0.39 | 0.06 | opening pair 2; opening solo 25; other solo 7; scheduled pair 20 |
| 29 | 0.55 | 55 | 0.71 | 34 | 17 | CE | 0.71 | 0.75 | 0.05 | counter-sell solo 8; opening pair 2; opening solo 27; scheduled pair 18 |
| 30 | 1.82 | 32 | 0.44 | 34 | 7 | CE | 0.44 | 0.44 | 0.06 | opening pair 4; opening solo 22; scheduled pair 6 |
| 31 | -3.90 | 41 | 0.63 | 80 | 23 | CE | 0.63 | 0.15 | 0.10 | counter-sell solo 2; opening pair 2; opening solo 18; other solo 1; scheduled pair 18 |


## 5. Caveats
* **In-sample:** 30 cycles. Shares are cycle-weighted by lots; CIs come from a cycle bootstrap in Section 1.
* **Trigger labels are associations.** A label marks a timing coincidence (for example, a buy-back within ±60 s). Only the share **above chance** counts as evidence for the trigger.
* **The far-OTM type is post-hoc** and concentrated in a few cycles: 6 cycles hold 98% of it.
* **The ATM reference at 09:15** is the D0 opening price.

## Next
Step 2, as agreed: **quantity, lot sizes and risk** of D0 selling. How many lots each type sells, and what sets the count: slot, book size, gap, premium. How risk is capped per side and per strike.

## Run order
`bl_d0s_label.py` → `bl_d0s_tt.py` (out-of-fold waves) → `bl_d0b_ledger.py` → `bl_d0t_types.py` (~1 min) → `make_d0t_report.py`.
