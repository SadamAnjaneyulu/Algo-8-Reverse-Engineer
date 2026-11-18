# Return Distribution Analysis

Source: `distribution.py` → `results/return_distribution.csv`, `ranked_cycles_{all,IS,OOS,OOS_clean}.csv`, `oos_leave_best_out.csv`, `signflip_tests.csv`, `monthly_stats.csv`. HOLD_SETTLE baseline, base costs, **original** settlement proxy (corrected-settlement numbers are in `SHARPE_METHODOLOGY_AUDIT.md` §4 and `TRANSACTION_COST_ANALYSIS.md`). Code executed, outputs observed.

## 1. Starting figures: all recomputed from artifacts — all reproduce

| Figure in the brief | Recomputed | OK |
|---|---:|:-:|
| IS net | ₹497,091 | ✔ |
| Full OOS net | ₹218,329 | ✔ |
| Clean OOS net (64 cycles) | ₹38,687 | ✔ |
| Exposed cycles / their P&L | 36 / ₹179,642 (82.3 % of OOS) | ✔ |
| Sharpe IS / OOS / clean | 1.104 / 0.691 / 0.167 | ✔ |
| OOS without 5 best cycles | ₹5,010 | ✔ |
| Frozen cut+re-entry, full OOS / clean | ₹67,163 / −₹114,188 | ✔ |
| Flatten 15:25, full OOS / clean | ₹118,941 / −₹1,903 | ✔ |
| 3× slippage clean / 6× clean | ₹6,074 / −₹42,844 | ✔ |
| Wings in sample | −₹70.7k gross (−₹83.0k net incl. their costs) | ✔ |

## 2. Per-cycle distribution (combined)

| | IS | Full OOS | OOS exposed | OOS clean | clean-before | clean-after |
|---|---:|---:|---:|---:|---:|---:|
| Cycles | 175 | 100 | 36 | 64 | 59 | 5 |
| Total net ₹ | 497,091 | 218,329 | 179,642 | 38,687 | 168,035 | −129,348 |
| Mean ₹ | 2,841 | 2,183 | 4,990 | 604 | 2,848 | −25,870 |
| **Median ₹** | 6,440 | **10,105** | 8,843 | 10,105 | 10,895 | −25,008 |
| Std ₹ | 23,338 | 29,722 | 22,716 | 33,082 | 31,164 | 46,944 |
| % positive / negative / zero | 65.1 / 34.9 / 0 | 61 / 39 / 0 | 58.3 / 41.7 / 0 | 62.5 / 37.5 / 0 | 64.4 / 35.6 / 0 | 40 / 60 / 0 |
| Best / worst ₹ | 79.7k / −89.5k | 49.6k / −124.2k | 36.6k / −46.7k | 49.6k / −124.2k | 49.6k / −124.2k | 35.8k / −73.7k |
| **Skew** | −0.83 | **−1.31** | −0.45 | −1.34 | −1.54 | +0.18 (n=5) |
| Excess kurtosis | 2.28 | 2.62 | −0.94 | 2.28 | 3.66 | −1.46 |
| Average win / loss ₹ | 15.7k / −21.1k | 21.1k / −27.3k | 21.5k / −18.2k | 20.8k / −33.1k | 20.9k / −29.8k | 19.4k / −56.0k |
| Payoff ratio | 0.74 | 0.77 | 1.19 | 0.63 | 0.70 | 0.35 |
| Top-5 winners ₹ (share of total) | 271k (55 %) | **213k (98 %)** | 161k (89 %) | 213k (551 %) | 213k (127 %) | n/a |
| Top-10 winners ₹ | 450k | 388k | 293k | 378k | 371k | n/a |
| Bottom-5 losers ₹ | −342k | −413k | −162k | −413k | −340k | −129k |
| Bottom-10 losers ₹ | −573k | −594k | −247k | −565k | −471k | n/a |
| Max consecutive losing cycles | 3 | 4 | 4 | 4 | 4 | 3 |
| Longest drawdown (cycles on cycle-ordered path) | 58 | 30 | 9 | 30 | 30 | 4 |
| t-stat of mean | 1.61 | 0.73 | 1.32 | 0.15 | 0.70 | −1.23 |

Per index (net ₹ / mean ₹ / median ₹): IS NIFTY 320k/3.0k/5.4k, SENSEX 177k/2.5k/7.5k; OOS NIFTY 147k/3.0k/12.9k, SENSEX 72k/1.4k/4.8k; exposed NIFTY +204k, SENSEX −25k; **clean NIFTY −58k, SENSEX +96k**.

## 3. Direct answers

| Question | Answer |
|---|---|
| Does a small number of large winners drive profits? | **Yes in OOS.** Top 5 of 100 cycles = 97.7 % of OOS net; remove them → ₹5.0k; remove 6 → −₹31.5k; remove 10 → −₹170k (`oos_leave_best_out.csv`). In IS the top 5 are 55 %, top 10 are 90 %. |
| Are most cycles losing? | **No.** 61–65 % of cycles win. |
| Is the distribution positively skewed? | **No — negatively** (−0.83 IS, −1.31 OOS). Many modest wins, few large losses: the signature of short volatility. |
| Does one index dominate? | Not persistently. NIFTY leads overall (≈2:1 in IS and OOS), but the sign flips by window: exposed = NIFTY +204k / SENSEX −25k; clean = NIFTY −58k / SENSEX +96k. |
| Is the median cycle profitable? | **Yes**: median +₹6.4k IS, +₹10.1k OOS (clean +₹10.1k). The median is far above the mean (4.6× OOS) — the mean is pulled down by the left tail. A positive median with a ~zero mean is exactly what a poorly-paid short-gamma book looks like. |

## 4. What the shape implies
* Average winner ₹21k vs average loser ₹27k (payoff 0.77) with a 61 % win rate gives a thin expectancy of ₹2.2k/cycle on ~₹41k premium sold per cycle (≈5 %).
* Sign-flip tests for H0 "symmetric about zero": IS p = 0.054, OOS p = 0.23, clean p = 0.44, exposed p = 0.096. **No sample rejects zero at 5 %.**
* The 5 clean-after cycles (Oct 29 → Nov 17 2026) lost ₹129k — two NIFTY and SENSEX expiries each with bad outcomes; with n = 5 this is an anecdote, not a regime.
* Monthly: IS 25 months, 72 % positive, std ₹49k; OOS 13 months, 62 % positive, std ₹115k (best +₹191k, worst −₹186k).

## 5. Quarterly pattern in OOS (net ₹, `oos_quarterly_net.csv`)

| Quarter | NIFTY | SENSEX | total |
|---|---:|---:|---:|
| 2025Q4 | −46.6k | +28.8k | −17.8k |
| 2026Q1 | −179.0k | −90.6k | **−269.6k** |
| 2026Q2 | +205.8k | +212.2k | **+418.0k** |
| 2026Q3 | +206.2k | +71.7k | **+277.9k** |
| 2026Q4 (to Nov 17) | −39.7k | −150.4k | −190.1k |

OOS P&L is regime-clustered: two good quarters (Q2–Q3 2026, ≈ +₹696k) offset by Q1 and Q4 2026 (≈ −₹460k) and the Q4 2025 stub. The exposed window (Jun 22–Oct 22) sits inside the good stretch, which is why it flatters the full OOS.

Figures: `figures/cumulative_net.png`, `figures/oos_ranked_cycles.png`.
