# Algo 8 — D0: roll-out and "other" buy-backs, and the opening burst

*Plan `D0_OPEN_ROLL_PLAN.md`, written before the tests (the addendum lists the post-hoc steps). In-sample discovery on D0; every score is leave-one-cycle-out (LOCO) or forward. Figure: `figures/bl_d0z_summary.png`. Scripts `bl_d0z_*.py`.*

## 0. Result

**Coverage (rule found, or timing gate met on unseen cycles): 81.3% → 84.9% of D0 lots. The 90% target is still not reached.** Roll-out passes the gate; "other" does not; the opening burst is decoded in structure but not in its counts.

| tier | before | after |
|---|---|---|
| 1 rule found | 63.5% | 63.3% |
| 2 timing/count gate met | 17.8% | 21.6% |
| 3 ranked below the gate / indicative / same-minute only | 14.2% | 10.6% |
| 4 unresolved | 4.5% | 4.5% |

| question | answer | evidence |
|---|---|---|
| **Roll-out buy-backs: above 0.85?** | **Yes, on the pre-registered set.** Adding the learned **sale clock** (does the timetable sell on this right in this, the next or the previous minute?) lifts AUC from 0.832 to **0.857** (CI 0.836–0.882, forward 0.824, within-cycle 0.846, placebo of the same set 0.458). Paired gain +0.025 (CI +0.015 to +0.037). Gate met, with a thin margin (forward 0.824 against 0.80). | Observed |
| Why did it work? | **The label.** A roll-out is defined by a same-right sale within 60 s *after* the buy-back, and 24% of buy-backs are followed by a sale by chance (roll-out lots: 100% by definition against 38% chance). The timetable tells when a sale is due, which is decision-time information. So the improvement is partly *predicting the timetable*, not a new buy-back reason. | Observed |
| **"Other" buy-backs: above 0.85?** | **No.** Best 0.797 (CI 0.760–0.837, forward 0.800); sale clock +0.013; decayed-lot / age features +0.010; post-hoc class clock 0.808. "Other" is a residual by construction (no stop-loss, take-profit, partner, burst or following sale: only 2.5% are followed by a sale against 23% chance). | Observed; stays below the gate |
| Did the two-stage product help? | No: roll-out 0.834, other 0.710, both below the single-stage models. | Observed |
| **Opening burst: what is bought back?** | The **stop at the first print, applied partially.** Among carried lots (cycles without a stop at the open) the take rate rises from 2% below 0.8× entry to 53% at 1.4–1.6×. Price ÷ entry at the open ranks the lots at AUC 0.850 (CI 0.745–0.910), within a cycle-and-right 0.79; a boosted model is **worse** (0.70, forward 0.72). The best threshold rule (open ÷ entry ≥ 1.3) has precision 0.34, recall 0.49. **Not gate-met.** | Observed |
| How many opening buy-backs? | Median 0.5 lots per cycle and right (many zero; up to 37). Best candidate: a fraction of the lots whose open price is ≥ 1.4× entry, exact 46% against 15% for the baseline, error 3.0 vs 4.2 lots, ρ 0.39. **Associated only** (ρ < 0.5). | Observed |
| **Opening sells** | In the first three minutes of cycles without a stop: 695 lots, of which scheduled waves 70 (10%), opening pairs 140 (20%), **opening solo 485 (70%)**. No candidate predicts the count (best, carried shorts: exact 11%, error 8.5 vs baseline 8.9, ρ 0.44); the number sold is **not** tied to the number bought back (ρ -0.05). | Observed; Unresolved |
| **Opening long buys** | **A clock event at 09:16:00 (median 60 s after the open, IQR 60–69) whose size follows the sells of the 09:16 minute**: ρ 0.92, within 2 lots in 89% of cycle-rights, error 1.0 vs 1.6 lots for the baseline (median ratio 1.00, i.e. about one long lot per lot sold). Exact only 37% (the baseline is exact 45%: counts are narrow, 6–14). **Count rule found (approximate); strike still unresolved.** | Observed |
| Gap days | In the 4 cycles that stop at the open the stop module sends a median 274 lots and the hedge module 88; the body then sells 11 lots in the first three minutes (against 37 on other days) and buys 5 long lots (against 20). | Observed |

