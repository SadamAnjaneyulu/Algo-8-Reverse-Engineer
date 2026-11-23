# Algo 8 — D0 solo selling after the counter-sells: a hidden strangle timetable, and the replacement stream

*Plan `D0_REPL_PLAN.md` (with an addendum for the post-hoc steps and one error caught on the way). In-sample discovery on D0, 24 cycles with minutes after the opening window (14,762 minute cells). Figure: `figures/bl_d0e_summary.png`. Scripts `bl_d0e_*.py`.*

## 0. Result
**1. About 15% of all D0 sell lots are a second scheduled timetable that we had mislabelled as solo selling.** In the SENSEX version before 16 Sep, at recurring seconds, the system sells **a call one step above ATM and a put one step below ATM within about a second of each other**: a strangle. 626 such pairs, **1,252 lots = 15.0% of D0 sell lots**, in 10 cycles. The pair detector had required the same strike, so these legs fell into "other solo", "counter-sell", "replacement" and "opening solo". *Observed.*

| | Result | Label |
|---|---|---|
| **Strikes** | CE at ATM + 1 step and PE at ATM − 1 step (ATM of the previous minute's close): exact in **83%** of 626 pairs; the legs are 1 s apart or less in 95%. | Observed |
| **Clock** | The same seconds in every cycle (Figure A). Timetable learned on one half of the cycles and scored on the other: precision **95%**, recall **84%**, F1 **0.89** (pair timing ±3 s). The learned timetable has 47–49 waves. | Observed |
| **AUC gate (strangle cells)** | **0.984** (CI 0.973–0.992), within-cycle 0.961, forward **0.959**; the clock alone gives 0.900; placebo 0.46. **Gate met.** | Observed |
| **Where it was hiding** | 709 of the 1,105 "other solo" lots (64%), plus 206 counter-sell, 172 replacement, 104 opening-solo and 46 extreme-solo lots. It is 36% of all solo lots of that version. | Observed |
| **Counter-sell result survives** | With the strangle legs removed from the outcome the causal counter-sell AUC is **0.884** (CI 0.851–0.912), within-cycle 0.891, forward 0.911 (`D0_CAUC.md`: 0.882). | Observed |
| **Replacement solo** | AUC **0.916** (CI 0.893–0.927), within-cycle 0.876, forward **0.847**: **gate met.** It is an **afternoon stream inside buy-back clusters**, not a one-for-one replacement (§2). | Observed |
| **Other solo that is left** | 396 lots (4.8% of D0 sells). Causal AUC **0.811** (CI 0.768–0.855), within-cycle 0.810: **gate not met.** | Observed; Unresolved |
| **Far-OTM roll-out** | Not judged. 12 cycles, mostly SENSEX before 16 Sep; the pooled AUC (0.958) is a cycle-level effect (placebo 0.85, within-cycle 0.78) and no test cycle has one. | Unresolved |

## 1. The strangle timetable (post-hoc finding)
* **How it was found.** The "other solo" slice repeated at the same clock seconds across cycles (6.9× the shifted-time chance, pooled; the recurrence is concentrated in SENSEX before 16 Sep, so only 13 of 22 cycles are above chance), while the market conditions that drive other solo sales were absent (spot fresh extreme in 2.6% of them). In SENSEX before 16 Sep, 73% had an opposite-right sale within 3 s. In all 304 pairs examined first, the call strike was exactly two steps above the put strike.
* **Detection.** Near-simultaneous CE/PE solo sales with different strikes: strike gap in steps (CE strike minus PE strike), SENSEX before 16 Sep: **2 steps in 626 of 674 near-simultaneous pairs**; no other gap has more than 17.

| und | version | dk | pairs | cycles |
|---|---|---|---|---|
| SENSEX | V1 | 1.000 | 17 | 7 |
| SENSEX | V1 | 2.000 | 626 | 10 |
| SENSEX | V1 | 3.000 | 8 | 4 |
| SENSEX | V1 | 6.000 | 11 | 2 |

* **Strikes** are the live ATM ± 1 step on the previous minute's close; 83% exact.
* **Timetable** (learned on each half, SENSEX before 16 Sep; first clock times): 09:16:04;09:16:09;09:16:12;09:29:00;09:30:59;09:31:06;09:46:02;09:46:07;09:53:00;09:59:00;10:00:58;10:16:00;10:29:00;10:29:58;10:31:00;10:46:00;10:59:00;11:01:58;11:11:28;11:16:00;11:29:00;11:31:00;11:46:00;11:53:00;11:59:00;12:11 …

## 2. Replacement solo: what it is
* **Not one-for-one.** After a same-right buy-back the sale is at the **same strike as the bought lot in 18%** of cases, the same as for a random same-right solo sale (18%); further out of the money in 35% (26% by chance). The premium sold ÷ premium bought has a median 1.01 against 1.60 by chance, but is spread widely (quartiles 0.58–1.98; within ±10% in 13%). Lots sold ÷ lots bought, median 2.0. *Observed.*
* **Which buy-backs are followed by a same-right sale** (within 60 s, against the same times shifted ±10 and ±15 minutes; kept at ≥1.5× both):

| reason | events | share_with_same_right_sale_0_60s | null_10min | null_15min | ratio_10 | ratio_15 | kept |
|---|---|---|---|---|---|---|---|
| 1 cycle-stop window | 30 | 0.400 | 0.033 | 0.083 | 12.000 | 4.800 | True |
| 2a clearance 15:10-15:13 | 160 | 0.131 | 0.188 | 0.084 | 0.700 | 1.556 | False |
| 2b clearance 15:14 | 83 | 0.120 | 0.205 | 0.102 | 0.588 | 1.177 | False |
| 2c clearance 15:15+ | 382 | 0.044 | 0.131 | 0.249 | 0.340 | 0.179 | False |
| 3 stop-loss | 1395 | 0.173 | 0.130 | 0.128 | 1.331 | 1.346 | False |
| 4 take-profit | 612 | 0.270 | 0.234 | 0.194 | 1.150 | 1.392 | False |
| 5 partner | 191 | 0.518 | 0.254 | 0.194 | 2.041 | 2.676 | True |
| 6 roll-out | 789 | 0.819 | 0.320 | 0.357 | 2.558 | 2.291 | True |
| 7 burst member | 409 | 0.000 | 0.099 | 0.119 | 0.000 | 0.000 | False |
| 8 other | 606 | 0.000 | 0.186 | 0.183 | 0.000 | 0.000 | False |

  * **Partner legs** (52% against about 20–25%) and the **cycle-stop window** follow. The "roll-out" row is definitional (the type is a same-right sale within 60 s after the buy-back); "burst" and "other" are 0 by construction for the same reason.
  * **Stop-loss (1.33× / 1.35×), take-profit and clearance buy-backs are not** followed by a same-right sale more than chance. So the stop-loss "replacement" is not a rule.
* **When.** 59% of replacement lots are at 14:00 or later (other solo: 9%). Replacement sales happen where buy-backs of both rights are recent (same right in 93%, other right in 87% of its minutes, against 36% of all minutes) and the sold premium is at its low in 48% (9% of all minutes).
* **What separates replacement from other solo** (market and book state only): AUC 0.867, driven mostly by the **time of day** (the minute index alone costs 0.16 AUC when shuffled; next features 0.009). By my rule (CI lower bound above 0.65) every slice is "distinct", but this is largely a time-of-day difference.
* **AUC gate** (cells with a replacement sale):

| variant | cells | auc | lo | hi | within_cycle_auc |
|---|---|---|---|---|---|
| V1 causal (bars to j-1, orders before minute j) | 435 | 0.916 | 0.893 | 0.927 | 0.876 |
| V2 + the minute's own bar | 435 | 0.938 | 0.913 | 0.948 | 0.912 |
| V3 + same-minute buy-backs (partly definitional) | 435 | 0.978 | 0.971 | 0.983 | 0.971 |
| placebo (V1 features shuffled within cycle) | 435 | 0.672 | 0.550 | 0.740 | 0.480 |

  Forward (first 16 → last 8 cycles): V1 0.847. With the strangle legs removed from the outcome: 0.907 (forward 0.845). Adding ladder-state features (post-hoc) changes nothing (0.918).

## 3. Other solo and the far-OTM roll-out
| slice | variant | cells | auc | lo | hi | within_cycle_auc |
|---|---|---|---|---|---|---|
| other solo | V1 causal (bars to j-1, orders before minute j) | 717 | 0.883 | 0.859 | 0.901 | 0.837 |
| other solo | V2 + the minute's own bar | 717 | 0.921 | 0.907 | 0.932 | 0.895 |
| other solo | V3 + same-minute buy-backs (partly definitional) | 717 | 0.929 | 0.916 | 0.938 | 0.903 |
| other solo | placebo (V1 features shuffled within cycle) | 717 | 0.694 | 0.631 | 0.725 | 0.526 |
| far-OTM solo | V1 causal (bars to j-1, orders before minute j) | 238 | 0.958 | 0.851 | 0.977 | 0.783 |
| far-OTM solo | V2 + the minute's own bar | 238 | 0.959 | 0.865 | 0.976 | 0.792 |
| far-OTM solo | V3 + same-minute buy-backs (partly definitional) | 238 | 0.963 | 0.902 | 0.980 | 0.802 |
| far-OTM solo | placebo (V1 features shuffled within cycle) | 238 | 0.853 | 0.769 | 0.928 | 0.480 |

* **Other solo (before relabelling)** looks like it passes (V1 0.883), but its forward check is 0.799 and most of the signal is the strangle clock. Adding the clock feature lifts it to 0.917 (forward 0.913); once the strangle legs are taken out, what is left scores 0.811.
* **Far-OTM roll-out:** after a same-right buy-back 64% of its lots are sold at a farther strike (`D0_SELL_TYPES.md`). It is concentrated in a few cycles, so the AUC cannot be separated from the cycle.

## 4. What this settles and what it leaves
* **Settled (Observed):** SENSEX before 16 Sep has a strangle timetable that explains 15% of D0 sell lots (AUC 0.98, timetable F1 0.89); the counter-sell AUC survives its removal; replacement solo is rankable at AUC 0.92 (forward 0.85) as an afternoon stream within buy-back clusters.
* **Not settled:** the remaining other solo (396 lots, AUC 0.81); the far-OTM roll-out; why the replacement stream sells at a premium similar to what was bought back; what the strangle is for (the data show the rule, not the reason).
* **Corrections to earlier D0 reports:** the "SENSEX V1: 12 scheduled waves" of `D0_SELLS.md` describes only the straddles; its main scheduled stream is this strangle. The "unexplained 30%" of `D0_SELL_TYPES.md` shrinks by 709 lots here, and 206 counter-sell, 172 replacement and 104 opening-solo lots were strangle legs.

## Caveats
* In-sample discovery, one-minute bars, 24 cycles, one forward split. Post-hoc: the strangle detection, timetable and relabel (labelled in the plan addendum).
* The strangle timetable is learned from the same cycles it is scored on only through the out-of-fold halves (parity); the AUC clock feature uses other cycles only.
* The detector's strike-gap rule (2 steps) is itself a finding of this step, so the 626 pairs are selected by it; the strike rule's 83% is therefore conditional on that selection.

## Run order
`bl_d0n_panel.py` → `bl_d0e_repl.py` (~4 min) → `bl_d0e_more.py` (~3 min) → `bl_d0e_clock.py` (~2 min) → `bl_d0e_strangle.py` → `bl_d0e_final.py` (~3 min) → `make_d0e_report.py`.
