# Algo 8 — are the unexplained (sub-1.2×) buy-backs triggered by a loss in ₹ or % of capital?

*Investigation only (no simulator change, no alpha). In-sample, observational (31 cycles with a D-1 log). Plan written before the tests: `BODY_CLOSE_CAPITAL_PLAN.md`. Every number is read from `outputs/bl_book_*` / `bl_summary_book*.json`. Figure: `figures/bl_capital_logic.png`. Capital = ₹2 crore as stated in `Info.txt` (not verified); ₹1 lakh = 0.05% of capital.*

## 0. Answer

| Question | Answer | Evidence level |
|---|---|---|
| Is a **loss amount (₹)** or **% of capital** the trigger of the sub-1.2× buy-backs? | **Not supported.** The book P&L *level* is a weak, non-monotone correlate (median book P&L at a residual D-1 buy-back = -0.07 lakh = -0.035% of capital; only 5% of them occur with the book ≤ −₹1 lakh). No loss level produces a step in the buy-back rate (§3). | Observed |
| Then is there a trigger **other than premium level**? | **Yes, something associated with a very recent adverse move — D-1 only.** The residual buy-backs go with a **fast rise in the lot's own premium / a fast adverse move of the underlying in the last 1–5 minutes** (AUC 0.78–0.79 for the lot's last-minute premium change; the 12 earlier variables alone reach 0.71, adding the short-horizon changes 0.85). The association fades with the look-back window (AUC 0.76 at 3 min → 0.50 at 60 min) (§4). | Observed (predictive); mechanism **Unresolved** |
| Is it a *book-level* loss? | **No more than a lot-level or underlying move:** book mark-only changes add only +0.011 AUC once lot/underlying short-horizon changes are in. The three variables are collinear, so they cannot be separated with minute data. | Observed |
| Is there a capital-based **cycle stop**? | **Yes, but it is a different rule and it is not what moves these buy-backs.** The first `s_` (stop) order of a cycle comes at a causal book P&L of about **-1.17 lakh (IQR -1.28 to -1.10; -0.59% of capital)** in 12 cycles; sub-1.2× buy-backs sit within 60 s of an `s_` order about twice as often as chance on D0 (§6) and cannot be tested on D-1 (one cycle with an `s_` order). | Observed (consistent with earlier U8) |
| D0? | **No loss or move signal** (leave-one-cycle-out gain ≤ 0.012 AUC); D0 buy-backs below 1.2× are clock-driven. | Observed |
| Is it a trailing stop (rebound from the trough)? | **No** (AUC 0.65–0.67; adds +0.004 over the short-horizon changes). | Observed (post-hoc check) |

So: **the unexplained buy-backs are not a "−₹X" or "−X% of capital" rule.** What I can say is that on D-1 they are more likely right after a quick adverse move, with no clean threshold; the residual rule is still **Unresolved**.

## 1. Definitions (locked in the plan)
* **Book P&L** = fill-priced cash flows of *all* modules (body, hedge, stop, lump, manual) since the first D-1 fill of the cycle + mark-to-market of every contract-level net position at the **previous completed minute close** (D0 minute 0 at the D0 open); lot sizes NIFTY 65 / SENSEX 20; no costs/slippage/settlement; contracts missing from the chain (mean 0.12% of open lots) use their last fill price. Check: in the 21 cycles with both days that end flat the final mark equals the realised cash P&L exactly — this validates the cash accounting only; it does **not** validate the marks, which I compare with the earlier U8 stop levels instead (§2).
* Variants: **B_total** (since cycle start), **B_day**, **drawdown** from the running peak, **B_CE / B_PE**, **own-right / other-right** P&L, and 5/15/30-minute changes. Added after the first results (post-hoc, labelled): **mark-only** changes (current net positions × price change, free of execution-price gaps), the lot's own premium change, the adverse underlying move, and the trough rebound.
* Targets (D-1): **A** = all sub-1.2× buy-backs on the cheapest-open-entry reference; **B (residual)** = those not within 3 s of a ≥1.5× buy-back (the part the previous report could not explain). Contract-minute unit: D-1 contract-minutes with cheapest-entry ratio < 1.2×.
* **Decision rule (fixed before running):** a level is a *trigger* only if (i) the hazard steps ≥ 3× between adjacent bins, (ii) adding the variables lifts leave-one-cycle-out AUC by ≥ 0.03 with the within-cycle permutation maximum below the gain, (iii) (i) replicates in chronological halves.