### The opening in order (09:15:00 = 0 s)

| klass | cycles | lots | first_s_median | all_orders_median_s | q25 | q75 | share_in_minute0 |
|---|---|---|---|---|---|---|---|
| stop module | 5 | 1619 | 7 | 24.6 | 7 | 42 | 0.6 |
| body buy-back | 27 | 522 | 11 | 25.5 | 4 | 74 | 0.7 |
| body sell | 29 | 1084 | 11 | 62 | 24 | 71 | 0.4 |
| hedge other | 5 | 540 | 16.9 | 16.9 | 7.1 | 22.6 | 1 |
| lump salvage | 8 | 148 | 17.1 | 26.7 | 16.3 | 135.5 | 0.6 |
| wing sell | 24 | 1275 | 18.2 | 25.9 | 14.2 | 69.1 | 0.7 |
| wing buy | 21 | 314 | 25.6 | 74.7 | 41.8 | 94.3 | 0.3 |
| body long buy | 30 | 698 | 59.5 | 63 | 60 | 69 | 0.2 |
| body long sell | 10 | 48 | 98 | 121 | 74 | 152 | 0.2 |

1. **0–10 s, gap days only:** stop module and hedge module liquidate the carried book at the first prints.
2. **~11 s:** the stop applied to carried lots at the first print (partial), and the first opening sells (mostly solo, 70%).
3. **~18–26 s:** the hedge controller releases wings freed by the buy-backs and buys wings for the new shorts.
4. **09:16:00–09:16:09:** the opening long buys, sized to the lots sold in the 09:16 minute.

## 1. Roll-out and "other" (cell = cycle × minute × right)

### Label audit (share of in-scope buy-back lots followed by a same-right sale within 60 s)

| t | lots | followed_real | followed_chance | excess |
|---|---|---|---|---|
| 3 | 2584 | 0.322 | 0.214 | 0.108 |
| 4 | 853 | 0.327 | 0.281 | 0.046 |
| 5 | 386 | 0.42 | 0.221 | 0.199 |
| 6 | 1259 | 1 | 0.376 | 0.624 |
| 7 | 1128 | 0.004 | 0.138 | -0.134 |
| 8 | 848 | 0.025 | 0.228 | -0.203 |

*Types: 3 stop-loss, 4 take-profit, 5 partner, 6 roll-out, 7 burst member, 8 other. Chance = the sale times shifted ±10 and ±15 minutes.*

### Timing gate

| outcome | set | auc | lo | hi | forward | within_cycle | placebo | gate | note |
|---|---|---|---|---|---|---|---|---|---|
| roll-out | REF + sale clock | 0.857 | 0.836 | 0.882 | 0.824 | 0.846 | 0.458 | met | gate set: pre-registered R-H1 set (roll-out) / best pre-registered set (other); POST-HOC rows labelled |
| roll-out | POST-HOC: REF + sale clock + decayed/age + class clocks | 0.856 | 0.832 | 0.879 | 0.824 | 0.846 | 0.441 | met | gate set: pre-registered R-H1 set (roll-out) / best pre-registered set (other); POST-HOC rows labelled |
| other | REF + sale clock + decayed/age | 0.797 | 0.76 | 0.836 | 0.8 | 0.795 | 0.493 | not met | gate set: pre-registered R-H1 set (roll-out) / best pre-registered set (other); POST-HOC rows labelled |
| other | POST-HOC: REF + sale clock + decayed/age + class clocks | 0.808 | 0.771 | 0.845 | 0.801 | 0.804 | 0.503 | not met | gate set: pre-registered R-H1 set (roll-out) / best pre-registered set (other); POST-HOC rows labelled |

