# Algo 8 decision engine v1 — built from the 35 live cycles, backtested 2 years in-sample / 1 year out-of-sample

**What this is.** A rule engine whose entry schedule, strike choice, wing choice, risk controls (per-lot stop, cycle stop, flatten) and settlement are taken from the 35 live cycles and run on the event-driven core (`src/algo8_v1.py`, parameters in `config/algo8_v1_params.json` with ledger hash and provenance). It is the closest executable approximation of Algo 8's observed decision making that the evidence supports. **It is not the original algorithm:** entry schedule and risk constants are descriptive, in-sample hypotheses; behaviours whose trigger is unknown are *not* modelled (off-schedule entries, Clock-B reductions, lump hedge, "4 % carry SL", "1 % expiry-day" rule, margin gate).
**Direction.** Replicating decision making and risk control, not maximising P&L: no parameter was tuned on any period; variants below are pre-declared sensitivities and ablations, and none was selected.

## 1. Read this first — what the IS/OOS split can and cannot tell you
* IS = D0 ≤ 2025-11-17 (173 eligible cycles, ≈ 2 years); OOS = D0 ≥ 2025-11-18 (100 cycles, ≈ 1 year), the same boundary as the earlier backtest; the single embargo cycle (D-1 in IS, D0 in OOS) is dropped.
* **The rules were read from 35 live cycles (2026-06-23 → 2026-10-22) that lie inside the OOS year.** So the **IS years are out-of-time for the rules** (a genuine test of whether the extracted decision rules behave sensibly on earlier data), whereas the **OOS year contains the sample the rules came from**. It is therefore reported in three tiers: clean before the live window (2025-11-18 → 2026-06-21, previously scored by earlier programmes for related strategies), the live window itself (rules read from it: in-sample), and after it (5 cycles).
* The original has no execution records before June 2026, so **nothing here shows that Algo 8 behaved this way in 2023–2025**, and historical P&L cannot be compared with the original.
* The 2-year IS has 68 SENSEX cycles only (SENSEX data start 2024-05-30). Expiry structures differ (NIFTY Thursday → Tuesday 2025-09; SENSEX Friday → Tuesday → Thursday): see §4.

## 2. The decision rules (all HYPOTHESES read from the 35 cycles; `config/algo8_v1_params.json`)
| Decision | Rule in v1 | Source / evidence |
|---|---|---|
| Entry timing, D-1 | sell CE and PE at the 24 minutes where the original sold in ≥ 50 % of the cycles (they cluster at 09:16 + 15 k min and at the :14 clock minutes), lots = conditional median | schedule covers 43 % of the original D-1 body-sell lots; the rest are off-schedule entries with an unknown trigger (U10), **not modelled** |
| Entry timing, D0 | same construction on D0, 38 minutes; **only while the book holds an open body short** and no cycle stop has fired | covers 33 % of original D0 body-sell lots; D0 trigger unknown (U11) |
| Strike | nearest strike to the previous completed minute's index close | exact 79 % in D-1 ladder windows, 45 % over all sells (parity S8) |
| Wing | one OTM same-right wing per body lot whose price ≈ 0.025 × body price | strike exact 32 % (S11); wing-to-body association is timing-only (U3) |
| Per-lot stop | buy back a body lot at LTP ≥ 1.60 × its own entry (entry ≤ ₹4 exempt); its wing closes with it | band 1.55–1.70; explains ≤ 17 % of original buy-backs (S15) |
| Cycle stop | cumulative LTP MTM ≤ −₹1,44,000 → liquidate everything, no further entries (marks: previous completed close) | −1.30 to −1.44 lakh band; reproduced 1/0/0 of 11 causally (S16) |
| Final flatten | D0 minute 359 (15:14) from 2026-08-03; minute 365 (15:20) before | observed last-short minute; pre-cutover rule extrapolated to all earlier history |
| Settlement | residual lots cash-settled at the official index close (Yahoo) | proxy (U12) |
| Execution | fill at the open of the decision minute; slippage max(₹0.10, 0.5 %) against the order; costs per `bt/account.py` | **cost rates other than the 2026 STT are unverified**; no bid/ask data |
| Size | lots as in the ladder, at each session's inferred lot size; **the cycle-stop rupee limit scales linearly with the session lot size** (₹1,44,000 at the 2026 size of the index: NIFTY 65 / SENSEX 20; user decision); the per-lot stop is a price multiple and needs no scaling | historical lot size is inferred from volumes (U14); variant S1 uses 2026 sizes; V8 keeps the limit fixed in rupees (changes 41 of 274 cycles, all with non-2026 lot sizes) |

