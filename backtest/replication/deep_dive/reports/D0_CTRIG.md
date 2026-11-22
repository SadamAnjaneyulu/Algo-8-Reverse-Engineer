# Algo 8 — D0 counter-sells: how they happen, when, and what triggers them

*Plan `D0_CTRIG_PLAN.md` (with an addendum written after the results). In-sample discovery on D0: 14,762 minute cells over 24 of the 30 cycles (the other 6 stop out in the opening minutes), 5,413 solo sale orders. Figure: `figures/bl_d0n_summary.png`. Scripts `bl_d0n_*.py`.*

## 0. Result
**A counter-sell is a solo sale of the right whose premium has just fallen to a new low. It often lands in the same second as a stop-loss buy-back of the other right, most likely because both react to the same spot move. Nothing here shows that the buy-back triggers it.** I could not turn this into an exact rule with one-minute bars.

| Question | Answer | Evidence | Label |
|---|---|---|---|
| **What is it?** | Solo sale of R′ (one lot in the median order) near the live ATM (35% exact, 82% within one step), mostly at strikes already short. "Counter" = another-right buy-back within ±60 s. | 1,713 counter-labelled orders | Observed |
| **Main trigger** | The sold right's ATM premium is at its low. 62% of counter-labelled lots are at a 60-minute premium low, against 9% of all minutes (6.8×) and 33% of other solo lots. | N2, N7 | Observed |
| **Same-second coupling to a buy-back** | 30% of stop-loss buy-backs have a sale on the other right within 2 s. In the ±2 s bins sales are 13× the shifted null (CI 7–31). **32% of counter-labelled lots** have a buy-back within 2 s (chance 3%). | N4 | Observed |
| **Is the buy-back the cause?** | Not shown. Among same-second pairs the sale comes first or in the same second in 77% of them, and after the buy-back in 23%. Past buy-backs add 0.005 AUC once market state is known. The simplest reading is one tick feeding two rules. | N2, N4 | Inferred |
| **Loss recovery?** | No. Premium sold vs loss on the stopped lots: Spearman 0.10 (CI 0.04–0.17), bar was 0.3; the shifted null is -0.13/-0.09. | N5 | Observed |
| **Quantity** | Not proportional to lots bought (Spearman 0.08 in same-second pairs). Burst size vs the favourable spot move: Spearman 0.19. | N5 | Observed |
| **Clock** | No. Counter-labelled sale times recur on other cycles' times at 1.7× chance (bar 3×); other solo sales 3.0×. | H7 | Observed |
| **When** | All day, every hour from 09 to 15. Counter-labelled lots by hour 09–15: 307, 222, 216, 252, 236, 373, 182; the largest hour is 14:00. Minute 1 of the 15-minute block is high for other solo sales (25% of lots) and only mildly for counter-labelled (13%). | N7 | Observed |
| **Exact rule** | **Not recovered.** Best out-of-fold exact-cell F1 0.37 (bar 0.50). The simple "premium at its 60-minute low" gives F1 0.36: precision 46%, recall 30%. Adding the minute's own bar lifts AUC 0.88 → 0.92, so the trigger sits inside the minute. | N2, N3 | Unresolved |

## 1. Hypotheses and verdicts
| # | Hypothesis | Verdict |
|---|---|---|
| H1 | The counter label is an artifact (counter and other solo cannot be told apart by market and book state) | **Not killed.** AUC 0.62 (CI 0.54–0.69); my bar to kill it was a CI lower bound above 0.55. But counter-labelled sales do differ on two simple conditions (premium low 62% vs 33%; same-second buy-back 32% vs 9%). They look like the premium-low ladder in the strongest moves. |
| H2 | Spot move | **Associated, not sufficient.** +0.10 AUC over baseline. |
| H3 | Premium state | **Strongest group.** +0.12 AUC. |
| H4 | Book state | **Associated.** +0.08 AUC; each group is redundant given the others (dropping any one costs at most 0.012). |
| H5 | Loss recovery | **Rejected** (N5). |
| H6 | Same-instant coupling | **Accepted** (≥3× null, CI above 1×). Cause not shown. |
| H7 | Clock | **Rejected** for counter-labelled sales. |

## 2. N1 — counter-labelled vs other solo sales (market and book state only)
| model | orders | counter_share | auc | auc_lo | auc_hi | prauc | pr_lo | pr_hi |
|---|---|---|---|---|---|---|---|---|
| time + right (baseline) | 4527 | 0.366 | 0.562 | 0.512 | 0.611 | 0.409 | 0.318 | 0.505 |
| + spot | 4527 | 0.366 | 0.627 | 0.563 | 0.705 | 0.447 | 0.341 | 0.585 |
| + premium | 4527 | 0.366 | 0.613 | 0.540 | 0.685 | 0.418 | 0.300 | 0.583 |
| + book | 4527 | 0.366 | 0.629 | 0.568 | 0.690 | 0.479 | 0.376 | 0.605 |
| all market/book (no buy-back features) | 4527 | 0.366 | 0.619 | 0.538 | 0.690 | 0.454 | 0.310 | 0.611 |
| all + past buy-backs | 4527 | 0.366 | 0.752 | 0.696 | 0.800 | 0.630 | 0.511 | 0.731 |

