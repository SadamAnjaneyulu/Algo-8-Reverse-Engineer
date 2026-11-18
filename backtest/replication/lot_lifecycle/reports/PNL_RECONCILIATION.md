# P&L Reconciliation (Phase 5)

**Result:** cycle-level P&L reconciles to the ledger **exactly**: for each of the 35 cycles, ledger cash + settlement cash − (Σ lot P&L + unrecorded-lot closing cash) = **₹0.000** under all four allocation conventions. **This identity is a cash-conservation check, not a correctness test of lot ownership** (review finding): any allocation, right or wrong, satisfies it, so it cannot detect mis-routing. The exact gross is **₹25,81,885** over 35 cycles, of which the 5 partial cycles are not lifecycle-meaningful, and **₹15,49,989 over the 30 complete cycles**. Code: `reconcile.py`; data `outputs/cycle_reconciliation.csv`.

## 1. Totals
| Quantity | Value |
|---|---:|
| **Gross P&L (ledger cash + settlement at the Yahoo official close), 35 cycles** | **₹25,81,885** (includes 5 partial cycles: 3 no D-1 log, 2 no D0 log) |
| Earlier order-level `live_cycle_pnl` gross, 35 cycles | ₹26,18,423 (difference −₹36,538) |
| **Gross P&L, 30 cycles with D-1 and D0 logs** | **₹15,49,989** (earlier phase ₹15.53 L: difference −₹2,517) |
| Σ lot P&L, 30 complete cycles, each convention | ₹15,49,989 (identical) |
| Unrecorded carry-in lots (5 partial cycles; primary D1 reading) | 161 lots; closing cash −₹14,771; entry P&L **unknown** |
| Cycles with no D0 log (2) | residual lots "settled" at the official close is an **artefact**; their gross is not a P&L |
| Max |identity residual| per cycle | **0.000** |

**Attribution of the ₹36,538 difference (corrected after review).** I previously attributed it to running-average fill prices. That is true only for a small part: over the **30 complete cycles the difference is −₹2,517** (largest single cycle −₹1,023, SENSEX 2026-08-20). **−₹33,744 comes from one partial cycle, NIFTY 2026-06-23 (no D-1 log, 52 unrecorded shorts)**, where the two computations also differ in how the pre-log part is treated; I did not isolate how much of that is price and how much is definition, so it is **UNATTRIBUTED**. The earlier "overstated by 1.4 %" statement is withdrawn for the 30-cycle figure (0.16 %).

**D1 interpretation range.** Totals above are identical under both readings of an unmatched body buy (`LOT_IDENTITY_METHODOLOGY.md` §6). Lot-level P&L is not: under the alternative reading 968 lots in the 30 complete cycles have unknown entries (P&L NaN) and the body-short P&L of known lots is ₹25.19 L vs ₹24.23 L primary. The range is a property of the ledger, not a result.

## 2. Unit accounting (every execution is accounted for)
Primary reading: sell lots 31,566 = short lots opened 16,179 + long lots closed by sells 15,387. Buy lots 32,086 = long lots opened 16,832 + short lots closed by buys 15,254 (15,093 recorded + 161 unrecorded). **Unmatched executions: 0** (tautological for a lot engine that consumes every fill — see the tests that check conservation *and* routing flags). **Flagged:** 161 unrecorded carry-in shorts; 991 body buys opened as longs (reading unresolved); 1,104 expiry-day EOD wing closes by body sells (routing inferred).

## 3. Allocation sensitivity (30 complete cycles, 13,211 body shorts)
| Convention | Carried (D-1-entered) body-short P&L | D0-entered body-short P&L | Total |
|---|---:|---:|---:|
| FIFO | ₹18.92 L | ₹5.32 L | ₹24.23 L |
| LIFO | ₹23.78 L | ₹0.45 L | ₹24.23 L |
| LOW_ENTRY_FIRST | ₹23.57 L | ₹0.66 L | ₹24.23 L |
| HIGH_ENTRY_FIRST | ₹19.37 L | ₹4.86 L | ₹24.23 L |

Here "carried" = every body short **entered on D-1** (4,375 lots, including those that were closed again on D-1), and "same-day" = entered on D0. **The carried / fresh split moves by ₹4.9 L across conventions** (the ±2.3 % quoted in the first draft used a different, ill-defined split and is withdrawn); per-lot P&L differs for 85.3 % of lots (median range ₹706, p90 ₹3,690). The total does not move. **No convention was selected.**

## 4. Costs and other assumptions
Gross P&L only. Costs/slippage are **not** included (the ledger has no charges). Settlement of lots held to expiry uses the Yahoo official close, a proxy for the exchange settlement price; it differs from the 15:29 spot bar by **up to 89 points in 13 early cycles**, so settled-lot P&L in those cycles is approximate. Wings, hedges and stop-module lots are in the all-role identity.

## 5. Per-cycle table
`outputs/cycle_reconciliation.csv` — ledger cash, settlement cash, Σ lot P&L per convention, unrecorded-lot count and closing cash, identity residual, `cross_role_eod_wing_closes`, open short lots, earlier gross, difference.