## 3. How close is v1 to the 35 live cycles? (in-sample; same pre-registered classes as the parity study)
| category | n_sim | n_act | P | R | lift_P | cls | R1_recall_for_comparison |
|---|---|---|---|---|---|---|---|
| D-1 body entries (17 ladder slots, first 3 min) | 2112 | 1888 | 0.71 | 0.80 | 1.58 | PARTIAL MATCH | 0.79 |
| D-1 body entries (all original D-1 body sells) | 2112 | 4834 | 0.96 | 0.42 | 1.52 | PARTIAL MATCH | 0.33 |
| D-1 wing entries | 2112 | 4337 | 0.88 | 0.43 | 1.46 | PARTIAL MATCH | 0.33 |
| D-1 body buy-backs | 568 | 1640 | 0.79 | 0.27 | 18.03 | PARTIAL MATCH | 0.24 |
| D0 body entries | 4435 | 12686 | 0.75 | 0.26 | 1.72 | PARTIAL MATCH | 0.00 |
| D0 body buy-backs | 6069 | 12714 | 0.48 | 0.23 | 7.13 | MISMATCH | 0.05 |
| D0 wing sells | 6069 | 10243 | 0.29 | 0.17 | 5.28 | MISMATCH | nan |
| D0 wing entries | 4435 | 9855 | 0.61 | 0.27 | 1.52 | PARTIAL MATCH | nan |

Inventory: contract-minutes exactly equal **7.9 %** (R1: 5.0 %); overnight short lots actual 104 vs v1 49 (R1: 36); cycle stops v1 9 of 35 vs 12 actual (R1: 1); orders per cycle v1 804 vs 1139 actual.
**Reading:** v1 moves D0 entries from 0 to precision 75 % / recall 26 % and raises D-1 recall to 42 %, but the original's off-schedule and D0 trigger-based actions are still absent, so the inventory path remains a MISMATCH. v1 is *closer*, not equivalent.

## 4. Backtest results (V0 base; net of slippage and estimated costs; ₹2 crore stated capital; weekly Sharpe = weekly net/₹2 Cr × √52, secondary diagnostic)
| group | cycles | gross | net | costs | weekly_sharpe | max_dd_pct_cycle_level | win_rate | profit_factor | worst_cycle | net_ex_top5 | cycle_stop_share | leg_stops_per_cycle |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| IS | 173 | 9,823,278.50 | 5,212,504.19 | 3,302,634.23 | 1.59 | -3.14 | 53.76 | 1.55 | -244,625.35 | 2,827,438.21 | 32.37 | 81.12 |
| OOS (all) | 100 | 3,427,641.75 | 383,528.39 | 1,998,978.46 | 0.22 | -6.61 | 55.00 | 1.06 | -554,013.52 | -1,065,156.30 | 25.00 | 90.56 |
| OOS clean before live window | 59 | 2,964,568.75 | 1,152,345.22 | 1,167,213.11 | 1.17 | -4.55 | 62.71 | 1.35 | -554,013.52 | -226,291.12 | 23.73 | 91.59 |
| OOS live window (rules read from it) | 36 | 758,986.75 | -339,822.89 | 750,031.27 | -0.58 | -4.43 | 41.67 | 0.85 | -204,246.08 | -1,403,664.12 | 25.00 | 90.78 |
| OOS after live window | 5 | -295,913.75 | -428,993.94 | 81,734.07 | -2.16 | -3.42 | 60.00 | 0.38 | -401,355.24 | -0.00 | 40.00 | 76.80 |
| IS NIFTY | 105 | 5,236,595.00 | 2,329,472.88 | 2,043,581.51 | 0.92 | -3.11 | 51.43 | 1.39 | -244,625.35 | 30,123.70 | 31.43 | 84.52 |
| IS SENSEX | 68 | 4,586,683.50 | 2,883,031.31 | 1,259,052.72 | 1.77 | -3.25 | 57.35 | 1.81 | -208,651.57 | 903,734.11 | 33.82 | 75.87 |
| OOS NIFTY | 49 | 3,048,092.75 | 1,445,047.14 | 1,014,756.90 | 1.35 | -4.07 | 55.10 | 1.60 | -285,063.75 | -3,637.56 | 18.37 | 91.41 |
| OOS SENSEX | 51 | 379,549.00 | -1,061,518.75 | 984,221.56 | -0.94 | -7.79 | 54.90 | 0.72 | -554,013.52 | -1,998,794.94 | 31.37 | 89.75 |
| IS strict only | 81 | 6,231,711.25 | 4,023,257.63 | 1,566,139.14 | 2.13 | -3.24 | 55.56 | 1.93 | -244,625.35 | 1,891,563.41 | 32.10 | 82.69 |
| OOS strict only | 72 | 1,401,145.25 | -746,769.31 | 1,430,292.85 | -0.53 | -6.41 | 52.78 | 0.85 | -554,013.52 | -2,080,379.54 | 27.78 | 90.96 |

