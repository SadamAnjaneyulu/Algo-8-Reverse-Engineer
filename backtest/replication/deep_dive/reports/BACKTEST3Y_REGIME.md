# Is the edge seasonal, or does it only work in some periods?

*Plan `BACKTEST3Y_REGIME_PLAN.md`, written before the tests. **Exploratory**: every cycle (IS, OOS, rule-fitted live window) is used and no untouched data remain. Unit = ISO week at a constant lot size. Scripts `bl_bt3_regime.py`, `make_regime_report.py`; figure `figures/bl_bt3_regime.png`.*

## 0. Answer

**No evidence that the edge is seasonal or confined to a period. The one thing that does separate good weeks from bad weeks is the size of the overnight/opening gap, and that finding is fragile.**

| question | answer | evidence |
|---|---|---|
| Does it work only in some stretch of time? | **No evidence of that.** 65% of weeks are positive; the rolling 26-week mean moves no more than shuffled weeks do (p = 0.81); no change point (p = 0.36); weeks are uncorrelated (lag-1 autocorrelation -0.13, band ±0.16). **The latest 26 weeks are the weakest stretch of the series (₹15k per cycle, interval -60k to 83k), still inside the noise band;** if it is decay it would take more weeks to show. First half ₹69k, second half ₹51k per cycle: difference -19k (CI -94k to 54k), not significant. | Observed |
| Is there a seasonal (calendar) pattern? | **Not supported.** Month of year p = 0.38, quarter 0.33, week of month 0.16, year 0.56, half-year 0.72, monthly-expiry week 0.87 (family tests, before Holm). | Observed |
| But February looks great. | February: ₹210k per cycle-week, 92% winning weeks, cell q = 0.005. **But one of 12 months will look like that by chance**: the family test across the 12 months does not beat shuffled labels. All three Februaries are positive (₹146k, ₹235k, ₹266k); three observations are a hypothesis (the Union Budget is in that month), not a season. | Observed; hypothesis only |
| What does separate good weeks from bad? | **The opening gap on D0** (D0 open vs D-1 close): family p = 0.002, Holm 0.028, the only supported family of 14. Net per cycle ₹131k (gap < 0.18% of spot), ₹77k (0.18–0.31%), **₹-28k (> 0.31%)**. Cycle stops rise from 21% to 31% to 47%. | Observed |
| Is the gap effect robust? | **Only partly.** It is monotone in-sample and in the rule-fitted window, but **not out of sample** (low / mid / high ₹36k / ₹147k / ₹10k); it is strong in SENSEX and weak in NIFTY; and the loss sits in the **carried D-1 book** (₹-40k per week in high-gap weeks against ₹72k in low-gap weeks), while the D0 module still adds ₹13k. It is the overnight risk of the carry, not a calendar effect, and the gap is not known when the D-1 book is built. | Observed |
| Is the P&L explained by the usual short-premium story? | **No.** The weekly net is unrelated to the realised ÷ implied ratio (Spearman -0.02, p = 0.77), to the realised move (-0.01) and to the implied move (-0.01). A hedged, stop-managed book of ≈ 1,300 orders per cycle does not behave like a plain short straddle. | Observed |

**Power.** The weekly net has mean ₹60k, standard deviation ₹236k, standard error ₹19k on 158 weeks. To detect a calendar effect of ₹150k per cycle in a single month at 80% power you need about 19 weeks of that month, i.e. ≈ 5 years. **This sample cannot find a seasonal effect of this size even if one exists.**

## 1. Stationarity (weekly net, constant lot size)

