# Algo 8 — Why Is Out-of-Sample Sharpe So Weak? Performance Diagnostic

**Scope:** diagnostic only. No parameters were optimised, the frozen baseline is unchanged, no results were overwritten, no ML was used, no losing cycle was excluded, and no profitable regime was selected. Original results (`backtest/results`, `backtest/reports`) are untouched; all new material is in `backtest/diagnostics/`. Reproduce with `bash backtest/diagnostics/run_all.sh`.

**Evidence labels used:** *Established* = exact arithmetic/decomposition on the data; *Plausible* = consistent with data, not isolated causally; *Unknown* = cannot be determined from available data. No causal claim is made from observational data alone.

## EXECUTIVE SUMMARY

| Question | Answer |
|---|---|
| **1. Why did Sharpe fall from 1.10 (IS) to 0.69 (OOS)?** | *Established:* mean weekly P&L fell only 10 % (₹4.69k → ₹4.20k) while its standard deviation rose 43 % (₹30.6k → ₹43.8k); swapping one factor at a time gives 0.77 (IS mean) / 0.99 (IS std). *Established:* the fall is **statistically indistinguishable from noise** (IS−OOS = 0.41, 95 % CI −2.3…+2.8; the Sharpe standard error on 52 weeks is ≈1.0). The Sharpe calculation itself is correct. |
| **2. Why only 0.17 on the 64 uninspected cycles?** | *Established:* mean ₹604/cycle (vs ₹2,841 IS), 95 % CI −₹7.8k…+₹8.4k; 95 % of the drop in per-cycle net is **lower gross P&L**, not costs. The window contains the worst quarter (2026Q1, −₹270k) and five final cycles (−₹129k). NIFTY's premium cushion shrank from 1.38× to 1.08× of realised move and overnight gaps doubled. *Plausible:* a different volatility regime; *Unknown:* whether the structure has a persistent edge at all (even IS, sign-flip p = 0.054). |
| **3. Is it profitable after realistic costs?** | **Not demonstrated.** Original clean-OOS net +₹39k; **with the corrected settlement it is +₹9k (Sharpe 0.04)**; it goes negative at 1.6× the assumed slippage. Full OOS corrected: ₹168k (Sharpe 0.54), but 82 % of the original OOS P&L comes from the inspected 36-cycle window, and the top-5 cycles equal 98 % of OOS net. True slippage and bid/ask are unmeasured. |
| **4. Which components contribute positively / negatively?** | **+** Short options' premium capture (gross ₹622k IS, ₹298k OOS; the short **put** earned the IS, the short **call** the OOS). **−** Long wings (−₹83k IS, −₹47k OOS net; never in the money in NIFTY, 0/154). **−** Friction (₹54k IS, ₹40k OOS). **−** Cut/re-entry (−₹151k vs plain hold in OOS; −₹153k in clean OOS). **−** Capital stops (−₹117k OOS but they reduce drawdown −₹373k → −₹266k). **−** Settlement proxy flattered OOS by ₹50k. |
| **5. Biggest weakness?** | *Established:* a short-gamma payoff (skew −1.3) whose **losses are booked overnight** (−₹106k IS, −₹111k clean OOS vs +₹496k earned intraday on D0), in the gap, before any in-session plugin gets its first look (48 % of the worst-decile OOS loss is already booked at D0 09:16) — on top of a thin cushion (premium ≈ 1.1–1.4× realised move) and a sample too small to tell it from zero. |
| **6. What next?** | Rank 1: replace unmeasured inputs (real slippage, exchange settlement) so the baseline net is trustworthy; rank 2: understand overnight/expiry-day risk; rank 3: the premium/realised-move cushion; then wings, sizing, cuts, regimes. See `NEXT_RESEARCH_HYPOTHESES.md`. |

## 1. Recomputed starting figures
All figures in the brief reproduce exactly from the artifacts (table in `RETURN_DISTRIBUTION_ANALYSIS.md` §1). No discrepancy.

## 2. Backtest errors / defects found (originals preserved, corrected runs labelled)

