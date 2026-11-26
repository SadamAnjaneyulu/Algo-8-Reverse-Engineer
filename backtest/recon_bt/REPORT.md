# Reconstructed Algo 8: performance backtest on the 3-year dataset (S200 = Rs 2.0 lakh hard stop)

*2026-11-26. Preregistered before any P&L (`PREREGISTRATION.md`). 275 weekly cycles (NIFTY 154, SENSEX 121), D0 2023-11-09 to 2026-11-12, free-running D-1 + D0 engines, costs and slippage included, capital stated as Rs 2 crore (not verified). Nothing is committed. **This tests our reconstruction of Algo 8, not the original system.***

## Result first
* **With the Rs 2 lakh stop (S200): net Rs 200.5 lakh over 275 cycles, win rate 68%, Sharpe 2.33, max drawdown Rs -24.9 lakh.** NIFTY and SENSEX are shown separately below.
* **Is 2L better than 1.2L? Not demonstrated.** Aggregate P&L is higher at 2L (+Rs 24.8 lakh) and the drawdown smaller, but the gain is **concentrated in a handful of cycles** (without the 5 biggest it turns -11.1 lakh), its week-bootstrap interval includes 0, and it is **negative in the 5 post-freeze cycles**. Rule fixed in advance: not supported.
* **No stop at all earns the most in this simulation (Sharpe 3.98) and has the smallest drawdown in rupees**: the stops realise losses that later recover, and they cannot stop gap losses (the worst cycle with a stop, Rs -13.5 lakh, is identical at 1.25L and 2L and is worse than the worst cycle without any stop, Rs -10.1 lakh: a stop that triggers after a gap or on a dip that later recovers can lose more than holding). The real system's stop exists for tail protection that this 3-year sample only partly contains.
* **Calibration against the real trade export (32 development cycles): at 2L the simulated gross P&L is 1.04x the real one with a per-cycle correlation of 0.74; at 1.25L it is 0.46x; with no stop 2.24x.** This is in-sample, 3 preregistered levels only, and it is evidence about the simulator, not proof that the real stop is 2L.
* **Overfitting verdict:** the rules were reconstructed on Jun-Oct 2026 (36 cycles = DEV). The other 234 older cycles (PRE) were never used: the strategy stays profitable there for NIFTY and SENSEX separately, at 3x costs and without its 5 best cycles (all of R1-R5 pass at every level), so this is **not** an artefact of the development window. The 5 post-freeze cycles (POST) are too few to judge and are negative at S125/S200. **But "profitable in simulation" is not "the real algo earned this"**: sizes, fills and rules before June 2026 are extrapolations (section 7).

## 1. Headline: S200, by instrument and period
| Scope | Period | Cycles | Net P&L (Rs lakh) | Win rate | Sharpe [95% CI] | Max DD Rs lakh (% of 2 cr) | Profit factor | Worst cycle (lakh) | Stop rate |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ALL | ALL_PERIODS | 275 | 200.5 | 68% | 2.33 [1.3, 3.7] | -24.9 (-7.3%) | 2.01 | -13.5 | 21% |
| ALL | PRE | 234 | 188.9 | 70% | 2.60 [1.4, 4.0] | -24.9 (-7.3%) | 2.22 | -13.5 | 19% |
| ALL | DEV | 36 | 19.9 | 58% | 1.96 [0.3, 4.0] | -7.4 (-3.4%) | 1.73 | -3.1 | 22% |
| ALL | POST | 5 | -8.3 | 20% | -2.93 | -12.4 (-6.1%) | 0.45 | -6.3 | 80% |
| ALL | USER_IS | 175 | 134.9 | 69% | 2.55 | -16.1 (-7.3%) | 2.23 | -10.9 | 19% |
| ALL | USER_OOS | 100 | 65.7 | 65% | 2.00 | -24.9 (-10.2%) | 1.74 | -13.5 | 24% |
| NIFTY | ALL_PERIODS | 154 | 121.4 | 66% | 2.06 [1.0, 3.3] | -16.1 (-7.3%) | 2.21 | -10.9 | 18% |
| NIFTY | PRE | 134 | 111.2 | 67% | 2.17 [1.0, 3.5] | -16.1 (-7.3%) | 2.35 | -10.9 | 17% |
| NIFTY | DEV | 18 | 16.9 | 61% | 2.57 [0.6, 5.3] | -5.5 (-2.6%) | 2.50 | -2.6 | 17% |
| NIFTY | POST | 2 | -6.7 | 0% | -75.24 | -6.7 (-3.4%) | 0.00 | -3.6 | 100% |
| NIFTY | USER_IS | 105 | 67.6 | 64% | 1.63 | -16.1 (-7.3%) | 1.95 | -10.9 | 19% |
| NIFTY | USER_OOS | 49 | 53.8 | 69% | 3.11 | -10.3 (-4.4%) | 2.84 | -4.7 | 16% |
| SENSEX | ALL_PERIODS | 121 | 79.1 | 70% | 1.64 [0.5, 3.1] | -21.2 (-7.4%) | 1.81 | -13.5 | 24% |
| SENSEX | PRE | 100 | 77.8 | 74% | 1.97 [0.6, 3.8] | -21.2 (-7.4%) | 2.06 | -13.5 | 22% |
| SENSEX | DEV | 18 | 3.0 | 56% | 0.51 [-1.5, 2.4] | -9.3 (-4.5%) | 1.19 | -3.1 | 28% |
| SENSEX | POST | 3 | -1.6 | 33% | -0.59 | -8.9 (-4.3%) | 0.81 | -6.3 | 67% |
| SENSEX | USER_IS | 70 | 67.3 | 77% | 2.98 | -10.5 (-4.5%) | 2.75 | -6.9 | 19% |
| SENSEX | USER_OOS | 51 | 11.8 | 61% | 0.48 | -21.2 (-9.7%) | 1.20 | -13.5 | 31% |