## 2. The cycle stop, for scale
First `s_` order of each cycle (12 cycles), book state at the previous minute close:
| quantile | book P&L (₹ lakh) | % of ₹2 crore | P&L since day start (₹ lakh) | drawdown from peak (₹ lakh) |
|---|---|---|---|---|
| 10% | -1.91 | -0.95% | -1.81 | 1.31 |
| 25% | -1.28 | -0.64% | -1.17 | 1.41 |
| 50% | -1.17 | -0.59% | -0.65 | 1.63 |
| 75% | -1.10 | -0.55% | 0.00 | 2.53 |
| 90% | -1.04 | -0.52% | 0.00 | 3.11 |

This is a little shallower than the earlier U8 result (≈ −₹1.30…−1.44 lakh at the close of the decision minute, a non-causal mark), as expected for previous-minute marks, and consistent with it. It is **0.5–0.65% of ₹2 crore**, below the stated "1% of capital" (₹2 lakh) — the stated percentage is not what fires. Cycle count is small (12); the level is read from causal minute marks. 9 of the 12 cycles fall between −1.35 and −1.0 lakh; the others are -2.55, -1.98, -0.56 lakh (data-resolution effects around the D0 open gap are likely, as noted in U8, but not tested here).

## 3. Is the book-loss *level* a trigger?
Median book state at each buy-back, by class (₹ lakh; negative = loss). Control for "how often is the book this bad": share of all D-1 cycle-minutes with the book ≤ −0.5 lakh = 7.9%, ≤ −1.0 lakh = 1.3%.
| day | class | orders | book P&L med (₹L) | day P&L med (₹L) | drawdown med (₹L) | Δ15 min med (₹L) | own-right P&L med (₹L) | other-right P&L med (₹L) | share ≤ -0.5L | share ≤ -1.0L |
|---|---|---|---|---|---|---|---|---|---|---|
| D-1 | middle (1.2-1.5x) | 236 | -0.22 | -0.22 | 0.41 | -0.12 | -0.42 | 0.14 | 28% | 14% |
| D-1 | stop-like (>=1.5x) | 650 | -0.06 | -0.06 | 0.18 | -0.04 | -0.77 | 0.52 | 21% | 2% |
| D-1 | sub-1.2x co-closed | 156 | -0.52 | -0.52 | 0.7 | -0.28 | -0.33 | -0.38 | 51% | 11% |
| D-1 | sub-1.2x residual | 282 | -0.07 | -0.07 | 0.27 | -0.09 | 0.08 | -0.28 | 17% | 5% |
| D0 | middle (1.2-1.5x) | 1390 | 1.04 | 0.18 | 0.74 | -0.05 | -0.18 | 0.71 | 9% | 1% |
| D0 | stop-like (>=1.5x) | 2466 | 0.91 | 0.0 | 0.84 | -0.14 | -0.88 | 1.31 | 12% | 7% |
| D0 | sub-1.2x co-closed | 792 | 1.29 | 0.34 | 0.8 | -0.08 | 2.07 | -1.14 | 10% | 2% |
| D0 | sub-1.2x residual | 4687 | 1.59 | 0.74 | 0.43 | 0.07 | 1.85 | -0.74 | 5% | 1% |

