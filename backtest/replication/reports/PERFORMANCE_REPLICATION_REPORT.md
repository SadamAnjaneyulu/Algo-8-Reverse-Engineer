# Performance Replication Report

**Result:** the reconstructed ladder **R1** earns a net weekly Sharpe of **1.47 in sample (IS, 175 cycles)** and **0.22 out of sample (100 cycles; clean 0.20)**, and **1.36 on the screenshot's window (3 Mar 2025–27 May 2026)** with a return of **9.95 %** and CAGR **8.0 %** against the screenshot's 47.22 % / 36.88 % / Sharpe 2.19. **This is NOT a replication of 2.19**: P&L is ~⅕ of the screenshot's, behavioural agreement is partial (decision report), the Sharpe differences are inside sampling error, and the benchmark's conventions are unknown. Code executed: `performance_run.py`, `performance_summary.py`, `sensitivity.py`; independent review of the code found and I fixed one look-ahead (the pre-fix numbers, e.g. IS 1.67 / OOS 1.06, are preserved in `results/v1_lookahead_biased/` and must not be cited).

## 1. What was run
* **R1** (the reconstruction): D-1 ladder (17 slots, 26 lots per leg), strike nearest the previous-minute index close, 1 wing per body lot at ≈ 2.44 % of body price, 1.6× leg stop (entry > ₹4), −₹1.44 L cycle stop on LTP MTM, carry overnight, no new sales on D0, D0 flatten at 15:14, no lump hedge. Rules were decoded from the live ledger (Jun–Oct 2026) and **applied unchanged, untuned** to 275 complete cycles 2023–2026 (NIFTY 154, SENSEX 121).
* **R2** = R1 + D0 sales at per-slot median lots **fitted to the live window** (hypothesis-level; reported for completeness; **not** independent on 2026 data).
* Methodology (identical to the earlier backtest and to the benchmark comparison): net P&L (0.5 % slippage min ₹0.10, statutory costs, ₹20/order, one order per lot) summed per ISO week across NIFTY+SENSEX ÷ ₹2 Cr; Sharpe = mean/std(ddof 1) × √52, rf 0, no compounding; drawdown on the cycle-ordered cumulative P&L (**not** minute-level; not comparable to the earlier minute-path drawdowns).
* Split preserved: IS ≤ 2025-11-17; OOS ≥ 2025-11-18 (exposed window 22 Jun–22 Oct 2026, clean-before, clean-after). Nothing was tuned on any sample.

## 2. Results (net; `performance_summary_replication.csv`)

| Sample | Cycles | Weeks | Net P&L | Return on ₹2 Cr | Sharpe (95 % bootstrap CI) | Vol (ann.) | Max DD | Win rate | Profit factor | Orders/cycle |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|
| **R1 IS** | 175 | 106 | ₹25.4 L | 12.7 % | **1.47** (0.18 … 2.78) | 4.3 % | −2.6 % | 60.6 % | 1.61 | 207 |
| **R1 OOS** | 100 | 52 | ₹2.6 L | 1.3 % | **0.22** (−1.61 … 2.83) | 5.9 % | −5.3 % | 60.0 % | 1.07 | 208 |
| R1 OOS exposed (live window; not clean for R1) | 36 | 18 | ₹0.9 L | 0.5 % | 0.27 | 4.8 % | −3.1 % | 50.0 % | 1.07 | 208 |
| **R1 OOS clean** (uninspected) | 64 | 34 | ₹1.7 L | 0.8 % | **0.20** (−1.73 … 3.32) | 6.5 % | −4.0 % | 65.6 % | 1.07 | 208 |
| R1 OOS clean-before | 59 | 31 | ₹6.1 L | 3.0 % | 0.89 (−1.45 … 5.01) | 5.7 % | −4.0 % | 66.1 % | 1.31 | 208 |
| **R1 screenshot window** (3 Mar 2025–27 May 2026) | 124 | 65 | ₹19.9 L | **9.95 %** (CAGR 8.0 %) | **1.36** (−0.22 … 3.38) | 5.9 % | −4.0 % | 63.7 % | 1.50 | 207 |
| R1 all 275 cycles | 275 | 158 | ₹28.0 L | 14.0 % | 0.95 (−0.17 … 2.24) | 4.9 % | −5.3 % | 60.4 % | 1.36 | 208 |
| R2 IS / OOS / clean | 175 / 100 / 64 | | ₹31.5 L / ₹0.2 L / ₹4.3 L | | 1.19 / 0.01 / 0.44 | | | | | ~600 |
| R2 live window | 36 | 18 | −₹4.2 L | | −0.97 | | | | | |