*PRE = D0 before 2026-06-22 (out-of-sample backwards); DEV = 2026-06-22..2026-10-22 (rules reconstructed here, in-sample); POST = from 2026-10-23 (after the freeze); USER_IS / USER_OOS = your earlier split (D0 <= 2025-11-17 / >= 2025-11-18). Sharpe: weekly cycle returns on Rs 2 crore, sqrt(52); CI = 4-week block bootstrap (blank when < 12 weeks). Drawdown from the minute-level net equity path.*

## 2. The three stop levels side by side (all periods)
| Level | Scope | Net (lakh) | Win | Sharpe | Max DD (lakh) | PF | Stop rate | Net w/o top-5 cycles | Net at 3x costs+slippage |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| S200 | ALL | 200.5 | 68% | 2.33 | -24.9 | 2.01 | 21% | 153.1 | -48.5 |
| S200 | NIFTY | 121.4 | 66% | 2.06 | -16.1 | 2.21 | 18% | 80.7 | -37.2 |
| S200 | SENSEX | 79.1 | 70% | 1.64 | -21.2 | 1.81 | 24% | 44.4 | -11.3 |
| S125 | ALL | 175.7 | 63% | 2.28 | -29.3 | 1.98 | 31% | 132.6 | -48.9 |
| S125 | NIFTY | 114.5 | 62% | 2.01 | -14.6 | 2.19 | 29% | 73.7 | -30.7 |
| S125 | SENSEX | 61.2 | 63% | 1.54 | -28.2 | 1.74 | 34% | 36.8 | -18.2 |
| NONE | ALL | 311.9 | 74% | 3.98 | -21.2 | 3.27 | 0% | 261.3 | 23.1 |
| NONE | NIFTY | 191.1 | 71% | 3.61 | -10.1 | 4.54 | 0% | 146.2 | 11.3 |
| NONE | SENSEX | 120.8 | 79% | 2.36 | -21.0 | 2.45 | 0% | 82.2 | 11.8 |

## 3. Other metrics, S125 and no-stop blocks
**S125 (1.25 lakh):**

| Scope | Period | Cycles | Net P&L (Rs lakh) | Win rate | Sharpe [95% CI] | Max DD Rs lakh (% of 2 cr) | Profit factor | Worst cycle (lakh) | Stop rate |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ALL | ALL_PERIODS | 275 | 175.7 | 63% | 2.28 [0.9, 3.7] | -29.3 (-7.7%) | 1.98 | -13.5 | 31% |
| ALL | PRE | 234 | 172.1 | 66% | 2.58 [1.2, 4.3] | -29.3 (-7.7%) | 2.20 | -13.5 | 29% |
| ALL | DEV | 36 | 11.3 | 50% | 1.30 [-0.7, 3.4] | -11.9 (-5.3%) | 1.42 | -3.1 | 36% |
| ALL | POST | 5 | -7.8 | 0% | -19.94 | -7.8 (-3.9%) | 0.00 | -1.8 | 100% |
| NIFTY | ALL_PERIODS | 154 | 114.5 | 62% | 2.01 [1.0, 3.2] | -14.6 (-6.6%) | 2.19 | -10.9 | 29% |
| NIFTY | PRE | 134 | 102.4 | 64% | 2.04 [0.9, 3.4] | -14.6 (-6.6%) | 2.25 | -10.9 | 28% |
| NIFTY | DEV | 18 | 15.4 | 56% | 2.40 [0.7, 4.3] | -4.7 (-2.3%) | 2.42 | -2.5 | 28% |
| NIFTY | POST | 2 | -3.3 | 0% | -53.15 | -3.4 (-1.7%) | 0.00 | -1.8 | 100% |
| SENSEX | ALL_PERIODS | 121 | 61.2 | 63% | 1.54 [0.0, 3.4] | -28.2 (-9.7%) | 1.74 | -13.5 | 34% |
| SENSEX | PRE | 100 | 69.7 | 68% | 2.05 [0.4, 4.2] | -25.8 (-8.9%) | 2.13 | -13.5 | 30% |
| SENSEX | DEV | 18 | -4.1 | 44% | -0.90 [-4.8, 2.3] | -12.5 (-6.0%) | 0.75 | -3.1 | 44% |
| SENSEX | POST | 3 | -4.5 | 0% | -309.85 | -4.6 (-2.3%) | 0.00 | -1.5 | 100% |

