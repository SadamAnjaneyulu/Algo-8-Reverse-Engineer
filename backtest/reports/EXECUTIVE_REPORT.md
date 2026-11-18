# Algo 8 portfolio-construction engine: historical backtest, executive report
Prepared for Rahul. Code commit `349115dc498443edcbd4d429c56f6724779b4ec8`; data commit `eb4097308d47ccc75078ab73ba76d33bb1c7030b`; configuration frozen in `backtest/FROZEN_CONFIG.json` before any out-of-sample accounting.

## The answer in five lines
1. **I tested the existing engine, but it contains no entry rule.** It cuts and re-enters baskets that are handed to it. I fed it the only documented basket structure (Algo 8's observed 09:16 four-leg basket: short ATM CE+PE, long wings 2,000 points away for NIFTY and 4,000 for SENSEX, three lots per leg) built from real Breeze prices. That structure is an extrapolation to 2023-2025 (it was observed in June-October 2026 only).
2. **The basket held to expiry made a small net profit.** In sample (175 weekly cycles, NIFTY + SENSEX, net of slippage and costs): **Rs 497,091** (2.49% of the stated Rs 2 crore, Sharpe 1.10). Out of sample (100 cycles): **Rs 218,329** (1.09%, Sharpe 0.69).
3. **Most of the out-of-sample profit sits in the window we had already studied.** The 36 cycles of 22 Jun - 22 Oct 2026 earned Rs 179,642. The 64 previously uninspected cycles earned **Rs 38,687** (Sharpe 0.17): break-even, and negative for NIFTY. Without its five best cycles the whole out-of-sample year earns Rs 5,010.
4. **The engine's cut and re-entry plugins did not help.** In the hold-to-expiry variant only 2 of the 25 plugin configurations beat plain holding in sample, by Rs 23,052 at best. The pre-registered rule froze `cut_t20000_f10000_re_cd1800band` for the hold-to-expiry variant and plain holding for the flatten variant. Out of sample the frozen plugin configuration earned Rs 67,163 (clean subset Rs -114,188) against Rs 218,329 for plain holding. In the walk-forward test its selection procedure earned Rs 99,126 against Rs 490,299 for holding.
5. **Python and C++ agreed on all 13,525 engine runs** (byte-identical outputs), and the accounting layer matches the engine's own ledger to the paisa wherever the engine closed every position.

## What this does and does not show
* It does **not** show that Algo 8 is profitable or that the engine reproduces it. The engine's cut and re-entry rules are example policies; Algo 8's entry rules are not decoded; position size (about Rs 0.5 crore notional per leg) is tiny against Rs 2 crore, so returns are small in rupee terms.
* Profits depend on a handful of cycles and on costs: clean out-of-sample net falls from Rs 38,687 to Rs 6,074 with 3x slippage and Rs -42,844 with 6x. The flatten-at-15:25 variant earns Rs 118,941 out of sample and Rs -1,903 on the clean subset.
* The wings are a margin device, not a loss limiter at the cycle level: their cumulative premium cost in sample was Rs 70,688, and they do not shrink the worst cycle (NIFTY -89,167 with wings vs -88,897 without; SENSEX -77,723 vs -60,940).
* Only 275 of 319 expected expiry cycles could be used (validation status Complete); results are for D-1/D0 only.

## Headline table (combined NIFTY + SENSEX, net of slippage and costs, base assumptions)
| exit | config | period | cycles | net_pnl | cum_return_pct | sharpe | max_dd_pct | win_rate_pct | profit_factor |
|---|---|---|---|---|---|---|---|---|---|
| HOLD_SETTLE | HOLD (baseline) | IS | 175 | 497,091 | 2.49 | 1.10 | -1.01 | 65.14 | 1.39 |
| HOLD_SETTLE | HOLD (baseline) | OOS | 100 | 218,329 | 1.09 | 0.69 | -1.86 | 61.00 | 1.20 |
| HOLD_SETTLE | HOLD (baseline) | OOS_clean_all | 64 | 38,687 | 0.19 | 0.17 | -1.86 | 62.50 | 1.05 |
| HOLD_SETTLE | cut_t20000_f10000_re_cd1800band (FROZEN) | IS | 175 | 520,143 | 2.60 | 1.26 | -0.86 | 62.29 | 1.42 |
| HOLD_SETTLE | cut_t20000_f10000_re_cd1800band (FROZEN) | OOS | 100 | 67,163 | 0.34 | 0.22 | -2.28 | 57.00 | 1.06 |
| HOLD_SETTLE | cut_t20000_f10000_re_cd1800band (FROZEN) | OOS_clean_all | 64 | -114,188 | -0.57 | -0.51 | -2.28 | 56.25 | 0.87 |
| FLATTEN_1525 | HOLD (FROZEN) | IS | 175 | 428,327 | 2.14 | 0.91 | -1.21 | 62.86 | 1.31 |
| FLATTEN_1525 | HOLD (FROZEN) | OOS | 100 | 118,941 | 0.59 | 0.39 | -1.93 | 59.00 | 1.11 |
| FLATTEN_1525 | HOLD (FROZEN) | OOS_clean_all | 64 | -1,903 | -0.01 | -0.01 | -1.93 | 59.38 | 1.00 |

Details: METHODOLOGY.md, NIFTY_REPORT.md, SENSEX_REPORT.md, COMBINED_REPORT.md, COST_AND_STRESS_REPORT.md, PARITY_REPORT.md, LIMITATIONS_AND_CONCLUSIONS.md; data in `backtest/results/` (trade ledger, monthly performance, stress tests).
