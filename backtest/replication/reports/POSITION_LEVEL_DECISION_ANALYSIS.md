# Position-Level Decision Analysis (why positions are retained, added, reduced, closed, replaced)

**Result:** at position level the real algo behaves like a **schedule-driven book with a loose price-stop overlay**, not like a single-rule controller. Price relative to the entry is the strongest single associate of D-1 reductions (AUC 0.70) but explains only about half of them; on D0 almost no single feature separates reductions from retentions (AUC ≤ 0.70). **No rule was promoted to "confirmed" in this document.** Code executed: `position_transitions.py`, `transition_stats.py`; data: 37,027 contract-slot observations from 35 live cycles (`position_transitions.csv`). All statements are **associations**; counter-examples are listed.

## 1. Method (what a "transition" is)

* The real ledger (tags `num` = body, `h_` = wing) is replayed into a lot book. Before each 15-minute slot (09:16 + 15k min, both days) the book is snapshotted; the **action** during the slot is classified per contract: RETAINED, ADDED, REDUCED, CLOSED (for contracts that existed at the snapshot; contracts newly OPENED are counted separately).
* **Decision-time features** (previous completed minute): contract price; price ÷ **cheapest** open entry and ÷ average entry; strike offset from spot (steps); Black-Scholes **IV and delta solved from the option price (r = 0) — derived measures, not vendor data**; cycle mark-to-market at LTP; hours to expiry; spot move; total open body lots.
* **Outcome:** price change of the contract over the slot.
* Limitation: 15-minute snapshots blur sub-slot decisions; a ratio measured at the slot start understates the ratio at the decision minute. Body-order decision times are known only to the minute (DAT-18).

## 2. Counts

| Role | Action | Observations |
|---|---|---:|
| Body | RETAINED / ADDED / REDUCED / CLOSED | 17,028 / 3,524 / 1,542 / 482 |
| Wing | RETAINED / ADDED / REDUCED / CLOSED | 9,764 / 3,132 / 696 / 859 |

## 3. Body positions: D-1 (7,679 observations; exit = REDUCED or CLOSED, rate 6.1 %)

| Price ÷ cheapest entry | n | Exit rate | Add rate |
|---|---:|---:|---:|
| ≤ 0.5 | 573 | 1.9 % | 0.9 % |
| 0.5–0.8 | 1,155 | 3.5 % | 4.0 % |
| 0.8–1.0 | 1,850 | 3.3 % | 25.4 % |
| 1.0–1.2 | 2,504 | 5.0 % | 38.1 % |
| 1.2–1.45 | 1,106 | 11.5 % | 14.6 % |
| 1.45–1.55 | 220 | 17.7 % | 10.9 % |
| 1.55–1.7 | 126 | 27.8 % | 3.2 % |
| 1.7–2.0 | 37 | **67.6 %** | 0 % |
| 2.0–3.0 | 6 | 33.3 % | 16.7 % |
| > 3.0 | 31 | 0 % | 0 % |

Univariate rank AUCs for *exit* on D-1: price ÷ cheapest entry **0.70**, |delta| **0.71**, price level 0.67, ÷ average entry 0.67, hours to expiry 0.46, IV 0.42, cycle MTM 0.45, spot move 0.51, strike offset 0.51, total book lots 0.52. For *add*: |delta| 0.65 (adds concentrate at 0.45–0.6 delta: 44.7 %), IV 0.37 (adds when IV is lower).

**Supporting evidence for a price-stop overlay:** exit rates rise monotonically from 3 % (ratio ≤ 1.0) to 68 % (1.7–2.0); the 1.55–1.7 band (where the 1.55–1.7× stop band sits) has 27.8 % exits vs 5 % at 1.0–1.2. Example: NIFTY 2026-06-30 D-1, PE 24100: 4 lots, price ₹142.25 = 1.81 × cheapest entry (78.55), delta −0.70, cycle MTM −₹24.7 k → **CLOSED**; 24050 PE: ratio 1.86, **CLOSED**.