* D-1 residual buy-backs: median book P&L -0.07 lakh; 17% at ≤ −0.5 lakh and 5% at ≤ −1.0 lakh (control 8% / 1.3%): over-represented in bad states, but most occur nowhere near a loss. Stop-like (premium-driven) buy-backs are the ones where the *own right* is deep in loss (-0.77 lakh) and the other right is ahead.
* **Hazard by book P&L level (D-1, per 1000 cycle-minutes):**
| book P&L (₹ lakh) | cycle-minutes | residual (B) events | residual per 1000 | all sub-1.2× (A) per 1000 | stop-like (S) per 1000 |
|---|---|---|---|---|---|
| ≤ -1.0 | 155 | 10 | 64.5 | 90.3 | 38.7 |
| -1.0 to -0.5 | 770 | 17 | 22.1 | 41.6 | 40.3 |
| -0.5 to -0.25 | 610 | 28 | 45.9 | 62.3 | 44.3 |
| -0.25 to 0 | 3375 | 63 | 18.7 | 21.9 | 18.7 |
| 0 to 0.25 | 4728 | 36 | 7.6 | 9.3 | 11.8 |
| 0.25 to 0.5 | 827 | 10 | 12.1 | 19.3 | 37.5 |
| 0.5 to 1.0 | 736 | 7 | 9.5 | 9.5 | 13.6 |
| > 1.0 | 547 | 10 | 18.3 | 20.1 | 21.9 |

  Rates are higher when the book is down, but non-monotone (the −1.0 to −0.5 bin is *lower* than −0.5 to −0.25) and the same pattern holds for the premium-driven stop-like class; no bin steps ≥ 3× in a way that identifies a level. **Rule (i) is not met for the level.**
