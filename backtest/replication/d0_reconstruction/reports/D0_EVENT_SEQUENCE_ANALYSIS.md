# D0 Event Sequence Analysis (Phase A, Gate 1)

**Result:** an auditable **order-level event table** now exists for all 35 live cycles (39,874 orders, 63,652 lots; 29,959 D0 orders). It reconciles exactly with the ledger, but **D0 decision analysis is possible for only 33 cycles, and state-dependent analysis for only 30** (3 cycles lack the D-1 book, 2 lack D0). **Gate 1 is passed with documented exceptions.** One headline from the previous phase did not survive a second-level re-check: the "60 % of D0 sales are replacements" figure came from minute-bucket matching; with second-level timing and a time-shift null, only a modest, class-dependent share is above chance (see `BUYBACK_AND_REPLACEMENT_ANALYSIS.md`). Code executed: `build_events.py`, `build_lineage.py`, `build_snapshots.py`; tables in `results/`.

## 1. Data audit and exceptions

| Cycle group | Cycles | Reason | Usable for |
|---|---:|---|---|
| D-1 and D0 fills present | 30 | — | everything |
| D0 only (carry-in book unknown): NIFTY 2026-06-23, 08-11, 09-15 | 3 | log starts / log gaps on D-1 (8/10, 9/14) | state-free event statistics only |
| D-1 only (no D0 fills): NIFTY 2026-09-01, 09-29 | 2 | log gaps (9/1, 9/29) | none for D0 |
| Split | Discovery 25 cycles with D0 (22 with carry-in) · Holdout 8 (8 with carry-in; NIFTY 09-29 has no D0) | | |

* **Order key:** the column-163 tag is unique per order (39,874 tags = 39,874 orders; DAT-01). One row per order; price = last fill's running order-average (= order VWAP, DAT-16).
* **Reconciliation checks (executed):** orders 39,874 = ledger; lots 63,652 = ledger; final net position of **all 1,674 contracts matches the ledger** (0 mismatches); FIFO lot lineage reproduces live gross P&L to ₹2.9 k of ₹2.62 M (0.11 %; max ₹1.0 k per cycle, from running-average prices); decision times decoded from `h_/s_/v_/m_` tags differ from the first fill second by a median −0.17 s (5th/95th pct −0.8/+0.5 s).
* **Position books:** per-role FIFO books (body, wing, lump, stop) with a documented routing table (`build_events.py`). A first version that pooled roles in one net position per contract misclassified ~2.8 k lots and was discarded before any analysis.

## 2. Event classes and precedence (every order gets exactly one; nothing forced)

Body orders (`num` tag): **BUYBACK** (closes shorts), **FINAL_LIQUIDATION** (buy-back at ≥ 15:10 D0), **SALE** classes for orders that open shorts, by precedence: **REPLACEMENT_SALE** if a same-day same-right body buy-back began ≤ 60 s earlier → else **SCHEDULED_SALE** if the first fill is inside a grid-A window (minute-of-hour 1/16/31/46, T−2 s … T+180 s, from 09:16) or the grid-:00 window 13:30–15:03 → else **OFF_SCHEDULE_SALE**. Sales that close long lots, and body buys that open longs, are **POSITION_REDUCTION_OF_LONG** / **UNCLASSIFIED** (kept). Hedges: **HEDGE_ADD**, **HEDGE_REPLACEMENT** (wing buy ≤ 30 s after a wing sale on the same right), **HEDGE_REDUCE**. Other modules: **STOP_MODULE_ORDER** (`s_`), **LUMP_HEDGE_ADD/SALVAGE** (`v_`), **MANUAL** (`m_`).

**Caveat on REPLACEMENT_SALE:** the label records *temporal association only*. Because buy-backs occur every few seconds on busy days, many scheduled or independent sales fall within 60 s of one; the time-shift null attributes ~65 % of the "within 60 s" mass to chance (below).

## 3. D0 event counts (orders / lots)

