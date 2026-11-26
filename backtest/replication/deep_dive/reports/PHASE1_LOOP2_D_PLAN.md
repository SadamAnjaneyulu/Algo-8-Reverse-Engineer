# Phase 1 final loop, Investigation D: 15:30 candle-close bursts. Preregistration

*Written 2026-11-25 **before** the D computations; the existing G1/G1b files (`outputs/phaseA/g1_bursts.csv`, `g1b_table.csv`, `g1b.json`) were read first and show: eight CE+PE pair bursts, starts 15:25:42 to 15:30:00 (`t0` 55542-55800 s), G1b condition holds in 7 of the 8 burst cycles and 12 of 29 cycles (precision 7/12). Experiments `P1-9-D*`. Analytic only: **no engine change and no extension of the engine session** (decided here, whatever the result). Evidence: historical reproduction on development cycles; the hypothesis is post-observation (G1b was formed after seeing the burst times). Nothing committed.*

## 1. What the available records can and cannot establish (to be verified, DT0)
* One-minute bars end at minute 374 (15:29:00-15:29:59). **The 15:00-15:30 candle is complete only at 15:30:00**; there is no 15:30 bar. The G1b condition used the close of minute 374, i.e. information that exists only from 15:30:00.
* Burst starts lie between 15:25:42 and 15:30:00. A burst that starts before 15:30:00 cannot have been triggered by the completed candle's close.
* Decision timestamps (`t_dec`) exist in the order table only for the non-body modules (`h_`, `s_`, `v_`, `m_`); the burst orders are body (`num`) orders, for which the record has the fill seconds only. Decision time and submission time cannot be separated for them.
* Post-auction cycles (from 3 Aug 2026): the index is frozen from 15:15, so the series is the rebased futures series (`bt3u`, as G1); pre-auction: the index (`bt3x`).

## 2. Tests (each tested once; selection counted: DT1-DT4 = 4)
| # | Test | Definition |
|---|---|---|
| DT0 | timestamp audit | for each burst: start second, the number of seconds between it and 15:30:00, whether it is at/after the candle completion; availability of `t_dec` for the burst orders |
| DT1 | reproduce G1b | condition = close of minute 374 outside the channel (highest high / lowest low of 14:00-14:30 and 14:30-15:00); same 29 cycles, same Fisher test: must give 7/8, p = 0.0033, else a defect in the old analysis |
| DT2 | **causal analogue** | the same condition evaluated on the close of **minute 369** (known from 15:25:00, before the earliest burst start 15:25:42): outside the channel. Success rule as G1b: holds in >= 5 of the 8 burst cycles **and** one-sided Fisher p <= 0.05 |
| DT3 | timestamp-convention sensitivity | the condition at reference minutes 369, 371, 373, 374: bursts hit (of 8), cycles with the condition (of 29), precision, recall, Fisher p; descriptive (4 conventions counted) |
| DT4 | timing concentration | share of burst starts within the last 120 s before 15:30:00, against the share expected if starts were uniform over 15:25:00-15:30:00 (binomial) |

## 3. Decision rules (fixed now)
* If **DT2 fails** its success rule: G1b is classified **temporal association on information not available at decision time; not a causal rule; data-limited** (what cannot be established: decision time of body orders; the 15:30 candle close at the time of 7 of 8 bursts).
* If **DT2 passes**: G1b becomes **plausible but unconfirmed** (a causal analogue is consistent with the bursts), with precision and false positives reported. It still does **not** enter the engine: eight events, post-observation hypothesis, precision about 58%.
* In every case: no 15:30 execution mechanism is invented, the engine's 15:29 bar end is not extended, G1b stays excluded from the baseline.

## 4. Limits stated in advance
Eight bursts; the burst definition (`j0 >= 368`, CE+PE pair, G1) is the old one; post-auction series is a proxy (rebased futures); the channel is the previous two clock-aligned 30-minute candles as in G1b; the in-progress candle's own high/low are not used (a different hypothesis, not tested).
