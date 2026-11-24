# D0 sizing treatments for the free-run simulator (A: drawn, B: fixed median, C: scaled) — plan

*Written before any run. Follows `D0_QTY.md` (lot counts of solo sells and buy-backs are only associated with features, no rule) and your decision to run **all three** treatments. In-sample discovery on the D0 of the 30 cycles with both logs; every fitted part is refit on each split's training cycles (as in `D0_FREE_RUN`).*

## Requirement lock
* **Objective:** show what each sizing treatment does to the free-running D0 reconstruction (lot match, size of the book, cycle profit and loss), scored on cycles not used to fit it, and how much a smaller account changes it.
* **What changes:** only the **lot counts** of (i) solo sell events and (ii) buy-back events, and a global **scale**. **Timing and triggers stay exactly as in `bl_d0_fr.py`** (timetable waves, D-1 breakout pairs, ladder, counter-sell accumulator, θ/tp stop rule, hedge controller, 15:14 clearance, cycle stop).
* **Unchanged and rule-exact:** scheduled pair lots (1+1), hedge wave = gap S−L, wing release ≤ long excess, clearance = all, opening wings (training median), carried book from the real D-1 orders.

## Treatments
| code | solo sell events (ladder and counter-sell events as generated) | buy-back events (a minute with ≥ 1 lot at the stop or take-profit level on a right) |
|---|---|---|
| **M0 reference** | as now: ladder lots = steps crossed (cap 10) or 1 per the fitted flag; counter-sell lots = ⌊r × simulated other-right buy-backs⌋ | every lot whose own minute high ≥ θ × entry or low ≤ tp × entry |
| **A draw** | lots drawn from the **empirical distribution of real solo-sell lots per (minute, right) cell given ≥ 1 solo lot**, training cycles only | lots drawn from the **empirical distribution of real buy-back lots per cell given ≥ 1 body buy-back (before 15:10, before the stop)**, training cycles only; capped at the lots open on that right |
| **B fixed** | **1 lot** (training median) | **2 lots** (training median), capped at lots open |
| **C scale s** | overlay on M0, A and B, s ∈ {1, 0.5, 0.25, 0.1} | |

* **Which lots a smaller or different buy-back takes** (A, B): the lots at the stop level first, then the rest, **highest minute-high ÷ entry first**. This is **my assumption**: `D0_BUYBACKS` found no rule for which lots a burst takes (a burst takes a median 33% of the lots above its lowest ratio). Sensitivity: the same run with oldest-first (FIFO) for A and B, reported next to it.
* **Scale mechanics (C):** carried lots kept with probability s (positions in other modules thinned binomially), carried cash × s, wave and breakout lots × s with unbiased random rounding (a pair keeps CE = PE), solo and buy-back counts × s with unbiased random rounding, opening wings × s, **cycle stop level × s** (so the stop stays the same share of the book). Hedge, clearance and release are exact on whatever book results.
* **What "your capital" means:** s = your capital ÷ the real system's, which is **not known to me** (only the book's notional, ₹16–22 crore per right at peak). s is a parameter; results for the four values are the answer, not one chosen value.
* **Randomness:** A and every s < 1 are random. **10 repetitions** (seeds 0–9); numbers are averages over repetitions per cycle, with the between-repetition spread reported. M0 and B at s = 1 are deterministic.
* **Splits:** s = 1 on all four splits of `D0_FREE_RUN` (OOF halves pooled, forward A, forward B). **s < 1 on the OOF halves only** (30 cycles), to limit cost.

## Integrity check (before anything else is read)
M0 at s = 1 with the new code must reproduce the stored `bl_d0_fr_orders.pkl.gz` exactly (same lots per cycle and class and minute). If it does not, the new code is wrong and is fixed before any treatment is compared.

## Metrics (fixed; no others)
1. **Lot F1** per class and overall, ±1 minute matching exactly as `D0_FREE_RUN` (s = 1 only; random thinning makes F1 at s < 1 meaningless).
2. **Lots per class**, simulated ÷ (s × real).
3. **Peak short lots per right** per cycle: simulated vs s × real, median ratio and Spearman across cycles.
4. **Cycle cash profit and loss**, D-1 + D0, before costs: simulated vs s × real. Spearman across cycles, median of (sim − s × real) in ₹ lakh, ratio of the sums, share of cycles with the same sign. *Real* = cash of all real orders of both days plus any position still open at the last bar valued at that bar's close. *Simulated* = the simulator's cash after liquidation at the stop or the 15:14 clearance, at the simulator's own prices (previous-minute close for sells, minute prices for the rest). **No commissions, no slippage, no tax. The real fills sit in the lower part of the bar for sells and the upper part for buys (`D0_QTY.md` A4); the simulator does not model that, so its profit and loss is on the favourable side by construction.**
5. **Cycle-stop agreement:** cycles where the real and simulated stop both occur / only one.
6. Cycle-bootstrap 95% CIs for: F1(A) − F1(M0), F1(B) − F1(M0), P&L Spearman(A) − Spearman(M0), P&L Spearman(B) − Spearman(M0).

## Hypotheses that can fail
* **H1** A raises overall lot F1 over M0 (CI of the difference above 0).
* **H2** A or B raises P&L fidelity (Spearman across cycles) over M0.
* **H3** A is not better than B: if the drawn distribution does not beat "always the median", the randomness adds noise without information.
* **H4** profit and loss scales with s: median of P&L(s) ÷ (s × P&L(1)) within 0.8–1.2, and the between-repetition spread grows as s falls (the cost of a small account is rounding noise, not a different strategy).

## Rules for reading the results
* The treatments are **sizing assumptions inside a simulator**, not recovered rules. A result better than M0 does not mean the real system sizes this way.
* **Not testable:** the real system's capital or margin, fills inside the bar, costs, the tick path that sets drip counts.
* No tuning of anything on test cycles. Any step added after seeing results goes in an addendum, labelled **post-hoc**.
* The three treatments are only compared with each other and with the real D0 of the same cycles; none of this is a forward or unseen-year test.

## Addendum — written after the first results (not pre-registered)
* **Scale mechanics changed after the first run.** The first run thinned the carried book and then scaled every drawn count again. For counter-sells and for A/B buy-backs the event rate already fell with the thinned book, so quantities shrank by about s² (M0 body-sell lots at s = 0.1 were 44% of s × real). That run is **discarded**. The scale is now **lot-identity thinning**: every decision (triggers, event sizes, which lots) runs at the real-size book; each lot carries a keep flag (probability s, a scheduled pair kept as a pair, drawn when the lot is created); cash, hedge, peak and the cycle stop (level × s) use kept lots only; opening wings × s with unbiased rounding. s = 1 is unchanged.
* **Integrity check compares lots aggregated by class, right, minute and strike**, not row by row (the original records one row of n lots, the new code n rows of 1 lot). Passed: 49 of 49 test cycles identical, in both versions of the code.
* **Null comparator added post-hoc** (after seeing a P&L Spearman of 0.81): hold the carried book to the 15:14 clearance and trade nothing on D0. It tells how much of the P&L ranking is just the market and the carried book.
* **Real P&L context added post-hoc:** mean, spread and a t-statistic of the real cycle P&L, to say what the simulated P&L is being compared with.
* A and B were also run with the **oldest-first** lot selection on the 10 / 1 repetitions the plan allowed (5 for A).
