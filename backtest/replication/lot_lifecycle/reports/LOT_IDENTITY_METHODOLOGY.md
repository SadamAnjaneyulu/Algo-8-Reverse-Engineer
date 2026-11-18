# Lot Identity and Allocation Methodology (Phase 2, §4.1)

**Result:** what the ledger *does* identify is an **order** (tag) and a **fill** (trade id + row), exact to the second and to the tick; it does **not** identify a lot's owner. Lots are therefore defined at **unit-lot granularity from entry fills**, and every closing fill is allocated to open lots under **four conventions run side by side**. **89 % of body short lots (30 complete cycles; 87 % over all 35) have a closing fill that depends on the convention** — lot-level lifecycles are ambiguous, while cycle-level totals are exact. Code: `ledger.py`, `lots.py`, `build_lots.py`.

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

## 5. Ambiguity actually observed (30 complete cycles, 13,211 body short lots; primary D1 interpretation, see §6)
| Measure | Value |
|---|---|
| Body shorts whose closing fill is identical under all 4 conventions | **1,473 (11 %)**; 11,738 (89 %) ambiguous. Over all 35 cycles: 1,885 unambiguous / 13,759 ambiguous / 161 entry-unrecorded body shorts (15,805) |
| Closing fill differs from FIFO under LIFO / LOW_ENTRY / HIGH_ENTRY | 86 % / 82 % / 59 % of lots |
| Per-lot P&L differs across conventions | 85.3 % of lots; median range ₹706, 90th pct ₹3,690 |
| Body-short P&L, 30 cycles, all four conventions | ₹24,23,330 (identical, by construction); the **carried (D-1-entered) share** is ₹18.92 L FIFO / ₹23.78 L LIFO / ₹23.57 L LOW_ENTRY / ₹19.37 L HIGH_ENTRY — a ₹4.9 L range |

(An earlier version of this report quoted 83 % ambiguity and a ±2.3 % carried-P&L range. Those figures came from the pre-review engine and from a different carried/non-carried split; they are superseded — see `INDEPENDENT_REVIEW.md`, `outputs/v1_pre_review/`.)

**Representing ambiguity:** `confidence` = ALLOCATION_UNAMBIGUOUS / ALLOCATION_AMBIGUOUS / ENTRY_UNRECORDED; `close_row_<convention>` and `pnl_<convention>` columns keep all four outcomes; no convention is selected.

## 6. Lots the ledger cannot fully describe — and an unresolved interpretation (review finding D1)
* **A body Buy with no recorded body short to close** has two readings the ledger cannot tell apart: (a) it closes a short that was opened before the log began (an *unrecorded* short — its P&L is unknowable), or (b) it opens a long. Both are implemented (`excess_body_buy='long'` is the **primary output**, `'unrecorded_short'` the alternative, `lots_alt_unrecorded_short.csv.gz`). Neither is a finding.
  * Primary (`long`): 991 body longs flagged `BODY_BUY_WITHOUT_RECORDED_SHORT_OPENED_AS_LONG`; 161 `UNRECORDED_CARRY_IN_SHORT` lots, all in the **5** cycles whose carry-in is unknown (3 without a D-1 log, 2 without a D0 log; flag `carry_in_known = False`).
  * Alternative (`unrecorded_short`): 968 body shorts in the 30 complete cycles become ENTRY_UNRECORDED with NaN P&L; 34,110 lots in total; the body-short P&L attributable to *known* lots rises to ₹25.19 L (a different population, not a better estimate).
  * Cycle totals are identical in both (ledger cash); **lot-level P&L of the affected lots is unknown under (a)**.
* **Settled shorts in the two cycles with no D0 log (146 lots):** "SETTLEMENT" is an artefact there (D0 unobserved).
* The earlier statements "ANOMALOUS lots are not matched to anything" and "153 unrecorded lots in 3 cycles" were wrong: such buys are *opened as longs* (primary) and may be closed later by a body Sell (`BODY_SELL_CLOSING_LONG`, 772 lots); unrecorded carry-in shorts number 161 in 5 cycles.
* **Expiry-day end-of-day cross-role closes (D3):** a body `num` Sell at/after 15:10 on expiry day in a contract where a wing long is open closes the wing long first (flag `CROSS_ROLE_EOD_WING_CLOSE`, 1,104 lots, close reason `CROSS_ROLE_EOD_WING_CLOSE_BY_BODY`) instead of opening a spurious body short. This routing is an **inference** from tags/timing (HYPOTHESIS), not an observation.
* **Stop-module lots (D2):** `s_`/`m_` buys/sells now also close previously stop-opened lots (role `stop`) before opening new ones; opens by a closing-side order (`h_` Sell, `v_` Sell, `s_` Buy) carry `OPENED_BY_CLOSING_SIDE_ORDER`.
* **Settlement price:** residual lots settle at the Yahoo official close (proxy). It differs from the 15:29 spot bar by **up to 89 points in 13 early cycles** (not "~3 points"), so settled-lot P&L in those cycles is approximate.

## 7. Field definitions changed by review (D6)
`entry_order_lots` = size of the originating **order** (sum over its fills); `entry_fill_lots` = size of the originating **fill**. They were conflated before. `holding_seconds` counts **market seconds** (09:15–15:30 each day, overnight excluded) for D-1 → D0 lots.

## 8. Associations (not identity)
* **Wing link** (`lot_links.csv.gz`): body entry lot ← wing lot bought within ±15 s (decision time from the `h_` tag), same right and day, optimal one-to-one: 12,255 of 15,644 recorded body short lots (78.3 %) linked, median |Δt| 4 s, median wing/body price 0.025. Confidence **POSSIBLE_TIMING_ONLY**.
* **Replacement link:** order-level, from the replacement analysis (classified; no lot-level claim).