* **Threshold-crossing event study** (first minute the book ≤ −L; buy-backs in the next 15 min ÷ the cycle's own base rate):
| first crossing of -L (₹ lakh) | cycles crossing | A all sub-1.2× (obs/expected) | B residual (obs/expected) | S stop-like (obs/expected) |
|---|---|---|---|---|
| 0.25 | 18 | 5.5 | 4.9 | 6.3 |
| 0.5 | 12 | 8.2 | 5.8 | 8.2 |
| 0.75 | 7 | 5.6 | 3.7 | 8.3 |
| 1.0 | 5 | 5.1 | 4.0 | 2.2 |

  The residual rate rises after a loss crossing, but so does the stop-like rate by a similar factor: a market move that hurts the book also moves premiums. The crossing alone cannot separate "loss trigger" from "move trigger".
* **Predictive value of the book variables (leave-one-cycle-out gradient boosting on D-1/D0 contract-minutes with cheapest-entry ratio < 1.2×):**
| day | target | 12 earlier variables | + book P&L (gain) | permuted-book max gain | + book + stop-activity controls | baseline + controls only |
|---|---|---|---|---|---|---|
| D-1 | A | 0.763 | 0.844 (+0.081) | -0.009 | 0.862 (+0.099) | 0.801 (+0.038) |
| D-1 | B | 0.711 | 0.803 (+0.092) | +0.002 | 0.820 (+0.109) | 0.741 (+0.030) |
| D0 | A | 0.846 | 0.858 (+0.012) | +0.002 | 0.857 (+0.011) | 0.857 (+0.011) |
| D0 | B | 0.857 | 0.859 (+0.002) | -0.000 | 0.860 (+0.003) | 0.861 (+0.004) |

  On D-1, adding the 10 book variables lifts AUC by +0.092 (residual target) with the permutation maximum at +0.002, and it survives controlling for how many stop-like buy-backs just occurred (+0.109 vs controls-only +0.030). So **something in the book variables matters on D-1 — rule (ii) is met by the variable set**; §4 shows it is the *change* variables, not the level, and that they are not specific to the book. On D0 the gain is +0.002: nothing.

## 4. What does go with the buy-backs: a very recent adverse move (D-1)
**Which look-back?** AUC of the own-right P&L change (mark-based, residual target; < 0.5 = recent loss goes with a buy-back):
| window (min) | AUC of own-right P&L change | CI low | CI high | loss-direction AUC (1 − AUC) |
|---|---|---|---|---|
| 3 | 0.236 | 0.187 | 0.278 | 0.764 |
| 5 | 0.259 | 0.212 | 0.316 | 0.741 |
| 10 | 0.334 | 0.286 | 0.39 | 0.666 |
| 15 | 0.364 | 0.317 | 0.412 | 0.636 |
| 20 | 0.395 | 0.339 | 0.455 | 0.605 |
| 30 | 0.451 | 0.395 | 0.52 | 0.549 |
| 45 | 0.479 | 0.435 | 0.547 | 0.521 |
| 60 | 0.499 | 0.451 | 0.559 | 0.501 |

The signal is concentrated in the last 3–5 minutes and disappears by ~45–60 minutes — a *rate of loss*, not an accumulated loss.

**Artifact control.** A P&L change that includes earlier buy-backs' execution-vs-mark gaps could predict its own continuation (a dripped buy-back episode). The mark-only change (current net positions × price change) avoids it (AUC; own right is loss direction when < 0.5):
| mark-only P&L change over … | D-1 all | D-1 no body buy-back on the right in prev 5 min | D-1 no stop-like in cycle in prev 15 min | D0 all |
|---|---|---|---|---|
| own right, 1 min | 0.210 | 0.210 | 0.209 | 0.505 |
| own right, 3 min | 0.240 | 0.253 | 0.202 | 0.529 |
| own right, 5 min | 0.272 | 0.295 | 0.200 | 0.534 |
| own right, 15 min | 0.384 | 0.392 | 0.239 | 0.573 |
| other right, 3 min | 0.725 | 0.725 | 0.771 | 0.475 |
| other right, 5 min | 0.693 | 0.687 | 0.762 | 0.472 |
| other right, 15 min | 0.583 | 0.575 | 0.703 | 0.459 |

Excluding minutes where the same right had a body buy-back in the previous 5 minutes, or where any stop-like buy-back occurred in the cycle in the previous 15 minutes, does not remove it (own 3-min 0.25 / 0.20). D0 shows none (0.53).

**Lot, underlying or book?** Univariate AUC on D-1 contract-minutes (residual target):
| variable (D-1, residual target) | AUC | CI |
|---|---|---|
| lot's own premium change, 1 min (%) | 0.776 | 0.738–0.834 |
| lot's own premium change, 3 min (%) | 0.776 | 0.734–0.817 |
| lot's own premium change, 5 min (%) | 0.742 | 0.666–0.788 |
| lot's own ₹ change per lot, 1 min | 0.788 | 0.737–0.841 |
| adverse underlying move, 1 min | 0.747 | 0.705–0.794 |
| adverse underlying move, 3 min | 0.746 | 0.699–0.803 |
| own-right book mark change, 1 min (loss direction = 1 − AUC) | 0.212 | 0.174–0.258 |
| own-right book mark change, 3 min | 0.228 | 0.178–0.283 |
| other-right book mark change, 1 min | 0.756 | 0.722–0.790 |
| other-right book mark change, 3 min | 0.755 | 0.712–0.791 |
| lot's own premium change, 15 min (%) | 0.658 | 0.602–0.709 |

Leave-one-cycle-out gradient boosting:
| model (D-1, residual target) | LOCO AUC | Δ |
|---|---|---|
| baseline | 0.711 | +0.000 |
| + lot/underlying short-horizon | 0.847 | +0.136 |
| + book mark-only | 0.845 | +0.134 |
| + both | 0.858 | +0.147 |
| permute lot/underlying block (shuffle one block, all features in) | 0.838 | -0.019 vs full |
| permute book block (shuffle one block, all features in) | 0.842 | -0.015 vs full |

The lot's own last-minute premium change is the single best variable (0.788), and the underlying's 1-minute adverse move is close (0.747); the book's own-right mark change (loss direction 0.788) is equivalent. Adding the book block on top of the lot/underlying block gains +0.011; shuffling either block alone costs about 0.019 / 0.015. **They carry the same information; minute data cannot tell them apart.**

**Shape (lot premium change over 3 min, residual buy-backs per 1000 contract-minutes):**
| lot premium change over 3 min (%) | contract-minutes | events | all per 1000 | first half per 1000 | second half per 1000 | NIFTY per 1000 | SENSEX per 1000 |
|---|---|---|---|---|---|---|---|
| ≤ -2 | 31566 | 30 | 1.0 | 1.0 | 0.9 | 1.3 | 0.8 |
| -2 to -0.5 | 9985 | 2 | 0.2 | 0.4 | 0.0 | 0.0 | 0.3 |
| -0.5 to 0 | 3595 | 3 | 0.8 | 1.6 | 0.0 | 0.0 | 1.5 |
| 0 to 1 | 6291 | 9 | 1.4 | 2.1 | 0.7 | 0.7 | 2.0 |
| 1 to 2 | 6239 | 7 | 1.1 | 1.2 | 1.0 | 1.9 | 0.5 |
| 2 to 3 | 5553 | 9 | 1.6 | 1.4 | 1.9 | 1.3 | 1.9 |
| 3 to 5 | 7523 | 30 | 4.0 | 4.5 | 3.5 | 1.7 | 5.6 |
| 5 to 8 | 6259 | 32 | 5.1 | 4.2 | 6.0 | 5.0 | 5.2 |
| > 8 | 5044 | 86 | 17.0 | 13.0 | 20.2 | 14.2 | 18.2 |

| lot premium rise over 3 min ≥ (%) | contract-minutes | events | hazard | lift vs base | recall |
|---|---|---|---|---|---|
| 0.5 | 33860 | 167 | 4.9 per 1000 | 1.9 | 80% |
| 1.0 | 30618 | 164 | 5.4 per 1000 | 2.1 | 79% |
| 2.0 | 24379 | 157 | 6.4 per 1000 | 2.5 | 75% |
| 3.0 | 18826 | 148 | 7.9 per 1000 | 3.1 | 71% |
| 5.0 | 11303 | 118 | 10.4 per 1000 | 4.1 | 57% |
| 8.0 | 5044 | 86 | 17.0 per 1000 | 6.7 | 41% |

* Graded rise, no single threshold: about 17 per 1000 when the lot's premium rose > 8% in 3 minutes versus about 1 per 1000 when flat or falling; it replicates in both chronological halves (split at expiry 2026-08-25) and in NIFTY and SENSEX. Even in the top bin only ~1.7% of contract-minutes end in a residual buy-back, so this is a tilt, not a rule. **Rule (i) holds only as a graded relationship; I do not call it a threshold.**
* Rupee version (own-right mark loss over the last 3 minutes, D-1, minutes with no body buy-back on that right in the previous 5):
| own-right 3-min mark loss ≥ ₹ | % of ₹2 crore | right-minutes | events | hazard | lift vs base | recall |
|---|---|---|---|---|---|---|
| 5,000 | 0.025 | 3465 | 79 | 22.8 per 1000 | 3.7 | 60% |
| 10,000 | 0.05 | 1386 | 51 | 36.8 per 1000 | 6.0 | 39% |
| 20,000 | 0.1 | 289 | 19 | 65.7 per 1000 | 10.8 | 14% |
| 30,000 | 0.15 | 83 | 7 | 84.3 per 1000 | 13.9 | 5% |
| 50,000 | 0.25 | 10 | 0 | 0.0 per 1000 | 0.0 | 0% |
| 75,000 | 0.375 | 2 | 0 | 0.0 per 1000 | 0.0 | 0% |

  The sizes involved are ₹10–30 thousand (0.05–0.15% of capital) — far below any plausible stop-loss amount — and the hazard saturates (no events at ≥ ₹50 thousand; very few minutes).
* Residual hazard by 15-min book P&L change (cycle-minute, D-1) is graded and replicates in both halves and when stop-like activity is excluded: from 3.3 per 1000 (15-min change 0 to +0.1 lakh) to 14.0 (−0.1 to 0) to 46.6 (−0.25 to −0.1) to 105.8 (−0.5 to −0.25 lakh) (steps 4.3×, 3.3×, 2.3×; the rate then plateaus: 105 per 1000 at −1.0 to −0.5). The first step (a 15-minute change of ₹10–25 thousand, 0.05–0.125% of capital) is far smaller than any loss-limit size.

## 5. Trailing-stop reading (post-hoc check)
A trailing stop would trigger on a rebound from the lowest price since entry.
| variable (D-1, residual target) | AUC | CI |
|---|---|---|
| trough rebound, % (price ÷ lowest close since oldest open lot entry − 1) | 0.647 | 0.578–0.699 |
| trough rebound, ₹ per lot | 0.674 | 0.626–0.723 |
| lot's own premium change, 3 min (comparison) | 0.776 | 0.720–0.821 |

Rebound from the trough is weaker than the 3-minute premium change and adds +0.047 AUC to the earlier variables versus +0.127 for the short-horizon changes; together +0.004 over short-horizon alone. **Not supported.**

## 6. Cycle stop adjacency and D0
* Sub-1.2× buy-backs within 60 s of an `s_` order: D0 26% vs shifted-time chance 12% (n = 223, 10 cycles with `s_`); residual 18% vs 11%; stop-like 47% vs 30%. D-1 has an `s_` order in one cycle only: no test possible.
* D0 sub-1.2× buy-backs sit on the *profitable* right (median own-right P&L +1.85 lakh vs other right -0.74) and book-level variables add +0.002 AUC: D0 is the clock-driven phase (earlier finding). Not analysed further.

## 7. Evidence register
| Claim | Label | Basis |
|---|---|---|
| A ₹ or %-of-capital **level** is not the trigger of the sub-1.2× buy-backs | **Observed** (not supported) | hazard by level non-monotone, no ≥3× identifying step; most events far from any loss |
| Cycle stop fires at ≈ −₹1.17 lakh (IQR 1.10–1.28), 0.59% of ₹2 crore | **Observed** (causal minute marks) | 12 cycles |
| D-1 sub-1.2× buy-backs follow a fast adverse move (lot premium / underlying / right-book mark, last 1–5 min); graded, replicates in halves and both underlyings | **Observed** (predictive) | 82,055 contract-minutes, 208 residual events |
| …and this is a book-level loss rather than a lot or underlying move | **Not separable** | collinear; book adds +0.011 |
| Trailing stop from the trough | **Not supported** | AUC 0.65–0.67, adds +0.004 |
| D0: no loss/move signal | **Observed** | GB gain ≤ 0.012 |
| The actual rule for the residual | **Unresolved** | tilt only; no threshold found |

## 8. Limits, post-hoc items, how this could be wrong
* **Minute marks.** The lot's premium may have moved within the decision minute; "last 1–3 minutes" is a lagged proxy for a faster, possibly tick-level, trigger (a spike filter or momentum condition would look like this). The residual may be an intra-minute premium-ratio trigger the minute close hides.
* **Definition of the P&L the algorithm uses is unknown** (realised only, per-basket, premium-based, margin-based, with or without hedges). I tested cumulative LTP mark with all modules, split by right and day; a different definition could behave differently. A capital trigger **between** those definitions is not excluded, but none of the tested ones produce a level effect.
* **Collinearity.** Lot premium, underlying move and right-book mark change move together; the report states the three are not separable rather than choosing one.
* **Post-hoc items:** mark-only changes, lot/underlying features, trough rebound, window scan, right-level hazard. The pre-registered list (plan) covered: levels, drawdown, 5/15/30-min changes, own/other-right loss, own strike-position ₹ loss (pre-registered level variables, D-1 residual target: own strike-position ₹ loss AUC 0.57, per-lot ₹ loss 0.60, book level 0.36 (loss direction 0.64), drawdown 0.66; all CIs in `bl_book_auc.csv`), and the cycle-stop adjacency.
* **Capital** is stated, not verified; "₹X" levels are reported in ₹ so another capital can be applied.
* **Five cycles with missing D-1/D0 logs** are not in the cumulative P&L; in-sample, 31 cycles; self red-team only; this is reconstructed behaviour, not the source logic.
* **Plan deviation:** GB for contract-minutes used all four targets; the crossing event study uses a base rate, not a shifted-time null; the "own strike-position ₹ loss" level test sits in the AUC table only.

## 9. Files
`src/bl_book_mtm.py` → `bl_book_tests1.py` (stop level, classes, hazard, crossing, `s_`) → `bl_book_tests2.py` (GB, 4 targets) → `bl_book_tests3.py` / `4` / `5` / `6` (right level, shape, window, mark-only control) → `bl_book_tests7.py` / `8` (lot vs underlying vs book; shape) → `bl_book_tests9.py` (trailing) → `bl_capital_fig.py` → `make_capital_report.py`. Outputs `outputs/bl_book_*`, `bl_summary_book*.json`. Tests `tests/test_bl.py` (`test_book_*`).