| series | weeks | mean | roll26_sd | roll26_sd_p | changepoint_t | changepoint_week | changepoint_p | first_half_mean | second_half_mean | diff | diff_lo | diff_hi | acf1 | acf2 | acf3 | acf4 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| net | 158 | 59977.2 | 31802.3 | 0.812 | -1.909 | 127 | 0.359 | 69397.7 | 50556.6 | -18841.1 | -94320.7 | 54476.6 | -0.127 | -0.046 | 0.025 | -0.099 |
| gross | 158 | 124336 | 38470.2 | 0.63 | -2.286 | 127 | 0.181 | 145187 | 103486 | -41700.8 | -117921 | 37417.6 | -0.106 | -0.03 | 0.043 | -0.084 |
| altA_net | 158 | 44020 | 27318.4 | 0.883 | -1.687 | 123 | 0.508 | 55931.7 | 32108.2 | -23823.5 | -90721.8 | 42748.8 | -0.149 | -0.104 | 0.092 | -0.082 |
| d1only | 158 | 25842.5 | 20527.4 | 0.921 | -1.065 | 123 | 0.909 | 17621.6 | 34063.5 | 16441.9 | -41650.7 | 69323.7 | -0.044 | -0.097 | 0.025 | 0.142 |
| d0adds | 158 | 34134.6 | 34032.2 | 0.184 | -2.252 | 128 | 0.194 | 51776.1 | 16493.1 | -35283 | -83760.1 | 11795.4 | -0.016 | -0.043 | -0.058 | -0.074 |

*Series: net = B/V2 point line; gross = before slippage and costs; altA_net = timetable A/V1 band; d1only = the D-1 book managed alone; d0adds = what the D0 module adds. `roll26_sd_p` = chance that shuffled weeks vary as much as the real rolling means (small = regimes). `changepoint_p` = chance that shuffled weeks contain a split at least as pronounced.*

## 2. Families (permutation test of the labels, Holm over the 14 families)

| family | groups | family_p | p_holm | best_cell_q | sign_ok | supported |
|---|---|---|---|---|---|---|
| month of year | 12 | 0.382 | 1 | 0.0048 | True | False |
| quarter | 4 | 0.327 | 1 | 0.0616 | True | False |
| calendar year | 4 | 0.5556 | 1 | 0.0232 | True | False |
| half-year | 7 | 0.7238 | 1 | 0.0072 | True | False |
| week of month (D0) | 5 | 0.1634 | 1 | 0.0129 | True | False |
| monthly-expiry week | 2 | 0.8686 | 1 | 0.0357 | True | False |
| timetable regime | 2 | 0.1472 | 1 | 0.0072 | True | False |
| weekday of D0 (within week) | 5 | 0.0502 | 0.6526 | 0.0806 | True | False |
| index (within week) | 2 | 0.2912 | 1 | 0.0414 | True | False |
| implied move at D-1 open (ex ante) | 3 | 0.215 | 1 | 0.0048 | True | False |
| D-1 morning range (ex ante) | 3 | 0.3528 | 1 | 0.0048 | True | False |
| opening gap on D0 (known at the D0 open) | 3 | 0.002 | 0.028 | 0.0048 | True | True |
| realised move (ex post) | 3 | 0.305 | 1 | 0.0048 | True | False |
| realised / implied ratio (ex post) | 3 | 0.8122 | 1 | 0.0357 | True | False |

*Supported = family permutation p < 0.05 after Holm AND a cell with FDR q < 0.10 AND the same sign in the A/V1 band and in the gross series. `best_cell_q` is the smallest Benjamini–Hochberg q among the family's cells (58 cells in total).*

## 3. Cells

