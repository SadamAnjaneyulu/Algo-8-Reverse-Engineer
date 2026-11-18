# Sharpe Methodology Audit

**Result:** the reported Sharpe ratios (IS 1.10, OOS 0.69, clean OOS 0.17) are **arithmetically correct and reproduce exactly**. I found **no formula defect**. The real problems are statistical (very wide uncertainty) and one input defect (settlement proxy, §4). Status of this document: code executed, outputs observed (`sharpe_audit.py` → `results/sharpe_audit.csv`, `results/sharpe_comparison.json`).

## 1. The ten questions

| # | Question | Answer (from `bt/metrics.py`, `summarize`, verified by re-computation) |
|---|---|---|
| 1 | What return series? | Net P&L per ISO week ÷ ₹2 crore. NIFTY and SENSEX cycles that expire in the same ISO week are **summed** (one portfolio series). |
| 2 | Daily, cycle or trade? | Neither daily nor per trade. One observation per **ISO week** (≈ one per expiry cycle). Trades are not treated as independent. |
| 3 | Frequency | Weekly (IS 106 weeks, OOS 52, clean 34). |
| 4 | Annualisation | `mean/std(ddof=1) × √52`. Valid only if weekly returns are close to independent (autocorrelation of \|move\| is ≈0.03/0.13, `regime_volclustering.csv`). |
| 5 | Risk-free rate | 0. Not subtracted. |
| 6 | Idle periods | Weeks with no cycle are **not** in the series. Re-computing with all calendar weeks as zero changes IS 1.10→1.10, OOS 0.69→0.69, clean 0.17→0.14. Immaterial. |
| 7 | Overlap NIFTY+SENSEX | Summed in the same week. Overlap is real: NIFTY and SENSEX are both short-vol on near-identical indices, so they are one bet, not two. Max 2 simultaneous baskets (`exposure_summary.json`). |
| 8 | Denominator capital | ₹2 crore constant (stated in `Info.txt`, **unverified**). Sharpe is scale-invariant: using ₹1 crore gives identical Sharpe (`denominator_check_Rs10M` column equals the reported value). Capital only matters for % return (IS 1.2 %/yr, OOS 1.1 %/yr on ₹2 cr). Peak margin **proxy** was ₹6.4 M (32 % of capital); SPAN margin is unknown. |
| 9 | Gross vs net | Reported Sharpe is **net** (slippage + statutory costs). Gross weekly Sharpe: IS 1.22, OOS 0.82, clean 0.28. Consistent: numerator net, denominator is the std of the same net series. |
| 10 | Missing / excluded cycles | 275 of 319 expected cycles are in. 44 were excluded by the earlier validation (status ≠ Complete, 1 embargo). Excluded cycles are **not** in either the P&L or the Sharpe. Whether excluded cycles are better or worse is unknown. |

## 2. Recomputed table (combined NIFTY+SENSEX, HOLD_SETTLE, base costs)

| Sample | Cycles | Weeks | Reported Sharpe | Weekly, idle=0 | **Daily** (business days, idle=0) | 95 % CI (block bootstrap, block=4 wk) | Lo (2002) SE |
|---|---:|---:|---:|---:|---:|---|---:|
| IS | 175 | 106 | 1.10 | 1.10 | 1.03 | −0.18 … 2.45 | 0.70 |
| Full OOS | 100 | 52 | 0.69 | 0.69 | 0.69 | −1.13 … 3.94 | 1.00 |
| OOS exposed (36 cycles) | 36 | 18 | 2.26 | 2.26 | 1.83 | −0.09 … 8.84 | 1.74 |
| OOS clean (64 cycles) | 64 | 34 | 0.17 | 0.14 | 0.14 | −1.93 … 4.22 | 1.24 |

