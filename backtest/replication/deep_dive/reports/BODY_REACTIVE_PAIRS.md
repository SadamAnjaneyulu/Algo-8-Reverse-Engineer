# Algo 8 — reactive pairs: CE+PE sells outside the fixed timetable, and the wave clock

*Investigation only. In-sample, observational (32 D-1 cycles). Plan written before the tests: `BODY_REACTIVE_PAIR_PLAN.md`. Numbers are read from `outputs/bl_react_*` / `bl_summary_react*.json`. Figure: `figures/bl_react_logic.png`.*

## 0. Answers

| Question | Answer | Evidence level |
|---|---|---|
| What is the **orange "reactive pair"**? | A **CE and a PE sold within 3 s at the same strike, outside every fixed timetable time**: 377 pairs in D-1 over 32 cycles = **11.8 pairs per cycle** (≈ 24 lots, 20% of D-1 sold lots). Every cycle has some. 77% are a single pair; at most 3 pairs in one burst. | Observed |
| Are they sold **outside the fixed timings**? | **Yes.** They appear from ~11:00 to 15:30 (11:00 → 2.2, 12:00 → 2.2, 13:00 → 2.6, 14:00 → 2.6, 15:00 → 1.4 pairs per cycle), at **any second** of the minute (uniform, p = 0.08); there is **no 15-minute timer** (only 2.4% come 14–15.5 min after the previous sell vs 3.0% by chance). | Observed |
| **What triggers them?** | **Not identified.** Only a **weak tilt** is visible: leave-one-cycle-out AUC 0.65 from the clock alone → 0.75 with market-move features → 0.71 with event history → 0.79 with everything. Book P&L (+0.012) and inventory (-0.003) add nothing. No single feature exceeds AUC 0.60, there is no threshold, and large moves (15-min move > 0.3%) produced 1 reactive pair in 218 minutes. | Observed (tilt); trigger **Unresolved** |
| **Which strike?** | **One strike off the ATM, on the side the market just moved.** Only 3.7% are at the previous-minute ATM (timetable pairs 93%); 82% are ±1 step; the strike lies on the side of the previous 15-minute move in **96%** of cases (5-min 92%). | Observed |
| What are the **wave triggers**? | **The clock only.** Each wave is a fixed clock time; waves fire in ≥ 95% of cycles whatever the market did (§5). Why a wave is at that second is not observable. | Observed; reason **Unresolved** |
| How to **know how many waves at what time**? | Use the table in §5: **33 waves per D-1** in both versions — 8 in 9:xx, 8 in 10:xx, 8 (V1) / 7 (V2) in 11:xx, then 3 / 3 / 3 (V1) or 3 / 2 / 5 (V2) in 12:xx / 13:xx / 14:xx. V1 = D-1 up to 2026-09-09, V2 = from 2026-09-16 (re-timing only, 33 waves in both). | Observed |

## 1. Definitions (locked in the plan)
* **Timetable pair** = a CE+PE pair inside a timetable cell (±3 s) of its version (from `BODY_SIZING_LOGIC.md`). **Reactive pair** = a pair (CE and PE at the same strike within ±3 s) **outside** every cell. 377 of the 1438 D-1 pairs (26%) are reactive.
* **Panel** = D-1 cycle-minutes (minute 5–373) without a timetable wave: 10,645 rows, 237 reactive-pair minutes (base 22 per 1000). Features are causal (previous minute close); blocks: clock, event history, market, book, inventory (plan).
* Pair detection is a ±3 s rule: two coincident solo sells at one strike would also be called a pair.

## 2. When (Observed)
| clock hour | reactive pairs per cycle | timetable pairs per cycle |
|---|---|---|
| 9:00 | 0.22 | 7.84 |
| 10:00 | 0.66 | 8.12 |
| 11:00 | 2.22 | 7.72 |
| 12:00 | 2.16 | 3.09 |
| 13:00 | 2.56 | 2.91 |
| 14:00 | 2.59 | 3.47 |
| 15:00 | 1.38 | 0.00 |

