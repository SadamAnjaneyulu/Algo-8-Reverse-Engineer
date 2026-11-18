# Benchmark (Sharpe 2.19) Methodology Status

**Result: still unverified.** Nothing in the repository, its 20+ branches, the delivery archives or the container contains the screenshot or any document stating how 2.19 was computed. No new fact about the benchmark was found in this phase, and none is invented here. Evidence labels: VERIFIED (read/computed), UNKNOWN. Searched: all tracked files and all branch heads for "2.19", "47.22", "36.88", "screenshot"; all images/PDFs/spreadsheets ever added in git history (only this project's own figures); `Algo8_Delivery/` archives; the container file system.

## 1. What the repository says (VERIFIED text, unverified source)
Three documents repeat one summary: *screenshot, 3 Mar 2025 – 27 May 2026, return 47.22 %, CAGR 36.88 %, Sharpe 2.19; different period from the live ledger; no trades; not reproduced* (`report/ALGO8_COMPLETE_RESEARCH_REPORT.md:608`, `audit/ALGO8_DATA_GAPS_AND_REQUIREMENTS.md:18`, `FINDINGS.md:133`). `Info.txt` contains no performance figure (only the BTST structure, the 4 %/1 % stops and ₹2 Cr capital).
Internal arithmetic (VERIFIED): 450 days = 1.232 years; 47.22 % over that span compounds to 36.9 % a year (matches the quoted CAGR). Implied P&L if the denominator were ₹2 Cr: ₹94.4 lakh (denominator unknown).

## 2. What is missing (UNKNOWN)
| Item | Needed to compare |
|---|---|
| The screenshot / source report | everything below |
| Original trade ledger for 3 Mar 2025 – 27 May 2026 | rebuilds the P&L series |
| Capital denominator | % returns |
| Return frequency (daily / weekly / per trade / monthly) | Sharpe scale |
| Annualisation (√252, √52, √12) | 2.19 vs ours differs by up to √(252/52) = 2.2× for the same series |
| Risk-free rate, compounding | numerator |
| Transaction costs, slippage, brokerage | the algorithm sends ~1,200 one-lot orders per cycle; ₹20/order is ~40 % of live gross P&L |
| Instruments (NIFTY, SENSEX, both) and margin treatment | scope |
| Backtest or live; fill model | realism |

## 3. What we can and cannot compare (VERIFIED computations from earlier phases; methodology: weekly ISO sums ÷ ₹2 Cr, √52, rf = 0)
| Series | Sharpe | Weeks | Comment |
|---|---:|---:|---|
| Live ledger, gross | 2.79 | 18 | standard error ≈ 1.7; same window the rules were decoded from |
| Live ledger, net of an assumed cost model | 1.71 | 18 | costs assumed, not the broker's |
| Reconstructed ladder R1, screenshot window | 1.36 net / 2.18 gross | 65 | rules not validated on D0; R1 ≈ ⅕ of the benchmark's return |
| Earlier 4-leg baseline, clean OOS | 0.04 | 34 | not Algo 8 behaviour |

**Verdict:** the incompatible conventions mean 2.19 can be neither confirmed nor refuted. The D0 reconstruction in this phase **does not change this**: the recovered D0 rules explain too little to produce a performance estimate, and none has been added to a backtest. Do not compare the 2.19 with any of the numbers above until the screenshot or its source report is supplied.