**NONE (reference):**

| Scope | Period | Cycles | Net P&L (Rs lakh) | Win rate | Sharpe [95% CI] | Max DD Rs lakh (% of 2 cr) | Profit factor | Worst cycle (lakh) | Stop rate |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ALL | ALL_PERIODS | 275 | 311.9 | 74% | 3.98 [2.9, 5.3] | -21.2 (-6.4%) | 3.27 | -10.1 | 0% |
| ALL | PRE | 234 | 266.7 | 76% | 3.92 [2.8, 5.4] | -21.2 (-6.4%) | 3.31 | -10.1 | 0% |
| ALL | DEV | 36 | 40.5 | 69% | 4.26 [1.3, 9.3] | -7.6 (-3.5%) | 3.47 | -3.1 | 0% |
| ALL | POST | 5 | 4.7 | 40% | 3.37 | -8.5 (-4.2%) | 1.83 | -3.4 | 0% |
| NIFTY | ALL_PERIODS | 154 | 191.1 | 71% | 3.61 [2.7, 4.8] | -10.1 (-2.8%) | 4.54 | -5.1 | 0% |
| NIFTY | PRE | 134 | 174.8 | 72% | 3.80 [2.8, 5.1] | -10.1 (-2.8%) | 5.16 | -5.1 | 0% |
| NIFTY | DEV | 18 | 20.3 | 67% | 3.32 [0.9, 7.0] | -5.7 (-2.8%) | 3.53 | -2.5 | 0% |
| NIFTY | POST | 2 | -4.0 | 0% | -7.69 | -6.9 (-3.5%) | 0.00 | -3.4 | 0% |
| SENSEX | ALL_PERIODS | 121 | 120.8 | 79% | 2.36 [1.1, 4.0] | -21.0 (-8.7%) | 2.45 | -10.1 | 0% |
| SENSEX | PRE | 100 | 91.9 | 80% | 2.11 [0.7, 4.0] | -21.0 (-8.7%) | 2.25 | -10.1 | 0% |
| SENSEX | DEV | 18 | 20.2 | 72% | 3.38 [0.6, 6.4] | -6.0 (-2.7%) | 3.41 | -3.1 | 0% |
| SENSEX | POST | 3 | 8.7 | 67% | 4.91 | -7.9 (-3.8%) | 6.41 | -1.6 | 0% |

## 4. Overfitting and robustness checks (preregistered)
| Check (PRE = 234 cycles unseen by rule development) | S200 | S125 | NONE |
|---|---|---|---|
| R1 PRE Sharpe > 0 and 95% block-bootstrap lower bound > 0 | PASS | PASS | PASS |
| R2 PRE net > 0 for NIFTY and SENSEX | PASS | PASS | PASS |
| R3 >= 60% of PRE quarters positive | PASS | PASS | PASS |
| R4 PRE net > 0 without the 5 best cycles | PASS | PASS | PASS |
| R5 PRE net > 0 at 3x costs | PASS | PASS | PASS |
| R6 POST net > 0 | FAIL | FAIL | PASS |
| R7 DEV->PRE Sharpe ratio (reported) | n/a (1.32) | n/a (1.98) | n/a (0.92) |

R7 (DEV Sharpe to PRE Sharpe, S200): 1.32 (DEV is lower than PRE: no sign that the development window flatters the result).

**S200 vs S125, paired per cycle** (week-clustered bootstrap, per week):

