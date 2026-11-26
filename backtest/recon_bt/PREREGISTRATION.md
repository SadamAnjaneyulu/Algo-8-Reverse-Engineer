# Reconstructed-Algo-8 performance backtest on the 3-year dataset: preregistration

*Written 2026-11-26 **before any P&L was computed**. Nothing is committed. Everything here is a historical simulation of OUR RECONSTRUCTION of Algo 8, not of the original system (see section 8).*

## 1. What is tested
The frozen reconstruction, **free-running** (mode F: no real orders anywhere): D-1 engine (B1, `one_lot_v2`) -> simulated carry -> D0 engine (forward configuration: clearance 15:14, all decoded rules, enforce risk guard), run on **all 275 complete weekly cycles** of the pinned dataset (commit `eb40973...`, NIFTY 154 / SENSEX 121, D0 2023-11-09 to 2026-11-12; the cycle list, status and exclusions are those of `backtest/results/cycle_feasibility.csv`; nothing is dropped silently).

## 2. The hard stop (user decision, 2026-11-26)
A **cycle hard stop on cumulative mark-to-market** (D-1 + D0, all positions, minute-level marks; liquidate everything, no more trading that cycle). Three levels, fixed now, no others: **S200 = Rs 2.0 lakh (the requested level)**, S125 = Rs 1.25 lakh (the frozen reconstruction level), NONE (reference only). `Info.txt` describes Algo 8 as "4% carry-forward SL and 1% of capital on expiry day"; a 1% stop on Rs 2 crore is Rs 2 lakh, but that is a D0-only/carry structure that earlier work did not reproduce (D0-only scope rejected). The cumulative-cycle stop is the one implemented and tested here; the Info.txt structure is not.

## 3. Splits (fixed now)
| Name | Definition | Role |
|---|---|---|
| DEV | D0 2026-06-22 .. 2026-10-22 (the window the rules and constants were reconstructed on) | **in-sample** for the reconstruction |
| PRE | D0 before 2026-06-22 (2023-11 to 2026-06) | out-of-sample backwards in time (rules reconstructed later; **not** a test of fidelity, a test of whether the same rules would have earned money earlier) |
| POST | D0 2026-10-23 on | the only out-of-sample window after the freeze |
| USER_IS / USER_OOS | the earlier backtest's boundary: IS D0 <= 2025-11-17, OOS D0 >= 2025-11-18 (embargo cycle dropped) | reported for continuity with `backtest/reports` |
Also reported: per calendar year, per quarter, per instrument, per cycle.

## 4. Conventions (fixed now)
* **Quantities:** the engines' own lots (D-1 timetable/ladder/breakout sizes; D0 fitted waves), with the **actual lot size of each session** (inferred in the dataset: NIFTY 50/25/75/65, SENSEX 10/20; `lot_d1` is used for the whole cycle because `lot_d0` is unreadable in 5 cycles). Sensitivity: P&L re-scaled to the 2026 lot sizes (NIFTY 65, SENSEX 20), i.e. constant notional-ish.
* **Rules applied to 2023-2025 are the 2026 rules** (timetable version V1 before 2026-09-16, V2 after; D0 constants = the frozen all-cycle fit). This is an extrapolation; the real system's history before June 2026 is unknown.
* **Fills (gross reference prices):** D-1: the engine replay's price at the fill second; D0: sells at the previous-minute close (the engine's entry price), rule buy-backs at the touch (stop: max(minute open, theta x entry); take-profit: min(open, tp x entry)), all other events at the minute close; the cycle stop and the clearance at the minute close. Flat at the end by construction (asserted; any residual would be cash-settled at the 15:29 spot close intrinsic and reported).
* **Costs:** exactly the earlier backtest's model (`bt/account.py`: slippage max(Rs 0.10, 0.5% of price) against every order, Rs 20 brokerage per order, exchange/SEBI/stamp/GST, STT by date). Its status is stated there as partly unverified (Algo 8's broker terms are unknown). Stress: 3x costs. D0 aggregated events are split at the freeze quantity (an order-count assumption; real D0 logs have more single-lot orders, so brokerage here is **under**stated).
* **Capital for % metrics:** the stated Rs 2 crore (`Info.txt`), constant, no compounding. **It is not a verified balance, and the engines' positions are far larger (hundreds of lots) than Rs 2 crore of margin could carry**; margin is not modelled. Win rate and Sharpe do not depend on it; drawdown % does. Rupee figures are primary.
* **Metrics:** one return per expiry cycle aggregated to ISO weeks, Sharpe/Sortino annualised sqrt(52), risk-free 0 (`bt/metrics.py`); win rate = share of cycles with net > 0; max drawdown from the minute-level equity path (net of costs); profit factor; expectancy; worst/best cycle; top-5 share of wins; CVaR(5%) of cycle P&L.

## 5. Overfitting controls (fixed now)
No parameter is tuned on P&L. The only choice among alternatives is the stop level, and the three levels are reported side by side, never selected by in-sample P&L. Evidence for "S200 is better than S125" requires **all** of: (a) paired per-cycle difference (S200 - S125) has a week-clustered bootstrap 95% interval above 0 in PRE; (b) the sign of the mean difference is positive in DEV, PRE and POST separately; (c) the improvement does not come from <= 5 cycles (positive after removing the 5 largest differences); (d) no larger worst-cycle loss or max drawdown beyond 25% worse than S125. Otherwise the stop levels are reported as "not separable on this evidence".
Robustness of the strategy itself (descriptive grade, counted, no re-fitting): **R1** PRE Sharpe > 0 with the 95% block-bootstrap lower bound > 0; **R2** PRE net > 0 for NIFTY and for SENSEX separately; **R3** >= 60% of PRE calendar quarters positive; **R4** PRE net > 0 after removing the 5 best cycles; **R5** PRE net > 0 at 3x costs; **R6** POST net > 0; **R7** DEV-to-PRE degradation reported (Sharpe PRE / Sharpe DEV). Verdict = count of R1-R6 passed.

## 6. Pipeline validation (before any result is interpreted)
The data builder must reproduce the existing 2026 caches on the 32 development cycles (arrays equal), the D-1 replay with the stop off must reproduce B1's order count (9,035) and legacy lot-level F1 0.6878, and the D0 part on those cycles must behave as Gate 6 mode F (same engine, frozen parameters instead of out-of-fold ones, so equality is not expected there; differences reported).

## 7. Deliverables
Per-cycle ledger, summary tables (all / NIFTY / SENSEX x splits x stop level), equity and drawdown curves, bootstrap intervals, a short report, tests. The complete Python algo as a clean package and then C++ are the next stages and are **not** part of this step.

## 8. Limits stated in advance
The reconstruction reproduces the real 2026 order stream only partially (keys F1 0.74 D-1, 0.42 D0); the real system's P&L is unknown; margin/capital and the real size are unknown; fills are minute-bar conventions; 2023-2025 behaviour of the real system is unknown; rules were reconstructed on DEV; costs partly unverified; the dataset has partial/missing cycles excluded (275 of 319).