| Class | Discovery orders | Discovery lots | Holdout orders | Holdout lots |
|---|---:|---:|---:|---:|
| BUYBACK | 6,757 | 7,876 | 1,087 | 1,128 |
| FINAL_LIQUIDATION | 1,534 | 2,313 | 256 | 550 |
| SCHEDULED_SALE | 2,615 | 2,855 | 542 | 542 |
| OFF_SCHEDULE_SALE | 2,675 | 2,905 | 605 | 609 |
| REPLACEMENT_SALE | 2,380 | 4,118 | 302 | 731 |
| POSITION_REDUCTION_OF_LONG | 530 | 704 | 137 | 222 |
| UNCLASSIFIED | 541 | 620 | 227 | 227 |
| HEDGE_ADD / HEDGE_REPLACEMENT / HEDGE_REDUCE | 4,075 / 519 / 3,226 | 7,443 / 1,029 / 8,942 | 707 / 57 / 481 | 1,045 / 338 / 1,301 |
| STOP_MODULE_ORDER | 260 | 2,319 | 127 | 1,196 |
| LUMP_HEDGE_ADD / SALVAGE, MANUAL | 1 / 249, 7 | 14 / 747, 32 | 0 / 62, 0 | 0 / 191, 0 |

(Counts only; the holdout columns are descriptive tallies, no rule was derived from them.) The holdout period had 4 stop cycles of 8 (1,196 stop-module lots) versus 7 of 22 in discovery.

## 4. Follow-up of buy-backs (transition table, discovery)

Previous state → trigger candidate → action → new state, for body buy-backs by observable subtype (decision-time labels: late = ≥ 15:10; salvage = price ≤ ₹1 or ≤ 5 % of entry; stop-like = price ≥ 1.55 × cheapest open entry; Clock-B = tick minute with seconds ≤ 30). Share of buy-backs followed within 180 s by **a sale on the same right** (any strike) / **same contract** / **none**:

| Subtype | Orders | Lots | Any follow ≤ 180 s | Same contract | Same right, other strike | Opposite right only | None | Median delay (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Late (≥ 15:10) | 1,534 | 2,313 | 34.6 % | 2.3 % | 19.8 % | 12.5 % | 65.4 % | 44 |
| Salvage | 379 | 438 | 78.1 % | 4.5 % | 69.4 % | 4.2 % | 21.9 % | 34 |
| Price ≥ 1.55× cheapest | 2,835 | 3,098 | 86.4 % | 5.0 % | 52.5 % | 28.9 % | 13.6 % | 35 |
| Clock-B tick minute | 264 | 290 | 87.1 % | 11.4 % | 70.5 % | 5.3 % | 12.9 % | 47 |
| Other | 3,281 | 4,061 | 76.3 % | 12.9 % | 53.0 % | 10.3 % | 23.7 % | 38 |

(`b2_buyback_followup_by_subtype.csv`; these raw follow rates are **not** corrected for the chance base rate, which is high — see the null in the replacement report.) A buy-back is rarely followed by a sale of **the same contract** (≤ 13 %): replacements mostly move to a different strike.

## 5. Timelines
* `figures/d0_event_timeline.png`: all D0 body orders of one discovery and one holdout SENSEX cycle (time vs strike offset from the previous-minute ATM; colour = class; size = lots).
* `figures/d0_position_state_timelines.png`: net short body lots by right, actual vs simulated, same two cycles.
* Representative structure: sales cluster in the first 3 minutes of grid-A slots (28 % of sale orders at minute-of-hour 1) and at minute 0 (following Clock-B ticks); buy-backs concentrate at minute-of-hour 14 (17.3 % of buy-back lots against 6.7 % under uniformity; 3.4× for non-stop-like lots) and rise sharply after 14:30 (15:00–15:29 holds 26 % of discovery buy-back lots); the 15:14 minute alone holds 846 lots of buy-backs and 763 lots of sales in discovery.
* **15:14 selling:** in 5 of the discovery cycles the algorithm *sells* 749 lots at 15:14 (median price ₹1.05, 99 % held to settlement, ₹54/lot) while buying back 846 lots: a late premium-collection step on near-worthless options — observed, not explained.