* Seconds-of-minute are uniform (p = 0.08). The minute within the 15-minute block is **not** uniform (p < 0.001): 18% of reactive pairs fall in the first minute of a block and 9% in the last (uniform would be 7% each) — they cluster around the 15-minute boundaries, but with no fixed second.
* **Clustering with other sells:** the reactive-pair hazard is highest right after another body sell:
| minutes since the last body sell | cycle-minutes | reactive-pair minutes | per 1000 |
|---|---|---|---|
| (0, 1] | 1166 | 61 | 52.3 |
| (1, 2] | 1032 | 26 | 25.2 |
| (2, 5] | 2576 | 43 | 16.7 |
| (5, 10] | 3091 | 55 | 17.8 |
| (10, 14] | 1476 | 24 | 16.3 |
| (14, 16] | 205 | 4 | 19.5 |
| (16, 20] | 348 | 5 | 14.4 |
| (20, 30] | 518 | 11 | 21.2 |
| (30, 60] | 231 | 8 | 34.6 |

  within a minute of the previous sell it is about 3× the base; the gap to the previous sell has median 2.9 min — they come in bursts with other sells, not on their own timer.
* **After a buy-back:** 13.4% of reactive pairs come within 60 s after a body buy-back (shifted-time chance 3.9%); at 5 min 19.4% vs 13.2%; at 15 min no excess (26.8% vs 27.8%). After a **stop-like** buy-back the excess is small (5.5% vs 2.1% at 60 s). A weak, short-lived link; not a lot-for-lot replacement (Spearman of pairs vs lots bought back in the previous 5 min = 0.10).

## 3. Which strike
* **Previous-minute ATM hit rate:** reactive 3.7%, timetable 93.2%, solo sells 18.0%. Reactive strike minus previous-minute ATM (steps): -2.0: 6%, -1.0: 46%, 0.0: 4%, 1.0: 36%, 2.0: 9%.
* **Side follows the move:** among reactive pairs whose strike differs from the ATM (n = 305), the strike side agrees with the sign of the previous spot move:
| look-back window | share (strike side vs ATM) follows the move |
|---|---|
| 1 min | 79.7% |
| 3 min | 87.5% |
| 5 min | 92.5% |
| 15 min | 96.1% |
| 30 min | 96.4% |

  A pair is therefore a **straddle shifted one strike toward the direction the index has been moving** (below the ATM after a fall, above after a rise). Both legs are sold at that one strike.
* The strike is **not** the strike of the last timetable pair (2.4%) and **not** the most-loaded strike (4.0%); 66% are strikes where the book is already short on both legs (timetable pairs: 80%), so they mostly **add to a strike already held**, one step from the ATM.

## 4. What predicts a reactive-pair minute
Leave-one-cycle-out gradient boosting (AUC; "shuffled" = that feature block permuted within cycle with all blocks otherwise in):
| model | reactive pair (AUC) | Δ vs clock only | solo sell (AUC, contrast) | buy-back (AUC, contrast) |
|---|---|---|---|---|
| clock only | 0.650 | +0.000 | 0.674 | 0.724 |
| clock + history | 0.711 | +0.061 | 0.701 | 0.830 |
| clock + market | 0.753 | +0.103 | 0.813 | 0.849 |
| clock + book | 0.663 | +0.012 | 0.718 | 0.782 |
| clock + inventory | 0.647 | -0.003 | 0.675 | 0.733 |
| all blocks | 0.788 | +0.138 | 0.817 | 0.872 |
| all blocks, history shuffled | 0.759 | +0.109 | 0.810 | 0.850 |
| all blocks, market shuffled | 0.684 | +0.034 | 0.730 | 0.835 |
| all blocks, book shuffled | 0.787 | +0.137 | 0.815 | 0.869 |
| all blocks, inventory shuffled | 0.793 | +0.143 | 0.814 | 0.870 |

