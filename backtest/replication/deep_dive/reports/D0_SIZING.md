# Algo 8 — D0 sizing in the free-run simulator: A (drawn), B (fixed median), C (scaled)

*Plan `D0_SIZING_PLAN.md` (pre-registered; the addendum lists the post-hoc changes, including a scale bug I fixed after the first run). In-sample discovery on D0 of 30 cycles; every fitted part is refit on each split's training cycles, as in `D0_FREE_RUN`. Figure: `figures/bl_d0v_summary.png`. Scripts `bl_d0v_sizing.py` → `bl_d0v_analysis.py` → `make_d0v_report.py`.*

## 0. Result

**None of the three sizing treatments reconstructs D0 better than the simulator as it was (M0).** Timing and triggers are identical in all of them; only lot counts change.

| | M0 reference | A draw | B fixed median |
|---|---|---|---|
| overall lot F1, OOF halves (30 cycles) | **0.410** | 0.368 (CI of change -0.061 to -0.025) | 0.382 (CI -0.066 to +0.007) |
| forward A (9) / forward B (10) | 0.452 / 0.390 | 0.448 / 0.366 | 0.494 / 0.359 |
| simulated ÷ real lots, body sells / buy-backs (OOF) | 1.06 / 1.09 | 0.97 / 1.01 | 0.58 / 0.68 |
| peak shorts per right, simulated ÷ real (median cycle) | 0.86 | 0.78 | 0.60 |
| cycle P&L, Spearman vs real (OOF, s = 1; null 0.50) | 0.81 | 0.81 | 0.84 |
| cycle P&L, sum simulated ÷ real (OOF) | 1.02 | 0.85 | 0.80 |
| stops found (real 11): both / real only / sim only (OOF) | 8 / 3 / 3 | 10 / 1 / 2 | 10 / 1 / 1 |

**Verdicts on the pre-registered hypotheses**

| hypothesis | verdict | evidence |
|---|---|---|
| H1 A raises overall lot F1 over M0 | **fails** | change in F1: OOF -0.042 (CI -0.061, -0.025), forward A -0.004, forward B -0.023; A is lower on all three |
| H2 A or B raises P&L fidelity (Spearman) over M0 | **fails** | all six CIs include 0 (e.g. OOF A -0.003 [-0.17, +0.18], B +0.030 [-0.14, +0.19]) |
| H3 A is not better than B | **holds** | A − B in F1: OOF -0.014 [-0.038, +0.010], forward A -0.046 [-0.079, -0.019], forward B +0.007 [-0.049, +0.098]; drawing the count adds noise, not information |
| H4 P&L scales with s (median P&L(s) ÷ (s × P&L(1)) within 0.8–1.2 at s = 0.1) | **fails** | M0 0.66, A 0.89, B 0.78. Lots and peak scale linearly (below); the P&L of a 0.1 account is dominated by rounding noise |

## 1. What each treatment does to the book (OOF, s = 1)

| treatment | cls | real | sim | matched | F1 | precision | recall |
|---|---|---|---|---|---|---|---|
| M0 reference | body_sell | 8336 | 8865 | 4252 | 0.494 | 0.48 | 0.51 |
| M0 reference | body_buyback | 9656 | 10498 | 3712 | 0.368 | 0.354 | 0.384 |
| M0 reference | wing_buy | 7312 | 6884 | 3237 | 0.456 | 0.47 | 0.443 |
| M0 reference | wing_sell | 8973 | 9721 | 3470 | 0.371 | 0.357 | 0.387 |
| M0 reference | body_long | 3082 | 760 | 469 | 0.244 | 0.617 | 0.152 |
| M0 reference | stop | 3515 | 3296 | 1456 | 0.428 | 0.442 | 0.414 |
| A draw | body_sell | 8336 | 8097.9 | 3837.4 | 0.467 | 0.474 | 0.46 |
| A draw | body_buyback | 9656 | 9711.7 | 3071.2 | 0.317 | 0.316 | 0.318 |
| A draw | wing_buy | 7312 | 6233.9 | 2852 | 0.421 | 0.458 | 0.39 |
| A draw | wing_sell | 8973 | 9129.4 | 2841.3 | 0.314 | 0.311 | 0.317 |
| A draw | body_long | 3082 | 779.1 | 486.7 | 0.252 | 0.625 | 0.158 |
| A draw | stop | 3515 | 3235.8 | 1272.6 | 0.377 | 0.393 | 0.362 |
| B fixed median | body_sell | 8336 | 4799 | 3289 | 0.501 | 0.685 | 0.395 |
| B fixed median | body_buyback | 9656 | 6561 | 2824 | 0.348 | 0.43 | 0.292 |
| B fixed median | wing_buy | 7312 | 3139 | 2177 | 0.417 | 0.694 | 0.298 |
| B fixed median | wing_sell | 8973 | 6196 | 2511 | 0.331 | 0.405 | 0.28 |
| B fixed median | body_long | 3082 | 766 | 508 | 0.264 | 0.663 | 0.165 |
| B fixed median | stop | 3515 | 2939 | 1146 | 0.355 | 0.39 | 0.326 |