| Period | Cycles | Cycles where the stop level matters | Better / worse | Total difference (lakh) | 95% interval | Difference without the 5 largest (lakh) |
|---|---:|---:|---:|---:|---|---:|
| PRE | 234 | 62 | 22 / 40 | 16.8 | [-13k, 40k] | -12.3 |
| DEV | 36 | 11 | 4 / 7 | 8.6 | [-35k, 180k] | -5.1 |
| POST | 5 | 5 | 1 / 4 | -0.5 | n/a | 0.0 |
| ALL | 275 | 78 | 27 / 51 | 24.8 | [-12k, 45k] | -11.1 |

Preregistered requirement for "S200 better supported": (a) PRE interval above 0: **False**; (b) positive mean in DEV, PRE and POST: **False**; (c) positive without the 5 largest in PRE: **False**; (d) worst cycle/DD not >25% worse: True. **Verdict: not separable on this evidence.**

**By year, S200 (net Rs lakh, win rate):**

| Index | Year | Cycles | Net | Win |
|---|---|---:|---:|---:|
| NIFTY | 2023 | 8 | 4.1 | 62% |
| NIFTY | 2024 | 51 | 9.3 | 67% |
| NIFTY | 2025 | 52 | 63.2 | 65% |
| NIFTY | 2026 | 43 | 44.8 | 65% |
| SENSEX | 2024 | 28 | 24.6 | 82% |
| SENSEX | 2025 | 48 | 50.6 | 75% |
| SENSEX | 2026 | 45 | 3.9 | 58% |

## 5. Calibration against the real trade export (32 development cycles, Jun-Oct 2026)
Real = cash flows of the real order log (fill prices, before brokerage and taxes) plus settlement of leftovers: **Rs 18.9 lakh**; the real system had 11 cycle stops in the D0 stage of 30 cycles.

| Simulated stop level | Sim gross (lakh) | Ratio to real | Per-cycle correlation with real | Cycles stopped in sim (of 32) |
|---|---:|---:|---:|---:|
| NONE | 42.5 | 2.24x | 0.43 | 0 |
| S125 | 8.7 | 0.46x | 0.56 | 13 |
| S200 | 19.8 | 1.04x | 0.74 | 8 |

## 6. Pipeline validation (before interpretation)
The data builder reproduces the 2026 research caches exactly on the 32 development cycles (32/32 D-1 and 32/32 D0 array sets identical) and the D-1 replay reproduces B1's 9,035 orders order-for-order (32/32 cycles identical). All 275 cycles hand off D-1 to D0 without error, and every cycle ends flat (no residual position, no settlement needed).

## 7. What this is not (read before using any number)
1. **The rules are our reconstruction** (keys F1 0.74 D-1, 0.42 D0 against the real 2026 orders), applied **unchanged to 2023-2025**, before the period in which Algo 8 was observed. Whether the real system traded this way then is unknown.
2. **Sizes:** the engines' lot counts at each session's actual lot size (NIFTY 50/25/75/65, SENSEX 10/20); hundreds of lots per cycle. Margin and the real capital are unknown: the Rs 2 crore denominator is a stated figure, so **drawdown %, annual return % and Calmar are not reliable**; rupee figures, win rate and Sharpe are (Sharpe does not depend on the denominator). Re-scaled to the 2026 lot sizes, S200 net is Rs 240.1 lakh.
3. **Fills** are one-minute-bar conventions (documented in the preregistration) with 0.5% adverse slippage and the earlier backtest's cost model (partly unverified). The D0 engine's aggregated events understate the real number of orders, so brokerage is understated.
4. **Short-premium strategies have negative skew**: a high win rate and a high Sharpe over a calm 3 years can coexist with rare large losses (worst cycle Rs -13.5 lakh here). The Sharpe confidence intervals above do not cover regime change.
5. POST has 5 cycles: no inference. Every number is a simulation of a reconstruction.

## 8. Next steps (not started)
1. Decide the stop level from evidence that is not in-sample (the sample cannot separate 1.25L from 2L; new expiries are the only cure).
2. Complete Python algo as a clean package (the D-1/D0 engines already exist; needs a single event-driven runner with the stop, accounting and a live-feed interface).
3. C++ port with Python/C++ parity tests (the earlier portfolio engine did this: 13,525 byte-identical runs).

Files: `results/summary_table.csv`, `cycle_ledger.csv`, `stress_concentration.csv`, `stop_paired.csv`, `by_year_S200.csv`, `calibration_vs_real.json`, `pipeline_validation.json`, `figures/equity_curves.png`, `figures/drawdown.png`; code `engine_run.py`, `run_all.py`, `analyze.py`, `make_report.py`, `validate_pipeline.py`.