By expiry structure (all periods, V0):
| group | cycles | net | weekly_sharpe | win_rate | cycle_stop_share |
|---|---|---|---|---|---|
| structure: NIFTY-Thursday-expiry#1 | 94 | 2,134,841.21 | 0.97 | 53.19 | 31.91 |
| structure: NIFTY-Tuesday-expiry#2 | 61 | 1,870,552.93 | 1.32 | 52.46 | 19.67 |
| structure: SENSEX-Friday-expiry#1 | 29 | 852,642.32 | 1.69 | 62.07 | 34.48 |
| structure: SENSEX-Thursday-expiry#3 | 60 | -367,400.85 | -0.27 | 56.67 | 28.33 |
| structure: SENSEX-Tuesday-expiry#2 | 30 | 1,336,271.09 | 1.49 | 50.00 | 40.00 |

**Caveats on these numbers.** Costs are large (≈ 39 % of gross) because the engine places ≈ 770 orders per cycle; the cost rates are estimates, not verified statutory figures (only the 2026 STT change is confirmed), so net figures are provisional. Drawdown is computed on the cycle-level cumulative P&L, not the minute path. There is no margin model (the cycle stop is the only capital control). The scaled cycle stop fires in about 32 % of in-sample cycles versus 25 % when the limit is held fixed in rupees (variant V8), because older, smaller lots reach a proportionally smaller limit. Cells of 5–60 cycles carry no confidence intervals. Differences between structures are confounded with lot size, liquidity and volatility.

