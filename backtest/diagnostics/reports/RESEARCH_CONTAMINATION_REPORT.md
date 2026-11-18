# Research Contamination Report

Source: `contamination.py` → `contamination_tables.csv`, `representativeness.csv`, `oos_quarterly_net.csv`. Code executed, outputs observed. Facts about *what was inspected* come from the project's own pre-registration (`backtest/PREREGISTRATION.md`) and the Algo 8 reverse-engineering history, not from me re-deriving them.

## 1. What was inspected, and when

| Period | Cycles | Status | Basis |
|---|---:|---|---|
| IS: D0 ≤ 2025-11-17 | 175 | **Development data** (configuration grid, selection, walk-forward) | Pre-registration |
| OOS clean-before: D0 2025-11-18 … 2026-06-18 | 59 | Not inspected during Algo 8 reverse engineering; accounting run **once** after freeze | Pre-registration |
| **OOS exposed: D0 2026-06-22 … 2026-10-22** | **36** | **Inspected** during reverse engineering (the live Algo 8 trade ledger `Trades_GKOHNP140.csv` covers it) | Pre-registration |
| OOS clean-after: D0 2026-10-29 … 2026-11-17 | 5 | Not inspected | Pre-registration |

## 2. Were rules or configuration decisions influenced by the exposed period?

| Decision | Source | Influenced by the exposed window? |
|---|---|---|
| Entry day/time (D-1, 09:16), ATM strike from the 09:15 spot bar, short CE+PE, long wings, 3 lots per leg | "Algo 8 observed structure, rulebook v0.6, observed not decoded" | **Yes — derived from observing the live ledger, which is the exposed window.** The structure was then extrapolated to 2023–2025. |
| Wing distances (NIFTY 2,000; SENSEX 4,000 → 2,000 on 2026-09-16) | Same | **Yes** (the SENSEX change date lies inside the exposed window). |
| The existence of the cut / re-entry / stop plugins | Plugin architecture of the engine, built from the reverse-engineering | **Yes** in design. |
| Cut/re-entry **thresholds** | Selected on IS only by pre-registered rule; frozen before any OOS accounting | **No** (per pre-registration and `FROZEN_CONFIG.json`). |
| Settlement, cost and slippage assumptions | Written before OOS | No, but see TRANSACTION_COST_ANALYSIS (they affect OOS materially). |

So the **strategy structure** is contaminated by the exposed window; only **plugin thresholds** are clean. IS and the clean OOS test the *extrapolation* of a structure first observed in the exposed window. That makes the clean OOS (64 cycles) the only fair test of the structure — and it is the weak one.

## 3. Results shown separately (net ₹ / Sharpe / mean per cycle with bootstrap 95 % CI)

| Config | Sample | Cycles | Net | Mean ₹/cycle (95 % CI) | Sharpe | P(mean ≤ 0) |
|---|---|---:|---:|---|---:|---:|
| HOLD | IS (development) | 175 | 497,091 | 2,841 (−748 … 6,220) | 1.10 | 0.06 |
| HOLD | OOS exposed (contaminated) | 36 | 179,642 | 4,990 (−2,575 … 12,195) | 2.26 | 0.10 |
| HOLD | **OOS clean** | 64 | 38,687 | **604 (−7,804 … 8,386)** | 0.17 | 0.43 |
| HOLD | clean-before | 59 | 168,035 | 2,848 (−5,276 … 10,229) | 0.90 | 0.24 |
| HOLD | clean-after | 5 | −129,348 | −25,870 | −3.41 | — |
| Frozen | IS | 175 | 520,143 | 2,972 | 1.26 | 0.04 |
| Frozen | OOS exposed | 36 | 181,351 | 5,038 | 2.39 | 0.09 |
| Frozen | **OOS clean** | 64 | −114,188 | −1,784 (−10,229 … 5,912) | −0.51 | 0.66 |

* **The exposed window supplies 82 % of the OOS P&L** (₹179.6k of ₹218.3k) with 36 % of the cycles. Calling the "full OOS" independent would be wrong. **Only the 64-cycle clean block is independent**, and it cannot be distinguished from zero.
* Mean per cycle, exposed vs clean: ₹4,990 vs ₹604; permutation p-value for the difference = **0.49** — the data cannot say the exposed window was better, only that it was. This is the central subtlety: a lucky window and a contaminated window look the same here.
* The clean-before block alone (59 cycles, ₹168k, Sharpe 0.90) is respectable; the weakness in the clean total is the five clean-after cycles (−₹129k). With n = 5 this proves nothing either way. I do not drop it.

## 4. Representativeness of the uninspected cycles (KS tests vs IS, `representativeness.csv`)

| Index | Feature | IS | Exposed | Clean | p(clean vs IS) | p(exposed vs clean) |
|---|---|---:|---:|---:|---:|---:|
| NIFTY | Premium % K | 0.81 | 0.73 | **1.04** | **0.006** | **0.008** |
| NIFTY | \|move\| % K | 0.72 | 0.47 | 1.05 | 0.16 | 0.07 |
| NIFTY | RV5 % | 0.70 | 0.66 | 0.89 | 0.08 | 0.49 |
| SENSEX | Premium % K | 0.86 | 0.78 | 0.89 | 0.14 | **0.04** |
| SENSEX | \|move\| % K | 0.79 | 0.79 | 0.82 | 0.91 | 0.50 |

The **clean NIFTY block lives in a different volatility regime** (premium +28 % vs IS, p = 0.006). The exposed window was a calmer regime than IS for NIFTY (|move| 0.47 %). Neither OOS block is a clone of IS. That cuts both ways: weak clean-OOS performance may reflect regime change rather than failure of the structure — but that is exactly the claim that cannot be tested with 64 cycles.

## 5. Discipline going forward
* **Contamination caused by this diagnostic:** I have now looked at the clean OOS descriptively (distributions, regimes, plugin variants at frozen thresholds, leg attribution). Nothing was tuned. But the clean OOS should be treated as **partially informed** for any *new* hypothesis proposed after reading this report. Label: **"CLEAN OOS — viewed descriptively in the DX diagnostic (date of commit); not usable as independent evidence for hypotheses derived from it."**
* Independent evidence now needs genuinely new data: (a) forward paper trading from 2026-11-18, (b) pre-2023 history (NIFTY 2021–2023 if obtainable), (c) other expiries/underlyings by pre-registration.
* Do not tune on the clean block either (rule restated).