| outcome | set | auc_loco | lo | hi | within_cycle | forward_auc | positives | cells |
|---|---|---|---|---|---|---|---|---|
| roll-out | REF (ALL of D0_BURST_LONG) | 0.832 | 0.802 | 0.859 | 0.822 | 0.791 | 505 | 14910 |
| roll-out | REF + sale clock | 0.857 | 0.832 | 0.881 | 0.846 | 0.824 | 505 | 14910 |
| roll-out | REF + decayed/age | 0.829 | 0.801 | 0.855 | 0.823 | 0.797 | 505 | 14910 |
| roll-out | REF + sale clock + decayed/age | 0.858 | 0.833 | 0.88 | 0.846 | 0.816 | 505 | 14910 |
| other | REF (ALL of D0_BURST_LONG) | 0.783 | 0.74 | 0.822 | 0.78 | 0.776 | 540 | 14910 |
| other | REF + sale clock | 0.796 | 0.757 | 0.837 | 0.795 | 0.786 | 540 | 14910 |
| other | REF + decayed/age | 0.793 | 0.754 | 0.829 | 0.79 | 0.783 | 540 | 14910 |
| other | REF + sale clock + decayed/age | 0.797 | 0.76 | 0.837 | 0.795 | 0.8 | 540 | 14910 |
| roll-out (this or next minute) | REF (ALL of D0_BURST_LONG) | 0.801 | 0.767 | 0.832 | 0.795 | 0.765 | 891 | 14910 |
| roll-out (this or next minute) | REF + sale clock | 0.819 | 0.785 | 0.848 | 0.806 | 0.779 | 891 | 14910 |
| roll-out (this or next minute) | REF + decayed/age | 0.803 | 0.769 | 0.831 | 0.802 | 0.768 | 891 | 14910 |
| roll-out (this or next minute) | REF + sale clock + decayed/age | 0.817 | 0.785 | 0.848 | 0.809 | 0.786 | 891 | 14910 |
| other (this or next minute) | REF (ALL of D0_BURST_LONG) | 0.774 | 0.735 | 0.813 | 0.762 | 0.774 | 995 | 14910 |
| other (this or next minute) | REF + sale clock | 0.775 | 0.739 | 0.814 | 0.77 | 0.77 | 995 | 14910 |
| other (this or next minute) | REF + decayed/age | 0.78 | 0.735 | 0.819 | 0.77 | 0.768 | 995 | 14910 |
| other (this or next minute) | REF + sale clock + decayed/age | 0.784 | 0.748 | 0.823 | 0.774 | 0.765 | 995 | 14910 |
| same-right sale this or next minute | REF + sale clock | 0.908 | 0.885 | 0.928 | 0.909 | 0.924 | 5698 | 14910 |
| roll-out | two-stage product P(buy-back) x P(sale next) | 0.834 |  |  |  |  | 505 | 14910 |
| other | two-stage product P(buy-back) x P(sale next) | 0.71 |  |  |  |  | 540 | 14910 |

*The tolerance outcome ("this or next minute") is a different, coarser class and is not a gate; its AUC is lower (roll-out 0.82, other 0.78) because its positives include neighbouring minutes.*

## 2. The opening burst

### Which carried lots are bought back at the first print (lot level)

| feature | pooled_auc | within_cycle_right_auc | cells |
|---|---|---|---|
| price / entry at the first print (open) | 0.85 | 0.788 | 26 |
| price / entry, minute-0 high | 0.854 | 0.802 | 26 |
| price / entry, minute-0 low | 0.849 | 0.799 | 26 |
| price / entry, minute-0 close | 0.847 | 0.798 | 26 |
| ITM depth at the open (steps) | 0.839 | 0.717 | 26 |
| entry price | 0.52 | 0.477 | 26 |
| entry class (code) | 0.407 | 0.467 | 26 |
| strike | 0.552 | 0.437 | 26 |
| ALL lot features (LOCO boosting) | 0.698 | 0.67 | 26 |

