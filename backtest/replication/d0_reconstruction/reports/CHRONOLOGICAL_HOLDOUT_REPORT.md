# Chronological Holdout Report (Phase D, Gates 3–5)

**Result (read with the independent review, `INDEPENDENT_REVIEW_D0.md`):** rule set **D0-v1**, frozen before evaluation, was evaluated once on the 8 holdout cycles. **Against the pre-registered criterion (L2 precision ≥ 0.5 and L2 recall ≥ 0.5, and better than the NULL control), only the 15:14 final-liquidation timing passes** (V1: precision 0.785, recall 0.604; cycle-bootstrap intervals are wide). **Scheduled sales fail narrowly on recall (0.483) under the pre-registered 2-minute-bin matching but would pass (precision 0.733 / recall 0.548) with a ±1-minute sliding window — the verdict is convention-dependent, Clock-B buy-backs, replacements, price-stop-like buy-backs and hedge actions fail.** The portfolio level is not reproduced (level correlation −0.33; change-from-10:00 correlation 0.77) and simulated D0 P&L is not reliable: the review found that lump-hedge lots stay in the simulated book after a stop (one holdout cycle contributes ₹217 k of spurious settlement). Replacement/Clock-B/buy-back failures are robust to all issues found. The failures are recorded; no rule was changed afterwards under the v1 name.

## 1. Design and disclosures
* **Split (chronological, whole cycles):** discovery = D0 < 2026-09-23 (25 cycles with D0, 22 with carry-in); holdout = D0 ≥ 2026-09-23 (SENSEX 09-24, 10-01, 10-08, 10-15, 10-22; NIFTY 10-06, 10-13, 10-19; NIFTY 09-29 has no D0). That is 26 % of the 35 cycles, aligned with the TEST boundary of the earlier exit-engine research.
* **Partial exposure (must be read with every number):** the earlier exit-engine research *scored* these TEST cycles for other models, and the Phase-4 descriptive tables pooled all 35 cycles (aggregates, no rule fitting). Pristine independence is therefore **not** claimed. n = 8 cycles: intervals below are wide; no statistical confidence is claimed.
* **Freeze:** `PREREGISTRATION_D0_v1.md`, `results/FREEZE.json` (SHA-256 of rules, simulator, comparison code and discovery event table) committed as `40642216` **before** the holdout run. Holdout event data cannot be loaded before `FREEZE.json` exists (guard + test `test_holdout_guard`).
* **Addendum 1 (disclosed bug fix):** a unit test found that the simulator's start book did not net a body sale against earlier body long lots (78 lots over 22 discovery cycles; 31 lots over 8 holdout cycles; 27 of 30 cycles affected). Rules and parameters were not changed. The corrected simulator (v1.1) was re-run on both splits; the v1.0 (frozen) outputs are kept in `results/v1_0_frozen_outputs/`. **Because the v1.0 holdout had already been seen, the v1.1 re-run is not independent evidence**; the conclusions are identical.
* Variants evaluated (pre-registered): NULL (flatten + cycle stop only), V0 (S1 scheduled + S2 Clock-B), V1 (V0 + 1.6× price stop). Every D0 starts from the **actual** overnight book.

## 2. Holdout results, variant V1 (v1.1), event level (lots, hierarchical matching; `compare_events_holdout_V1.csv`)

| Category | Sim lots | Actual lots | L2 precision | L2 recall | Cycle-bootstrap 95 % CI (precision / recall) | Pre-registered pass? |
|---|---:|---:|---:|---:|---|:-:|
| All body sales | 410 | 1,952 | 0.756 | 0.159 | | — |
| **Scheduled sales** | 405 | 542 | 0.647 | **0.483** | 0.60–0.71 / 0.40–0.55 | **No (recall)** |
| Replacement sales | 5 | 731 | 0.000 | 0.000 | | No |
| Buy-backs excl. final | 308 | 1,128 | 0.562 | 0.153 | | No |
| Clock-B buy-backs | 5 | 113 | 0.200 | 0.009 | | No |
| Price-stop-like buy-backs (ratio ≥ 1.55) | 303 | 411 | 0.472 | 0.348 | 0.35–0.54 / 0.21–0.47 | No |
| **Final liquidation (≥ 15:10)** | 423 | 550 | **0.785** | **0.604** | 0.46–1.00 / 0.49–0.71 | **Yes** (NULL: 0.75 / 0.32) |
| Hedge additions | 405 | 1,383 | 0.689 | 0.202 | | No |
| Hedge reductions | 1,183 | 1,301 | 0.299 | 0.272 | | No |