Per index (weekly): IS NIFTY 0.95 / SENSEX 0.77; OOS NIFTY 0.69 / SENSEX 0.36; clean NIFTY −0.37 / SENSEX +0.71; exposed NIFTY 4.70 / SENSEX −0.38.
Monthly (13 OOS months): mean ₹16.8k, median ₹48.7k, std ₹114.8k, 62 % positive, monthly-annualised Sharpe 0.51; IS (25 months) 1.39, 72 % positive. Monthly series are too short to rank anything.

**Do not compare** the weekly Sharpe with the daily one as if they measured the same thing: the daily figure includes idle days and intra-cycle mark-to-market noise.

## 3. Why Sharpe fell from 1.10 to 0.69 (arithmetic)

| | IS | OOS |
|---|---:|---:|
| Mean weekly net P&L | ₹4,690 | ₹4,199 (−10 %) |
| Std of weekly P&L | ₹30,639 | ₹43,841 (**+43 %**) |

Swapping one factor at a time: OOS Sharpe with the IS mean = 0.77; OOS Sharpe with the IS std = 0.99. So most of the fall is **higher P&L volatility** (fatter loss tail: worst cycle −₹124k vs −₹90k, skew −1.31 vs −0.83), not a collapse of the average.

**Is the fall significant?** No. Bootstrap difference IS−OOS = 0.41, 95 % CI **[−2.33, +2.84]**, P(IS ≤ OOS) = 0.38. With 52 OOS weeks the standard error of an annualised Sharpe is ≈1.0; the 1.10→0.69 move is well inside noise. Even the IS Sharpe of 1.10 has a 95 % CI that includes zero (−0.18 … 2.45); a sign-flip test of mean cycle P&L gives one-sided p = 0.054 for IS, 0.23 OOS, 0.44 clean OOS (`signflip_tests.csv`). Detecting a true Sharpe of 1.0 at ~2 SE needs roughly 4 years of independent weekly data.

## 4. Defects and caveats found

| ID | Finding | Status | Effect on Sharpe |
|---|---|---|---|
| S-1 | **Settlement proxy.** Original run settles at the 15:30 spot bar (150 NIFTY / 93 SENSEX cycles) which differs from the independent official daily close by mean \|Δ\| 15 pts (NIFTY) / 22 pts (SENSEX), max 241 pts. The proxy is on average 3.1 pts (NIFTY) closer to the strike than the official close, which favours the short straddle (details: `TRANSACTION_COST_ANALYSIS.md` §4). Corrected run (`SETTLE_YAHOO`, see `settlement_sensitivity.py`): | **Established** that the proxy differs; which one equals the exchange settlement is **plausible, not proven** (Yahoo = official index close). | IS 1.10→1.01; OOS 0.69→**0.54**; clean 0.17→**0.04**. Original results preserved, corrected run separately labelled. |
| S-2 | Weekly series mixes NIFTY-only weeks (Nov 2023–May 2024) with two-index weeks. IS variance is therefore not stationary. | Established | Not quantified; direction unclear |
| S-3 | Fixed 3 lots/leg while lot size changes (NIFTY 50→25→75→65; SENSEX 10→20), so exposure in index units and rupee notional is **not** constant over time. | Established | Not quantified |
| S-4 | Capital ₹2 cr unverified. | Unresolved | None on Sharpe |
| S-5 | One SENSEX IS cycle (2025-04-08) has an entry print of ₹38.30 on the first-ever trade of the contract; see `POSITION_AND_LEG_ATTRIBUTION.md`. | Established | IS only; makes IS **worse**, not better |

## 5. Conclusion
The Sharpe pipeline is sound. The numbers are weak mainly because (i) the sample is small and negatively skewed, (ii) volatility rose OOS, and (iii) the settlement proxy overstated P&L by ~₹50k on the full OOS. Corrected full-OOS Sharpe = **0.54**, corrected clean = **0.04**. None of 1.10 / 0.69 / 0.17 / 0.54 can be distinguished from each other or, at 95 %, from zero.