**Counter-evidence (must be kept):**
* 237 of 465 D-1 exit events (**51 %**) occur at ratio < 1.2; 166 (36 %) at 1.2–1.55; only 62 (**13 %**) at ≥ 1.55. A stop at 1.55–1.7× therefore explains at most ~⅓ of D-1 reductions at this resolution.
* 37.8 % of D-1 exits are **in profit** (price < average entry): e.g. NIFTY 2026-06-30, CE 24100 reduced at 0.40 × entry (₹30.15 vs ₹75.9, cycle MTM +₹23 k). These are not stops (scheduled / side / basket reductions — EXT-15).
* Of 75 D-1 observations at ratio ≥ 1.7, 48 (64 %) were **not** reduced in the slot (e.g. NIFTY 2026-07-21 CE 24100: 1 lot at 1.81 × entry, delta 0.74, cycle MTM −₹59 k, retained; PE 21000 at ratio 1.83 but price ₹1.1 — exempt, ≤ ₹4).
* Cycle MTM does **not** separate exits on D-1 (AUC 0.45; exit rate 4.7 % at < −₹1 L vs 5.9 % at 0–0.5 L). The cycle-level control is a *terminal* stop, not a gradual de-risking.

## 4. Body positions: D0 (14,897 observations; exit rate 10.5 %, add rate 12.5 %)

* Weak association everywhere: AUC exit — |delta| 0.70, price 0.67, cycle MTM 0.64, book lots 0.63, ratio ÷ cheapest 0.61, ÷ average 0.55, hours to expiry 0.37, IV 0.36.
* Exit rate by price ratio is flat-to-hump: 7 % (≤ 0.8), 12 % (1.0–1.2), 19–23 % (1.2–1.7), 10 % (> 3.0). The 1.7× stop does **not** show on D0 (ratio ≥ 1.7: 15.3 % exit), consistent with EXT-05 ("per-lot stop is weak on D0").
* Hours to expiry matters: **26 %** of positions are reduced in the final hour (0–1 h) vs 6–10 % at 1–6 h (clock/flatten/salvage behaviour; EXT-07/08).
* Cycle MTM > +₹1 L: 15 % exit vs 0.9 % when MTM < −₹1 L (after a cycle stop nothing is left to reduce — this partly reflects stop liquidation already removing positions).
* Adds on D0 concentrate at 0.3–0.6 |delta| (34–49 %), the at-the-money zone; IV AUC 0.25 (adds when IV is low relative to the book), price AUC 0.69.

## 5. Replacement and re-entry (association with timing only)
* D0 body sells: 60 % (7,591 of 12,675 lots) occur within the same or next minute of a same-side buy-back; D-1: 14 %. Median re-sell delay 28 s after the buy-back; same lots re-sold in 99.7 % of Clock-B rebalance pairs (STK-05), at a median 0 steps from ATM (re-centring).
* Replacement lots earn ₹78/lot (D0) and ₹86/lot (D-1) versus ₹294/₹469 for **off-schedule** sales (§ gap analysis).
* **Unknown:** which contract is bought back (best single criterion hit@1 0.66, MGT-04), whether to replace, at what quantity.

## 6. Wings
* Wings: 68 % retained, 22 % added, 11 % reduced or closed (14,451 observations); they are released when body lots are bought back (HDG-06: 4,653 lots "released within 60 s"). Wing price ≈ 2.44 % of the sold body (IQR 2.2–2.6 %), one wing lot per body lot (median).

## 7. What this means for rule reconstruction
| Question from the brief | Answer |
|---|---|
| Why are some positions retained? | Most are (17,028 of 22,576 body observations). Retention is the default; reductions need a schedule slot, a price trigger or time-to-expiry. |
| Why closed? | Mixed: price ≥ ~1.5× entry on D-1 (strongest, still ≈ 13 % of exits at ≥ 1.55×), profit/side/basket reductions on schedule, final-hour clearance on D0. **No single rule reaches 80 % precision/recall** (EXT-10). |
| Why added? | Schedule slots (ladder), near-ATM delta zone, lower IV; not market direction (ENT-05). |
| Why strikes changed (replaced)? | ATM re-centring after Clock-B buy-backs (STK-05). Trigger unknown. |
| Why quantities reduced? | Mostly one lot per acting tick (MGT-04, 89–99 %). |
| Why overnight? | The D-1 ladder is built to be carried; no overnight-risk rule other than the cycle stop was identified. Delta/IV/MTM do not separate carried vs closed positions at the end of D-1. |
| Gamma / volatility / capital utilisation | Gamma was **not** computed here (only delta and IV); capital utilisation cannot be inferred (SIZ-05). |

**Not claimed:** that any association above is *the* rule. Each is recorded in the evidence register with its counterexamples.
