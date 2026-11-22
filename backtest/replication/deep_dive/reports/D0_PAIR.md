# Algo 8 — D0: what else decides the counter-sale, and what triggers the buy-back

*Plan `D0_PAIR_PLAN.md` (addendum at the end lists what changed after the first run, including a leak I fixed). In-sample discovery on D0, 24 cycles with minutes after the opening window. Figure: `figures/bl_d0p_summary.png`. Scripts `bl_d0p_*.py`.*

## 0. Result
**1. The 2 s / 5 s / 10 s / 60 s gaps are not separate stages. They are the waiting time for the next sale after a stop-loss, and I found no extra condition that decides it.**
**2. The buy-back is not fired by the lot crossing 1.4× its entry. It fires when the stopped option's premium is breaking to a new high, the spot has been moving against it, and the same side was bought back a minute or two earlier. That is the mirror image of the sale trigger (premium at a new low).** I could not recover an exact rule.

| Question | Answer | Label |
|---|---|---|
| **Are the four windows real steps?** | No. They are my cumulative cut-offs. Real share minus chance: 26% at 2 s, 37% at 5 s, 45% at 10 s, 55% at 60 s. The chance level itself climbs (2.8% → 28%). | Observed |
| **Shape of the delay** | The chance per second that the first sale arrives falls steadily: 0.118 in the first second, 0.022 at 5–10 s, 0.0064 at 30–60 s, 0.0008 at 5–15 min. No plateaus. | Observed |
| **Does the sale always come?** | Almost. Of the 554 events with no sale within 60 s, 95% get one later (median wait 4.1 min, 52% within 5 min). | Observed |
| **Another condition that must hold?** | **None found.** Best out-of-fold AUC for "sale within 10 s" is 0.64 (CI 0.60–0.68; placebo 0.58). No factor passes the gate test. Adding the minute's own bar lifts it to 0.70 (and 0.68 → 0.80 for 60 s). The rest is the price path inside the minute. | Observed; rest Not testable |
| **Is the 1.4× crossing the buy-back trigger?** | No. Of lots that crossed 1.4× at some point, only 10% were bought back in the same minute, 8% in the next, and 17% not before the clearance/stop or never. For stop-loss lots the median gap between first crossing and buy-back is 5 minutes (30% within 1 min, 29% over 15). 43% of all right-minutes already have some lot above 1.4×, and only 16% of those minutes see a buy-back. | Observed |
| **What does pick the minute?** | In minutes where a lot is ≥1.4×, adding spot (+0.07 AUC), premium of the stopped right (+0.08) and recent buy-backs on that side (+0.08) each clear my bar; side loss (+0.02) does not. The top single feature is "premium makes a new 60-minute high in the minute". | Observed |
| **Mirror image** | Sale: close of the previous minute at a new low → sale in 34% of minutes at a 15-minute window (46% at 60), against 10% otherwise. Buy-back: close at a new high (lots ≥1.4×) → 40% (56% at 60), against 11%. Both curves have the same shape and no sharp window. | Observed |
| **Exact buy-back rule** | **Not recovered.** Best tree: precision 44% (against 16% for crossing alone, 2.7×) but recall 32%, F1 0.37, bar 0.50. | Unresolved |
| **How it ties together** | When spot moves, one option's premium goes to a new high (buy-back) and the other's to a new low (sale) in the same seconds. That would give the same-second pairs without either action triggering the other. | Inferred |

## 1. Part A — the timing of the sale
**A0 — real vs chance** (all stop-loss events; chance = buy-back times shifted ±15 minutes):

| window_s | share_events_real | share_events_null | excess | ratio |
|---|---|---|---|---|
| 2 | 0.289 | 0.028 | 0.261 | 10.415 |
| 5 | 0.419 | 0.053 | 0.366 | 7.885 |
| 10 | 0.536 | 0.089 | 0.447 | 6.015 |
| 60 | 0.832 | 0.282 | 0.550 | 2.947 |

**A5 — arrival rate of the first sale at or after the buy-back** (events at risk = no sale yet; 1434 events in the panel):