Gross (before slippage/costs): R1 IS 2.29, OOS 1.03, clean 0.95, screenshot window 2.18, all 1.76 (gross P&L ₹39.6 L IS, ₹12.1 L OOS).
Capital utilisation: not measured (no margin model). Position-level attribution for the live window is in the gap analysis (P&L streams); across 2023–26 R1's net P&L splits by index: **NIFTY +₹11.7 L IS / +₹9.2 L OOS, SENSEX +₹13.7 L IS / −₹6.6 L OOS**.
Return distribution: win rate 60 %, profit factor 1.07–1.61, 16 of 275 cycles hit the cycle stop (9 IS, 7 OOS). Monthly net in the screenshot window (₹ lakh): Mar 1.5, Apr 1.1, May 2.1, Jun 6.1, Jul −0.8, Aug 3.8, Sep 4.6, Oct −0.3, Nov 2.2, Dec 5.4, Jan −2.5, Feb −0.7, Mar −4.7, Apr 1.9, May 0.2.

## 3. Against the benchmark (2.19)

| Quantity | Screenshot (unverified) | R1, same window | Verdict |
|---|---|---|---|
| Return | 47.22 % | 9.95 % net (15.8 % gross) | R1 ≈ ⅕ (net) – ⅓ (gross) of the benchmark |
| CAGR | 36.88 % | 8.0 % | |
| Sharpe | 2.19 (conventions unknown) | **1.36** net / 2.18 gross (SE 0.9) | Indistinguishable statistically; **not comparable** until the convention is known |
| Costs / capital / instruments | unknown | 0.5 % slippage, ₹20/order, ₹2 Cr, NIFTY+SENSEX | unmatched |

Two features of the live algo explain the scale gap on the evidence we have: the live book is ~2.4× larger overnight and ~12.7 k D0 lots are sold (R1 sells none), and live gross in the live window is ₹26.2 L vs R1's ₹4.4 L (ratio ≈ 6). A back-of-envelope scaling of R1 by that ratio would "reach" the benchmark's scale — **that is exactly the kind of reasoning this programme does not accept as replication**: it would be fitting the size to the target without the missing D0 rules.

## 4. Sensitivity (R1; evidence-band alternatives and stresses, NOT tuning; `sensitivity_summary.csv`; weekly Sharpe)

| Case | IS | OOS | OOS clean | OOS exposed |
|---|---:|---:|---:|---:|
| Base R1 | 1.47 | 0.22 | 0.20 | 0.27 |
| Leg stop 1.55× | 1.18 | 0.27 | 0.28 | 0.23 |
| Leg stop 1.70× | 1.30 | 0.07 | −0.11 | 0.57 |
| Cycle stop −₹1.30 L | 1.48 | 0.23 | 0.20 | 0.32 |
| Cycle stop −₹2.00 L | 1.08 | 0.23 | 0.22 | 0.24 |
| Costs ×2 | 0.93 | −0.26 | −0.23 | −0.33 |
| Slippage ×3 | 0.84 | −0.43 | −0.39 | −0.53 |
| Slippage ×6 | −0.17 | −1.31 | −1.26 | −1.41 |
| No wings (diagnostic only; the live algo does buy wings) | 2.00 | 0.80 | 0.72 | 1.00 |

Reading: the result **depends strongly on friction** (every ×2 of costs removes ≈ 0.5 of Sharpe; slippage ×3 makes OOS negative) — the live algo's real fills (marketable limits, unknown depth) are the missing measurement. The wings cost ≈ 0.5–0.6 of Sharpe in this simulator (consistent with the earlier diagnostic that far wings never paid); I do **not** propose removing them: the live algo buys them and their margin role is unmeasured.

## 5. Honest assessment
| Statement | Evidence |
|---|---|
| The decoded D-1 machinery produces a **positive** net P&L in the 2023–2025 sample it was never fitted to (IS Sharpe 1.47, CI 0.18–2.78, 9 stops in 175 cycles). | Established arithmetic; only the CI's lower bound is above 0, narrowly, and IS contains no live ledger to validate decisions against. |
| It **does not hold up OOS** (0.22; clean 0.20; SENSEX OOS −₹6.6 L). | Established; same direction as the earlier 4-leg diagnostic (clean ≈ 0), CI ±1.5. |
| It captures 17 % of live gross P&L and 0 % of D0 sales: missing rules are **the** driver of the gap. | Established (gap analysis). |
| Sharpe near 2.19 on the benchmark window requires **gross** accounting (2.18); net it is 1.36. | Established; benchmark costs unknown. |
| Behaviour + performance both consistent with the original? | **No.** Behaviour agrees partially (D-1 entries 82/67 %, D0 0–23 %); performance is ~⅕ of the screenshot's net return. Replication is **not achieved**. |

## 6. Review and integrity notes
* The independent review found the D0-open look-ahead (fixed, regression-tested). The earlier published-in-this-session figures (IS 1.67, OOS 1.06, window 2.00 net) were wrong; all numbers above are post-fix.
* Rules (ladder, wing ratio, leg-stop band, cycle stop) were read from the 2026 live window; IS and clean-before OOS are therefore out-of-time for rule discovery, but the exposed window is not clean for R1.
* Position sizes are one lot per order at the dataset's inferred lot size; NIFTY lot size changed 25→75→65 over the sample, so rupee exposure is not constant across years (same caveat as the earlier Sharpe audit).
* No Python/C++ parity exists for R1/R2 (see implementation report). No parameter was tuned on OOS.
