# Order sequence around each late burst: is the sell-to-close a mechanical wing unwind? (pre-registration)

*Written 2026-11-24 **before** any test below ran. Follows `LATE_SALE_FOCUSED.md`. Question: the 34 sell-to-close orders (27 post-auction, all sold below entry) sit beside the short-sale bursts (24 of 27 within 60 s). Is that a restructuring decision, or the **wing controller** doing its documented job (D-1 engine README: "about 4 seconds after body orders, buy exactly the gap between short and long lots on each right ...; when shorts fall, sell the excess wings, outermost first")? The mechanism predicts the sell-to-close follows a **cover (stop-out)** or a **drop in short lots** on the same right, ~4 s after a body order, and leaves **long lots ≈ short lots** on that right. Frozen rule, score and hashes untouched.*

## Definitions (fixed)
* Orders are the real D-1 orders ≥ 15:15 in the development cycles (post-auction primary; pre-auction reported). Book per right from the order ledger (flat at 09:15): short lots S = Σ(−net) over strikes with net < 0, long lots L = Σ net over strikes with net > 0.
* A **close-long cluster** = close_long orders in one cycle and one right with gaps ≤ 10 s. A **body order** = any order of module `num` (open_short, cover_short, or body long).
* **Tolerance** for "balanced": |L − S| ≤ max(1, 10% of S).

## Tests (family of 3, BH 10%)
| ID | Statistic | Null / rule |
|---|---|---|
| **W1 wing balance restored** | share of close-long clusters with L_before > S_before + tolerance **and** |L_after − S_after| ≤ tolerance | null: the share of random time points (uniform over 15:15–15:40, same cycle and right, 5,000 draws) where the same two-part condition would hold for a hypothetical close that brings L to S; **meaningful** if excess ≥ 0.30 |
| **W2 ~4 s after a body order** | median lag from the cluster's first order back to the most recent body order, and the share with lag in 2–8 s | null: the same share for random time points; **meaningful** if excess ≥ 0.30 |
| **W3 follows a stop-out** | share of close-long clusters preceded within 60 s by a cover_short **on the same right** | null: share for random time points; **meaningful** if excess ≥ 0.30 |

## Descriptive (no p-value)
* **Timelines** of every late order (time, role, module, right, strike, lots, price) for each cycle with a sell-to-close, and for each such cluster which came first (the cluster or the nearest short-sale burst) and by how many seconds.
* Whether the sold wing is the **outermost** held long on its right.
* Counts of close-long orders by module (h_ vs num) and by whether S fell just before.

## Decision
* **Mechanical unwind supported** if W1 and W3 are BH-significant and meaningful; then the sell-to-close is not an independent late-sale decision and the "restructuring" reading is replaced by "stop-out → wing unwind".
* **Not supported:** the close-long is something else (unresolved).
* Same development cycles; 27 post-auction orders in 7 cycles, so effectively about 8–12 clusters: low power, and "not supported" means "not detectable".