| ID | Defect | Effect | Status | Where |
|---|---|---|---|---|
| D1 | **Settlement proxy** (15:30 spot bar) vs official close: proxy 3.1 pts (NIFTY) closer to the strike | IS −₹23.9k, **OOS −₹50.4k**, clean −₹29.4k; Sharpe IS 1.01, OOS **0.54**, clean **0.04** | Established difference; settlement truth *plausibly* = official close, not verified against the exchange | `SETTLE_YAHOO` run |
| D2 | **First-print entry** SENSEX 2025-04-08 (₹38.30 sold vs ≈ ₹600–1,500 an instant later) | IS only; makes IS worse (≈ −₹90k) | Established | `POSITION_AND_LEG_ATTRIBUTION.md` §4 |
| D3 | Fixed 3 lots while lot size changes; NIFTY-only weeks mixed with 2-index weeks | exposure not constant; not quantified | Established (existence) | Sharpe audit S-2/S-3 |
| — | Sharpe formula | none | Verified correct | `SHARPE_METHODOLOGY_AUDIT.md` |

The "delay improves P&L" anomaly was explained by D2 (one contract), not by a systematic effect.

## 3. Hypothesis table: what explains the weak OOS Sharpe?

| Candidate | Verdict | Evidence |
|---|---|---|
| Entry structure | **Contributes (Plausible)** | Edge is premium minus realised move; the clean-OOS cushion collapsed; side that earns flips by window. |
| Basket construction / wings | **Costs ₹83k IS, no protection (Established)** | 0/154 NIFTY wings ITM; wings 2–4× the max observed move. Not the cause of the OOS fall (wing net cost per cycle: ₹474 IS vs ₹471 OOS). |
| Cut / re-entry logic | **Hurts OOS (Established observationally)** | −₹151k vs hold; no worst-cycle reduction. IS "gain" (+₹23k) is inside noise. |
| Hedge structure | **Ineffective at observed scale** | as above |
| Market regimes | **Plausible, not testable** | clean NIFTY regime differs (KS p 0.006); no decision-time feature predicts P&L. |
| Execution costs | **Not the cause, but fragile** | 5 % of per-cycle decline; break-even slippage 1.6× on clean. |
| Research contamination | **Large (Established)** | 82 % of OOS P&L in the inspected window; structure derived there. |
| Backtesting errors | **Yes, modest (Established)** | settlement proxy ₹50k; one bad entry print. |
| Plain sampling noise | **Large (Established)** | Sharpe SE ≈ 1.0; no sample rejects zero at 5 %. |

## 4. Failure mechanisms (the most important section)

