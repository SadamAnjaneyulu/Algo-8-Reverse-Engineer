# Algo 8 — D0 chunk 5: free-running reconstruction, and D0 overview

*Plan `D0_FREE_RUN_PLAN.md`, written before the tests. In-sample: D0 of the 30 cycles with both logs. The simulator starts from the real book carried from D-1. Every fitted part is refit on the training cycles of each split. Figure: `figures/bl_d0fr_summary.png`.*

## 0. Result
* **How accurately D0 is reconstructed:**

| split | cycles | lot F1 | precision | recall | F1, exact strike | null (+15 min) | AUC any activity (95% CI) |
|---|---|---|---|---|---|---|---|
| out-of-fold (cycle halves) | 30 | **0.410** | 0.415 | 0.406 | 0.194 | 0.151 | **0.830** (0.800–0.859) |
| unseen A: same version, later cycles | 9 | **0.452** | 0.477 | 0.429 | 0.258 | 0.093 | **0.869** (0.827–0.896) |
| unseen B: train V1, test V2 | 10 | **0.390** | 0.355 | 0.432 | 0.188 | 0.107 | **0.826** (0.776–0.858) |

* **D0 is reconstructed less well than D-1.** D-1 reached lot F1 0.63 / 0.62 and AUC 0.92 / 0.91 on unseen cycles. *Observed.*
* **The weak links** are solo selling (70% of D0 sells), the size and timing of buy-back bursts, and the stop.
  * Errors compound: the hedge classes follow simulated body orders, and a stop missed or added changes the rest of the day.
* **The stop** in free running agrees on 24 of 30 cycles (out-of-fold): 8 found, 3 missed, 3 false. These follow differences between simulated and real P&L.

## 1. By class (out-of-fold)
| cls | real_lots | sim_lots | matched | precision | recall | F1 | F1_strict | F1_within1 |
|---|---|---|---|---|---|---|---|---|
| body_sell | 8336 | 8865 | 4252 | 0.480 | 0.510 | 0.494 | 0.299 | 0.453 |
| body_buyback | 9656 | 10498 | 3712 | 0.354 | 0.384 | 0.368 | 0.159 | 0.291 |
| wing_buy | 7312 | 6884 | 3237 | 0.470 | 0.443 | 0.456 | 0.160 | 0.300 |
| wing_sell | 8973 | 9721 | 3470 | 0.357 | 0.387 | 0.371 | 0.155 | 0.234 |
| body_long | 3082 | 760 | 469 | 0.617 | 0.152 | 0.244 | 0.007 | 0.016 |
| stop | 3515 | 3296 | 1456 | 0.442 | 0.414 | 0.428 | 0.313 | 0.342 |


* `body_long` is only partly modelled: the 09:15 opening wings and the clearance. The body-stream long trades during the day are not (3,082 real lots against 760 simulated).
* Not modelled: 908 lots (`h_` shorts and covers, `v_` shorts and buys, `m_`).

**Unseen cycles, by class:**

| cls | forward A (same version, later cycles) | forward B (train V1, test V2) |
|---|---|---|
| body_buyback | 0.408 | 0.399 |
| body_long | 0.185 | 0.239 |
| body_sell | 0.533 | 0.413 |
| stop | 0.605 | 0.515 |
| wing_buy | 0.492 | 0.402 |
| wing_sell | 0.379 | 0.329 |


## 2. AUC
| split | AUC_model | ci_lo | ci_hi | AUC_raw_simulator | cells | positives |
|---|---|---|---|---|---|---|
| OOF (cycle halves) | 0.830 | 0.800 | 0.859 | 0.748 | 22500 | 5440 |
| forward A (same version, later cycles) | 0.869 | 0.827 | 0.896 | 0.797 | 6750 | 1121 |
| forward B (train V1, test V2) | 0.826 | 0.776 | 0.858 | 0.737 | 7500 | 1388 |


