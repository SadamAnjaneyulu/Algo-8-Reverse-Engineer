# Original Sharpe Benchmark (2.19): what is known, what is not

**Result:** the 2.19 **cannot be verified or reproduced** from anything in this repository. It exists only as a one-line summary of a backtest screenshot that is **not in the repo**, has **no trades**, no methodology, and was never reproduced. Our 0.04 (clean OOS, corrected settlement) and the 2.19 are **not comparable**. Evidence labels: **VERIFIED** (read in a repo file / computed here), **INFERRED**, **UNVERIFIED / UNKNOWN**. Code executed: `live_pnl.py`; arithmetic below was computed.

## 1. Where 2.19 comes from

| Source in repo | What it says | Status |
|---|---|---|
| `report/ALGO8_COMPLETE_RESEARCH_REPORT.md:608` | "Lineage X's documents mention a prior backtest screenshot (3 Mar 2025 – 27 May 2026: return 47.22 %, CAGR 36.88 %, Sharpe 2.19). It covers a different period, comes with no trades, and was **not reproduced**; it is not evidence here." | VERIFIED text |
| `audit/ALGO8_DATA_GAPS_AND_REQUIREMENTS.md:18` | Same figures; "Different period; not reproduced; no trades for it". | VERIFIED text |
| `FINDINGS.md:133` | "the supplied screenshot covers 3 Mar 2025–27 May 2026, which is not in this data". | VERIFIED text |
| `Info.txt` | Contains **no** performance figure. Only: BTST algorithm, 4 % carry-forward SL, 1 % of capital on expiry day, capital ₹2 Cr. | VERIFIED |
| The screenshot image itself | **Not in the repository** (searched all images/PDFs). | **MISSING** |

(Other hits of "2.19" in the repo are unrelated numbers.) **Action needed from you:** supply the screenshot or its source report; without it every item in §3 stays unknown.

## 2. What the three numbers imply (arithmetic, VERIFIED)

* 3 Mar 2025 → 27 May 2026 = 450 days = 1.232 years. A 47.22 % return over 1.232 years compounds to **36.9 %** a year → matches the quoted CAGR 36.88 %. So the return/CAGR pair is internally consistent as a simple total return over that span.
* **Implied P&L if the denominator were ₹2 Cr:** 0.4722 × ₹2 Cr = **₹94.4 lakh** in 15 months (**unverified** denominator). For scale, the live ledger's gross P&L in its 4-month window was ₹26.2 lakh (all 35 cycles; ₹15.5 lakh over the 30 clean D-1+D0 cycles), i.e. ~₹6.5 L/month gross vs ~₹6.3 L/month implied by the screenshot — same order of magnitude *before* any costs, but this is a coincidence of scale, not a reconciliation.
* A Sharpe of 2.19 with a 36.9 % CAGR implies an annual volatility of roughly 36.9/2.19 ≈ 16.8 % **if** the Sharpe used CAGR-like returns and a 0 % risk-free rate — an **inference** only; the screenshot's convention is unknown.

## 3. Items required by the brief — status

| Item | Status |
|---|---|
| Evaluation period | **VERIFIED as quoted:** 3 Mar 2025 – 27 May 2026. It does **not** overlap the live ledger (23 Jun – 22 Oct 2026). It **does** overlap our Breeze dataset (124 complete cycles). |
| Instruments | **UNKNOWN** (NIFTY only? SENSEX only? both?). |
| Capital denominator | **UNKNOWN** (₹2 Cr is the only stated capital, in `Info.txt`). |
| Return methodology (daily MTM / realised / per cycle; compounding) | **UNKNOWN.** The CAGR consistency suggests compounding of the total return only. |
| Observation frequency | **UNKNOWN.** |
| Annualisation | **UNKNOWN** (√252 daily, √52 weekly and √12 monthly give materially different values for the same series). |
| Risk-free rate | **UNKNOWN.** |
| Transaction costs / brokerage / slippage | **UNKNOWN.** The ladder trades ≈1,200 orders per cycle; ₹20/order brokerage alone is ≈ 40 % of gross P&L in the live window (below), so this is the single most important unknown. |
| Margin methodology | **UNKNOWN.** |
| NIFTY and SENSEX combined? | **UNKNOWN.** |
| Computed on realised portfolio returns? | **UNKNOWN** (a backtest screenshot suggests simulated, not live, returns). |
| Backtest vs live | The screenshot is a **backtest** (no trades supplied, period precedes the live ledger). Whether it was produced by the algo vendor's own engine, with what fill model, is unknown. |

## 4. Comparable measurements we **can** make (all computed here, methodology stated)

Same convention as our earlier backtest: sum of NIFTY+SENSEX P&L per ISO week ÷ ₹2 Cr, mean/std(ddof 1) × √52, risk-free 0, no compounding. Costs = the **assumed** model (₹20/order, statutory rates, no slippage for live fills which are actual prices).

| Series | Window | Weeks | Total | Sharpe (weekly, √52) | Standard error (Lo) |
|---|---|---:|---:|---:|---:|
| **Real Algo 8 ledger**, gross of costs | 23 Jun–22 Oct 2026, 35 cycles | 18 | ₹26.2 L | **2.79** | ≈ 1.7 |
| Real ledger, net of the assumed cost model | same | 18 | ₹15.6 L | **1.71** | ≈ 1.7 |
| Real ledger, 30 clean D-1+D0 cycles only, gross | | 17 | ₹15.5 L | 1.90 | ≈ 1.8 |
| Real ledger, 30 clean cycles, net | | 17 | ₹6.0 L | 0.77 | ≈ 1.8 |
| Our earlier 4-leg baseline (clean OOS, corrected settlement) | Nov 2025–Nov 2026, 64 cycles | 34 | ₹9.3k | **0.04** | ≈ 1.2 |
| Reconstructed ladder R1 (this programme, after look-ahead fix), net | 3 Mar 2025–27 May 2026, 124 cycles | 65 | ₹19.9 L | **1.36** | 0.9 |
| R1, gross | same | 65 | ₹31.6 L | 2.18 | |

(The costs in the live rows are the cost model applied to the real fills, **not** the broker's actual charges, which are unknown. Brokerage alone, ₹20 × ~37 k orders, is ₹7.5 L.)

## 5. Comparability verdict
* **0.04 vs 2.19: not comparable.** The 0.04 comes from a 4-order-per-cycle caricature of Algo 8 (≈ 1/300 of the real order flow), on a clean-OOS sample, after cost assumptions and a settlement correction. The 2.19 is from an unknown simulator, unknown costs and a different period.
* The real algo's own realised P&L in the only window we can see is ~1.7 (net of the assumed costs) to ~2.8 (gross) with a standard error of ~1.7 over 18 weeks. A Sharpe near 2 is **plausible** for the real behaviour, but our evidence for it is statistically weak and the live window is the same window the rules were decoded from.
* We therefore **cannot** call 2.19 "reproduced", "refuted" or "gap closed" yet. The first step to closing this is obtaining the screenshot/source and its stated conventions.