| lag | at_risk | first_sales | hazard_per_second | share_of_at_risk |
|---|---|---|---|---|
| 0-1 s | 1434 | 169 | 0.118 | 0.118 |
| 1-2 s | 1265 | 72 | 0.057 | 0.057 |
| 2-5 s | 1193 | 113 | 0.032 | 0.095 |
| 5-10 s | 1080 | 118 | 0.022 | 0.109 |
| 10-20 s | 962 | 161 | 0.017 | 0.167 |
| 20-30 s | 801 | 112 | 0.014 | 0.140 |
| 30-60 s | 689 | 133 | 0.006 | 0.193 |
| 60-120 s | 556 | 120 | 0.004 | 0.216 |
| 120-300 s | 436 | 170 | 0.002 | 0.390 |
| 300-900 s | 266 | 133 | 0.001 | 0.500 |

The decay is smooth. A mix of event types can produce the same curve, so this does not prove one process.

**A2 — can the factors predict the sale?** Outcome = a solo sale of the other right **at or after** the buy-back second (see the addendum for why not before). LOCO AUC:

| model | auc | lo | hi | positive_rate |
|---|---|---|---|---|
| all factors | 0.643 | 0.598 | 0.681 | 0.342 |
| placebo (features shuffled within cycle) | 0.580 | 0.507 | 0.629 | 0.342 |
| only F1_premium_low | 0.562 | 0.511 | 0.617 | 0.342 |
| all minus F1_premium_low | 0.631 | 0.597 | 0.668 | 0.342 |
| only F2_ladder_step | 0.582 | 0.547 | 0.614 | 0.342 |
| all minus F2_ladder_step | 0.647 | 0.597 | 0.685 | 0.342 |
| only F3_recent_sales | 0.582 | 0.546 | 0.621 | 0.342 |
| all minus F3_recent_sales | 0.611 | 0.562 | 0.656 | 0.342 |
| only F4_lots | 0.543 | 0.489 | 0.587 | 0.342 |
| all minus F4_lots | 0.618 | 0.580 | 0.653 | 0.342 |
| only F5_size | 0.405 | 0.373 | 0.446 | 0.342 |
| all minus F5_size | 0.642 | 0.602 | 0.675 | 0.342 |
| only F6_spot | 0.558 | 0.524 | 0.595 | 0.342 |
| all minus F6_spot | 0.636 | 0.592 | 0.669 | 0.342 |
| only F7_clock | 0.534 | 0.481 | 0.595 | 0.342 |
| all minus F7_clock | 0.634 | 0.587 | 0.673 | 0.342 |
| only F8_cycle | 0.582 | 0.510 | 0.644 | 0.342 |
| all minus F8_cycle | 0.613 | 0.563 | 0.654 | 0.342 |

Largest permutation-importance drops (outcome ≤10 s):

| feature | drop_in_auc | family |
|---|---|---|
| secs_since_solo_R_sale | 0.028 | F3_recent_sales |
| min_in_15 | 0.016 | F7_clock |
| fav_ret_1 | 0.016 | F6_spot |
| share_own | 0.013 | F4_lots |
| prem_vs_daymin | 0.011 | F1_premium_low |
| n_own | 0.010 | F4_lots |
| prem_chg_3 | 0.005 | F1_premium_low |
| sell_own_5 | 0.005 | F3_recent_sales |

Rates for the main candidate conditions: at a 60-minute premium low 36% (sale within 10 s) against 30% when not; a solo sale on the same right in the previous 60 s 39% against 23%. The "ladder step" (price now ÷ price at the last sale of the same contract) shows only mild gradients:

| ratio | n | sale_2 | sale_10 | sale_60 |
|---|---|---|---|---|
| (0.0, 0.7] | 75.000 | 0.080 | 0.173 | 0.360 |
| (0.7, 0.8] | 53.000 | 0.113 | 0.170 | 0.377 |
| (0.8, 0.9] | 63.000 | 0.143 | 0.254 | 0.381 |
| (0.9, 1.0] | 386.000 | 0.181 | 0.272 | 0.619 |
| (1.0, 1.1] | 600.000 | 0.228 | 0.382 | 0.657 |
| (1.1, 5.0] | 256.000 | 0.234 | 0.461 | 0.688 |

