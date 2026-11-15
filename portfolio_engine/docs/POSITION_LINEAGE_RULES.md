# Position lineage rules (M2-A, DRAFT for review)

## 1. Fill decomposition (convention-independent, L1)
For every non-duplicate fill, in the engine's deterministic order, with `inv` = signed inventory of its instrument before the fill:
* against the inventory: `close_qty = min(q, |inv|)`, `open_qty = q − close_qty`; if `open_qty > 0` the fill is a **reversal**;
* with the inventory or flat: `close_qty = 0`, `open_qty = q`.
Emit `CP:<fill_id>` if `close_qty > 0` (episode = the episode being reduced) and `OA:<fill_id>` if `open_qty > 0` (episode = the current or newly created one). `OA.qty + CP.qty = fill qty`.

## 2. Allocation under a convention (L2)
State per instrument: ordered list of lots `[oa_id, remaining_qty, price]`.
| Convention | Closing portion of `c` units | Output |
|---|---|---|
| FIFO | consume lots from the front until `c` is exhausted | one `ClosingAllocation` per lot touched: `allocated_qty`, `entry_price`, `exit_price`, `realized_pnl = direction × (exit − entry) × allocated_qty` (paise·units, exact int64) |
| LIFO | consume from the back | same |
| AVG | one pool per episode, `avg_cost` updated on every opening, unchanged by closings | one row `CP → POOL(episode)` with `pool_avg_cost` and `realized_pnl = direction × (exit − avg) × c`; `ownership = NOT_IDENTIFIABLE`; `PositionSlice(kind=POOL)` lists `contributing_oa_ids` as *provenance* |
Reversal: the closing part is allocated as above against the episode being closed; the opening remainder creates `OA` and a fresh lot/pool in the new episode. The remainder is **never** part of a ClosingAllocation.

## 3. Lifecycle state machine (per episode)
```
(first opening fill) ──► CREATED
CREATED/ADDED/PARTIALLY_REDUCED ──opening fill──► ADDED
… ──closing fill, inventory > 0 after──► PARTIALLY_REDUCED
… ──closing fill, inventory = 0 exactly──► CLOSED
… ──closing fill with excess opening──► REVERSED (this episode) + CREATED (next episode, started_by_reversal)
end of data, inventory > 0: expiry <= last data date ──► EXPIRED_UNCLOSED ; else ──► OPEN_AT_END_OF_DATA
INCOMPLETE_SOURCE_HISTORY: reserved for evidence that inventory pre-dates the export (a closing fill with no inventory); TP-01 reports 0 unmatched units, so 0 expected; covered by a synthetic test only.
```
Each event stores `fill_id` and `parent_order_id`, the quantity, inventory after, and (per convention) the allocations produced. `CLOSED` vs `REVERSED` and `ADDED` vs `CREATED` are decided only by the role rule (§1).

## 4. Invariants (all executable; run after every fill in strict mode and at the end)
| # | Invariant |
|---|---|
| I1 | per instrument: `Σ OA − Σ CP = |signed inventory|` (direction-aware) |
| I2 | per episode: `opened − closed = remaining` |
| I3 | per OA: `qty = Σ allocated (FIFO/LIFO) + remaining slice` — holds under each convention separately |
| I4 | per CP: `qty = Σ its ClosingAllocation.allocated_qty` (FIFO/LIFO); AVG: one row of `qty` |
| I5 | per fill: `OA.qty + CP.qty = quantity`; ≤ 1 OA and ≤ 1 CP |
| I6 | `Σ over all realized_pnl by convention` equals the M1 portfolio realized P&L for that convention (exact for FIFO/LIFO, tolerance 1e-6 for AVG) |
| I7 | `Σ remaining slices (FIFO)` = `Σ remaining slices (LIFO)` = M1 remaining units (37,480) — per-OA remaining differs by convention, the total does not |
| I8 | every Basket view is a **partition** of its member universe (episodes / OAs / CPs): no member in two baskets of one view; `Σ basket totals = universe total` |
| I9 | views are never summed against each other; a member may appear once per view |
| I10 | `EXPIRED_UNCLOSED` episodes carry **no** settlement P&L |
| I11 | a reversal creates exactly one CP and one OA, in two different episodes |