* **Market block** adds +0.103; shuffling it from the full model costs 0.104. **History block** adds +0.061 (shuffling: 0.029). Book and inventory: no effect.
* For contrast, **solo sells** respond much more to the market block (+0.139); **buy-backs** to history and market (+0.106 / +0.125).
Strongest single features (D-1, AUC with cluster-bootstrap CI; permutation null maximum; chronological halves):
| feature | AUC | CI low | CI high | permutation max | half 1 | half 2 |
|---|---|---|---|---|---|---|
| age_stop | 0.597 | 0.571 | 0.622 | 0.51 | 0.626 | 0.574 |
| S_tot | 0.592 | 0.566 | 0.618 | 0.525 | 0.602 | 0.586 |
| S_PE | 0.591 | 0.57 | 0.613 | 0.522 | 0.602 | 0.581 |
| age_sell | 0.416 | 0.389 | 0.441 | 0.531 | 0.395 | 0.437 |
| age_bb | 0.58 | 0.531 | 0.614 | 0.545 | 0.584 | 0.577 |
| S_CE | 0.58 | 0.556 | 0.61 | 0.52 | 0.589 | 0.571 |
| a15 | 0.576 | 0.551 | 0.604 | 0.528 | 0.582 | 0.569 |
| n_sched | 0.573 | 0.545 | 0.598 | 0.522 | 0.584 | 0.561 |
| j | 0.568 | 0.546 | 0.593 | 0.53 | 0.578 | 0.559 |
| a3 | 0.564 | 0.535 | 0.591 | 0.524 | 0.557 | 0.57 |

* `age_stop` = minutes since the last stop-like buy-back (longer → more likely; rows with no stop-like buy-back yet are excluded from this single-feature AUC); `S_tot`, `S_CE`, `S_PE` = short lots held, which grow through the day (part clock; the inventory block adds nothing in the model); `age_sell` below 0.5 means a recent sell raises the odds. No feature passes AUC 0.60. **Decision rule (pre-registered):** the market block meets it (gain +0.10 ≥ 0.03, shuffle test, strongest feature `a15` AUC 0.576 with halves 0.58 / 0.57), and so does the history block (`age_stop`, halves 0.63 / 0.57); book and inventory do not. But the effects are small, graded and not a rule:
| |15-min spot move| (%) | cycle-minutes | reactive-pair minutes | reactive per 1000 | solo sell per 1000 |
|---|---|---|---|---|
| (0.0, 0.1] | 8021 | 168 | 21.0 | 46.8 |
| (0.1, 0.2] | 1959 | 58 | 29.6 | 82.7 |
| (0.2, 0.3] | 441 | 10 | 22.7 | 176.9 |
| (0.3, 5.0] | 218 | 1 | 4.6 | 142.2 |

  Pairs react mildly to moves up to ~0.3% and **disappear in large moves**, while solo sells keep rising. So the reactive pairs are **not** the same trigger as the solo sells (move/breakout).