The last row uses past buy-backs, so it partly rebuilds the label itself. It should not be read as a trigger.

## 3. N2 — what predicts a solo sale in a minute
| model | features | auc | auc_lo | auc_hi | prauc | pr_lo | pr_hi | gain_over_baseline |
|---|---|---|---|---|---|---|---|---|
| baseline (time, right, underlying) | 7 | 0.745 | 0.692 | 0.770 | 0.471 | 0.366 | 0.545 | 0.000 |
| + spot | 22 | 0.842 | 0.812 | 0.863 | 0.510 | 0.443 | 0.562 | 0.096 |
| + premium | 17 | 0.861 | 0.838 | 0.881 | 0.530 | 0.469 | 0.575 | 0.115 |
| + book | 22 | 0.821 | 0.788 | 0.835 | 0.502 | 0.391 | 0.567 | 0.076 |
| + buy-backs (past) | 20 | 0.801 | 0.755 | 0.823 | 0.496 | 0.374 | 0.559 | 0.055 |
| spot + premium | 32 | 0.858 | 0.834 | 0.878 | 0.520 | 0.460 | 0.571 | 0.113 |
| all decision-time | 60 | 0.876 | 0.861 | 0.889 | 0.540 | 0.463 | 0.588 | 0.131 |
| all + bar j (contemporaneous) | 65 | 0.917 | 0.898 | 0.932 | 0.684 | 0.646 | 0.715 | 0.171 |

* **Placebo** (features shuffled within each cycle): AUC 0.685 (CI 0.630–0.722). It is well above 0.5 because the pooled AUC also rewards the level differences between cycles (underlying, version). **Read the gains against the baseline and the placebo, not against 0.5.**
* **Contemporaneous check:** adding the minute's own bar lifts PR-AUC from 0.54 to 0.68. The sale reacts to a move inside the same minute.
* **Forward check** (first 16 cycles → last 8): baseline 0.61, premium 0.80, all decision-time 0.82, with bar j 0.89.

Ablation (all decision-time minus one group):
| dropped | auc | auc_lo | auc_hi | prauc | pr_lo | pr_hi |
|---|---|---|---|---|---|---|
| spot | 0.878 | 0.863 | 0.890 | 0.547 | 0.457 | 0.600 |
| prem | 0.864 | 0.851 | 0.875 | 0.538 | 0.457 | 0.596 |
| book | 0.873 | 0.857 | 0.884 | 0.538 | 0.462 | 0.598 |
| bb | 0.872 | 0.857 | 0.888 | 0.534 | 0.453 | 0.582 |

Largest permutation-importance drops (LOCO, in AUC):
| feature | drop_in_auc | se | group |
|---|---|---|---|
| min_in_15 | 0.075 | 0.020 | base |
| prem_vs_daymin | 0.070 | 0.013 | prem |
| prem_chg_3 | 0.012 | 0.003 | prem |
| prem_chg_15 | 0.010 | 0.002 | prem |
| j | 0.009 | 0.002 | base |
| prem_chg_5 | 0.005 | 0.003 | prem |
| fav_ret_5 | 0.005 | 0.003 | spot |
| fav_ret_30 | 0.004 | 0.003 | spot |

`min_in_15` (position in the 15-minute block) and `prem_vs_daymin` (premium ÷ its day low) dominate. **Past buy-back features rank low.**

## 4. N3 — from predictors to a rule
| rule | exact_precision | exact_recall | exact_F1 | exact_F1_lo | exact_F1_hi | exact_placebo_F1 | exact_ratio_vs_placebo | tol_F1 | tol_placebo_F1 | flagged_cells |
|---|---|---|---|---|---|---|---|---|---|---|
| tree: spot + time | 0.232 | 0.582 | 0.332 | 0.299 | 0.378 | 0.353 | 0.941 | 0.580 | 0.579 | 5026 |
| tree: premium + time | 0.267 | 0.614 | 0.372 | 0.330 | 0.429 | 0.355 | 1.048 | 0.627 | 0.581 | 4606 |
| tree: spot + premium + time | 0.267 | 0.614 | 0.372 | 0.326 | 0.438 | 0.353 | 1.053 | 0.627 | 0.579 | 4606 |
| tree: all market/book | 0.267 | 0.614 | 0.372 | 0.320 | 0.436 | 0.352 | 1.057 | 0.627 | 0.580 | 4606 |
| tree: all + past buy-backs | 0.267 | 0.614 | 0.372 | 0.321 | 0.433 | 0.355 | 1.048 | 0.627 | 0.581 | 4606 |
| hand rule (post-hoc): ATM premium at its day low (close at j-1) | 0.475 | 0.250 | 0.327 | 0.281 | 0.379 | — | — | 0.535 | — | 1052 |
| hand rule (post-hoc): ATM premium at 60-min low | 0.455 | 0.304 | 0.365 | 0.321 | 0.409 | — | — | 0.596 | — | 1338 |
| hand rule (post-hoc, uses bar j): ATM premium makes new day low in minute j | 0.583 | 0.309 | 0.404 | 0.345 | 0.478 | — | — | 0.557 | — | 1061 |
| hand rule (post-hoc): day low OR spot fresh 60-min extreme | 0.424 | 0.314 | 0.361 | 0.319 | 0.411 | — | — | 0.583 | — | 1480 |