| family | cell | weeks | mean_net | lo | hi | p_cell | q_bh | mean_gross | mean_altA_net | win_weeks |
|---|---|---|---|---|---|---|---|---|---|---|
| month of year | 1 | 13 | 32582.6 | -92103.7 | 192442 | 0.739 | 0.765 | 91837.5 | 46392 | 0.385 |
| month of year | 2 | 13 | 210156 | 105416 | 310952 | 0 | 0.005 | 271914 | 170222 | 0.923 |
| month of year | 3 | 13 | 92936.3 | -76746.8 | 252045 | 0.284 | 0.415 | 160377 | 63991.2 | 0.846 |
| month of year | 4 | 13 | -81083.7 | -204815 | 35215.3 | 0.179 | 0.281 | -36194.6 | -99824 | 0.462 |
| month of year | 5 | 13 | 46310.8 | -80903.3 | 177502 | 0.503 | 0.621 | 124698 | 54965.7 | 0.692 |
| month of year | 6 | 13 | 91007.3 | -31031.4 | 210143 | 0.15 | 0.249 | 160361 | 61037.6 | 0.692 |
| month of year | 7 | 13 | 79286.1 | -4926.3 | 174688 | 0.066 | 0.16 | 143354 | 63218.4 | 0.615 |
| month of year | 8 | 13 | 15247.5 | -95404.6 | 115210 | 0.802 | 0.816 | 75622.3 | 4735.74 | 0.615 |
| month of year | 9 | 14 | 26247.2 | -66207.8 | 117008 | 0.538 | 0.637 | 85808.1 | 12628.1 | 0.571 |
| month of year | 10 | 13 | 67970.4 | -58949.9 | 180971 | 0.286 | 0.415 | 137052 | 50863.3 | 0.615 |
| month of year | 11 | 14 | 52754.6 | -80799.4 | 177798 | 0.413 | 0.556 | 123348 | 32526.3 | 0.643 |
| month of year | 12 | 13 | 89460.5 | -7581.74 | 188984 | 0.072 | 0.167 | 156895 | 70781.6 | 0.692 |
| quarter | 1 | 39 | 111892 | 21076.3 | 195921 | 0.016 | 0.062 | 174710 | 93535.2 | 0.718 |
| quarter | 2 | 39 | 18744.8 | -52331.6 | 93634.9 | 0.644 | 0.718 | 82954.9 | 5393.07 | 0.615 |
| quarter | 3 | 40 | 39910 | -17376.2 | 95150.2 | 0.171 | 0.276 | 101200 | 26505 | 0.6 |
| quarter | 4 | 40 | 69629.1 | -552.541 | 135817 | 0.053 | 0.146 | 138705 | 50918.8 | 0.65 |
| calendar year | 2023 | 8 | 25579.7 | -95560 | 149449 | 0.709 | 0.748 | 82109 | 22075.4 | 0.5 |
| calendar year | 2024 | 52 | 66067.6 | -3612.11 | 138819 | 0.065 | 0.16 | 154501 | 48399.9 | 0.635 |
| calendar year | 2025 | 53 | 89702.6 | 35189.3 | 145558 | 0.004 | 0.023 | 140471 | 72895 | 0.736 |
| calendar year | 2026 | 45 | 24044.5 | -45745.4 | 88772.7 | 0.476 | 0.6 | 77982.4 | 8851.56 | 0.578 |
| half-year | 2023H2 | 8 | 25579.7 | -95281.8 | 148963 | 0.678 | 0.73 | 82109 | 22075.4 | 0.5 |
| half-year | 2024H1 | 26 | 54323.2 | -51960.7 | 165905 | 0.312 | 0.441 | 135252 | 38843.8 | 0.577 |
| half-year | 2024H2 | 26 | 77812 | -12452.4 | 165545 | 0.084 | 0.178 | 173750 | 57956 | 0.692 |
| half-year | 2025H1 | 26 | 81233.6 | -21318.9 | 179433 | 0.12 | 0.226 | 129126 | 75446 | 0.731 |
| half-year | 2025H2 | 27 | 97857.9 | 38373.3 | 156530 | 0.001 | 0.007 | 151396 | 70438.4 | 0.741 |
| half-year | 2026H1 | 26 | 60398.1 | -35730.2 | 145254 | 0.213 | 0.325 | 122119 | 34102.6 | 0.692 |
| half-year | 2026H2 | 19 | -25702.5 | -119115 | 63685.6 | 0.61 | 0.694 | 17585.5 | -25702.5 | 0.421 |
| week of month (D0) | 1 | 37 | 110132 | 29584.7 | 191177 | 0.008 | 0.036 | 176694 | 88202.6 | 0.757 |
| week of month (D0) | 2 | 38 | 56179 | -18238.4 | 127939 | 0.136 | 0.246 | 118361 | 46190.7 | 0.579 |
| week of month (D0) | 3 | 35 | -19065.4 | -110253 | 66936.1 | 0.68 | 0.73 | 38019.7 | -41237.4 | 0.571 |
| week of month (D0) | 4 | 36 | 96661 | 33447.8 | 157746 | 0.002 | 0.013 | 166586 | 81951.6 | 0.694 |
| week of month (D0) | 5 | 12 | 37849.1 | -50949.9 | 129544 | 0.392 | 0.541 | 106827 | 35788.9 | 0.583 |
| monthly-expiry week | monthly-expiry week | 42 | 65417.1 | 8744.08 | 121997 | 0.024 | 0.081 | 132227 | 53811.1 | 0.619 |
| monthly-expiry week | other week | 116 | 58007.5 | 11071.3 | 102648 | 0.008 | 0.036 | 121479 | 40474.9 | 0.655 |
| timetable regime | before June 2026 (timetable assumed) | 137 | 70913.3 | 30222.4 | 112615 | 0.001 | 0.007 | 138385 | 52510.1 | 0.672 |
| timetable regime | from June 2026 (observed) | 21 | -11368.3 | -99025.1 | 74392.2 | 0.828 | 0.828 | 32686 | -11368.3 | 0.476 |
| weekday of D0 (within week) | Friday | 27 | 153003 | 21662.7 | 287305 | 0.025 | 0.081 | 250200 | 126356 | 0.556 |
| weekday of D0 (within week) | Monday | 5 | -174451 | -348279 | 31599.7 | 0.082 | 0.178 | -120600 | -140322 | 0.2 |
| weekday of D0 (within week) | Thursday | 146 | 39828.1 | -7332.01 | 88556 | 0.104 | 0.208 | 102922 | 21197 | 0.568 |
| weekday of D0 (within week) | Tuesday | 86 | 68010.5 | 7896.55 | 122895 | 0.029 | 0.088 | 122138 | 59622.2 | 0.581 |
| weekday of D0 (within week) | Wednesday | 9 | 199129 | -71830.6 | 500901 | 0.146 | 0.249 | 265766 | 134585 | 0.778 |
| index (within week) | NIFTY | 154 | 45553.1 | 2414.42 | 87316.7 | 0.041 | 0.119 | 110164 | 36686.8 | 0.565 |
| index (within week) | SENSEX | 121 | 80820.5 | 16612 | 144935 | 0.01 | 0.041 | 143103 | 54017.9 | 0.578 |
| implied move at D-1 open (ex ante) | low | 53 | 57560.8 | 9331.11 | 107547 | 0.017 | 0.062 | 116074 | 40848.8 | 0.604 |
| implied move at D-1 open (ex ante) | mid | 52 | 101757 | 45835 | 161281 | 0 | 0.005 | 166464 | 82209.5 | 0.731 |
| implied move at D-1 open (ex ante) | high | 53 | 21402.4 | -54078.3 | 98199.4 | 0.57 | 0.661 | 91264.5 | 9722.14 | 0.604 |
| D-1 morning range (ex ante) | low | 53 | 95402.3 | 49389.1 | 142332 | 0 | 0.005 | 160592 | 77754.2 | 0.736 |
| D-1 morning range (ex ante) | mid | 52 | 55016.5 | -13268.9 | 125014 | 0.121 | 0.226 | 118643 | 39087.1 | 0.615 |
| D-1 morning range (ex ante) | high | 53 | 29419 | -44773.3 | 97507.1 | 0.422 | 0.556 | 93665.1 | 15125.5 | 0.585 |
| opening gap on D0 (known at the D0 open) | low | 53 | 130555 | 72770.1 | 190046 | 0 | 0.005 | 199520 | 114368 | 0.755 |
| opening gap on D0 (known at the D0 open) | mid | 52 | 77331.2 | 32777.4 | 121129 | 0 | 0.005 | 143426 | 61715.1 | 0.692 |
| opening gap on D0 (known at the D0 open) | high | 53 | -27627.8 | -103897 | 46241.4 | 0.472 | 0.6 | 30422.5 | -43689.4 | 0.491 |
| realised move (ex post) | low | 53 | 80359.2 | 36994.9 | 122977 | 0 | 0.005 | 141210 | 66197.1 | 0.736 |
| realised move (ex post) | mid | 52 | 18240.4 | -36232.6 | 71457.5 | 0.526 | 0.636 | 81438 | 10562.9 | 0.538 |
| realised move (ex post) | high | 53 | 80544.4 | -4663.14 | 163534 | 0.06 | 0.158 | 149551 | 54668.6 | 0.66 |
| realised / implied ratio (ex post) | low | 53 | 66516.4 | 17538.3 | 116919 | 0.008 | 0.036 | 127911 | 45869.1 | 0.679 |
| realised / implied ratio (ex post) | mid | 52 | 42680.7 | -12472.2 | 101983 | 0.146 | 0.249 | 108838 | 33280.7 | 0.615 |
| realised / implied ratio (ex post) | high | 53 | 70408 | -10033 | 145290 | 0.086 | 0.178 | 135967 | 52707.4 | 0.642 |

