# Executive Summary — Individual Short-Option Lot Lifecycle Reconstruction

**Can we explain the lifecycle of each original Algo 8 short-option lot, from entry to final disposition, using evidence rather than assumptions?**
**Partly.** For every short lot we can state, **exactly**, its entry (fill id, time, tick price, size) and the exact P&L of the cycle it belongs to. We **cannot** say which closing order closed which lot: the export has no allocation id, and for **83 % of body short lots the closing fill changes with the (unknown) allocation method**. Where a lifecycle claim does not depend on ownership (contract-level buy-back timing, quantities, totals, expiry behaviour of deep-OTM lots) it is firm; where it does (holding time, per-lot P&L, carried-vs-fresh monetisation) it is a range. No buy-back, replacement or sale trigger was recovered, and nothing is proposed for the engine.

## 1. What was reconstructed
* A **fill-level ledger** with exact per-fill prices (raw column 137; earlier phases used a running order average) and a **unit-lot lifecycle dataset**: 34,882 lots (17,400 short, plus 153 unrecorded carry-in shorts), identity, entry fill, disposition, exact P&L, under **four allocation conventions** run side by side.
* An **association layer** (wing links 73 % of body shorts, timing only; replacement classes at order level), a **carried-lot dataset** (3,137 lots, MFE/MAE, D0 paths), a **contract-minute hazard panel**, and 13 charts that separate actual from inferred.

## 2. Confirmed from the ledger (CONFIRMED OBSERVATION)
* **Every execution is accounted for:** 31,566 sold lots = 17,400 short lots opened + 14,166 long lots closed; 32,086 bought lots = 17,329 long lots opened + 14,757 short lots closed. Unmatched executions: 0.
* **Lot-level P&L reconciles to the ledger to ₹0.000 in all 35 cycles.** Exact gross = **₹25.82 L** (35 cycles) and **₹15.50 L** (30 complete cycles). The earlier "live gross ₹26.2 L" was overstated by ₹36.5 k (running-average price applied per fill).
* The 22 repeated trade ids are coincidental (not duplicates); order tags are unique; whole-lot quantities.
* Deep-OTM carried lots expire: **76 % of carried lots more than 6 strike steps from spot at the D0 open are held to settlement** vs ≤ 1 % within 3 steps (STRONGLY SUPPORTED).

## 3. What remains a hypothesis
Buy-backs come in bursts (lift 2.1–2.5, recall 0.64–0.67); price ≥ 1.55× entry, the last hour, ITM migration and the Clock-B minute each raise the buy-back rate 1.4–2.9× but **no predicate exceeds 7.5 % precision** (the union has precision 2.6 % vs a 2.4 % base rate). **A sale on the opposite right within 30 s of a buy-back is 4.8× more frequent than chance** — more than a same-right (2.0–2.9×) or same-contract (≤ 1.6×) sale. Scheduled-sale timing is reproduced but its quantity is not (recall 0.19–0.55 depending on tolerance and definition).

## 4. What failed validation (REJECTED)
Decay take-profit (price ≤ 0.5× entry: lift 0.87 / 0.69); salvage of ≤ ₹1 contracts (lift 0.11 / 0.04 — they are **held**); same-contract replacement as a general pattern (≤ 1.6× chance, below chance beyond 60 s). The previous phase's "60 % replacements" is not supported (only 1.6 % of buy-backs qualify as STRONGLY SUPPORTED same-contract/right replacements, and that count is unstable between ~140 and ~260 with the null draws).

## 5. Simulator defects (from the D0 independent review)
| Defect | Outcome |
|---|---|
| A passive lump lots kept after a stop | **Fixed** in `d0_sim_v2.py` (regression: SENSEX 2026-09-24 gross +₹22 k → −₹173 k vs live −₹153 k). Corrected holdout-label D0 P&L increment is **−₹1.53 L** (legacy +₹0.08 L; live +₹1.90 L). |
| B replacement sales get no wings | **Not fixable from the ledger** (41 % paired, no rule): explicit bounds `none`/`one_per_lot`, effect ≤ ₹0.07 L. UNKNOWN. |
| C fixed-bin matching | **Fixed** (one-to-one window matching with tolerance sensitivity); the scheduled-sale verdict is **not robust** (recall 0.19–0.55). |
| D 09:15 look-ahead | **Fixed in new code** (`features.py`, panel built from D-1+D0 arrays), tested; the legacy event table is preserved unfixed and flagged. |
| E start-book | **Independently audited**: equal to v1.1 in 30/30 cycles (not independent evidence). |
Also found and fixed in this milestone: a failing parity test caused by 400 stored diagnostic engine runs generated without the C++ check (now `parity=True`; 180 engine tests unchanged).

## 6. Coverage and reconciliation
* **Short-option activity accounted for: 100 % of units** (every ledger lot, 63,652). P&L reconciled **exactly** for all 35 cycles; but a **meaningful lifecycle P&L exists only for the 30 cycles with both D-1 and D0 logs** (3 cycles miss D-1: 153 shorts of unknown entry; 2 miss D0: 146 shorts "settled" as an artefact).
* Allocation range: carried-lot P&L ₹38.8–40.6 L (±2.3 %); per-lot P&L differs for 79.7 % of lots (median ₹578).

## 7. Python/C++ parity and engine
No new logic exists in C++ and none was ported; parity holds for the unchanged engine (180 tests + 400 stored runs). **No new rule is validated enough to be considered for the engine.**

## 8. Independent review
See `INDEPENDENT_REVIEW.md` (an adversarial reviewer re-implemented the lot accounting, the opening book, the matching and the panel features). Findings and responses are recorded there; this summary is corrected for them.

## 9. Evidence status
All 35 cycles were previously inspected; chronological blocks are labels, not holdouts; **no rule is validated**. Sharpe 2.19 is unverified and was not used.

## 10. Next highest-value task
Obtain **allocation or parent-order identifiers and sub-second timestamps** (ask the platform whether the export can include them) — without them lot-level questions stay ranges. In parallel, test the **cross-right sale after a buy-back** as a position-balance hypothesis (CE/PE exposure symmetry before and after) on **new** data (a forward export), since all 35 cycles are spent.