| # | Problem | What happened | Trades / positions | Market conditions | Portfolio construction response | Financial impact | Evidence | Status |
|---|---|---|---|---|---|---|---|---|
| 1 | Sharpe 1.10 → 0.69 | Mean −10 %, vol +43 % | whole book | wider loss tail (worst −₹124k vs −₹90k) | none | Sharpe −0.41 | `sharpe_comparison.json` | Established (arithmetic), cause Plausible |
| 2 | Clean-OOS 0.17 | Mean ₹604/cycle | 64 cycles | NIFTY premium/\|move\| 1.08× vs 1.38× IS; overnight gaps 0.62 % vs 0.28 % | unchanged | −₹2.2k/cycle vs IS | `regime_descriptive.csv` | Established (description), cause Plausible |
| 3 | Profit concentration | Top-5 cycles = 98 % of OOS net | NIFTY/SENSEX Q2–Q3 2026 | calm window | none | removal of 5 → ₹5k | `oos_leave_best_out.csv` | Established |
| 4 | Overnight gap losses | −₹106k IS, −₹111k clean, 48 % of OOS worst-decile loss booked by D0 09:16 | short legs held through the night | gap days | first plugin tick D0 09:16 (reaction, not prevention) | clean OOS overnight > clean net | `pnl_time_decomposition_summary.csv` | Established; "un-hedgeable by current rules" Plausible |
| 5 | Wings don't protect | wings never reached (max NIFTY move 963 vs 2,000) | 4 wings/cycle | no tail event | fixed distance | −₹83k IS, −₹47k OOS | `wing_summary.csv` | Established |
| 6 | Cut logic hurts | 23 helped / 20 hurt, loser avg 2.3× winner | 43 OOS cycles acted | gaps, then reversal | whole-leg cut at ~2× price | −₹356k (cut only), −₹151k (frozen) | `plugin_helped_hurt.csv` | Established observationally; mechanism Plausible |
| 7 | Re-entry mixed | +₹259k vs cut-only OOS; band −₹54k OOS (6 cycles) | 40 cycles | | 30-min cooldown, band | still below hold | `plugin_effect.log` | Established / band effect Unknown (n=6) |
| 8 | Capital stops | DD ↓ (−373k → −266k), net −₹117k | 24 cycles | | 4 %/1 % stop | trade-off | `plugin_effectiveness.csv` | Established |
| 9 | Settlement bias | proxy closer to strike | 243 cycles | | n/a | +₹50k OOS flattering | `settlement_sensitivity.csv` | Established; mechanism Unknown |
| 10 | Execution fragility | clean OOS turns negative at 1.6× slippage | all fills | | n/a | ₹39k → 0 | `breakeven_slippage.csv` | Established (sensitivity), actual slippage Unknown |
| 11 | Contamination | exposed window = 82 % of OOS P&L | 36 cycles | calm NIFTY window | structure observed there | | `contamination_tables.csv` | Established |
| 12 | Side flip | short put earned IS, short call OOS | | rising vs different | symmetric | ₹636k vs ₹0.2k put | `leg_attribution_summary.csv` | Established |

## 5. Final diagnosis (evidence-based)
1. The Sharpe numbers are correct; their weakness is dominated by **sampling error** (SE ≈ 1.0): the IS 1.10, OOS 0.69, clean 0.17 and corrected 0.54/0.04 cannot be told apart, and none can be told from zero at 95 %.
2. The thin edge is **premium minus realised distance**. It was large in the exposed window (calm NIFTY), small elsewhere.
3. Losses arrive **overnight** and **in the tail**; the plugins and wings do not address either (cuts react after the gap; wings sit beyond any observed move).
4. Contamination and two backtest defects (settlement proxy, one entry print) overstated OOS performance by roughly ₹50k; the corrected full-OOS Sharpe is 0.54 and clean 0.04.
5. The cut/re-entry plugins, as frozen, **reduce** OOS P&L.

## 6. Ranked research priorities
1. Measure real slippage and obtain exchange settlement values; re-baseline once (H1, H2).
2. Overnight and expiry-day risk (H3, H4).
3. Premium/realised-move cushion as the single explanatory variable (H5).
4. Wing purpose via margin (H6). 5. Exposure normalisation (H7). 6. Cut/re-entry restructure (H8). 7. Regime conditioning (H9, last).
Independent evidence must come from new data (forward paper trading from 2026-11-18, pre-2023 history).

## 7. Files
Reports: `SHARPE_METHODOLOGY_AUDIT.md`, `RETURN_DISTRIBUTION_ANALYSIS.md`, `MARKET_REGIME_ANALYSIS.md`, `POSITION_AND_LEG_ATTRIBUTION.md`, `PLUGIN_EFFECTIVENESS_REPORT.md`, `TRANSACTION_COST_ANALYSIS.md`, `RESEARCH_CONTAMINATION_REPORT.md`, `NEXT_RESEARCH_HYPOTHESES.md`. Tables: `../results/*.csv|json`. Charts: `figures/`. Scripts: `../*.py`; test: `../../tests/test_diagnostics.py`.
Honest labelling: all scripts were **executed** and outputs **observed**; the corrected settlement run was **computed analytically** (settlement leg re-valued; fills unchanged) rather than by a full engine re-run; plugin OOS runs skipped the C++ parity check (parity validated earlier on 13,525 runs).