**A3 — gate test.** A factor is a gate only if the sale follows within 10 s at least 60% of the time when it is on and at most 20% when off. The stumps fitted on training cycles never switched on at a level that meets this (no gate accepted):

| rule | share_events_on | p_sale_10s_on | p_sale_10s_off | p_sale_2s_on | p_sale_2s_off | p_sale_60s_on | p_sale_60s_off | gate_accepted |
|---|---|---|---|---|---|---|---|---|
| stump on secs_since_solo_R_sale | 0.000 | — | 0.342 | — | 0.201 | — | 0.614 | False |
| stump on min_in_15 | 0.000 | — | 0.342 | — | 0.201 | — | 0.614 | False |
| depth-2 tree on secs_since_solo_R_sale + min_in_15 | 0.000 | — | 0.342 | — | 0.201 | — | 0.614 | False |

**With the minute's own bar** (post-hoc, diagnostic):

| outcome | model | auc | lo | hi |
|---|---|---|---|---|
| sale_2 | decision-time factors | 0.609 | 0.540 | 0.666 |
| sale_2 | minute-j bar only | 0.617 | 0.560 | 0.670 |
| sale_2 | decision-time + minute-j bar | 0.668 | 0.616 | 0.737 |
| sale_10 | decision-time factors | 0.643 | 0.603 | 0.675 |
| sale_10 | minute-j bar only | 0.654 | 0.608 | 0.691 |
| sale_10 | decision-time + minute-j bar | 0.703 | 0.664 | 0.736 |
| sale_60 | decision-time factors | 0.681 | 0.641 | 0.724 |
| sale_60 | minute-j bar only | 0.723 | 0.682 | 0.763 |
| sale_60 | decision-time + minute-j bar | 0.795 | 0.762 | 0.828 |


## 2. Part B — what triggers the buy-back
**B1 — what happens after a lot first crosses θ× its entry** (high of its contract):

| theta | group | lots_that_crossed | bought_before_crossing | lag0 | lag1 | lag2_5 | lag6_15 | later_in_scope | clearance_stop_or_never |
|---|---|---|---|---|---|---|---|---|---|
| 1.200 | all lots | 6937 | 0.088 | 0.068 | 0.056 | 0.092 | 0.105 | 0.354 | 0.237 |
| 1.200 | carried from D-1 | 1153 | 0.070 | 0.152 | 0.065 | 0.042 | 0.081 | 0.177 | 0.413 |
| 1.200 | entered on D0 | 5784 | 0.092 | 0.051 | 0.054 | 0.102 | 0.110 | 0.389 | 0.202 |
| 1.400 | all lots | 5462 | 0.193 | 0.100 | 0.083 | 0.116 | 0.108 | 0.229 | 0.171 |
| 1.400 | carried from D-1 | 967 | 0.165 | 0.150 | 0.077 | 0.048 | 0.066 | 0.141 | 0.354 |
| 1.400 | entered on D0 | 4495 | 0.199 | 0.089 | 0.084 | 0.130 | 0.117 | 0.248 | 0.132 |
| 1.600 | all lots | 4343 | 0.339 | 0.142 | 0.128 | 0.085 | 0.061 | 0.118 | 0.128 |
| 1.600 | carried from D-1 | 734 | 0.270 | 0.142 | 0.068 | 0.040 | 0.031 | 0.082 | 0.368 |
| 1.600 | entered on D0 | 3609 | 0.353 | 0.142 | 0.140 | 0.094 | 0.067 | 0.125 | 0.079 |

**B4 — stop-loss lots, minutes from first crossing of 1.4× to the buy-back:** 2,541 lots, median 5, same minute 15%, within 5 minutes 52%, over 15 minutes 29%.

**B2 — which reference price, exact-cell F1 (out-of-fold, threshold on the training cycles).** Cell outcome `y_bb` = any in-scope body buy-back on the right in the minute; `y_loss` = one with a decision ratio ≥1.2. Flag-everything floor and a ±15-minute shifted version are shown:

