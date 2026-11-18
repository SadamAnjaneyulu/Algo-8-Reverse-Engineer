# Carried-Lot Intraday Buy-back Analysis (Phase 3)

**Result:** carried lots (body shorts opened on D-1 and still open at the D0 open: **3,137 lots in 30 cycles**; the *count* is convention-free, the *identity* of the lots is not) are mostly bought back (74–78 % depending on allocation), a **large share early in the session under FIFO but not under LIFO** (median close minute 75 vs 210). **No hypothesis is a trigger**: price ≥ 1.55× cheapest entry, last hour, "recent buy-back" and ITM migration each raise the per-contract-minute buy-back rate ≈ 1.4–3× but with precision ≤ 7.5 %; **decay take-profit and ≤ ₹1 salvage fail (lift < 1)**. The idea that intraday buy-backs of carried lots explain the unreproduced P&L is **not testable at lot level** (ownership ambiguity, 89 %). **All 30 cycles were previously inspected; the "later block" is not an independent holdout; all tests below are EXPLORATORY.** Code: `carried_lots.py`, `panel.py`, `carried_analysis.py`; data `outputs/carried_lots*.csv.gz`, `contract_minute_panel.csv.gz`, `carried_hypothesis_tests.csv`.

## 1. Lot-level facts about the carried lots (30 cycles)
| Quantity | Value | Status |
|---|---|---|
| Carried lots | 3,137. Closed on D0 / settled: **FIFO 2,879 / 258**; settled count differs by convention: LIFO 260, LOW_ENTRY 263, HIGH_ENTRY 254 | count CONFIRMED; split convention-dependent |
| Option price at D0 open ÷ entry price | quantiles 10/25/50/75/90 % = 0.40 / 0.64 / 0.87 / 1.01 / 1.17 | CONFIRMED |
| Close price ÷ entry price (FIFO) | median 0.53 | allocation-dependent |
| MFE on D0 (entry − lowest price before close) | median 59 pts | FIFO |
| MAE on D0 (highest price − entry) | median −9.5 pts | FIFO |
| Median minutes from D0 open to close | CE 87, PE 53 | FIFO |
| Held to settlement by strike distance at D0 open | ≤ 3 steps: ≤ 1 % (n = 2,452); 3–6 steps: 2.5 % (n = 364); > 6 steps: **75.7 %** (n = 321) | CONFIRMED (FIFO set) |

## 2. Disposition and timing depend on the convention (`carried_disposition_by_convention.csv`)
| Convention | Body buy-back | Stop-module | Settlement | Median close minute |
|---|---:|---:|---:|---:|
| FIFO | 77.8 % | 14.0 % | 8.2 % | 75 |
| LIFO | 74.4 % | 17.0 % | 8.6 % | 210 |
| LOW_ENTRY_FIRST | 74.5 % | 16.9 % | 8.6 % | 204 |
| HIGH_ENTRY_FIRST | 77.6 % | 14.2 % | 8.2 % | 84 |

FIFO closing-time distribution: 44 % in the first 30 minutes, 10 % 09:45–10:45, 13 % 10:45–12:15, 17 % 12:15–14:15, 16 % 14:15–15:30. **Whether carried lots are monetised early (FIFO) or late (LIFO) cannot be determined.**

**D1 sensitivity.** Under the alternative reading of unmatched body buys (`unrecorded_short`) the number of D-1-entered body-short rows grows from 4,375 to 5,452 (968 of the extra rows are unrecorded-entry lots) and settled ones from 258 to 365 — i.e. part of the "carried book" is itself an interpretation. The disposition table above is for the primary reading.

## 3. Hypotheses (EXPLORATORY; contract-minute panel: 164,643 rows built, **158,575 used** after restricting to minutes j ≤ 358; 3,754 buy-back events; base rate 2.37 %)
Features use only the state before minute *j* and bar *j*−1 (D0 minute 0 reads the last D-1 bar; perturbation-tested). **Provenance of thresholds (disclosure):** H1 (1.55×), H3 (Clock-B) and H6 (≤ ₹1) come from the project's earlier literature; H2 (0.5×), H4 (≥ 1 step), H5 (≤ 1 h) and H7 (≤ 2 min) are round numbers I chose before computing, but the file was first committed after evaluation, so **pre-registration cannot be demonstrated**. Intervals are 95 % cycle-level bootstrap CIs on lift (500 draws, cycles resampled).