## 5. The waves: exact clock times (Observed)
Waves fire at fixed clock times (seconds after 09:16:00 in `outputs/bl_react_wave_clock.csv`); every time below is one 1-lot CE + one 1-lot PE pair at the ATM (previous-minute ATM hit 93%). Fire rates: 100% of V1 cells and 90% of V2 cells fire in ≥ 95% of cycles.
| version | hour | waves | clock times (each = one 1-lot CE + one 1-lot PE pair) |
|---|---|---|---|
| V1 | 9:xx | 8 | 09:16:01, 09:16:02, 09:16:07, 09:31:00, 09:31:00, 09:46:00, 09:46:31, 09:47:06 |
| V1 | 10:xx | 8 | 10:01:10, 10:15:59, 10:16:00, 10:16:00, 10:16:58, 10:31:10, 10:46:31, 10:47:31 |
| V1 | 11:xx | 8 | 11:01:00, 11:01:10, 11:15:59, 11:16:58, 11:31:10, 11:46:00, 11:46:31, 11:47:31 |
| V1 | 12:xx | 3 | 12:01:10, 12:31:00, 12:31:10 |
| V1 | 13:xx | 3 | 13:16:00, 13:30:00, 13:45:00 |
| V1 | 14:xx | 3 | 14:00:00, 14:15:00, 14:30:00 |
| V2 | 9:xx | 8 | 09:16:01, 09:16:02, 09:16:08, 09:30:59, 09:31:00, 09:46:00, 09:46:31, 09:47:06 |
| V2 | 10:xx | 8 | 10:01:10, 10:15:59, 10:16:00, 10:16:58, 10:31:01, 10:31:10, 10:46:31, 10:47:31 |
| V2 | 11:xx | 7 | 11:01:10, 11:15:59, 11:16:58, 11:31:02, 11:31:10, 11:46:31, 11:47:31 |
| V2 | 12:xx | 3 | 12:01:10, 12:31:02, 12:31:10 |
| V2 | 13:xx | 2 | 13:31:02, 13:45:00 |
| V2 | 14:xx | 5 | 14:00:00, 14:15:00, 14:30:00, 14:31:02, 14:45:00 |

* **Count per hour:** V1 9:xx = 8, 10:xx = 8, 11:xx = 8, 12:xx = 3, 13:xx = 3, 14:xx = 3; V2 9:xx = 8, 10:xx = 8, 11:xx = 7, 12:xx = 3, 13:xx = 2, 14:xx = 5.
* **Trigger:** the clock itself. Nothing in the data (spot, premium, notional, P&L, the day's move) changes whether a wave fires; the cycle stop is the only thing known to halt the schedule (earlier paired-sell study).
* **Why those seconds / how many** cannot be observed from fills: that is the configuration of the strategy. The times are the median order time of each wave across the cycles of the version (ledger order times; jitter about ±1–2 s). Waves in the same cell are ranked within a cycle (e.g. three waves at 09:16:01, :02, :07).

## 6. Evidence register
| Claim | Label | Basis |
|---|---|---|
| Reactive pairs: 11.8 per cycle, from 11:00, any second, no 15-min timer | **Observed** | 377 pairs, 32 cycles |
| Strike one step off the ATM, on the side of the recent move (96% vs 15-min move) | **Observed** | n = 305 |
| Weak link to buy-backs (≈ 13% vs 4% within 60 s) and to other sells (bursts) | **Observed** | shifted-time null |
| Market-move and event-history features give a small, graded predictive tilt; book P&L and inventory none | **Observed** (predictive) | LOCO GB, shuffle tests |
| What triggers a reactive pair | **Unresolved** | no threshold or rule found |
| Waves: clock only; table of times | **Observed** | cell fire rates ≥ 95% |
| Why this timetable | **Unresolved** | not observable |

## 7. Limits and how this could be wrong
* **±3 s pair rule** may merge two coincident solo sells (CE and PE) triggered by the same event into a "pair"; that would make reactive pairs two solo sells at one strike one step off the ATM — the same strike regime as solo sells (solo ATM hit 18%, offset −1 for most). I cannot separate the two with second-resolution fills.
* **Minute-resolution market features:** a trigger on tick prices, the live ATM inside the minute or the order book would look like a weak tilt here.
* **Cells** (timetable windows) come from a ≥ 0.5-pairs-per-cycle cut; a reactive pair at a low-frequency timer time (< 0.5 per cycle) is counted as reactive.
* In-sample; D-1 only; no source code; features are predictive, not causal.

## 8. Files
`src/bl_react_panel.py` → `bl_react_tests1.py` / `1b` / `3` (when, timer, buy-back, strike, side) → `bl_react_tests2.py` (prediction, ~10 min) → `bl_react_waves.py` (clock times) → `bl_react_fig.py` → `make_react_report.py`. Outputs `outputs/bl_react_*`, `bl_summary_react*.json`. Tests `tests/test_bl.py` (`test_react_*`).