| outcome | rule | theta_median | precision | recall | F1 | shifted_15min_F1 | flag_all_F1 | base_rate | flagged |
|---|---|---|---|---|---|---|---|---|---|
| y_bb | own entry, bar j | 1.600 | 0.178 | 0.410 | 0.248 | 0.182 | 0.231 | 0.130 | 4435 |
| y_bb | own entry, bar j-1 | 1.500 | 0.159 | 0.461 | 0.236 | 0.195 | 0.231 | 0.130 | 5587 |
| y_bb | strike-average entry, bar j | 1.200 | 0.153 | 0.523 | 0.237 | 0.214 | 0.231 | 0.130 | 6580 |
| y_bb | strike-average entry, bar j-1 | 1.100 | 0.143 | 0.609 | 0.232 | 0.219 | 0.231 | 0.130 | 8171 |
| y_bb | side mark ratio (highs), bar j | 1.100 | 0.139 | 0.174 | 0.155 | 0.135 | 0.231 | 0.130 | 2395 |
| y_bb | side mark ratio (close), bar j-1 | 1.100 | 0.134 | 0.147 | 0.140 | 0.127 | 0.231 | 0.130 | 2098 |
| y_loss | own entry, bar j | 1.600 | 0.153 | 0.681 | 0.250 | 0.130 | 0.108 | 0.057 | 3760 |
| y_loss | own entry, bar j-1 | 1.600 | 0.135 | 0.595 | 0.220 | 0.129 | 0.108 | 0.057 | 3735 |
| y_loss | strike-average entry, bar j | 1.500 | 0.124 | 0.488 | 0.197 | 0.126 | 0.108 | 0.057 | 3341 |
| y_loss | strike-average entry, bar j-1 | 1.300 | 0.107 | 0.651 | 0.183 | 0.132 | 0.108 | 0.057 | 5171 |
| y_loss | side mark ratio (highs), bar j | 1.300 | 0.167 | 0.209 | 0.185 | 0.102 | 0.108 | 0.057 | 1063 |
| y_loss | side mark ratio (close), bar j-1 | 1.300 | 0.151 | 0.164 | 0.157 | 0.096 | 0.108 | 0.057 | 923 |

The per-lot rule on bar j beats its shifted version for `y_loss` (0.25 vs 0.13) but with precision 15%. For all buy-backs (`y_bb`) no rule beats the flag-everything floor (0.23). Strike-average and side-level references do not do better than the lot's own entry.

**B3 — the main test:** only minutes where some lot is ≥1.4× entry (6,315 cells, positive rate 16.5%):

| model | features | cells | positive_rate | auc | lo | hi | prauc | gain_over_G0_G1 |
|---|---|---|---|---|---|---|---|---|
| G0 baseline | 6 | 6315 | 0.165 | 0.611 | 0.570 | 0.650 | 0.292 | -0.120 |
| G0+G1 lot state | 14 | 6315 | 0.165 | 0.732 | 0.694 | 0.777 | 0.416 | 0.000 |
| +G2 spot against the right | 23 | 6315 | 0.165 | 0.805 | 0.747 | 0.856 | 0.533 | 0.073 |
| +G3 premium of the right | 18 | 6315 | 0.165 | 0.814 | 0.757 | 0.864 | 0.585 | 0.083 |
| +G4 side loss | 21 | 6315 | 0.165 | 0.756 | 0.712 | 0.796 | 0.439 | 0.024 |
| +G5 book | 20 | 6315 | 0.165 | 0.817 | 0.798 | 0.832 | 0.514 | 0.085 |
| +G6 other right | 17 | 6315 | 0.165 | 0.800 | 0.766 | 0.833 | 0.495 | 0.068 |
| all families | 43 | 6315 | 0.165 | 0.869 | 0.840 | 0.892 | 0.631 | 0.137 |
| placebo (all families, shuffled within cycle) | 43 | 6315 | 0.165 | 0.531 | 0.495 | 0.564 | 0.188 | — |

* Families that clear my bar (+0.03 over G0+G1 and CI lower bound above 0.55): **+G2 spot against the right, +G3 premium of the right, +G5 book, +G6 other right**.
* Ablation (all families minus one): G1 0.870, G2 0.861, G3 0.857, G4 0.866, G5 0.848, G6 0.866 against all 0.869. Each family is partly redundant with the others.
* Forward check (first 16 cycles → last 8): G0 0.57, G0+G1 0.72, +G2 0.80, +G3 0.82, +G4 0.72, +G5 0.79, +G6 0.79, all 0.86.

