# Actual vs Simulated Comparison (Phase G)

**Result:** at event level the simulation reproduces the **timing and approximate strike of scheduled sales** and the **15:14 clearance**, and nothing else reliably; at execution level the simulated price is within about 1.3 % of the actual order price; at portfolio level the simulation holds the right book size only in discovery and loses it in the holdout. Matching is hierarchical and count-based (L1 = same cycle/right/strike within the same 2-minute bucket; L2 = strike mismatch allowed; L3 = timing mismatch up to 10 minutes). Code executed: `compare_events.py`, `mismatch_report.py`; variant V1, simulator v1.1. Discovery numbers are development data (rules were fitted there); holdout numbers are the evaluation (partially exposed).

## 1. Decision agreement (V1; precision = matched ÷ simulated lots; recall = matched ÷ actual lots)

| Category | Split | L1 P / R | **L2 P / R** | L3 P / R | Sim lots | Actual lots |
|---|---|---|---|---|---:|---:|
| Body sales (all) | discovery | 0.46 / 0.11 | 0.80 / 0.19 | 0.94 / 0.22 | 1,842 | 7,880 |
| | holdout | 0.72 / 0.15 | 0.76 / 0.16 | 0.94 / 0.20 | 410 | 1,952 |
| Scheduled sales | discovery | 0.40 / 0.30 | 0.71 / 0.53 | 0.85 / 0.63 | 1,659 | 2,248 |
| | holdout | 0.60 / 0.45 | 0.65 / 0.48 | 0.74 / 0.55 | 405 | 542 |
| Replacement sales | discovery | 0.08 / 0.01 | 0.14 / 0.01 | 0.33 / 0.02 | 183 | 3,136 |
| | holdout | 0 / 0 | 0 / 0 | 0 / 0 | 5 | 731 |
| Buy-backs excl. final | discovery | 0.41 / 0.10 | 0.62 / 0.14 | 0.77 / 0.18 | 1,490 | 6,427 |
| | holdout | 0.40 / 0.11 | 0.56 / 0.15 | 0.74 / 0.20 | 308 | 1,128 |
| Clock-B buy-backs | discovery | 0.10 / 0.02 | 0.19 / 0.04 | 0.19 / 0.04 | 183 | 795 |
| | holdout | 0.20 / 0.01 | 0.20 / 0.01 | 0.20 / 0.01 | 5 | 113 |
| Price-stop-like buy-backs | discovery | 0.44 / 0.22 | 0.61 / 0.31 | 0.75 / 0.37 | 1,307 | 2,621 |
| | holdout | 0.38 / 0.28 | 0.47 / 0.35 | 0.62 / 0.46 | 303 | 411 |
| Final liquidation | discovery | 0.25 / 0.27 | 0.32 / 0.35 | 0.40 / 0.44 | 2,029 | 1,840 |
| | holdout | 0.46 / 0.35 | **0.79 / 0.60** | 0.83 / 0.64 | 423 | 550 |
| Hedge additions | discovery | 0.19 / 0.05 | 0.77 / 0.20 | 0.93 / 0.24 | 1,659 | 6,396 |
| | holdout | 0.33 / 0.10 | 0.69 / 0.20 | 0.85 / 0.25 | 405 | 1,383 |
| Hedge reductions | discovery | 0.12 / 0.06 | 0.29 / 0.16 | 0.39 / 0.21 | 3,851 | 7,129 |
| | holdout | 0.18 / 0.16 | 0.30 / 0.27 | 0.46 / 0.42 | 1,183 | 1,301 |

## 2. Execution agreement (L1-matched sales; holdout 367 orders, discovery 1,183)
Simulated reference price vs actual order price: median difference +0.19 % (holdout) / +0.49 % (discovery); median absolute 1.34 % / 2.30 %. Strike agreement given a time match: scheduled sales exact for 67 % of actual lots, strike-mismatch for 27 %, no match 5 % (holdout, non-consuming nearest-order labels). Quantity agreement is the weak point (recall ≤ 0.5 even where timing agrees). Timestamp: 94.6 % of simulated sales within one minute of an actual same-right sale (weak, sales are frequent); **sub-minute and intra-second timing cannot be assessed** (fills are whole seconds; body decision times unavailable).

## 3. Portfolio-state agreement (net short body lots by right at 10:00…15:00)

| Variant | Split | Correlation | MAE (lots) | Mean actual | Mean simulated |
|---|---|---:|---:|---:|---:|
| NULL | discovery / holdout | 0.64 / −0.52 | 38 / 67 | 71 / 75 | 39 / 8 |
| V0 | discovery / holdout | 0.57 / −0.48 | 32 / 68 | 71 / 75 | 63 / 16 |
| **V1** | discovery / holdout | **0.79 / −0.33** | 26 / 60 | 71 / 75 | 51 / 17 |

MAE by hour (V1, discovery): 16 (10:00) → 34 (15:00); (holdout): 53 → 65. Gross exposure, hedge coverage, portfolio premium and realised/unrealised P&L were compared only through the P&L increments: D0 increment sim vs live — discovery V1 ₹6.1 L vs ₹5.3 L (corr 0.77), holdout V1 ₹0.08 L vs ₹1.9 L (corr 0.62); NULL discovery ₹12.0 L (corr 0.67). Active-contract count and gross exposure were not separately tabulated.

## 4. Mismatch classification (holdout V1, share of each actual class's lots; non-consuming nearest simulated order of the same right and side; `mismatch_summary_V1.csv`, `mismatch_events_V1.csv`)

| Actual class | L1 exact | Incorrect strike (L2) | Incorrect timing (L3) | Missing rule / missing state |
|---|---:|---:|---:|---:|
| Scheduled sale | 67 % | 27 % | 0 % | 5 % |
| Off-schedule sale | 16 % | 16 % | 54 % | 14 % |
| Replacement sale | 14 % | 8 % | 30 % | 49 % |
| Buy-back | 10 % | 31 % | 19 % | 39 % |
| Final liquidation | 7 % | 80 % | 13 % | 0 % |

(Non-consuming labels flatter classes where simulated orders are dense — e.g. off-schedule sales within 10 minutes of a scheduled simulated sale — compared with the count-consuming table above.) Reasons by class: **scheduled** — correct trigger, imperfect quantity and ±1-strike choice; **final liquidation** — correct minute, strike-level differences because the simulated book differs; **buy-backs/replacements** — **missing rule** (trigger unknown); **off-schedule** — missing rule; other categories carry **ambiguous transaction ordering** (whole-second fills) and **missing contract data** (far wings absent from the chain; flagged in the order log), neither quantifiable here beyond the flag counts. **Execution-price difference** is ≤ 1.4 % (median absolute).

## 5. Conclusion
The behavioural gap is concentrated exactly where the earlier phase located it — the D0 buy-back/replacement process — and is **not** closed by anything recovered so far. P&L similarity (discovery ₹6.1 L vs ₹5.3 L) is **not** behavioural replication: the same simulator with no D0 trading rules (NULL) gives ₹12 L and the same correlation.