* **B undersizes**: with 1 lot per solo event and 2 per buy-back it trades about 58% of the real sell lots and holds a peak of about 60% of the real book. Its precision is higher (fewer wrong lots) and its recall lower; the hedge follows the smaller book.
* **A calibrates the totals** (sell lots 0.97×, buy-back lots 1.01× the real) but puts the lots in the wrong cells more often than M0, so F1 falls. Repetition spread of F1 is 0.008 (OOF) to 0.033 (forward B).
* **M0** over-sells slightly (1.06×) and over-buys-back (1.09×): every lot that crosses the stop level is bought back, where the real system takes fewer (`D0_QTY.md` B3).

## 2. Lot F1 by treatment and split

| split | treatment | reps | F1 | F1_rep_sd | sim_lots | real_lots | F1_body_sell | F1_body_buyback | F1_wing_buy | F1_wing_sell | F1_stop | dF1_vs_M0 | dF1_lo | dF1_hi |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| OOF (cycle halves) | M0 reference | 1 | 0.41 | 0 | 40024 | 40874 | 0.494 | 0.368 | 0.456 | 0.371 | 0.428 |  |  |  |
| OOF (cycle halves) | A draw | 10 | 0.368 | 0.008 | 37187.8 | 40874 | 0.467 | 0.317 | 0.421 | 0.314 | 0.377 | -0.042 | -0.061 | -0.025 |
| OOF (cycle halves) | B fixed median | 1 | 0.382 | 0 | 24400 | 40874 | 0.501 | 0.348 | 0.417 | 0.331 | 0.355 | -0.029 | -0.066 | 0.008 |
| OOF (cycle halves) | A draw, oldest-first | 5 | 0.38 | 0.013 | 37478.4 | 40874 | 0.473 | 0.329 | 0.428 | 0.32 | 0.446 |  |  |  |
| OOF (cycle halves) | B fixed, oldest-first | 1 | 0.391 | 0 | 24652 | 40874 | 0.502 | 0.368 | 0.422 | 0.343 | 0.358 |  |  |  |
| forward A (same version, later cycles) | M0 reference | 1 | 0.452 | 0 | 9091 | 10106 | 0.533 | 0.408 | 0.492 | 0.379 | 0.605 |  |  |  |
| forward A (same version, later cycles) | A draw | 10 | 0.448 | 0.03 | 9148 | 10106 | 0.516 | 0.377 | 0.466 | 0.332 | 0.732 | -0.004 | -0.056 | 0.068 |
| forward A (same version, later cycles) | B fixed median | 1 | 0.494 | 0 | 6401 | 10106 | 0.565 | 0.415 | 0.485 | 0.384 | 0.801 | 0.042 | -0.035 | 0.148 |
| forward A (same version, later cycles) | A draw, oldest-first | 5 | 0.459 | 0.012 | 8551 | 10106 | 0.511 | 0.394 | 0.467 | 0.331 | 0.764 |  |  |  |
| forward A (same version, later cycles) | B fixed, oldest-first | 1 | 0.492 | 0 | 6407 | 10106 | 0.576 | 0.409 | 0.477 | 0.379 | 0.801 |  |  |  |
| forward B (train V1, test V2) | M0 reference | 1 | 0.39 | 0 | 13312 | 10947 | 0.413 | 0.399 | 0.402 | 0.33 | 0.515 |  |  |  |
| forward B (train V1, test V2) | A draw | 10 | 0.366 | 0.033 | 10707.6 | 10947 | 0.407 | 0.315 | 0.385 | 0.287 | 0.551 | -0.023 | -0.052 | 0.006 |
| forward B (train V1, test V2) | B fixed median | 1 | 0.36 | 0 | 6918 | 10947 | 0.425 | 0.374 | 0.37 | 0.328 | 0.338 | -0.03 | -0.113 | 0.03 |
| forward B (train V1, test V2) | A draw, oldest-first | 5 | 0.358 | 0.028 | 10469.2 | 10947 | 0.398 | 0.323 | 0.373 | 0.301 | 0.474 |  |  |  |
| forward B (train V1, test V2) | B fixed, oldest-first | 1 | 0.447 | 0 | 6214 | 10947 | 0.45 | 0.402 | 0.406 | 0.356 | 0.734 |  |  |  |

