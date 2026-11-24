# Why the simulator earns less than the real Algo 8 — entry, exit and sizing, and how to stop overfitting

*Exploratory diagnosis on the real log (35 cycles, Jun – Oct 2026) vs the simulator. No rule was adopted in this step. Scripts: `bl_d0x_diag.py`, `bl_d0x_book.py`, `bl_d0x_fixA.py`.*

> **Correction (2026-11-24, `LATE_D1_RULE.md`):** two conclusions below are withdrawn. (1) "Real book +16 short lots, further OTM (1.4 vs 0.5 steps), 15:15–15:29 = 14.4 lots" rests on one cycle (NIFTY D-1 16 Oct 2026, a 240-lot deep-OTM call ratio); without it: +4 lots (median +9.5), offset −0.2 steps, late sales 15:15–15:29 ≈ 6.8 lots. (2) "Fix A rejected": 97% of its −₹38k change is one stop flip (SENSEX 8 Oct, −₹7.09 lakh); on the other 18 cycles the change is −₹1.0k mean, ₹0 median — Fix A is unresolved. The overnight-book gap (₹74.9k) itself survives, but 63% of it is 2 stop flips.

## 1. The "₹56k vs ₹24.5k" premise was wrong
* The ₹56k real expiry-day figure included **4 post-auction cycles whose real log is missing a whole day** (no D-1 fills, or no D0 fills). Their "real" results are marks, not trades: 11 Aug (+₹3.0 lakh, no D-1 fills), 15 Sep (+₹4.5 lakh, no D-1 fills), 29 Sep (+₹4.9 lakh, no D0 fills), 1 Sep (−₹1.4 lakh, stopped on D-1, no D0 fills).
* On the **19 complete post-auction cycles**, real Algo 8 makes **₹25,968 per cycle** (both days). The free-running simulator makes ₹-24,804. The gap is real (₹50,772), but it is half of what the incomplete data suggested.

## 2. Where the gap comes from (complete cycles)
"D0 from real book" = the simulator's expiry-day logic started from the **real** overnight book.
| era | real (₹) | sim D0 from real book (₹) | sim free-run (₹) | gap real − free-run | of which D0 logic | of which overnight book | cycles |
|---|---|---|---|---|---|---|---|
| after | 25,968 | 49,926 | -24,804 | 50,772 | -23,958 | 74,730 | 19 |
| before | 96,054 | 66,637 | 101,352 | -5,298 | 29,417 | -34,715 | 11 |

* **Expiry-day entry / exit logic is not what loses money after the auction**: given the real overnight book it earns **more** than the real system (it gives back ₹23,958 of the gap).
* **The overnight book the simulator builds on D-1 is the problem** (₹74,730 per cycle): with the same D0 rules, a different carried book produces a very different expiry day (and a different cycle-stop path).
* Before the auction the errors run the other way and roughly cancel.

## 3. How the overnight books differ (means per cycle at the D-1 close)
| book | era | short lots | short calls | short puts | short strike, steps OTM | long lots (wings) | D-1 premium cash (₹) |
|---|---|---|---|---|---|---|---|
| real | after | 107 | 68.63 | 38.21 | 1.41 | 151 | 409,713 |
| real | before | 99.91 | 50.91 | 49.00 | 0.99 | 155 | 429,882 |
| sim | after | 90.95 | 54.21 | 36.74 | 0.54 | 130 | 381,954 |
| sim | before | 92.18 | 44.36 | 47.82 | 1.20 | 134 | 404,743 |

After the auction the real book is **larger (+16 short lots), more call-heavy, placed further out of the money (1.4 vs 0.5 steps) and carries more wings**. The extra size comes from **late D-1 selling**: real short lots per cycle 14:15–14:59 = 16.6 (simulator 13.2), 15:00–15:14 = 7.2 (3.6), **15:15–15:29 = 14.4 (1.7)**, **15:30–15:40 = 6.4 (0)** — options trade until 15:40 since the auction; the simulator's breakout window ends at 15:15 and its data end at 15:29.