## 5. Sensitivities and ablations (pre-declared; none selected; none changes the rules)
| period | variant | cycles | gross | net | costs | weekly_sharpe | max_dd_pct_cycle_level | cycle_stop_share | orders_per_cycle |
|---|---|---|---|---|---|---|---|---|---|
| IS | A1_no_cycle_stop | 173 | 9,524,229.50 | 4,377,010.90 | 3,680,204.36 | 1.14 | -5.37 | 0.00 | 851.62 |
| IS | A2_no_leg_stop | 173 | 8,142,601.00 | 4,144,183.43 | 2,839,364.54 | 0.81 | -9.34 | 56.65 | 655.94 |
| IS | A3_no_flatten_hold | 173 | 9,678,166.53 | 5,922,129.00 | 2,586,752.76 | 1.78 | -3.15 | 32.37 | 590.03 |
| IS | A4_D1_entries_only | 173 | 4,860,232.75 | 3,089,632.48 | 1,166,102.91 | 1.46 | -2.62 | 14.45 | 263.36 |
| IS | A5_no_wings | 173 | 10,519,569.75 | 7,731,442.52 | 1,737,722.93 | 2.21 | -3.56 | 32.37 | 382.13 |
| IS | S1_2026_lot_sizes | 173 | 13,209,290.50 | 8,193,341.66 | 3,349,065.00 | 2.02 | -3.88 | 32.37 | 764.59 |
| IS | V0_base | 173 | 9,823,278.50 | 5,212,504.19 | 3,302,634.23 | 1.59 | -3.14 | 32.37 | 764.59 |
| IS | V1_slippage_x0 | 173 | 9,718,399.00 | 6,424,729.16 | 3,293,669.84 | 1.96 | -2.83 | 32.95 | 762.37 |
| IS | V2_slippage_x3 | 173 | 9,802,779.00 | 2,568,836.78 | 3,301,050.15 | 0.80 | -4.75 | 32.37 | 764.38 |
| IS | V3_costs_x2 | 173 | 9,823,278.50 | 1,909,869.96 | 6,605,268.46 | 0.59 | -4.63 | 32.37 | 764.59 |
| IS | V4_cycle_stop_mark_open | 173 | 9,749,480.25 | 5,135,478.29 | 3,304,287.75 | 1.57 | -3.39 | 32.37 | 764.94 |
| IS | V5_leg_k155 | 173 | 9,042,505.75 | 4,414,131.47 | 3,311,504.80 | 1.41 | -3.53 | 31.79 | 766.44 |
| IS | V6_leg_k170 | 173 | 9,334,902.50 | 4,801,578.70 | 3,241,357.41 | 1.39 | -4.20 | 33.53 | 750.21 |
| IS | V7_cycle_limit_130k | 173 | 10,320,029.25 | 5,781,139.54 | 3,257,833.34 | 1.80 | -3.00 | 32.95 | 754.53 |
| IS | V8_fixed_rupee_cycle_stop | 173 | 9,387,874.50 | 4,674,300.35 | 3,395,446.32 | 1.38 | -5.38 | 24.86 | 787.06 |
| OOS (all) | A1_no_cycle_stop | 100 | 3,931,668.25 | 580,997.79 | 2,208,826.24 | 0.32 | -5.98 | 0.00 | 849.44 |
| OOS (all) | A2_no_leg_stop | 100 | -1,764,976.50 | -4,402,766.81 | 1,699,271.58 | -1.48 | -27.84 | 63.00 | 649.24 |
| OOS (all) | A3_no_flatten_hold | 100 | 4,003,327.68 | 1,447,665.11 | 1,606,976.41 | 0.76 | -5.18 | 27.00 | 602.84 |
| OOS (all) | A4_D1_entries_only | 100 | 1,537,623.00 | 337,967.76 | 714,671.62 | 0.23 | -6.02 | 12.00 | 263.84 |
| OOS (all) | A5_no_wings | 100 | 4,851,902.00 | 2,866,223.41 | 1,100,807.76 | 1.49 | -4.97 | 24.00 | 387.54 |
| OOS (all) | S1_2026_lot_sizes | 100 | 3,322,167.25 | 288,023.70 | 1,997,844.96 | 0.16 | -6.64 | 25.00 | 767.68 |
| OOS (all) | V0_base | 100 | 3,427,641.75 | 383,528.39 | 1,998,978.46 | 0.22 | -6.61 | 25.00 | 767.68 |
| OOS (all) | V1_slippage_x0 | 100 | 3,263,054.00 | 1,255,151.33 | 2,007,902.67 | 0.70 | -5.75 | 25.00 | 770.88 |
| OOS (all) | V2_slippage_x3 | 100 | 3,456,695.50 | -1,696,338.96 | 2,007,912.30 | -0.97 | -11.79 | 24.00 | 771.76 |
| OOS (all) | V3_costs_x2 | 100 | 3,427,641.75 | -1,615,450.07 | 3,997,956.92 | -0.93 | -11.35 | 25.00 | 767.68 |
| OOS (all) | V4_cycle_stop_mark_open | 100 | 3,407,882.50 | 371,479.73 | 1,995,078.58 | 0.21 | -6.21 | 25.00 | 766.32 |
| OOS (all) | V5_leg_k155 | 100 | 3,136,318.25 | 91,405.64 | 1,999,399.76 | 0.05 | -7.41 | 26.00 | 767.80 |
| OOS (all) | V6_leg_k170 | 100 | 2,737,841.75 | -281,255.69 | 1,980,167.78 | -0.15 | -7.39 | 27.00 | 760.44 |
| OOS (all) | V7_cycle_limit_130k | 100 | 3,399,420.25 | 409,326.17 | 1,961,946.13 | 0.23 | -6.81 | 28.00 | 753.20 |
| OOS (all) | V8_fixed_rupee_cycle_stop | 100 | 3,427,641.75 | 383,528.39 | 1,998,978.46 | 0.22 | -6.61 | 25.00 | 767.68 |

Ablations show what each part of the decision engine *does* in the replica (for example, removing the wings lowers costs and raises the diagnostic Sharpe; removing the per-lot stop worsens the OOS drawdown severely). They are **not** recommendations: the aim is to reproduce Algo 8's observed structure, so no variant replaces the base rules.

## 6. Verdict
* v1 is a **faithful implementation of what the 35 cycles show at the schedule level** (D-1/D0 ladders, ATM strikes, wings, stops, flatten) and is deterministic, causal and tested (31 tests).
* It is **not yet close to the original at the inventory level** (8 % of contract-minutes exact; the engine carries 47 % of the original overnight shorts), because about 57 % of D-1 and 67 % of D0 body-sell lots fall outside the per-minute schedule (their triggers are not revealed by the records).
* The IS/OOS numbers describe how this rule set behaves historically; they say nothing about the original's performance and the OOS year is contaminated by construction (§1).
* To get closer: parent-order ids and sub-second timestamps (see `NEXT_PHASE_ALPHA_READINESS.md` §5) so the off-schedule and D0 triggers can be identified or rejected instead of approximated.

## 7. Reproduce
`python3 src/params_from_35.py && python3 src/run_v1_parity.py && python3 src/run_v1_backtest.py && python3 src/make_v1_report.py` (≈ 5 min; needs the ledger, the pinned dataset commit and the per-cycle cache). Outputs: `outputs/v1_backtest_cycles.csv` (every cycle × variant), `v1_backtest_summary.csv`, `v1_parity_*.csv`. Tests: `python3 -m pytest tests -q`.