*Oldest-first lot selection (the plan's sensitivity) changes F1 by +0.012 (A, OOF), +0.009 (B, OOF) and by more in the 9–10-cycle forward splits (B, forward B: +0.087). The choice of which lots a buy-back takes matters and is not recovered.*

## 3. Cycle profit and loss (before costs)

| split | treatment | cycles | spearman | median_err_lakh | sum_ratio | same_sign | sim_sum_lakh | real_sum_lakh | sim_median_lakh | real_median_lakh |
|---|---|---|---|---|---|---|---|---|---|---|
| OOF (cycle halves) | M0 reference | 30 | 0.81 | 0.017 | 1.017 | 0.867 | 15.776 | 15.508 | 0.328 | -0.075 |
| OOF (cycle halves) | A draw | 30 | 0.808 | 0.067 | 0.853 | 0.833 | 13.233 | 15.508 | 0.372 | -0.075 |
| OOF (cycle halves) | B fixed median | 30 | 0.84 | 0.014 | 0.799 | 0.833 | 12.396 | 15.508 | 0.466 | -0.075 |
| OOF (cycle halves) | A draw, oldest-first | 30 | 0.834 | 0.026 | 0.799 | 0.933 | 12.388 | 15.508 | 0.407 | -0.075 |
| OOF (cycle halves) | B fixed, oldest-first | 30 | 0.855 | 0.012 | 0.708 | 0.833 | 10.979 | 15.508 | 0.321 | -0.075 |
| forward A (same version, later cycles) | M0 reference | 9 | 0.95 | -0.2 | 0.508 | 0.889 | 2.107 | 4.144 | -1.238 | -0.17 |
| forward A (same version, later cycles) | A draw | 9 | 0.967 | 0.069 | 1.209 | 0.778 | 5.008 | 4.144 | 1.686 | -0.17 |
| forward A (same version, later cycles) | B fixed median | 9 | 0.983 | 0.176 | 1.403 | 0.778 | 5.812 | 4.144 | 1.34 | -0.17 |
| forward A (same version, later cycles) | A draw, oldest-first | 9 | 0.9 | -0.102 | 0.608 | 0.889 | 2.518 | 4.144 | -1.29 | -0.17 |
| forward A (same version, later cycles) | B fixed, oldest-first | 9 | 0.95 | 0.085 | 1.24 | 0.778 | 5.138 | 4.144 | 1.132 | -0.17 |
| forward B (train V1, test V2) | M0 reference | 10 | 0.782 | 0.116 | 22.796 | 0.8 | 8.358 | 0.367 | 0.093 | -0.882 |
| forward B (train V1, test V2) | A draw | 10 | 0.915 | -0.032 | -1.191 | 0.7 | -0.437 | 0.367 | 0.074 | -0.882 |
| forward B (train V1, test V2) | B fixed median | 10 | 0.758 | -0.014 | -2.527 | 0.8 | -0.927 | 0.367 | -0.447 | -0.882 |
| forward B (train V1, test V2) | A draw, oldest-first | 10 | 0.806 | -0.059 | 1.285 | 0.9 | 0.471 | 0.367 | -1.061 | -0.882 |
| forward B (train V1, test V2) | B fixed, oldest-first | 10 | 0.83 | 0.147 | -1.143 | 0.8 | -0.419 | 0.367 | -0.203 | -0.882 |

* **Null comparator (post-hoc):** holding the carried book to 15:14 and trading nothing gives Spearman **0.50** with the real P&L and sums to 2.1 lakh against the real 15.5. The simulator's 0.81–0.84 is therefore real information beyond the market and the carried book, but about half of the ranking is not.
* **The real P&L is small against its own noise.** Over the 30 cycles: sum ₹15.5 lakh, mean ₹0.52 lakh per cycle, spread (sd) ₹2.0 lakh, t ≈ 1.4; median cycle ₹-0.08 lakh. **Before brokerage, taxes and the fill position inside the bar** (sells fill in the lower part of the bar, buys in the upper). Against ~₹20 crore of notional per right this is a thin edge, not a measured one.
* **A sum ratio near 1 is not accuracy.** The sums are small differences of large flows, so M0's 1.02 in OOF is within the noise of the per-cycle spread; forward A (sums 2.1 vs 4.1 lakh) and forward B (8.4 vs 0.4 lakh) show the level error. Spearman and the per-cycle median error are the fair readings.
* Simulated P&L uses the simulator's own prices (previous-minute close for sells, minute prices otherwise), which are better than the real fills by construction.

## 4. C: scale s (OOF cycles, lot-identity thinning)

| treatment | s | median_ratio_to_s_x_P1 | sum_ratio | between_rep_sd_lakh | noise_per_real_size_lakh | peak_ratio |
|---|---|---|---|---|---|---|
| M0 reference | 1 | 1 | 1 | 0 | 0 | 0.864 |
| M0 reference | 0.5 | 0.962 | 1.176 | 0.266 | 0.532 | 0.872 |
| M0 reference | 0.25 | 0.866 | 0.998 | 0.286 | 1.145 | 0.868 |
| M0 reference | 0.1 | 0.661 | 1.105 | 0.173 | 1.729 | 0.898 |
| A draw | 1 | 1 | 1 | 0.5 | 0.5 | 0.775 |
| A draw | 0.5 | 0.943 | 1.089 | 0.424 | 0.848 | 0.794 |
| A draw | 0.25 | 0.929 | 1.055 | 0.324 | 1.298 | 0.796 |
| A draw | 0.1 | 0.887 | 1.042 | 0.191 | 1.912 | 0.757 |
| B fixed median | 1 | 1 | 1 | 0 | 0 | 0.601 |
| B fixed median | 0.5 | 0.989 | 1.285 | 0.257 | 0.515 | 0.613 |
| B fixed median | 0.25 | 0.968 | 1.254 | 0.24 | 0.96 | 0.621 |
| B fixed median | 0.1 | 0.782 | 1.307 | 0.162 | 1.625 | 0.584 |

| treatment | s | spearman | median_err_lakh | sum_ratio | same_sign |
|---|---|---|---|---|---|
| M0 reference | 1 | 0.81 | 0.017 | 1.017 | 0.867 |
| M0 reference | 0.5 | 0.814 | 0.016 | 1.196 | 0.833 |
| M0 reference | 0.25 | 0.765 | 0.009 | 1.015 | 0.833 |
| M0 reference | 0.1 | 0.669 | 0.004 | 1.124 | 0.8 |
| A draw | 1 | 0.808 | 0.067 | 0.853 | 0.833 |
| A draw | 0.5 | 0.773 | 0.088 | 0.929 | 0.767 |
| A draw | 0.25 | 0.682 | -0.012 | 0.9 | 0.767 |
| A draw | 0.1 | 0.616 | 0.016 | 0.889 | 0.767 |
| B fixed median | 1 | 0.84 | 0.014 | 0.799 | 0.833 |
| B fixed median | 0.5 | 0.78 | 0.05 | 1.027 | 0.8 |
| B fixed median | 0.25 | 0.74 | 0.009 | 1.002 | 0.8 |
| B fixed median | 0.1 | 0.622 | 0.031 | 1.044 | 0.767 |
| A draw, oldest-first | 1 | 0.834 | 0.026 | 0.799 | 0.933 |
| B fixed, oldest-first | 1 | 0.855 | 0.012 | 0.708 | 0.833 |

| treatment | s | peak_ratio_median | peak_spearman | lots_ratio_body_sell | lots_ratio_body_buyback | lots_ratio_wing_buy | lots_ratio_wing_sell | lots_ratio_stop |
|---|---|---|---|---|---|---|---|---|
| M0 reference | 1 |  | 0.5 | 1.064 | 1.087 | 0.942 | 1.083 | 0.938 |
| M0 reference | 0.5 | 0.923 | 0.505 | 1.089 | 1.115 | 0.99 | 1.143 | 0.871 |
| M0 reference | 0.25 | 0.904 | 0.478 | 0.999 | 1.02 | 0.931 | 1.071 | 0.992 |
| M0 reference | 0.1 | 0.94 | 0.412 | 0.961 | 0.986 | 0.948 | 1.085 | 0.977 |
| A draw | 1 |  | 0.593 | 0.971 | 1.006 | 0.853 | 1.017 | 0.921 |
| A draw | 0.5 | 0.934 | 0.604 | 0.983 | 1.011 | 0.906 | 1.068 | 0.919 |
| A draw | 0.25 | 0.874 | 0.552 | 0.948 | 0.984 | 0.917 | 1.068 | 0.93 |
| A draw | 0.1 | 0.848 | 0.519 | 0.91 | 0.924 | 0.936 | 1.061 | 1.063 |
| B fixed median | 1 |  | 0.562 | 0.576 | 0.68 | 0.429 | 0.69 | 0.836 |
| B fixed median | 0.5 | 0.806 | 0.565 | 0.616 | 0.737 | 0.52 | 0.792 | 0.681 |
| B fixed median | 0.25 | 0.782 | 0.557 | 0.574 | 0.696 | 0.546 | 0.799 | 0.743 |
| B fixed median | 0.1 | 0.749 | 0.523 | 0.573 | 0.679 | 0.599 | 0.826 | 0.81 |
| A draw, oldest-first | 1 |  | 0.608 | 0.973 | 1.018 | 0.871 | 1.048 | 0.858 |
| B fixed, oldest-first | 1 |  | 0.594 | 0.585 | 0.69 | 0.436 | 0.698 | 0.822 |

* **Linear in lots, noisy in P&L.** Lots per class and the peak book stay within about 0.9–1.1 of s × real for M0 at every s. P&L ranking falls from 0.81 (s = 1) to 0.77 (0.25) and 0.67 (0.1) for M0, and to 0.62 / 0.62 for A / B, against the null 0.50.
* **Lot-rounding noise per cycle, in real-size ₹ lakh:** M0 0.5 (s = 0.5) → 1.1 (0.25) → 1.7 (0.1), against a real cycle P&L spread of 2.0. At s = 0.1 an account's result for one cycle is nearly as much rounding as strategy. The ranking stays above the null at every s (0.67–0.81 for M0), but with 30 cycles the margin over the null at s = 0.1 is inside the noise of a Spearman.
* The stop level was scaled with s (the stop stays the same share of the book); stops found at s = 0.1: M0 reference 7/11, A draw 8/11, B fixed median 6/11 (s = 1: 8/11, 10/11, 10/11).

## 5. What to use for the backtest

| use | choice | why |
|---|---|---|
| **point backtest** | **M0 at the real scale**, i.e. the simulator's own rules | highest lot F1 (OOF 0.410, forward 0.452 / 0.390); no treatment beat it; lot totals within 1.06× / 1.09× |
| **sizing-uncertainty band** | **A**, 10+ draws per cycle | right total lots (0.97× / 1.01×); between-draw P&L sd ≈ 0.50 lakh per cycle shows how much unknown sizing moves a cycle |
| **low-size bound** | **B** | about 58% of real sell lots; useful only as "what if it trades less", not as a reconstruction |
| **your capital** | s from your capital; **s ≥ 0.25 is usable, s = 0.1 is within noise of the null** | P&L ranking 0.77 / 0.68 / 0.74 at s = 0.25 and 0.67 / 0.62 / 0.62 at 0.1 (M0 / A / B) against a null of 0.50; with 30 cycles a Spearman has a standard error of about 0.15–0.18, so 0.1 cannot be told from the null. The real system's ~₹20 crore per right makes s = 0.1 about ₹2 crore per right |

A better lot match would need the tick path (what sets the count inside a minute); until then M0 is the simulator to use, and A is the honest error bar on it.

## 6. Adversarial read

* **These are sizing assumptions inside a simulator.** A result better than M0 would not have shown that the real system sizes that way; the result being worse is a weaker statement than it sounds, because M0's timing is shared by all three and a wrong count in a right minute is penalised the same as a wrong minute.
* **Which lots a buy-back takes is my assumption** (most-adverse first); oldest-first moves F1 by up to +0.09 in a 10-cycle split. Not recovered from the data.
* **Forward splits are 9 and 10 cycles.** Their P&L and F1 differences have wide CIs; only the OOF (30 cycles) comparisons carry weight, and even there H2 is not rejected in either direction.
* **The P&L is cash before costs on 30 cycles with a sd about four times its mean.** It cannot say whether the real system makes money, only whether the simulator tracks the sign and rank of what it did.
* **Everything is in-sample discovery on these 32 cycles.** None of it has been run on cycles outside them, and no result here is a statement about a 3-year history.
* **Not testable:** the real system's capital or margin, fills inside the bar, costs, the tick path.

## Addendum (post-hoc, also in `D0_SIZING_PLAN.md`)
* First scale run discarded: counts were scaled twice (about s²). Replaced by lot-identity thinning; integrity check (M0, s = 1 identical to the stored free-run, 49/49 cycles, lots by class/right/minute/strike) passes with both versions of the code.
* Null comparator and real-P&L context added after seeing a Spearman of 0.81.