| Hypothesis | Dev (22 cycles): precision / recall / lift [95 % CI] | Later (8 cycles): precision / recall / lift [95 % CI] | Cycles with lift > 1 (dev / later) | Verdict |
|---|---|---|---|---|
| H1 price ≥ 1.55 × cheapest open entry | 7.0 % / 0.31 / 2.71 [2.17, 3.36] | 4.3 % / 0.28 / 2.44 [1.60, 3.86] | 82 % / 88 % | HYPOTHESIS (weak trigger) |
| H2 price ≤ 0.5 × average entry | 2.2 % / 0.33 / 0.87 [0.72, 0.995] | 1.2 % / 0.36 / 0.69 [0.46, 0.90] | 32 % / 13 % | **REJECTED** as a trigger (lift < 1; dev CI upper bound borderline) |
| H3 Clock-B minute | 4.2 % / 0.10 / 1.62 [1.33, 1.90] | 2.9 % / 0.11 / 1.63 [1.09, 1.98] | 64 % / 50 % | HYPOTHESIS (timing only) |
| H4 ITM by ≥ 1 step | 3.6 % / 0.22 / 1.41 [1.13, 1.77] | 4.3 % / 0.40 / 2.43 [1.71, 4.29] | 82 % / 100 % | HYPOTHESIS (unstable lift) |
| H5 last hour | 7.5 % / 0.37 / 2.93 [2.38, 3.35] | 4.7 % / 0.35 / 2.64 [2.07, 3.01] | 64 % / 50 % | HYPOTHESIS (time-of-day) |
| H6 price ≤ ₹1 | 0.3 % / 0.03 / 0.11 [0.06, 0.18] | 0.1 % / 0.01 / 0.04 [0.01, 0.09] | 0 % / 0 % | **REJECTED** (near-worthless contracts are *held*) |
| H7 ≤ 2 min since a cycle buy-back | 5.5 % / 0.67 / 2.12 [1.86, 2.49] | 4.4 % / 0.64 / 2.51 [2.04, 4.29] | 86 % / 88 % | HYPOTHESIS (clustering) |

* **Excluding the first minutes (j ≥ 6)** — 43 % of buy-backs in minutes 0–5 have no recorded inventory and are missing from the panel (237 of 3,991 buy-back contract-minutes lost) — lifts are essentially unchanged (e.g. H1 2.76 / 2.45, H5 3.02 / 2.82, H7 2.19 / 2.54; `carried_hypothesis_tests.csv`).
* **Coverage vs precision:** the union of H1–H7 contains 89.7 % of buy-back events (dev 89.3 %, later 91.7 %) but its precision (2.6 %) is close to the base rate (2.4 %): the predicates cover most minutes. **No combination of these simple predicates is a trigger.**
* Per-minute lift above 1 for H1/H5/H7 is stable across both blocks; the blocks are chronological by cycle (22 / 8) but **not independent**, and 7 hypotheses × 2 variants × 2 blocks were examined without multiplicity correction.
* **Clustering (H7)** has the highest recall (0.64–0.67): buy-backs come in bursts — consistent with a cycle- or portfolio-level action rather than independent per-lot decisions (**HYPOTHESIS**).

## 4. Questions of the brief
| Item | Answer |
|---|---|
| Entry time/price, time carried | CONFIRMED per lot (dataset) |
| Price at D0 open, MFE, MAE | CONFIRMED paths (market data); close timing convention-dependent |
| Partial vs full closure | contract-level exact (buy-back orders close 1–42 lots; median 1); lot-level ambiguous |
| Another short opened in the same contract after the close | see `REPLACEMENT_ANALYSIS.md` |
| Survived to settlement | 254–263 lots (≈ 8 %); far-OTM (> 6 steps) 76 % — **STRONGLY SUPPORTED** that deep-OTM carried lots are left to expire |
| Correlations with time since entry, strike distance, CE/PE, entry price, unrealised P&L, adverse excursion, exposure, scheduled windows, cycle stop | strike distance and price level matter (above); the rest are not separable from allocation ambiguity at lot level |
| IV, Greeks | **not used**: no reliable historical IV inputs — UNKNOWN |

**Verdict on the central hypothesis:** "carried-lot intraday buy-backs are the main unreproduced P&L stream" is **UNKNOWN at lot level**: the allocation range moves the carried/fresh P&L split by ₹4.9 L and the timing of monetisation by hours; at contract level the buy-back events are exact and cluster in time, but no trigger was recovered.
