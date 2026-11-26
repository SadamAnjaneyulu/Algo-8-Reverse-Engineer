# D0: roll-out and "other" buy-backs, and the opening burst — plan

*Written before the tests below. Builds on `D0_BB_TYPES`, `D0_BURST_LONG`, `D0_QTY`, `D0_HEDGE`, `D0_STOP_CLEAR`. In-sample discovery on D0 (panel of `bl_d0w_panel`: 25 cycles, 14,910 minute cells (cycle × minute × right, j ≥ 1) for Part R; the 30 cycles' opening minutes for Part O). Every score is leave-one-cycle-out (LOCO) or forward.*

## Goal and what "pass" means (locked)
* **Part R:** try to lift the timing ranking of **roll-out** (AUC 0.842, CI lower bound 0.812) and **other** (0.79) buy-backs to the same gate as the other types: LOCO AUC ≥ 0.85 with cycle-bootstrap lower bound > 0.82, forward ≥ 0.80, placebo of the **same feature set** < 0.65.
* **Part O:** decode the opening burst (09:15–09:17): what is bought back, how many, what is sold and bought afterwards, in which order and how large. Gates: lot or cell AUC ≥ 0.85 for selection and timing; a count or size rule is "found" if it fits ≥ 60% exactly **or** cuts the mean error ≥ 20% below the best baseline with ρ ≥ 0.5 (as in `D0_QTY_PLAN`).
* **No tuning to pass.** Every feature below has a stated reason; thresholds are fitted on training cycles only. A class that does not pass stays below the gate, and the coverage table is recomputed from the tests.

## What the exploration showed (descriptive, before this plan; not findings)
* **Roll-out is defined by a *future* sale** (a same-right body sale within 60 s after the buy-back), and by chance about 29% of buy-backs have one. At decision time the sale is not known, so the label mixes a buy-back reason with a coincidence. **Other** is the residual of the precedence rules: 90% D0-origin, median price ÷ entry 1.01, median hold 32 minutes, 45% between 14:26 and 15:10, 64% solo-sold.
* **Opening (09:15 = minute 0):** 366 buy-back lots in minute 0 (309 carried, median price ÷ entry 1.55); 421 body-sell lots in minute 0 and 628 in minute 1; 146 + 536 long-buy lots in minutes 0–1; wing releases 1,123 lots in minute 0 and stop-module lots 1,096 (cycles that stop at the open). Among carried lots at the open, the take rate rises with price ÷ entry from 2–4% below 1.0 to 53% at 1.4–1.6, lot-level AUC about 0.85 on the minute-0 prices. Opening sells (6–42 lots per right, every cycle) are uncorrelated with the opening buy-backs (ρ −0.05); long buys per right are 6–14 lots in every cycle (ρ 0.46 with the opening sells).

## Part R — roll-out and "other"
**R0 label audit.** For roll-out: the share of buy-back cells with a same-right sale within 60 s *by chance* (buy-back times shifted ±10 min, clock kept); the excess over chance by hour. For other: lot profile by hour, ratio, age, strike distance, entry class.

**Hypotheses (each with a decision-time feature set; all bars to j−1, orders strictly before the minute):**
* **R-H1 Sale clock.** A roll's sale often coincides with the scheduled timetable. Features: the learned share of the other training cycles (same underlying × version × right) that sold in this minute, the next minute and the previous minute (±0), as in `D0_FULL_AUC`. *If supported:* roll-out AUC rises by ≥ 0.01 with the CI of the paired gain above 0.
* **R-H2 Decayed lots and age.** "Other" lots are cover-backs of decayed or aged lots: lots at ≤ 0.5, ≤ 0.3, ≤ 0.2 of entry; minimum and mean price ÷ entry; oldest, newest, mean lot age in minutes; minutes to 15:10 (a taper into the clearance).
* **R-H3 Two stages.** P(roll-out) ≈ P(buy-back in the cell) × P(same-right sale in this or the next minute), the second stage trained with the sale-clock features. *Test:* AUC of the product against the single-stage model.
* **Sets:** ALL of `D0_BURST_LONG` (E + lot state + clock) as the reference; + R-H1; + R-H2; + R-H1 + R-H2; the product.
* **Tolerance outcome (reported separately, not a gate):** roll-out or other in this minute **or the next**. It is a different, coarser class (a one-minute timing tolerance, as in the lot F1 matching); it does not change the status of the minute-level class.

## Part O — the opening burst
* **O1 Which carried lots are bought back at the first print.** Lot level (carried lots at the open, cycles without a stop at the open): single-feature and LOCO-boosting AUC (price ÷ entry at the open, the high of minute 0, ITM depth at the open, entry price, strike distance, lot type); the threshold rule "take every lot with minute-0 high ÷ entry ≥ θ" with θ fitted on training cycles (F1, precision, recall); ranking by loss and precision@m.
* **O2 How many.** Per (cycle, right): lots taken vs the number of lots at or beyond θ, vs the number at or beyond 1.2, vs carried lots; exact fit, error, ρ against the median baseline.
* **O3 Opening sells.** Per (cycle, right): lots sold in minutes 0–2 = scheduled-wave lots (the timetable of `D0_SCHED_RULE`, learned out of fold) + remainder; the remainder against candidates: lots bought back at the open, carried shorts, carried longs, minute-0 range and return in steps, underlying; LOCO ratio fits; exact, error, ρ.
* **O4 Opening long buys.** Per (cycle, right): lots vs sells in minutes 0–2, sells in minute 1, carried shorts after the buy-backs, a constant per underlying; LOCO fits as above. (Strike: not re-tested; `D0_BURST_LONG` found no rule.)
* **O5 Sequence.** Median seconds after 09:15:00 and after the first body order for: buy-backs, stop-module orders, wing releases, body sells, long buys, wing buys; whether the order of components is the same in every cycle.
* **O6 Gap days.** Cycles with a stop at the open vs without: what differs in the sequence (the stop module liquidates, then the body keeps selling in 9 of 11 cycles, `D0_STOP_CLEAR`).

## Rules for reading the results
* Fixed gradient-boosting settings (200 iterations, depth 3, lr 0.05, min leaf 50, L2 1.0); no tuning on a test cycle; thresholds fitted per fold.
* Any step added after seeing results goes in an addendum labelled **post-hoc**.
* **Not testable here:** the tick path (what sets counts and seconds inside a minute), the first-print order of events within a second, the real system's capital.
* **Coverage correction.** `D0_BURST_LONG` gave the 95 burst-member lots bought back in minute 0 the ranking gate of cells at j ≥ 1. They were not in that panel. The coverage table is recomputed with the minute-0 buy-backs as their own class (0.9% of D0 lots).
