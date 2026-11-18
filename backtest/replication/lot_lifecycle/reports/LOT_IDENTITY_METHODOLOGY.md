# Lot Identity and Allocation Methodology (Phase 2, §4.1)

**Result:** what the ledger *does* identify is an **order** (tag) and a **fill** (trade id + row), exact to the second and to the tick; it does **not** identify a lot's owner. Lots are therefore defined at **unit-lot granularity from entry fills**, and every closing fill is allocated to open lots under **four conventions run side by side**. **82 % of body short lots have a closing fill that depends on the convention** — lot-level lifecycles are ambiguous, while cycle-level totals are exact. Code: `ledger.py`, `lots.py`, `build_lots.py`.

## 1. Identifiers available (CONFIRMED OBSERVATION; tests in `INITIAL_AUDIT.md`)
| Identifier | Status |
|---|---|
| Order id | column-163 tag, unique per order (39,874). The numeric order id (col 4) is reused across days: not used. |
| Trade / fill id | col 28; unique **per fill within a date/segment** (41,399 unique of 41,421; the 22 repeats are different orders/contracts/dates). Fill key = (date, trade id, row). |
| Per-fill price | raw col 137, tick-exact; order VWAP from it equals the earlier running-average price exactly. |
| Timestamps | seconds (fills); microsecond decision time only for `h_/s_/v_/m_` tags. Within-second order = file order. |
| Allocation / parent / strategy-basket id | **absent**. AlgoId (col 144) identifies the underlying only. |
| Quantity | always whole multiples of the lot (65/20): 100 % divisible into unit lots. |

## 2. Lot definition
`lot_id = <index><expiry>-<entry fill row>-<k>`: the k-th unit lot of an entry fill. It is **independent of the allocation convention**, so lots can be compared across conventions. A lot is opened by a fill that has no opposite-side inventory left in the routed roles; it is closed by exactly one later fill (or by settlement).

## 3. Role routing (uses real order metadata, not an assumed allocation)
Orders carry a module tag. Closes are routed: `num` closes body lots; `h_` closes wing (then lump); `v_` closes lump (then wing); `s_`/`m_` buys close body, lump, wing and sells close wing, lump, body. Within the routed role the **allocation convention** picks the lot. *Assumption (HYPOTHESIS):* a module closes lots of its own role first; where a module closes another role's lots (stop module) it is observed in the ledger (RSK-10/12).

## 4. Allocation conventions (none is claimed to be the original method)
FIFO; LIFO; LOW_ENTRY_FIRST (close the open lot with the lowest entry price: the earlier research reported that stop buy-backs track the cheapest open entry); HIGH_ENTRY_FIRST. Each convention yields the same cycle totals (exact) and different lot lifecycles.

## 5. Ambiguity actually observed (30 complete cycles, 14,149 body short lots)
| Measure | Value |
|---|---|
| Body shorts whose closing fill is identical under all 4 conventions | **2,404 (17 %)**; 11,745 (83 %) ambiguous |
| Closing fill differs from FIFO under LIFO / LOW_ENTRY / HIGH_ENTRY | 80 % / 77 % / 55 % of lots |
| Median |Δ close time| where it differs | 1,462 s / 1,391 s / 185 s |
| Per-lot P&L range across conventions | 79.7 % of lots differ; median ₹578, 90th pct ₹3,597 |
| Carried-lot P&L total | FIFO ₹40.6 L; LIFO ₹39.2 L; LOW_ENTRY ₹40.6 L; HIGH_ENTRY ₹38.8 L (cycle total equal ₹24.6 L for all body shorts) |

**Representing ambiguity:** `confidence` = ALLOCATION_UNAMBIGUOUS / ALLOCATION_AMBIGUOUS / ENTRY_UNRECORDED; `close_row_<convention>` and `pnl_<convention>` columns keep all four outcomes; no convention is selected.

## 6. Lots the ledger cannot fully describe
* **UNRECORDED_CARRY_IN_SHORT (153 lots):** in the three cycles whose D-1 log is missing, body buy-backs of a short that was opened before the log. They are created as shorts with unknown entry (P&L unknown) — never as phantom longs.
* **ANOMALOUS_OPEN_LONG_BY_BODY_BUY (985 lots):** body buys with no body-short inventory in cycles with a known carry-in: flagged, kept as longs, **not** matched to anything.
* **Settled shorts in the two cycles with no D0 log (146 lots):** "SETTLEMENT" is an artefact there (D0 unobserved).

## 7. Associations (not identity)
* **Wing link** (`lot_links.csv.gz`): body entry lot ← wing lot bought within ±15 s (decision time from the `h_` tag), same right and day, optimal one-to-one: 12,258 of 16,748 body short lots (73 %) linked, median |Δt| 4 s, median wing/body price 0.025. Confidence **POSSIBLE_TIMING_ONLY**.
* **Replacement link:** order-level, from the replacement analysis (classified; no lot-level claim).
