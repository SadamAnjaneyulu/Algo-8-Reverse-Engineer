# Algo 8 — D0 counter-sells: the AUC gate

*Plan `D0_CAUC_PLAN.md`, written before the run (a post-hoc follow-up, §3, is labelled). In-sample discovery on D0: 14,762 minute cells (cycle × minute × right) over 24 cycles; 667 cells carry a counter-sell. Figure: `figures/bl_d0c_summary.png`. Scripts `bl_d0c_auc.py`, `bl_d0c_expl.py`.*

## 0. Result: the gate is met
**Counter-sell cells are ranked at AUC 0.882 (95% CI 0.859–0.903) using only information from before the minute.** The gate was 0.85 with a forward check of at least 0.80.

| Check | Result | Gate |
|---|---|---|
| **V1 causal, pooled leave-one-cycle-out AUC** | **0.882** | ≥ 0.85 ✔ |
| Forward check (first 16 cycles → last 8) | **0.886** | ≥ 0.80 ✔ |
| Within-cycle AUC (mean over 22 cycles with ≥5 counter cells) | **0.873** | reported |
| Placebo (features shuffled within each cycle), pooled / within-cycle | 0.582 / 0.497 | reported |
| PR-AUC (base rate 4.5%) | 0.290 | reported |

* **Observed.** The within-cycle AUC removes the cycle-level base-rate effect that pooled AUC rewards, and it also clears 0.85 (0.873) with a placebo at chance (0.497).
* **What a pass means.** It is a **ranking**: the minutes that will carry a counter-sell sit far above the rest. It is not a recovered rule. The exact-cell F1 of single rules stays below 0.5 (`D0_CTRIG.md`), and the PR-AUC of 0.29 against a 4.5% base rate says that a hard threshold on the ranking would still flag many minutes without a counter-sell.

## 1. The three variants
| variant | features | auc | lo | hi | prauc | within_cycle_auc |
|---|---|---|---|---|---|---|
| V1 causal (bars to j-1, orders before minute j) | 64 | 0.882 | 0.859 | 0.903 | 0.290 | 0.873 |
| V2 + the minute's own bar | 71 | 0.935 | 0.910 | 0.955 | 0.507 | 0.932 |
| V3 + same-minute buy-backs (partly definitional) | 74 | 0.957 | 0.935 | 0.973 | 0.613 | 0.955 |
| placebo (V1 features shuffled within cycle) | 64 | 0.582 | 0.517 | 0.631 | 0.057 | 0.497 |

* **V2** adds the minute's own bar (0.935): not knowable ahead, it shows that part of the trigger sits inside the minute.
* **V3** adds buy-backs of the other right in the same minute (0.957). The counter label is itself defined by such a buy-back, so V3 is **partly definitional** and is not used for the gate.

## 2. Counter-sells are as predictable as solo sales in general
| variant | features | auc | lo | hi | prauc | within_cycle_auc |
|---|---|---|---|---|---|---|
| V1 causal (bars to j-1, orders before minute j) | 64 | 0.877 | 0.862 | 0.889 | 0.542 | 0.857 |
| V2 + the minute's own bar | 71 | 0.925 | 0.909 | 0.939 | 0.705 | 0.916 |
| V3 + same-minute buy-backs (partly definitional) | 74 | 0.930 | 0.916 | 0.943 | 0.715 | 0.923 |
| placebo (V1 features shuffled within cycle) | 64 | 0.671 | 0.609 | 0.710 | 0.215 | 0.489 |

Forward check for any solo sale, V1: 0.818. The counter label (a solo sale next to a buy-back of the other right) is predicted **at least as well** as solo selling in general (0.882 against 0.877, within-cycle 0.873 against 0.857). *Inferred:* a counter-sell is a solo sale that happens in a strong, one-directional move, which also produces the other right's buy-back.

## 3. What drives it (post-hoc follow-up)
| model | features | auc | within_cycle_auc |
|---|---|---|---|
| V1 causal (reference) | 64 | 0.882 | 0.873 |
| V1 + stop pressure of the other right | 76 | 0.885 | 0.876 |
| V1 minus base | 57 | 0.870 | 0.864 |
| V1 minus spot | 49 | 0.881 | 0.870 |
| V1 minus prem | 50 | 0.863 | 0.854 |
| V1 minus book | 49 | 0.880 | 0.877 |
| V1 minus bb | 51 | 0.865 | 0.858 |
| only base (+ base) | 7 | 0.632 | 0.559 |
| only spot (+ base) | 22 | 0.827 | 0.841 |
| only prem (+ base) | 21 | 0.848 | 0.861 |
| only book (+ base) | 22 | 0.787 | 0.760 |
| only bb (+ base) | 20 | 0.775 | 0.741 |
| only other-right stop pressure (+ base) | 19 | 0.830 | 0.837 |

* **Premium of the sold right** is the largest single family: alone (with the clock) it reaches 0.848; dropping it costs the most (0.018).
* **Spot move** alone 0.827; **book state** 0.787; **past buy-backs** 0.775. Each is redundant given the others (dropping any one costs at most 0.018).
* **The stop pressure of the other right** (its largest lot ratio, premium at a new high, side loss) alone gives 0.830, but adds only +0.003 to V1: it is already contained in the sold right's own state, as expected if both react to one move. *Observed.*

Strongest features (AUC lost when shuffled, counter cells):
| feature | drop_in_auc | family |
|---|---|---|
| prem_chg_1 | 0.018 | prem |
| prem_vs_daymin | 0.016 | prem |
| min_in_15 | 0.010 | base |
| since_bb_other | 0.009 | bb |
| phx_prem_low_60 | 0.006 | prem |
| fav_ret_15 | 0.004 | spot |
| bb_own_1 | 0.003 | bb |
| oth_max_ratio_close_prev | 0.002 | other_stop |
| bb_other_1 | 0.002 | bb |
| expo_own | 0.002 | book |

* The 1-minute change of the sold option's premium and its position against its day low lead. Time since the last buy-back of the other right and the minute within the 15-minute block follow.

## 4. What this does and does not settle
* **Settled (Observed):** the minutes that carry a counter-sell can be identified ahead of time at AUC 0.88, from the sold option's premium collapsing, the spot moving in its favour, how recently the other right was bought back, and the clock position. This holds forward in time and within each cycle.
* **Not settled:** the exact second and size of each sale, and whether the buy-back and the sale are one decision or two rules on the same move (`D0_PAIR.md`). One-minute bars cannot show that.

## Caveats
* In-sample discovery, one-minute bars, 24 cycles, cycle-bootstrap CIs; the forward check is one split.
* The V1 feature set includes the premium-low windows that were added after the first counter-sell tests (`D0_CTRIG_PLAN.md` addendum). They are causal (bars to j−1), and the placebo stays at chance.
* Positives are rare (4.5% of cells), so high AUC coexists with modest precision.

## Run order
`bl_d0n_panel.py` → `bl_d0c_auc.py` (~2 min) → `bl_d0c_expl.py` (~3 min) → `make_d0c_report.py`.
