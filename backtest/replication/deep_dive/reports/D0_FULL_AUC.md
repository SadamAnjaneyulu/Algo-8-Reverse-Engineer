# Algo 8 — D0 selling, every selling type, on cycles the model has not seen

*Plan `D0_FULL_AUC_PLAN.md` (addendum lists what changed after the first results). In-sample discovery on D0: 26 cycles with minutes before their stop, 14,962 minute cells (cycle × minute × right, 09:15 to the minute before the stop or 15:10), 7,704 of the 8,336 D0 sell lots fall in these cells. **Everything below is scored on cycles that were not used to fit that score:** the model and the clock timetables are learned on training cycles only. Figure: `figures/bl_d0f_summary.png`. Scripts `bl_d0f_*.py`.*

## 0. Result
**Whole D0 selling is reproduced at AUC 0.89–0.93 on unseen cycles as long as the timetable version has been seen** (worst of 30 random splits 0.846, worst single cycle 0.817). Per selling type, 4 of 13 pass the strict causal rule (scheduled pair, strangle pair, counter-sell solo, far-OTM solo; 62% of all D0 sell lots) and 3 more pass once the same-minute information is allowed; 5 small types are indicative only and 1 is not met.

| Whole D0 selling ("any sell" in the minute, on the right) | Causal | With the minute's own bar and same-minute buy-backs |
|---|---|---|
| **S1 leave-one-cycle-out** (every cycle predicted by a model that never saw it) | **0.914** (CI 0.893–0.931), within-cycle 0.912 | 0.950 |
| **S2b forward in time**, inside each timetable version (first two thirds → last third) | **0.929** | 0.963 |
| **S4 thirty random halves** of the cycles, mean ± sd (worst split) | **0.887 ± 0.023** (0.846) | 0.923 ± 0.022 (0.881) |
| **S3b new timetable version, three new-version cycles added** | **0.882** | — |
| **S3 new timetable version, no adaptation** (train before 16 Sep, test from 16 Sep) | **0.628** | — |
| Placebo (features shuffled within each cycle), S1 | 0.491 (within 0.500) | — |

* **Cycle by cycle (S1):** median AUC 0.930, worst 0.817, 88% of the 24 scored cycles at or above 0.85 (Figure C).
* **The one case that fails is a new timetable.** The system's clocks changed on 16 Sep. A model trained only on the old clocks scores 0.63 on the new cycles; after seeing **three** cycles of the new version it is back to 0.88. This is the real risk for "new data": a changed timetable has to be re-learned, and about three cycles are enough. *Observed.*
* **Type assignment:** among the 3,601 cells with a sale, the predicted type (the highest one-vs-rest probability) is the true type in **73%** of cells (always guessing the commonest type: 34%). Scheduled pairs and strangles are recognised in 96–97% of their cells; counter-sell 63%, replacement 55%, other solo 47%; re-centre, breakout, extreme and far-OTM are rarely picked (7–33%). *Observed.*

## 1. Every type
| type | lots_share | cells | S1_causal | S2b_causal | S4_mean_causal | S1_plus_minute | S4_mean_plus_minute | verdict |
|---|---|---|---|---|---|---|---|---|
| scheduled pair | 0.207 | 1283 | 0.997 | 0.998 | 0.971 | 0.997 | 0.971 | met (causal) |
| strangle pair | 0.150 | 781 | 0.983 | 0.973 | 0.977 | 0.990 | 0.986 | met (causal) |
| counter-sell solo | 0.172 | 523 | 0.888 | 0.901 | 0.877 | 0.962 | 0.956 | met (causal) |
| replacement solo | 0.124 | 343 | 0.902 | 0.842 | 0.888 | 0.980 | 0.978 | met with same-minute information only |
| other solo | 0.048 | 258 | 0.816 | 0.834 | 0.798 | 0.914 | 0.903 | met with same-minute information only |
| far-OTM solo | 0.089 | 225 | 0.875 | — | 0.926 | 0.921 | 0.948 | met (causal) |
| extreme solo | 0.043 | 145 | 0.926 | 0.903 | 0.917 | 0.992 | 0.991 | indicative (<150 cells) |
| opening solo | 0.070 | 77 | 0.998 | 0.998 | 0.999 | 0.999 | 0.999 | indicative (<150 cells) |
| opening pair | 0.022 | 42 | 0.999 | 0.999 | 0.990 | 0.999 | 0.990 | indicative (<150 cells) |
| re-centre pair | 0.029 | 164 | 0.856 | 0.819 | 0.772 | 0.930 | 0.874 | met with same-minute information only |
| breakout pair | 0.014 | 90 | 0.798 | 0.701 | 0.781 | 0.902 | 0.885 | indicative (<150 cells) |
| other pair | 0.027 | 176 | 0.920 | 0.659 | 0.773 | 0.916 | 0.784 | not met |
| late solo | 0.005 | 16 | 0.989 | 0.976 | 0.978 | 0.991 | 0.984 | indicative (<150 cells) |