| rule | f1 | precision | recall | theta_median | theta_q25 | theta_q75 |
|---|---|---|---|---|---|---|
| take every lot with minute-0 high / entry >= theta | 0.317 | 0.264 | 0.395 | 1.5 | 1.5 | 1.5 |
| take every lot with open / entry >= theta | 0.401 | 0.337 | 0.495 | 1.3 | 1.3 | 1.3 |
| placebo: random set of the true size per cycle and right |  | 0.175 |  |  |  |  |

*2,722 carried lots in 26 cycles without a stop at the open; 200 bought back. LOCO boosting AUC 0.698 (CI 0.56–0.84), forward 0.717 on 53 lots, placebo 0.62. precision@m (the lots a ranking puts first that were really taken): high ÷ entry 0.47, open ÷ entry 0.44, chance 0.17.*

### How many bought back, per cycle and right

| candidate | n | exact | within1 | mae | rho |
|---|---|---|---|---|---|
| median fraction x n_ge12 | 52 | 0.385 | 0.615 | 3.673 | 0.402 |
| median fraction x n_ge14 | 52 | 0.423 | 0.577 | 3.712 | 0.414 |
| median fraction x n_ge16 | 52 | 0.423 | 0.538 | 3.75 | 0.224 |
| median fraction x n_ro14 | 52 | 0.462 | 0.558 | 3.038 | 0.392 |
| median fraction x n | 52 | 0.308 | 0.635 | 4.019 | 0.19 |
| baseline: median of the other cycles | 52 | 0.154 | 0.615 | 4.192 |  |

### Opening sells (minutes 0–2)

| target | candidate | n | exact | within2 | mae | rho |
|---|---|---|---|---|---|---|
| sells | median ratio x S0 | 38 | 0.105 | 0.237 | 8.474 | 0.444 |
| sells | median ratio x L0 | 38 | 0 | 0.105 | 11.29 | 0.42 |
| sells | median ratio x bb | 38 | 0 | 0.105 | 25.974 | -0.051 |
| sells | median ratio x sched | 38 | 0.026 | 0.053 | 14.658 | 0.231 |
| sells | median ratio x range_steps | 38 | 0.026 | 0.237 | 9.5 | 0.169 |
| sells | median ratio x abs_ret | 38 | 0.053 | 0.105 | 14.553 | 0.218 |
| sells | median ratio x S0_oth | 38 | 0 | 0.026 | 16.158 | -0.457 |
| sells | baseline: median of the other cycles, same underlying | 38 | 0.026 | 0.158 | 8.868 |  |
| rem | median ratio x S0 | 38 | 0.053 | 0.263 | 7.684 | 0.533 |
| rem | median ratio x bb | 38 | 0.105 | 0.158 | 19.921 | -0.036 |
| rem | median ratio x range_steps | 38 | 0.053 | 0.158 | 10.079 | -0.042 |
| rem | median ratio x abs_ret | 38 | 0.026 | 0.132 | 14.5 | -0.012 |
| rem | baseline: median of the other cycles, same underlying | 38 | 0.053 | 0.105 | 8.553 |  |

### Opening long buys

| target | candidate | n | exact | within2 | mae | rho |
|---|---|---|---|---|---|---|
| lbuy | median ratio x sells | 38 | 0.026 | 0.447 | 5.158 | 0.465 |
| lbuy | median ratio x sells_j1 | 38 | 0.368 | 0.895 | 1 | 0.922 |
| lbuy | median ratio x sched | 38 | 0.053 | 0.158 | 6.737 | 0.639 |
| lbuy | median ratio x S3 | 38 | 0.026 | 0.158 | 5.763 | 0.094 |
| lbuy | median ratio x S0 | 38 | 0 | 0.237 | 4.842 | -0.088 |
| lbuy | median ratio x bb | 38 | 0 | 0.105 | 17.816 | -0.027 |
| lbuy | median ratio x range_steps | 38 | 0.079 | 0.474 | 3.263 | 0.368 |
| lbuy | baseline: median of the other cycles, same underlying | 38 | 0.447 | 0.737 | 1.579 |  |