Top permutation importances:

| feature | drop_in_auc | family |
|---|---|---|
| prem_high60_c | 0.034 | G3 |
| hour | 0.021 | G0 |
| adv_move_60 | 0.019 | G2 |
| bb_own_5 | 0.018 | G5 |
| min_in_15 | 0.012 | G0 |
| prem_chg_1_cp | 0.011 | G3 |
| min_in_5 | 0.009 | G0 |
| adv_move_1_c | 0.008 | G2 |
| bb_own_1 | 0.007 | G5 |
| age_cross_mean | 0.006 | G1 |

`prem_high60_c` is the premium making a new 60-minute high inside the minute (bar j). `bb_own_5` is lots bought back on the same side in the previous 5 minutes: **buy-backs come in clusters**.

**B5 — rule.** Depth-3 tree inside crossing-present minutes: | tree_precision | tree_recall | tree_F1 | crossing_only_precision | crossing_only_recall | crossing_only_F1 | precision_ratio | flagged | crossing_cells |
|---|---|---|---|---|---|---|---|---|
| 0.444 | 0.318 | 0.370 | 0.165 | 0.541 | 0.253 | 2.696 | 1375 | 6315 |

Accepted only with F1 ≥ 0.50: **not met**. The in-sample tree splits first on "premium at a new 60-minute high in the minute", then on a buy-back on the same side within the last minute with a ≥12% premium rise, or on the 60-minute spot move against the right (`outputs/bl_d0p_b5_tree.txt`).

**B6 (post-hoc) — lookback window of the premium breakout.** Each side at bar j and at the decision time (close of j−1):

| side | window_min | cells | share_cells | rate_when_on | rate_when_off | auc |
|---|---|---|---|---|---|---|
| sale: premium of the sold right makes a new low | 5 | 14762 | 0.249 | 0.325 | 0.073 | 0.701 |
| sale: premium of the sold right makes a new low | 15 | 14762 | 0.153 | 0.455 | 0.078 | 0.708 |
| sale: premium of the sold right makes a new low | 30 | 14762 | 0.114 | 0.551 | 0.082 | 0.702 |
| sale: premium of the sold right makes a new low | 60 | 14762 | 0.090 | 0.635 | 0.086 | 0.691 |
| sale: premium of the sold right makes a new low | 120 | 14762 | 0.076 | 0.684 | 0.090 | 0.678 |
| sale: premium of the sold right makes a new low | day | 14762 | 0.070 | 0.695 | 0.094 | 0.667 |
| buy-back: premium of the stopped right makes a new high (cells with a lot ≥1.4×) | 5 | 6315 | 0.291 | 0.323 | 0.100 | 0.667 |
| buy-back: premium of the stopped right makes a new high (cells with a lot ≥1.4×) | 15 | 6315 | 0.180 | 0.433 | 0.106 | 0.676 |
| buy-back: premium of the stopped right makes a new high (cells with a lot ≥1.4×) | 30 | 6315 | 0.125 | 0.537 | 0.112 | 0.669 |
| buy-back: premium of the stopped right makes a new high (cells with a lot ≥1.4×) | 60 | 6315 | 0.075 | 0.678 | 0.123 | 0.639 |
| buy-back: premium of the stopped right makes a new high (cells with a lot ≥1.4×) | 120 | 6315 | 0.048 | 0.696 | 0.138 | 0.593 |
| buy-back: premium of the stopped right makes a new high (cells with a lot ≥1.4×) | day | 6315 | 0.035 | 0.676 | 0.146 | 0.564 |
| buy-back: premium of the stopped right makes a new high (all cells) | 5 | 14762 | 0.208 | 0.241 | 0.101 | 0.602 |
| buy-back: premium of the stopped right makes a new high (all cells) | 15 | 14762 | 0.104 | 0.360 | 0.104 | 0.606 |
| buy-back: premium of the stopped right makes a new high (all cells) | 30 | 14762 | 0.063 | 0.501 | 0.106 | 0.602 |
| buy-back: premium of the stopped right makes a new high (all cells) | 60 | 14762 | 0.034 | 0.661 | 0.112 | 0.580 |
| buy-back: premium of the stopped right makes a new high (all cells) | 120 | 14762 | 0.022 | 0.674 | 0.118 | 0.553 |
| buy-back: premium of the stopped right makes a new high (all cells) | day | 14762 | 0.015 | 0.667 | 0.122 | 0.537 |
| sale (decision-time, close of j-1 below the prior closes) | 5 | 14762 | 0.249 | 0.257 | 0.095 | 0.629 |
| sale (decision-time, close of j-1 below the prior closes) | 15 | 14762 | 0.153 | 0.341 | 0.099 | 0.634 |
| sale (decision-time, close of j-1 below the prior closes) | 30 | 14762 | 0.113 | 0.400 | 0.102 | 0.628 |
| sale (decision-time, close of j-1 below the prior closes) | 60 | 14762 | 0.089 | 0.455 | 0.104 | 0.622 |
| sale (decision-time, close of j-1 below the prior closes) | 120 | 14762 | 0.076 | 0.472 | 0.108 | 0.610 |
| sale (decision-time, close of j-1 below the prior closes) | day | 14762 | 0.070 | 0.476 | 0.110 | 0.601 |
| buy-back (decision-time, close of j-1 above the prior closes; cells with a lot ≥1.4×) | 5 | 6315 | 0.298 | 0.303 | 0.106 | 0.650 |
| buy-back (decision-time, close of j-1 above the prior closes; cells with a lot ≥1.4×) | 15 | 6315 | 0.186 | 0.404 | 0.110 | 0.661 |
| buy-back (decision-time, close of j-1 above the prior closes; cells with a lot ≥1.4×) | 30 | 6315 | 0.128 | 0.488 | 0.117 | 0.650 |
| buy-back (decision-time, close of j-1 above the prior closes; cells with a lot ≥1.4×) | 60 | 6315 | 0.079 | 0.565 | 0.130 | 0.615 |
| buy-back (decision-time, close of j-1 above the prior closes; cells with a lot ≥1.4×) | 120 | 6315 | 0.054 | 0.592 | 0.141 | 0.583 |
| buy-back (decision-time, close of j-1 above the prior closes; cells with a lot ≥1.4×) | day | 6315 | 0.043 | 0.565 | 0.147 | 0.562 |

