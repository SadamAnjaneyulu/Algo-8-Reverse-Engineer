# Body Module lifecycle (D-1 and D0, separately) — plan, written before the analysis

Scope: investigation only; no simulator/engine change, no alpha, no Sharpe/return optimisation. Ledger and earlier outputs read-only. In-sample (35 live cycles, not a holdout). Every finding is tagged **Observed / Inferred / Unresolved**. "Body" here = the numeric-tag order stream (its sells, buy-backs and its own long-wing buys); hedge (`h_`), lump (`v_`), stop (`s_`) orders appear in the event table as separate modules.

## 1. Inputs and what they allow (audited)
| Asset | Use |
|---|---|
| `Trades_GKOHNP140.csv` via `bh_common.order_table` | orders with limit price, validity, fill second, contract; decision stamp for non-body modules |
| Limit price ≈ live price × (1 ∓ 0.15) (Body/Hedge study) | recovers each order's **decision-time price** (±≈ 1 %) |
| Chain minute data (open/close/volume by strike, spot close) | spot at minute ends only; no bid/ask, no high/low |
| `bh_b1_order_roles.csv` | contract-level role of each order (open_short, cover_short, open_long, close_long) |
| `lot_lifecycle` lots (4 ownership conventions) | lot-level lifecycle **only as convention-labelled sensitivity**; strike-position level is ownership-free |
| `cycles.csv` | 35 cycles; 5 have unknown carry-in (D-1 or D0 log missing) — flagged, excluded from inventory claims |

## 2. The ATM-reference problem and how it is handled
Body orders carry no sub-second stamp, and the minute data give spot only at minute ends. "ATM at decision time" is therefore bracketed, not assumed:
* **R1 prev-close:** nearest strike to spot close of minute j−1 (causal, available to the algo).
* **R2 current-close:** nearest strike to spot close of minute j (non-causal; the other end of the bracket).
* **R3 parity-implied spot (new):** for a CE and PE sold at the same strike within ≤ 2 s, implied spot = K + C_ref − P_ref with C_ref/P_ref recovered from the limit prices (decision-time prices). Validated against chain spot (error distribution reported) before use. Gives a decision-time ATM for straddle pairs.
* **R4 synthetic ATM:** argmin |C − P| on the chain at minute j−1 (tested in the earlier study; kept as comparator).
Offsets are reported in strike steps (NIFTY 50, SENSEX 100) for each reference; a sold strike is "unambiguous ATM" only if the references agree. A null (nearest strike to the spot of a random other minute of the same day) accompanies every hit rate.

## 3. D-1 study (position building and overnight carry)
| ID | Question | Method | Criterion fixed in advance |
|---|---|---|---|
| D1-A | Strike selection | offset distribution vs R1–R3; CE vs PE; by slot, und, expiry era; behaviour when the market moved since the previous slot; exceptions (non-zero offsets) tested for systematic direction (toward the move? ITM/OTM? time-of-day?) | an exception class is "systematic" only if its direction differs from 50/50 with Holm-adjusted p < 0.05 |
| D1-B | Quantity | order sizes; accumulate-at-same-strike vs migrate-to-new-strike (per slot and right); number of distinct strikes per slot; lots per slot vs slot index, spot move since previous slot, ATM-change indicator, und; cross-cycle ladder stability (similarity to the modal ladder) | descriptive + variance decomposition; formulas must beat the slot-index baseline |
| D1-C | Lifecycle | strike-position paths (open, adds, reductions, close, carry) at contract level; lot lifecycle from the lot engine under all four conventions as sensitivity (holding times, close types) | ownership-free first |
| D1-D | Ending logic | minute histogram of the last body sells/buy-backs; whether selling stops at a clock time; scheduled closes; what is carried (moneyness, price ratio, strike, long/short, lump) vs what is closed; relation to premium/spot at the close | carry composition compared with closed inventory |
| D1-E | Event table | every Body/Hedge/stop/lump order in time order with ATM refs, selected strike, offset, action, quantity, resulting contract position and per-right S/L | full CSV + representative excerpts |

## 4. D0 study (management and liquidation) — independent of D-1
| ID | Question | Method |
|---|---|---|
| D0-A | Opening inventory | contract-level S/L by strike at the D0 open from D-1 events; compare with the first D0 orders (buy-backs of positions not recorded as short ⇒ unrecorded carry-in); lump lots |
| D0-B | Strike selection | same offset analysis as D1-A on D0 sells; share at already-short strikes (accumulation) vs new strikes vs D-1 carried strikes; ITM/OTM bias |
| D0-C | Management | classify every D0 body order (new short at new strike / add at existing strike / partial cover / full cover / roll leg / long open / long close); re-entry after buy-back (60 s pairing as descriptive filter, with a shuffled null); strike migration after a buy-back (old→new offset vs spot move); clock structure of sells and buy-backs (minute-of-hour, seconds); hazard of buy-back against five pre-registered drivers (distance from spot in steps, price ÷ entry, time since entry, minutes since open, spot move over the last 5 min) with Holm |
| D0-D | Ending | what happens from 15:00: first/last orders by module and role, 15:14 flatten share of S and L closed, residual positions at the last event and their settlement status, pre/post 2026-08-03 cutover, short vs long handling, unrecordable positions (carried to settlement) |
| D0-E | Event table | as D1-E |

## 5. Deliverables
`reports/BODY_LIFECYCLE_D1_D0_INVESTIGATION.md` (two lifecycle models, deliverables table, unexplained-behaviour register D-1 / D0, evidence tags) · `outputs/bl_events_d1.csv`, `outputs/bl_events_d0.csv` (time-ordered event tables) · scripts `src/bl_*.py` · tests `tests/test_bl.py` · figures. D-1 and D0 are analysed by separate scripts; the combined flow is written only after both.

## 6. Limits fixed in advance
No bid/ask or tick data; body fills at second resolution (decision time unknown within the minute); lot ownership is a convention; zero-fill/cancelled orders invisible; the 0.15 limit cushion is a modal estimate. A hit rate is never read as "the algorithm targets X" without the exceptions and a null.

---
## Addendum (written after the analysis; the plan above is unchanged)
* Added during the work: `bl_explore.py` (parity-implied spot check, reference-lag scan, seconds-from-slot-start table, candidate rules for non-scheduled sells); order classes `slot_minute / minute_before_slot / roll_sell / other` introduced after the first look at the time structure (post-hoc, labelled in the report).
* **Correction:** the 15:14-flatten split used the reported cut-over date 2026-08-03 first; the per-cycle data show no flatten for D0 dates 08-04…08-13 and a flatten from D0 2026-08-25, so the report uses the **observed break** (no measurable flatten ≤ 2026-08-13; D0 08-18/08-20 cycles have no body closing after 14:30 and are undetermined).
* Parity-implied spot (R3) turned out noisier than the minute closes and is a cross-check only.