### Gap days vs other days (median lots per cycle, minutes 0–2)

| group | cycles | body buy-back | body sell | body long buy | wing sell | wing buy | stop module | hedge other | lump salvage |
|---|---|---|---|---|---|---|---|---|---|
| stop at the open (gap day) | 4 | 29 | 11 | 5 | 18.5 | 0 | 273.5 | 87.5 | 26 |
| no stop at the open | 26 | 10.5 | 37 | 20.5 | 48 | 10 | 0 | 0 | 0 |

## 3. Coverage by class

| cls | lots | share | tier_before | tier_after | note |
|---|---|---|---|---|---|
| wing buy | 9370 | 0.1874 | 1 | 1 | gap S-L / excess rule, 94-97% exact given the body orders |
| wing sell | 9941 | 0.1988 | 1 | 1 | gap S-L / excess rule, 94-97% exact given the body orders |
| lump salvage | 952 | 0.019 | 1 | 1 | gap S-L / excess rule, 94-97% exact given the body orders |
| stop module | 3515 | 0.0703 | 1 | 1 | cumulative MTM stop; liquidates the whole book |
| sell: scheduled pair | 2105.25 | 0.0421 | 1 | 1 | met (causal) |
| sell: strangle pair | 1530.54 | 0.0306 | 1 | 1 | met (causal) |
| sell: counter-sell solo | 1753.7 | 0.0351 | 2 | 2 | met (causal) |
| sell: replacement solo | 1263.56 | 0.0253 | 3 | 3 | met with same-minute information only |
| sell: other solo | 484.025 | 0.0097 | 3 | 3 | met with same-minute information only |
| sell: far-OTM solo | 912.005 | 0.0182 | 2 | 2 | met (causal) |
| sell: extreme solo | 435.113 | 0.0087 | 3 | 3 | indicative (<150 cells) |
| sell: opening solo | 716.357 | 0.0143 | 3 | 3 | indicative (<150 cells) |
| sell: opening pair | 225.199 | 0.0045 | 3 | 3 | indicative (<150 cells) |
| sell: re-centre pair | 293.472 | 0.0059 | 3 | 3 | met with same-minute information only |
| sell: breakout pair | 146.736 | 0.0029 | 3 | 3 | indicative (<150 cells) |
| sell: other pair | 276.149 | 0.0055 | 4 | 4 | not met |
| sell: late solo | 47.893 | 0.001 | 3 | 3 | indicative (<150 cells) |
| buy-back: stop-loss | 3076.93 | 0.0615 | 2 | 2 | timing gate met |
| buy-back: roll-out | 1263.4 | 0.0253 | 3 | 2 | timing gate met: AUC 0.857 with the sale clock |
| buy-back: burst member | 1230.06 | 0.0246 | 2 | 2 | timing gate met |
| buy-back: clearance | 2713.75 | 0.0543 | 1 | 1 | rule (D0_STOP_CLEAR) |
| buy-back: take-profit | 1015.72 | 0.0203 | 2 | 2 | timing gate met |
| buy-back: other | 1009.77 | 0.0202 | 4 | 4 | timing gate not met |
| buy-back: partner | 459.634 | 0.0092 | 2 | 2 | timing gate met |
| buy-back: cycle-stop window | 292.928 | 0.0059 | 1 | 1 | rule (D0_STOP_CLEAR) |
| long buy: opening (<= 09:20) | 724 | 0.0145 | 3 | 2 | clock at 09:16:00; count ≈ sells of the 09:16 minute (rho 0.92); strike unresolved |
| long buy: intraday | 340 | 0.0068 | 2 | 2 | LOCO AUC 0.896; 111 positive cells; small sample |
| long buy: after 15:09 | 152 | 0.003 | 4 | 4 | not examined as a class |
| long sell: clearance (>= 15:14) | 1246 | 0.0249 | 1 | 1 | 84% of longs open at 15:14 are sold; a price rule adds 0.7 points |
| long sell: intraday | 1250 | 0.025 | 3 | 3 | AUC 0.831, gate not met |
| hedge other + other | 819 | 0.0164 | 4 | 4 | not examined |
| buy-back: opening minute (09:15) | 435.819 | 0.0087 |  | 3 | the stop applied at the first print, partial take; ranking AUC 0.85 but CI 0.75-0.91, boosting 0.70 |

