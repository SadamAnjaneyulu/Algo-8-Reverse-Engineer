# Executive Summary — Individual Short-Option Lot Lifecycle Reconstruction

**Can we explain the lifecycle of each original Algo 8 short-option lot, from entry to final disposition, using evidence rather than assumptions?**
**Partly.** For every short lot we can state, **exactly**, its entry (fill id, time, tick price, size) and the exact P&L of the cycle it belongs to. We **cannot** say which closing order closed which lot: the export has no allocation id, and for **89 % of body short lots (30 complete cycles) the closing fill changes with the unknown allocation method**; a second ledger ambiguity (a body buy with no recorded short: close of an unrecorded short, or a long open?) is unresolved. Where a claim does not depend on ownership (contract-level buy-back timing, quantities, totals, expiry behaviour of deep-OTM lots) it is firm; where it does (holding time, per-lot P&L, carried-vs-fresh monetisation) it is a range. No buy-back, replacement or sale trigger was recovered, and nothing is proposed for the engine. *This summary was corrected after an independent review; see `INDEPENDENT_REVIEW.md`.*

## 1. What was reconstructed
* A **fill-level ledger** with exact per-fill prices (raw column 137) and a **unit-lot lifecycle dataset**: **33,172 lots** (16,340 short incl. 161 unrecorded carry-in shorts), identity, entry fill, disposition, P&L, under **four allocation conventions** side by side, plus an alternative dataset for the second ambiguity (34,110 lots).
* An **association layer** (wing links 78 % of recorded body shorts, timing only; replacement classes at order level), a **carried-lot dataset** (3,137 lots, MFE/MAE), a **contract-minute hazard panel** (164,643 rows; 158,575 analysed), 13 charts separating actual from inferred.

## 2. Confirmed from the ledger (CONFIRMED OBSERVATION)
* **Every execution is accounted for:** 31,566 sold lots = 16,179 short lots opened + 15,387 long lots closed; 32,086 bought lots = 16,832 long lots opened + 15,254 short lots closed (primary reading). Unmatched executions: 0 — a bookkeeping statement, **not** proof of correct ownership.
* **Cycle-level P&L reconciles to the ledger to ₹0.000 in all 35 cycles** (a cash-conservation identity). Exact gross = **₹25.82 L** (35 cycles) and **₹15.50 L** (30 complete cycles). The earlier ₹26.18 L differs by −₹36.5 k, of which only −₹2.5 k lies in the 30 complete cycles; −₹33.7 k comes from one partial cycle (NIFTY 2026-06-23) and is **unattributed**.
* The 22 repeated trade ids are coincidental; order tags are unique; quantities are whole lots.
* Deep-OTM carried lots expire: **76 % of carried lots > 6 strike steps from spot at the D0 open are held to settlement** vs ≤ 1 % within 3 steps (STRONGLY SUPPORTED).

## 3. What remains a hypothesis
Buy-backs come in bursts (lift 2.1–2.5, recall 0.64–0.67); price ≥ 1.55× cheapest entry, the last hour, ITM migration and the Clock-B minute each raise the buy-back rate 1.4–2.9×, but **no predicate exceeds 7.5 % precision** (union precision 2.6 % vs 2.4 % base rate). After a buy-back, an **opposite-right sale within 30 s is ≈ 2.8× the chance level** (unscheduled; exploratory, 32 cells, no multiplicity control) while the overall same-right sale-within-60-s rate is **at chance (ratio 1.25, CI 0.91–1.56)**. Scheduled-sale timing is partly reproduced; its quantity is not (recall 0.19–0.55).

## 4. What failed validation
Decay take-profit (lift 0.87 / 0.69) and ≤ ₹1 salvage (0.11 / 0.04 — those contracts are **held**); same-contract replacement as a general pattern; the first draft's replacement headline (4.8× cross-right, 139 STRONGLY SUPPORTED) after the null was corrected — now **0** strongly supported at primary thresholds (88 at a relaxed threshold); the previous phase's "60 % replacements" is not supported.

## 5. Simulator defects (from the D0 independent review)
| Defect | Outcome |
|---|---|
| A passive lump lots kept after a stop | **Handled as an explicit assumption with two bounds** in `d0_sim_v2.py`. Holdout-label D0 P&L increment: −₹1.53 L (passive closed at stop) vs +₹0.08 L (kept), live +₹1.90 L; the swing is mostly one cycle (SENSEX 2026-09-24, −₹1.95 L). Neither bound reproduces live. |
| B replacement sales get no wings | **Not fixable from the ledger**: bounds `none`/`one_per_lot`, effect ≤ ₹0.07 L. UNKNOWN. |
| C fixed-bin matching | **Fixed** (one-to-one window matching, tolerance sensitivity); scheduled-sale verdict **not robust**. |
| D 09:15 look-ahead | **Fixed in new code** and perturbation-tested (the legacy event table is preserved, flagged). |
| E start-book | **Audited**: equal to v1.1 in 30/30 cycles (not independent evidence). |
Also fixed: a failing parity test caused by 400 stored diagnostic engine runs generated without the C++ check.

## 6. Coverage and reconciliation
* **Short-option activity accounted for: 100 % of ledger units** (63,652 lots). P&L is exact at **cycle** level for all 35 cycles; **lot-level lifecycle P&L is meaningful only for the 30 complete cycles** (5 partial cycles: 161 shorts of unknown entry; 146 shorts "settled" as an artefact in 2 cycles with no D0 log).
* Allocation range: the carried / D0-entered split of body-short P&L moves by ₹4.9 L across conventions (total ₹24.23 L fixed); per-lot P&L differs for 85 % of lots (median range ₹706). Under the alternative reading of unmatched body buys, 968 lots have unknown entries.

## 7. Python/C++ parity and engine
No new logic exists in C++ and none was ported; parity holds for the unchanged engine (stored runs `parity=True`; backtest tests pass). **No new rule is validated enough to be considered for the engine.**

## 8. Independent review
An adversarial review found nine defects (D1–D9) and minor errors after the first results were produced; all are recorded in `INDEPENDENT_REVIEW.md` with the preserved pre-review outputs, the fixes and regression tests. All numbers above are post-review and **CONTAMINATED-DEVELOPMENT**.

## 9. Evidence status
All 35 cycles were previously inspected; chronological blocks are labels, not holdouts; **no rule is validated**. Sharpe 2.19 is unverified and was not used.

## 10. Next highest-value task
Obtain **allocation or parent-order identifiers and sub-second timestamps** from the platform (without them lot-level questions stay ranges), and resolve the body-buy ambiguity by supplying the pre-log position (opening positions at the first D-1 session). In parallel, pre-register and test the **cross-right sale after a buy-back** as a CE/PE exposure-balance hypothesis on **new** data (a forward export), since all 35 cycles are spent.
