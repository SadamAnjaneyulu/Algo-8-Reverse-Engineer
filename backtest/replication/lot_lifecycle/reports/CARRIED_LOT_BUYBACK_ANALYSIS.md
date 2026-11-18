# Carried-Lot Intraday Buy-back Analysis (Phase 3)

**Result:** carried lots (body shorts opened on D-1 and still open at the D0 open: **3,137 lots in 30 cycles**) are mostly bought back (74–78 % depending on allocation), a **large share early in the session under FIFO but not under LIFO** (median close minute 75 vs 210). **No pre-defined hypothesis is a trigger**: price ≥ 1.55× entry, last-hour, "recent buy-back" and ITM migration each raise the per-contract-minute buy-back rate 2–3× but with precision ≤ 7.5 %; **decay take-profit and ≤ ₹1 salvage are REJECTED**. The hypothesis "intraday buy-backs of carried lots explain the unreproduced P&L" is **not testable at lot level** because who-closes-whom is ambiguous (83 %). Evidence labels: **all 30 cycles were previously inspected; the "later block" is not an independent holdout.** Code: `carried_lots.py`, `carried_analysis.py`; data `outputs/carried_lots*.csv.gz`, `contract_minute_panel.csv.gz`.

## 1. Lot-level facts about the carried lots (30 cycles)
| Quantity | Value | Status |
|---|---|---|
| Carried lots | 3,137 (closed on D0 2,879; held to settlement 258) | CONFIRMED (count is convention-free) |
| Option price at D0 open ÷ entry price | quantiles 10/25/50/75/90 % = 0.40 / 0.64 / 0.87 / 1.01 / 1.17 | CONFIRMED |
| Close price ÷ entry price (FIFO) | median 0.53 | allocation-dependent |
| MFE on D0 (entry − lowest price before close) | median 59 pts | FIFO |
| MAE on D0 (highest price − entry) | median −9.5 pts (price typically never exceeds entry) | FIFO |
| Median minutes from D0 open to close | CE 87, PE 53 | FIFO |
| Held to settlement by strike distance at D0 open | ≤ 3 steps: ≤ 1 %; > 6 steps: **75.7 %** (n = 321) | CONFIRMED |

## 2. Disposition and timing depend on the convention (`carried_disposition_by_convention.csv`)
| Convention | Body buy-back | Stop-module | Settlement | Median close minute |
|---|---:|---:|---:|---:|
| FIFO | 77.8 % | 14.0 % | 8.2 % | 75 |
| LIFO | 74.4 % | 17.0 % | 8.6 % | 210 |
| LOW_ENTRY_FIRST | 74.5 % | 16.9 % | 8.6 % | 204 |
| HIGH_ENTRY_FIRST | 77.6 % | 14.2 % | 8.2 % | 84 |

FIFO closing-time distribution: 44 % in the first 30 minutes (09:15–09:45), 10 % 09:45–10:45, 13 % 10:45–12:15, 17 % 12:15–14:15, 16 % 14:15–15:30. **Whether carried lots are monetised early (FIFO) or late (LIFO) cannot be determined**; both are consistent with the identical contract-level buy-backs.

## 3. Hypotheses (fixed before evaluation; contract-minute panel, 164,643 rows, 3,754 buy-back events, base rate 2.4 %; convention-free features from the state before minute *j* and bar *j*−1)
| Hypothesis | Dev: precision / recall / lift | Later block: precision / recall / lift | Cycles with lift > 1 (dev / later) | Verdict |
|---|---|---|---|---|
| H1 price ≥ 1.55 × cheapest open entry | 7.0 % / 0.31 / 2.7 | 4.3 % / 0.28 / 2.4 | 82 % / 88 % | **HYPOTHESIS** (association; weak trigger) |
| H2 price ≤ 0.5 × average entry (decay take-profit) | 2.2 % / 0.33 / **0.87** | 1.2 % / 0.36 / 0.69 | 32 % / 13 % | **REJECTED** |
| H3 Clock-B minute | 4.2 % / 0.10 / 1.6 | 2.9 % / 0.11 / 1.6 | 64 % / 50 % | HYPOTHESIS (timing only) |
| H4 ITM by ≥ 1 step | 3.6 % / 0.22 / 1.4 | 4.3 % / 0.40 / 2.4 | 82 % / 100 % | HYPOTHESIS (unstable lift) |
| H5 last hour (≤ 1.0 h to expiry) | 7.5 % / 0.37 / 2.9 | 4.7 % / 0.35 / 2.6 | 64 % / 50 % | HYPOTHESIS (time-of-day) |
| H6 price ≤ ₹1 (salvage) | 0.3 % / 0.03 / **0.11** | 0.1 % / 0.01 / 0.04 | 0 % / 0 % | **REJECTED** (near-worthless contracts are *held*) |
| H7 ≤ 2 min since a cycle buy-back | 5.5 % / 0.67 / 2.1 | 4.4 % / 0.64 / 2.5 | 86 % / 88 % | HYPOTHESIS (clustering of buy-backs) |

* **Coverage vs precision:** the union of H1–H7 contains 90 % of buy-back events but its precision (2.6 %) equals the base rate (2.4 %): the predicates cover most minutes. **No combination of these simple predicates is a trigger.**
* **Consistent across blocks:** H1, H5 and H7 keep lift 2.4–2.9 in both blocks; H2 and H6 fail in both. The blocks are chronological by cycle (22 / 8) but **not independent**.
* **Clustering (H7)** is the strongest recall (0.64–0.67): buy-backs come in bursts — consistent with a cycle-level or portfolio-level action rather than independent per-lot decisions (**HYPOTHESIS**).

## 4. Questions of the brief
| Item | Answer |
|---|---|
| Entry time/price, time carried | CONFIRMED per lot (dataset) |
| Price at D0 open, MFE, MAE | CONFIRMED paths (market data); close timing convention-dependent |
| Partial vs full closure | contract-level exact (buy-back orders close 1–42 lots; median 1); lot-level ambiguous |
| Another short opened in the same contract after the close | see Replacement report: same-contract excess over chance ≤ 1.6× |
| Survived to settlement | 258 lots (8 %); far-OTM (> 6 steps) 76 % — **STRONGLY SUPPORTED** that deep-OTM carried lots are left to expire |
| Correlations with time since entry, strike distance, CE/PE, entry price, unrealised P&L, adverse excursion, portfolio exposure, scheduled windows, cycle stop | strike distance and price level matter (above); the rest are not separable from allocation ambiguity at lot level; hazard predicates H1–H7 summarise what is testable |
| IV, Greeks | **not used**: no reliable historical IV inputs (SENSEX OI absent; no quotes) — UNKNOWN |

**Verdict on the central hypothesis:** "carried-lot intraday buy-backs are the main unreproduced P&L stream" is **UNKNOWN at lot level** (the allocation range moves carried-lot P&L only ±2.4 %, but the *timing* of monetisation changes by hours); at contract level the buy-back events are exact and cluster in time, but no trigger was recovered.