### What is still outside 90%

| class | share of D0 lots | tier | why |
|---|---|---|---|
| sell: replacement solo | 2.5% | 3 | met with same-minute information only |
| long sell: intraday | 2.5% | 3 | AUC 0.831, gate not met |
| buy-back: other | 2.0% | 4 | timing gate not met |
| hedge other + other | 1.6% | 4 | not examined |
| sell: opening solo | 1.4% | 3 | indicative (<150 cells) |
| sell: other solo | 1.0% | 3 | met with same-minute information only |
| buy-back: opening minute (09:15) | 0.9% | 3 | the stop applied at the first print, partial take; ranking AUC 0.85 but CI 0.75-0.91, boosting 0.70 |
| sell: extreme solo | 0.9% | 3 | indicative (<150 cells) |
| sell: re-centre pair | 0.6% | 3 | met with same-minute information only |
| sell: other pair | 0.6% | 4 | not met |
| sell: opening pair | 0.5% | 3 | indicative (<150 cells) |
| long buy: after 15:09 | 0.3% | 4 | not examined as a class |

Tiers 3 and 4 total 15.1%; reaching 90% needs 5.1% more. The pieces are small and mostly need the tick path (counts, exact seconds, which lots) or same-minute information.

## 4. Adversarial read

* **The roll-out gain is real but modest and partly the label.** AUC 0.857 against a gate of 0.85, forward 0.824. It depends on a timetable learned on training cycles (a new timetable version breaks it: `D0_FULL_AUC`). It was one of four pre-registered sets; the pre-registered R-H1 set is the one gated.
* **"Other" is a residual, not a mechanism.** It is defined by the absence of other reasons and of a following sale, so a high AUC would mean predicting the absence of everything else. Its 0.80 is a ranking of "unexplained buy-backs", 2.0% of D0 lots.
* **The opening burst is explained in structure, not in counts.** The stop at the first print and the 09:16:00 long buys are clear; how many opening lots are sold, how many carried lots are taken, and which strikes the longs use are not recovered. With 26 cycles and 200 opening buy-backs the lot-level numbers are noisy (CI of the open-ratio AUC 0.75–0.91).
* **Coverage is not accuracy.** The free-run lot F1 (0.39–0.45) is unchanged: nothing found here is a rule the simulator can execute apart from the opening long count (which needs the sells it follows).
* **In-sample discovery on 32 cycles from one period;** nothing here was run on a 3-year history.

## Addendum — post-hoc steps (not pre-registered)
* Class-specific clocks (learned share of other cycles with a roll-out or an "other" buy-back in the minute ±1) were added after "other" stayed below the gate: they lift "other" to 0.808 (still not met) and leave roll-out unchanged.
* The roll-out gate is taken on the **pre-registered R-H1 set** with its own placebo (computed after the first run only for the best set).
* A bootstrap CI for the single-feature opening AUC and the fixed rounding of the count baseline were added after the first run (the baseline had been left unrounded and showed 0% exact).
* **Coverage correction:** `D0_BURST_LONG` gave the minute-0 buy-backs (cells at j = 0, outside its panel) the gate of j ≥ 1 cells; they are now a separate class (0.9% of D0 lots, tier 3).
