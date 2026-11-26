# Phase 1, Gates 3b (wing release) and 3c (overnight lump): result

*2026-11-25. Plan `PHASE1_GATE3BC_PLAN.md`, written before computing. Experiments `P1-3B-0`, `P1-3C-0` (`outputs/phase1/3BC.json`). Teacher-forced on the real position; no engine run (nothing was supported). Evidence: historical reproduction on the 32 development cycles. Nothing committed.*

## Gate 3b report: wing release (which long is sold)
| Field | Content |
|---|---|
| Status | **CONDITIONAL**: no alternative rule supported; the engine rule stands |
| Baseline | engine rule W1 (outermost first); B1 wing sell F1 0.497 (recall 0.41) |
| Result | population 589 of 600 real wing sells with two or more held wing contracts (chance 0.262): **W1 outermost 0.411, W2 cheapest premium 0.413**, W3 most recent 0.362, W6 most lots 0.261, W4 oldest 0.127, W5 innermost 0.024 |
| Criteria | support rule (+0.05 vs W1, interval above 0, >= 20 of 32 cycles): W2 +0.002 [0.000, 0.006] (31 of 32 cycles >= W1) fails the +0.05 bar; W3 -0.049 [-0.163, +0.063]; W4, W5, W6 significantly worse; **none supported** |
| Reading | W1 and W2 almost always select the same contract (the outermost wing is the cheapest); the choice is about 15 points above chance and stops there. 11 of the 589 orders involve a strike outside the downloaded chain (premium set to 0 = cheapest, a stated limit) |
| Classification | wing release quantity and timing **Confirmed**; which wing **Partial** (0.41 exact; likely limited by the lot-level history that the log does not give) |

## Gate 3c report: overnight lump
| Field | Content |
|---|---|
| Status | **CONDITIONAL**: size remains Unresolved; engine form stands |
| Baseline | engine: 0.827x NIFTY / 0.503x SENSEX of heavy-side shorts; error about +/-13 lots, 24% median (earlier work) |
| Result | 30 cycles with a lump, 73 orders, 1,489 lots (mean 49.6 lots per cycle). **Side:** predicted heavy side equals the real lump side in 28 of 30 cycles (0.933). **Size, leave-one-cycle-out mean absolute error:** M1 (engine form) **18.6 lots**, M2 heavy minus light 25.3, M3 total shorts 22.2, **M4 constant per underlying 16.8**. Median relative error: M1 0.163, M2 0.287, M3 0.376, M4 0.242 |
| Criteria | support rule (MAE lower by >= 20%, interval below 0, >= 20 of 30 cycles better): M2 +35.9% (worse), M3 +19.3% (worse), M4 -9.7% with interval [-17.2, +7.5] and 10 of 30 cycles better: **none supported** |
| Reading | a plain constant is about as good as any position-based size: **the lump size is not explained by the position** (consistent with a capital or risk input the log does not contain). The engine form is kept as a fitted parameter, labelled as such |
| Classification | lump side **Confirmed** (0.93), clock regimes **Confirmed**, strike **Partial**, **size Unresolved** (irreducible without margin/capital records) |

## Limits
Same development cycles; about 30 lump cycles (wide intervals); held wing lots come from fills (the lot sold is not in the log; oldest-first within a contract is a convention); module labels inferred; ten rules counted.