`AUC_raw_simulator` scores each cell by the simulator's own activity alone (no fitted model).

## 3. Fitted parts per split
| split | train | test | theta | tp | ladder | counter_r | opening_wings | waves |
|---|---|---|---|---|---|---|---|---|
| OOF half 0 test | 15 | 15 | 1.400 | 0.100 | [0.05, 60, True] | 0.250 | 20 | 158 |
| OOF half 1 test | 15 | 15 | 1.400 | 0.100 | [0.1, 60, True] | 0.500 | 13 | 211 |
| forward A (same version, later cycles) | 21 | 9 | 1.400 | 0.100 | [0.05, 60, True] | 0.250 | 14 | 220 |
| forward B (train V1, test V2) | 20 | 10 | 1.400 | 0.100 | [0.05, 60, True] | 0.250 | 13 | 176 |


## 4. D0 decoded: overview of chunks 1–5
| part | rule found | accuracy (out-of-fold unless stated) | status |
|---|---|---|---|
| Pair sells | **Fixed timetable per underlying × version** (seconds repeat across cycles); strike nearest the previous close | pair-lot F1 0.805, precision 96%, strike 99% | Observed |
| Pairs off the timetable | Opening burst around 09:16; re-centring after buy-backs; D-1 two-candle breakout | breakout F1 0.375 vs placebo ≤ 0.10 | Observed, partial |
| Solo sells (70%) | D0 spot ladder (0.05 step, lots = steps crossed, fresh 60-min extreme) + counter-sell after other-right buy-backs | F1 0.38–0.40 | Observed, weak |
| D0 selling AUC | market + rules | 0.932 (causal 0.893) | Observed |
| Buy-back stop | own premium ≥ 1.4× entry on the minute high (D-1: 1.6×) | lot F1 0.39 (null 0.22) | Observed |
| Take-profit | premium ≤ 0.1× entry | raises deep-profit recall to 30% | Observed |
| Buy-back bursts | side-level cut of about 10% of the right's lots, across 3 strikes | trigger not found (no AUC ≥ 0.70) | Unresolved |
| Carried-lot buy-backs | not tied to their own premium (D-1 entry or D0 open) | AUC ≈ 0.55 | Unresolved |
| Buy-back AUC | market + book | 0.815 (causal 0.787) | Observed |
| Hedge controller | buy the gap S − L about 4 s after the body order; lump counts as hedge on D0 | waves = gap 94% | Observed |
| Wing strike | premium nearest 2.5% of ATM | exact 38%, ±1 69% (chance 10% / 30%) | Observed, weaker than D-1 |
| Lump salvage | released by the controller when L > S | 99.9% of lots while L > S | Observed; wing vs lump choice unresolved |
| Cycle stop | cumulative MTM (D-1 + D0) ≤ −L, checked live | 11/11, no false alarm (minute close); L between 1.17 and 1.29 lakh | Observed |
| 15:14 clearance | buy back all shorts (99.95%), sell longs | — | Observed |
| **Complete D0** | all of the above, free-running | lot F1 0.41 / 0.45 / 0.39; AUC 0.83 / 0.87 / 0.83 | Observed |

## 5. Caveats
* **In-sample.** All structure was found on these 30 cycles. Unseen splits test parameters, not the discovery itself.
* **The stop uses the minute close**, a look-ahead of less than one minute, because the real stop acts on live prices.
* **Sale prices** in the simulator are the previous minute's close. Buy-backs and wing trades use the minute's close for cash.
* **The chained variant** (D0 started from the simulated D-1 book) is **not built** in this chunk. Errors would compound further.
* **Unseen split B** uses V1 waves for V2 cycles. The timetable differs by version, so pair sells degrade there.

## Run order
`bl_d0_fr.py` (~20 s) → `bl_d0_fr_score.py` (~40 s) → `make_d0fr_report.py`. Needs the chunk 1–4 outputs.