Variant V0 (no price stop): scheduled 0.648/0.428; final liquidation 0.490/0.309 (fails); NULL: final liquidation 0.747/0.316 (fails on recall). Exact-match (L1) levels: scheduled sales precision 0.60 / recall 0.45; final liquidation 0.46 / 0.35.
**Execution:** among L1-matched sale orders (367), simulated reference price vs actual order price: median +0.19 %, median absolute 1.34 %. **Timing:** 94.6 % of simulated sales lie within 1 minute of an actual same-right sale (a weak test: sales are frequent).

## 3. Portfolio state and P&L (holdout)

| Variant | Net short body lots (hourly marks): corr / MAE / mean actual / mean sim | D0 P&L increment: sim vs live (corr) | Stop cycles: sim / live / agree |
|---|---|---|---|
| NULL | −0.52 / 67 / 74.6 / 8.0 | −₹2.2 L vs +₹1.9 L (0.35) | 5 / 4 / 4 |
| V0 | −0.48 / 68 / 74.6 / 15.8 | −₹3.2 L vs +₹1.9 L (0.06) | 6 / 4 / 4 |
| **V1** | **−0.33 / 60 / 74.6 / 17.2** | **+₹0.08 L vs +₹1.9 L (0.62)** | 4 / 4 / 4 |

The simulated book **collapses** (mean 17 lots vs 75): the cycle stop fires in 4–6 of 8 cycles in the simulation (live: 4) and, because decisions to rebuild exposure are not reproduced, the book stays empty. The Clock-B threshold (134 total short lots, fitted on discovery) is rarely met in the smaller holdout books: **the rule's scale does not transfer**. In discovery the same simulator gave state correlation 0.79 (V1) and 6 of 7 live stop cycles; the drop from 0.79 to −0.33 is the out-of-sample failure.
**Robustness to sequencing:** shifting every fill by one minute (decision at j, fill at j+1) leaves all agreement metrics unchanged but moves the holdout D0 increment from +₹0.08 L to −₹1.26 L (discovery ₹6.1 L → ₹8.3 L): **P&L is sensitive to intra-minute ordering and fill assumptions; behavioural agreement is not**.

## 4. Discovery vs holdout (V1, L2)
Scheduled sales precision/recall 0.71/0.53 → 0.65/0.48; price-stop-like 0.61/0.31 → 0.47/0.35; final liquidation 0.32/0.35 → 0.79/0.60 (improves out of sample; the reason is not established); Clock-B buy-backs 0.19/0.04 → 0.20/0.01. State correlation 0.79 → −0.33.

## 5. Recorded failures (no post-hoc change)
| Rule | Failure | Classification |
|---|---|---|
| S1 scheduled quantity = discovery slot medians | recall 0.48 (< 0.5), exact quantity 45 % | Incorrect quantity (slot median is a blunt rule) |
| S2 Clock-B act threshold | 5 lots simulated vs 113 actual | Incorrect trigger (scale-dependent) |
| S2 replacement | 5 vs 731 lots | Missing rule |
| S3 1.6× price stop on D0 | precision 0.47 / recall 0.35 | Incorrect trigger |
| Hedge actions | recall 0.2–0.27 | Missing rule (wing release/replacement logic) |
| State/P&L | negative correlation | Consequence of the above plus the cycle-stop interaction |

**Next version (v2)** would require an independent validation period; none exists in this ledger. Any further work with these 35 cycles is development, not validation.