* **Acceptance bar** (out-of-fold F1 at least 0.50 and 3× placebo): **not met by any rule.** Best out-of-fold tree 0.37; placebo 0.35.
* **Flag-everything floor:** exact-cell F1 0.24, ±1-minute F1 0.45. The ±1-minute column therefore flatters every rule (see the addendum). Use the exact-cell columns.
* **Hand rules were chosen after the fact** (labelled post-hoc, not fitted). With the minute's own bar ("premium makes a new day low in minute j") the exact F1 is 0.40 (precision 58%, recall 31%).
* Fitted on all cycles (in-sample), the tree's first split is "premium at a 60-minute low"; below it, "premium fell more than 29% in 3 minutes" or minute 0/1 of the block (`outputs/bl_d0n_n3_tree.txt`).

## 5. N4 — same-second coupling
Stop-loss buy-backs (R) against solo sales on R′, lag in seconds (sale minus buy-back), 1 s bins:

| lag_s | orders | null | ratio |
|---|---|---|---|
| -10 | 56 | 13.50 | 4.15 |
| -9 | 63 | 14.00 | 4.50 |
| -8 | 80 | 12.00 | 6.67 |
| -7 | 60 | 14.00 | 4.29 |
| -6 | 55 | 10.00 | 5.50 |
| -5 | 88 | 13.00 | 6.77 |
| -4 | 132 | 9.50 | 13.89 |
| -3 | 136 | 13.00 | 10.46 |
| -2 | 126 | 10.50 | 12.00 |
| -1 | 148 | 13.00 | 11.38 |
| 0 | 280 | 12.00 | 23.33 |
| 1 | 132 | 16.00 | 8.25 |
| 2 | 120 | 13.00 | 9.23 |
| 3 | 97 | 16.50 | 5.88 |
| 4 | 64 | 9.50 | 6.74 |
| 5 | 53 | 6.50 | 8.15 |
| 6 | 61 | 13.50 | 4.52 |
| 7 | 67 | 14.00 | 4.79 |
| 8 | 63 | 7.50 | 8.40 |
| 9 | 45 | 8.00 | 5.62 |
| 10 | 102 | 19.50 | 5.23 |

Share of solo lots with an other-right buy-back (any reason) within the window:

| window_s | share_all_solo_lots | share_counter_lots | share_noncounter_lots | null_share_all_lots |
|---|---|---|---|---|
| 2 | 0.176 | 0.319 | 0.113 | 0.028 |
| 5 | 0.295 | 0.432 | 0.235 | 0.056 |
| 60 | 0.646 | 1.000 | 0.490 | 0.290 |

* **By buy-back reason**, the share of events with a sale within 2 s:

| type | events | share_with_tight_sale |
|---|---|---|
| 1 cycle-stop window | 30 | 0.200 |
| 2a clearance 15:10-15:13 | 160 | 0.031 |
| 2b clearance 15:14 | 83 | 0.000 |
| 2c clearance 15:15+ | 382 | 0.021 |
| 3 stop-loss | 1395 | 0.295 |
| 4 take-profit | 612 | 0.025 |
| 5 partner | 191 | 0.047 |
| 6 roll-out | 789 | 0.098 |
| 7 burst member | 409 | 0.152 |
| 8 other | 606 | 0.097 |

Only stop-loss (and, weakly, burst, roll-out and cycle-stop) go with a same-second sale. Take-profit (2.5%) and partner (4.7%) do not.
* **Direction:** of 1000 same-second sale orders, 45% are in the very same second, 32% come before the buy-back and 23% after. Order inside a second is not observable.
* **Size and price:** median 1 lot sold per 1 lot bought; the same strike in 10% of pairs; premium sold ÷ premium bought median 0.63.
* **Which stop-loss events have a sale:** the share is the same whatever the lots bought (30%, 30%, 27%, 30%), and higher when the other right's premium is at its low (94% within ±60 s against 70% otherwise; within 2 s 32% against 25%). This is consistent with a shared market state rather than a fixed paired action. *Inferred.*