## 5. Worked examples (will be synthetic tests; not Algo 8 claims)
* **Reversal:** short 100, buy 130 → CP 100 (episode ends `REVERSED`), OA 30 (new long episode); never "a 130-unit close".
* **FIFO / LIFO / AVG:** short A = 65 @ 100, short B = 65 @ 120, buy 65 @ 110. FIFO closes A (short 100 bought back at 110: **−10 × 65**), LIFO closes B (short 120 bought back at 110: **+10 × 65**); AVG pool 110 gives 0 and states no ownership. (An earlier draft of this line had the signs reversed; the executed test `test_ab_lots_fifo_lifo_avg_confined_to_analytical_layer` caught it.)
* **Partial fills:** parent P with fills 65 + 65 + 65 → three OAs, one ParentOrder; counted once as a decision.

## 6. Python / C++ boundary (proposal, needs approval)
| Component | Language | Why |
|---|---|---|
| fill decomposition, OA/CP, lots with `oa_id`, ClosingAllocation, PositionSlice, lifecycle events, I1–I7, I10–I11 | **C++ core + Python reference**, shared fixtures, byte-identical dumps | deterministic state and identity; extends the M1 pattern |
| Model A (cycle container) and basket reconciliation (I8) | **both** | pure function of instrument identity; cheap; guards partition logic |
| Model B (opening cohorts) and Model C (closing batches) | **Python only** | need order-entry minute, app key, order-number blocks, TP-03 window attribution — analytical inputs outside the core state; outputs labelled ANALYTICAL; reconciled against the core totals |
| Wing/body associations, forensics, charts | **Python only** | research analytics |
M1 files (`events.tsv`, `state_dump.tsv`, `roles.tsv`) and the M1 parity artifacts are **unchanged**; M2 adds new files only (`parents.tsv`, `allocations.tsv`, `lifecycle.tsv`, `slices.tsv`, `baskets.tsv`).

## R1 ADDENDUM — intra-second fill-order convention (appended 2026-11-15; earlier text unchanged)

**Rule.** The fill-order rule inside one second is the declared convention **`SOURCE_ROW_ORDER_CONVENTION`** (source-file row order), implemented as the engine tie order `src` (alias `source_row`). Source timestamps have one-second resolution. All lineage, closing-batch, wing/body and forensic outputs use **`SOURCE_ROW_ORDER_CONVENTION`**: fills of the same instrument within the same second are processed in source-file row order. This is a deterministic convention, **not verified intra-second execution chronology**. Under the sensitivity-only policies (`sells_first`, `buys_first`, `trade_id`, `order_no`, `sensex_trade_id_time`) aggregate opening/closing units, final inventory and cash are unchanged, but episode identity, reversal counts, opening/closing allocation membership, FIFO/LIFO attribution, closing-batch membership and wing/body membership can change for a small number of instruments. These must not be treated as order-independent facts. **No number in this report changed**; the delivered outputs are byte-identical to the pre-R1 baseline except for a `tie_order_convention` field added to four manifests. Full evidence and the five separately reported populations: `reports/R1_TIE_ORDER_CONVENTION.md`.

| Policy | Fills whose open/close split changes | Episodes changed | Instruments changed | Reversal-ended episodes (primary 23) |
|---|---:|---:|---:|---:|
| `sells_first` | 2 | 1 | 1 | 23 |
| `buys_first` | 4 | 12 | 5 | 23 |
| `trade_id` | 4 | 4 | 2 | 21 |
| `order_no` | 4 | 4 | 2 | 21 |
| `sensex_trade_id_time` | 0 | 0 | 0 | 23 |