## 4. Fix tested: extend the D-1 breakout window after the auction (no fitted parameter)
Decision-level check first (extended breakout fires vs real late sale minutes, ±1 minute):
| era | late_sale_minutes | extended_fires | fires_after_1515 | fires_matched | random_matched | precision | random precision |
|---|---|---|---|---|---|---|---|
| after | 93 | 29 | 16 | 22 | 13 | 0.76 | 0.45 |
| before | 45 | 8 | 1 | 7 | 1 | 0.88 | 0.12 |

End-to-end on the complete cycles:
| era | sim | cycles | real (₹) | sim (₹) | mean abs. error (₹) | spearman | stops_agree | carried short sim | carried short real | late shorts sim | late shorts real |
|---|---|---|---|---|---|---|---|---|---|---|---|
| after | base | 19 | 25,968 | -24,804 | 131,087 | 0.76 | 12 | 90.95 | 107 | 5.26 | 21.58 |
| after | fixA | 19 | 25,968 | -63,111 | 151,078 | 0.69 | 11 | 97.05 | 107 | 11.47 | 21.58 |
| before | base | 11 | 96,054 | 101,352 | 102,057 | 0.50 | 10 | 92.18 | 99.91 | 3.64 | 12.55 |
| before | fixA | 11 | 96,054 | 101,352 | 102,057 | 0.50 | 10 | 92.18 | 99.91 | 3.64 | 12.55 |

**Rejected.** Decisions move towards the real ones (late shorts 5.3 → 11.5 vs 21.6; carried book 91 → 97 vs 107) but the P&L moves away (−₹24.8k → −₹63.1k vs +₹26.0k real). Copying **how much** the real system sells late, without copying **which strikes and sides** it sells, makes things worse. The missing rule is about **strike and side selection in the late session**, not volume.

## 5. Why every fix keeps overfitting — and the protocol that stops it
**Why:** 19 complete post-auction cycles; each cycle's P&L depends on dozens of interacting decisions; any rule tuned to make those 19 P&L numbers match will fit noise. The 16 Sep – 22 Oct cycles have now been inspected cycle by cycle: they are **contaminated** as validation data.

**Protocol for every further reconstruction change (binding from now):**
1. **Fit decisions, never P&L.** Targets are order-level: which minute sells, which side, which strike offset, how many lots, which lots are bought back and when (thousands of observations, not 19).
2. **Teacher-forced scoring.** Each day is simulated from the **real** state at its start (real D-1 open book, real carried book for D0), so a rule is judged on its own decisions, not on compounded earlier errors.
3. **Cross-validation by cycle.** Any constant estimated from data is estimated leave-one-cycle-out; a rule is kept only if its decision accuracy holds out-of-fold.
4. **Complexity budget.** At most one new parameter per rule, each with a market-structure or log-level reason written down before testing.
5. **P&L only at the end, once.** Free-run P&L fidelity is checked after decisions are frozen; it can reject a rule, never tune one.
6. **Clean hold-out from the future.** The 35 real cycles are now development data. The next ≥ 30 real cycles (forward log) are locked as the validation set before anyone looks at them.
7. **Ledger.** Every variant tried is recorded (`outputs/d0x/`, this report) and counted in the Deflated Sharpe / PBO of the final strategy.

## 6. What to do next
* **Late D-1 strike / side rule:** build the decision table for real late sales (minute, side, strike offset from ATM and from the last sale, book imbalance, premium) and fit it teacher-forced with leave-one-cycle-out — this is the most likely missing piece (Section 3).
* **Extend the data cache to 15:39** (raw option bars exist) so the 15:30–15:40 session can be simulated at all.
* **Collect the forward log** for the clean hold-out; until then no reconstruction change can be validated, and the battery verdict (NO-GO) stands.