No window stands out. Shorter windows flag more minutes at about 30%; longer windows fewer at about 70%.

## 3. What is not known
* **What decides, second by second, whether the sale follows.** The minute's bar adds a lot. Tick data would be needed. **Not testable here.**
* **Whether the premium-breakout reading is the real mechanism or a proxy** for something I have not built (for example a level in the underlying, an indicator on the spot, or the vendor's own signal). The decision-time versions are weaker than the contemporaneous ones.
* **The exact buy-back rule.** Precision 44%, recall 32% is not a rule.
* **The remaining ~35% of non-stop buy-backs** (burst members, roll-outs, others) are not separately explained here.

## Addendum — changes after the first run
1. **Leak fixed.** The first version of the Part A models used the outcome "sale within ±W s" together with the feature "seconds since the last solo sale". A sale just before the buy-back made the feature reveal the outcome (AUC 0.86, a spurious gate with 100%). The outcome is now "at or after the buy-back"; the ±W shares remain only as descriptive numbers (A0). The plan's A-part should be read that way.
2. **Post-hoc, after seeing results:** the hazard table and the minute-j bar check (A5), the lookback-window comparison (B6), and its decision-time version, added to rule out the fill of the order itself printing the new high or low.
3. B1–B5 as planned. The cell outcome `y_loss` (decision ratio ≥1.2) was added next to `y_bb` as a secondary view.
4. The events here are grouped by lots flagged stop-loss, so counts differ slightly from `D0_COUNTER.md`.

## Caveats
* In-sample, one-minute bars, 24 cycles, cycle-bootstrap CIs. No untouched data.
* The contemporaneous bar contains the algo's own fills. The decision-time versions show the same pattern, weaker.
* Lot state uses the ledger convention (highest-ratio lot removed).

## Run order
`bl_d0p_a.py` (~3 min) → `bl_d0p_a2.py` → `bl_d0p_b.py` (~3 min) → `bl_d0p_b6.py` → `make_d0p_report.py`.
