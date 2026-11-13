# M2-B reconciliation report (real ledger, executed)

Source: `Trades_GKOHNP140.csv` sha256 `86e65ab6ece492a7…` → TP-01 ledger sha256 `3b47c55150d79535…`; 41,421 fills; primary tie order `src`. Produced by `tools/m2b_reconcile.py` (raw numbers in `m2b_reconciliation.json`). **No logic was adjusted to force a match.**

| Target (from existing research) | Reproduced | Match |
|---|---:|---|
| Opening allocations 23,684 | 23,684 | True |
| Closing portions 17,760 | 17,760 | True |
| TP-02 `exit_event_timelines` rows 17,760 | 17,760; same `close_row` set: True; quantity mismatches: 0 | True (equal rows and quantities; semantics of the TP-02 table not relied upon) |
| Inventory episodes 2,667 | 2,667; ids and opened/closed/direction/end reason equal TP-01 for FIFO, LIFO, AVG | True |
| Mixed (open + close) parents 26 | 26 = 23 containing a reversal fill + 3 multi-fill parents without a reversal; OA + CP units equal the parents' fill units: True | True |
| Opened / closed / remaining 1,414,545 / 1,377,065 / 37,480 | 1,414,545 / 1,377,065 / 37,480 (Σ OA units 1,414,545, Σ CP units 1,377,065) | True |

**Realized gross P&L (₹) from the sum of closing allocations vs TP-01:** FIFO 2,100,552.00 vs 2,100,552.00; LIFO 2,096,874.50 vs 2,096,874.50; AVG 2,100,111.63 vs 2,100,111.63 (TP-01 rounds AVG to 2 decimals).

**Remaining slices:** FIFO 37,480, LIFO 37,480, AVG pools 37,480 units (= 37,480, all in expired contracts). Terminal statuses: {'CLOSED': 2563, 'EXPIRED_UNCLOSED': 81, 'REVERSED': 23}. No settlement P&L exists for the 81 `EXPIRED_UNCLOSED` episodes.

**Observed layer across conventions:** hash of `observed_allocations + lifecycle + episodes` is `c9ff014a5919e0fe` for FIFO, LIFO and AVG (identical). **Analytical difference confined to allocation:** 15,889 of 17,760 closing portions (1,193,495 units) attribute to different opening allocations under FIFO vs LIFO (descriptive; not a quality measure).

**Parents:** `parents.tsv` rows 39,874; roles {'OPENING_ONLY': 23057, 'CLOSING_ONLY': 16791, 'MIXED': 26}; missing values {'algo_id': 1}; conflicts none; Σ parent units = Σ fill units: True.

**Identity vs tie order (documented limit, not hidden):** identities are invariant to FIFO/LIFO/AVG, but **conditional on the tie-order convention**: under `sells_first` / `buys_first` 20 fills in 5 instruments change their episode/portion rows (42 rows). All of them lie in the 46 instruments with mixed-side same-second fills (confined: True); they are a **superset** of TP-01's 3 close-quantity-ambiguous instruments (False that they are confined to those): a same-second buy and sell can change episode numbering without changing any fill's close quantity. The primary `src` order (file order, verified chronological) stays authoritative.

**Invariants executed on the real data:** I-unique-observed-ids, I1, I2, I11, I-unique-ca-ids, I4, I6, I3, I7, I-ownership-label, I-AVG-no-ownership, I5, I10, I-observed-layer-identical-across-conventions (row-level re-derivation from emitted rows, lifecycle events and input fills after the independent review).