## 4. The opening-gap effect in detail

Tercile edges of the weekly mean opening gap: 0.176% and 0.313% of spot.

**By module (mean per week, ₹)**

| gap tercile | net | gross | D-1 book alone (net) | D0 module adds (net) | net, A/V1 band |
|---|---|---|---|---|---|
| low | 130555 | 199520 | 71779 | 58777 | 114368 |
| mid | 77331 | 143426 | 46465 | 30866 | 61715 |
| high | -27628 | 30422 | -40327 | 12699 | -43689 |

**By split (net, ₹)**

| split | low | mid | high | weeks (low/mid/high) |
|---|---|---|---|---|
| IS | 152198 | 75468 | -34418 | 38 / 36 / 32 |
| LIVE_FITTED | 135152 | -2310 | -104522 | 6 / 7 / 5 |
| OOS | 36111 | 146726 | 9982 | 9 / 9 / 16 |

**By index (cycle level, net at constant lot size, ₹)**

| und | low | mid | high |
|---|---|---|---|
| NIFTY | 91659 | 17239 | 8853 |
| SENSEX | 199042 | 106565 | -75423 |

## 5. How to find out for real (what would confirm any of this)

* **Write the rule down now, test it on cycles that do not exist yet.** For the gap: the candidate is "the D-1 carry loses when the next opening gap is large", which is a risk to size the overnight protection against, not a filter (the gap is unknown when D-1 trades). For February: "February weeks outperform", to be checked on February 2027 (4–5 weeks).
* **A forward test needs about as many cycles as the effect is small.** At the sd above, a month-specific effect needs ≈ 4 years; a gap effect (₹130k vs −₹28k, a far larger difference) is testable in 1–2 years of paper trading.
* **Collect what the sample lacks:** earlier years (the validated dataset starts in November 2023), ideally through 2020–2022 with the same one-minute option data, which would add independent repeats of every month and a different volatility regime.
* **If a rule is added, it is a new strategy** and goes through the pre-registered in-sample / out-of-sample procedure again; the cycles used here are no longer untouched.

## 6. Adversarial read

* **Multiple looks.** 14 families, 58 cells, and the OOS cycles were already seen. The correction (Holm over families, FDR over cells) controls false positives within this list, not the earlier looks; one supported family of 14 at Holm 0.028 is a hypothesis.
* **The weekly unit throws away information** but removes the dependence between NIFTY and SENSEX cycles of the same week; cycle-level families (index, weekday) use within-week permutations.
* **The timetable before June 2026 is assumed** (B/V2). A period effect in 2023–2025 could come from that assumption; the A/V1 band shows the same stationarity result (`altA_net` row).
* **Lot size.** Everything is restated at the 2026 lot sizes; costs are the earlier model's and partly fixed in rupees (brokerage), so older years with smaller lots carry relatively more cost.
* **Absence of evidence is not evidence of absence** (see Power).