## 6. N5 — quantity and loss recovery
* **Loss recovery rejected:** 1477 stop-loss events; premium sold in the next 60 s vs the realised loss, Spearman 0.10. Median sold premium ₹2,883, median loss ₹2,256, no proportionality.
* **Bursts:** 2,032 bursts (same right, gaps ≤30 s). Median 1 order, lots 10/50/90% = 1/1/6. Bursts of 5+ lots hold 50% of lots. 32% of bursts contain a counter-labelled order.

## 7. N6 — mechanics
| counter | orders | lots_per_order | exact_atm | median_off_steps | carried_strike | d0_strike | new_strike | median_px_over_atm |
|---|---|---|---|---|---|---|---|---|
| counter-labelled | 1713 | 1.044 | 0.353 | 0.000 | 0.536 | 0.416 | 0.047 | 0.965 |
| other solo | 3700 | 1.096 | 0.230 | 0.000 | 0.557 | 0.394 | 0.048 | 0.860 |

Counter-labelled sales sit at the exact ATM more often (35% vs 23%) and at a higher premium relative to the ATM (0.97 vs 0.86), but the strike offset median is 0 steps for both, and 54% / 56% go to strikes already short from D-1.

## 8. N7 (post-hoc) — what each counter-labelled sale satisfies
Share of orders meeting each condition (a sale can meet several), against the share of all minutes:
| condition | counter_labelled | other_solo | all_panel_cells_chance |
|---|---|---|---|
| sl_2s | 0.236 | 0.051 | — |
| bb_2s | 0.316 | 0.094 | 0.035 |
| prem_low_60 | 0.619 | 0.333 | 0.091 |
| prem_low_day | 0.518 | 0.288 | 0.071 |
| prem_newlow_j | 0.622 | 0.375 | 0.072 |
| spot_fresh_60 | 0.396 | 0.199 | 0.064 |
| clock_min | 0.290 | 0.444 | 0.196 |

First condition met, in this order (share of lots):
| why | counter_labelled_share | other_solo_share |
|---|---|---|
| 1 buy-back within 2 s | 0.316 | 0.094 |
| 2 R′ premium at 60-min low | 0.396 | 0.274 |
| 3 spot fresh 60-min extreme | 0.025 | 0.036 |
| 4 minute 0/1/14 of the 15-min block | 0.112 | 0.308 |
| 5 none of these | 0.150 | 0.288 |

**85% of counter-labelled lots meet at least one**, against at most 39% for the same sales moved ±10–15 minutes (the shifted check leaves out the buy-back condition, so it is an upper bound). The premium low covers a further 40% of counter-labelled lots that have no same-second buy-back.

## 9. What is not known
* **The exact trigger.** Premium lows explain about 30% of sale minutes at best. The minute's own bar adds a lot, so the rule fires on intraminute moves that one-minute bars cannot show. **Not testable here.**
* **Whether the buy-back and the sale are one decision or two rules on the same tick.** The data fit the second, and I can't separate them without tick data.
* **Why a premium low sometimes does not sell** (precision 45–58%).
* **The remaining sale minutes** (premium not at a low): minute-of-block structure (minute 1 and 14) belongs to the other solo types.

## Addendum — changes made after seeing results (all labelled in the text)
1. **Panel starts at minute 4 (09:19)**, not 09:16: opening solo is its own type and the feature windows are incomplete before that. 24 of 30 cycles remain.
2. **Gradient boosting** is the histogram version, which has no row subsampling (the plan's 0.8 could not be used); other settings as planned.
3. **N3 metric:** the plan said lot-level F1. A cell-level F1 with ±1 minute tolerance was run first and has a high floor (flag-everything 0.45), so **exact-cell F1 is the reported metric** and the threshold is picked on it. Lot-level F1 needs a size rule and is not computed.
4. **Post-hoc:** the premium-low features (`phx_*`), the hand rules, the same-second follow-up (N4b) and the condition table (N7) were added after N2.
5. N1's baseline model includes cycle-level features (underlying, version), so cycle-level differences in selling can leak into the pooled AUC. The placebo row shows how much.

## Caveats
* **In-sample discovery**, one-minute bars, 24 cycles. Cycle-bootstrap CIs. No untouched data, so none of this is out-of-sample evidence.
* Order within a second cannot be observed.

## Run order
`bl_d0n_panel.py` → `bl_d0n_model.py` (~3 min) → `bl_d0n_more.py` → `bl_d0n_tight.py` → `bl_d0n_rule.py` (~3 min) → `bl_d0n_decomp.py` → `make_d0n_report.py`.