*S1 leave-one-cycle-out, S2b forward inside each version, S4 mean of 30 random cycle halves. "—" = no test cycle has that type. "Plus minute" adds the minute's own spot and premium bar and the buy-backs of the same minute; for the types whose label is itself a buy-back within 60 s (re-centre, counter, replacement) that is partly definitional.*

* **Passing causally (4 types, 62% of lots):** scheduled pair, strangle pair, counter-sell solo, far-OTM solo. Replacement solo is at 0.902 (S1) and 0.888 (S4) but 0.842 in the forward test, which has only 33 positive cells; under the strict rule that puts it in the next group.
* **Passing only with same-minute information (3):** replacement solo, other solo, re-centre pair.
* **Indicative only (<150 cells, 5):** extreme solo, opening solo, opening pair, breakout pair, late solo; their AUCs are high where the clock decides them (opening) and noisy otherwise.
* **Not met (1):** other pair.
* **The types that fall short are small and noisy:** replacement solo, other solo, extreme solo, opening solo, opening pair, re-centre pair, breakout pair, other pair, late solo together are 38% of D0 sell lots. The three small pair types (re-centre, breakout, other pair) have 90–176 cells and swing by ±0.1 between random halves; as one group ("event pairs") they reach 0.899 (S1), 0.866 (S2b), 0.790 (S4 mean).

## 2. What carries the AUC
| outcome | learned clock features + time position only | market, book and past buy-backs only (no clock features) |
|---|---|---|
| any D0 sell | 0.841 | 0.853 |
| breakout pair | 0.746 | 0.769 |
| counter-sell solo | 0.568 | 0.885 |
| event pairs (re-centre + breakout + other pair; post-hoc group) | 0.882 | 0.886 |
| extreme solo | 0.542 | 0.927 |
| far-OTM solo | 0.903 | 0.882 |
| late solo | 0.989 | 0.987 |
| opening pair | 0.999 | 0.999 |
| opening solo | 0.998 | 0.998 |
| other pair | 0.930 | 0.907 |
| other solo | 0.648 | 0.810 |
| re-centre pair | 0.805 | 0.850 |
| replacement solo | 0.713 | 0.901 |
| scheduled pair | 0.997 | 0.934 |
| strangle pair | 0.979 | 0.972 |

*(leave-one-cycle-out, causal; all causal features together are in §1.)*
* **Whole selling:** the learned clock + time position alone gives 0.84 and market, book and past buy-backs alone 0.85; together 0.91. They are complementary.
* **Timetable types** (scheduled pair, strangle, opening, late) are carried by the **learned clock** (0.98–1.00 alone).
* **Market-driven types** (counter-sell, replacement, extreme) are carried by **market, book and past buy-backs** (0.89–0.93 alone); the clock alone is at 0.54–0.71.
* **Other solo** is the weakest type either way (0.81 with everything, 0.65 clock only).

## 3. What this does and does not show
* **Observed:** a single causal model with learned timetables ranks the minutes of D0 selling at AUC 0.91 on unseen cycles, 0.93 forward in time inside a version and 0.89 on average over random halves, and the types that carry 62% of D0 sell lots are individually at or above 0.85.
* **Not shown:** lots, strikes and seconds. This is a ranking of minutes and a type label for them; the order-level reconstruction is `D0_FREE_RUN.md` (lot F1 about 0.4).
* **Not met:** the four small/noisy types (38% of lots) under the strict causal rule; a **new timetable version** without a few cycles to re-learn it.
* **Optimism:** the types (including the strangle), the far-OTM cut and several features were found after looking at all 26 cycles. The unseen-cycle numbers protect against fitting a model to a cycle, not against the structure having been chosen with all cycles in view. A real test needs new cycles scored with everything frozen now.

## Caveats
* Cells with a sale are 24% of all cells, so PR-AUC is far lower than AUC; the ranking is strong, a hard threshold would not be precise.
* Per-cycle AUCs use the 24 cycles with at least 5 positives. Three cycles that stop out before 09:16 have no cells.
* The "plus minute" variant is a convention of the D-1 work; it is not knowable ahead.

## Run order
`bl_d0f_panel.py` → `bl_d0f_auc.py` (~6 min, one thread per worker: `OMP_NUM_THREADS=1`) → `bl_d0f_abl.py` (~2 min) → `make_d0f_report.py`.
