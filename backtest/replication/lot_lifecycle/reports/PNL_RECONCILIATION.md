# P&L Reconciliation (Phase 5)

**Result:** lot-level P&L reconciles to the ledger **exactly**: for every one of the 35 cycles, ledger cash + settlement cash − (Σ lot P&L + unrecorded-carry-in closing cash) = **₹0.000** under all four allocation conventions. **The earlier "live gross" (₹26.18 L) was overstated by ₹36.5 k** because per-fill running-average prices were applied to each fill; the exact total is **₹25.82 L** (35 cycles) and **₹15.50 L over the 30 complete cycles**. Cycle totals do not depend on the allocation convention; lot-level and class-level P&L do. Code: `reconcile.py`; data `outputs/cycle_reconciliation.csv`.

## 1. Totals
| Quantity | Value |
|---|---:|
| Ledger cash flows, 35 cycles (exact per-fill prices) | see `cycle_reconciliation.csv` |
| Settlement cash (residual lots at Yahoo official close) | included |
| **Gross P&L (ledger cash + settlement), 35 cycles** | **₹25,81,885** |
| Earlier order-level `live_cycle_pnl` gross | ₹26,18,423 (difference −₹36,538; max ₹33,744 in one cycle) |
| **Gross P&L, 30 cycles with D-1 and D0 logs** | **₹15,49,989** (earlier phase: ₹15.53 L) |
| Σ lot P&L (30 complete cycles), each convention | ₹15,49,989 (identical) |
| Unrecorded carry-in lots (3 cycles with no D-1 log) | 153 lots; closing cash −₹14,700; entry P&L **unknown** |
| Cycles with no D0 log (2) | residual lots "settled" at the official close is an **artefact**; their gross is not a P&L |
| Max |identity residual| per cycle | **0.000** |

The ₹36.5 k difference to the earlier figure comes from `live_cycle_pnl.py` using the running-average `px_fill` as if it were each fill's price (exact only per order); the order totals were exact. All earlier results that quote "live gross ₹26.2 L" are therefore overstated by 1.4 % (they remain valid in sign and shape).

## 2. Unit accounting (every execution is accounted for)
Sell lots 31,566 = short lots opened 17,400 + long lots closed by sells 14,166. Buy lots 32,086 = long lots opened 17,329 + short lots closed by buys 14,757 (14,604 recorded + 153 unrecorded). **Unmatched executions: 0.** **Flagged:** 153 unrecorded carry-in shorts; 985 anomalous body long opens.

## 3. Allocation sensitivity (30 complete cycles; body shorts)
| Convention | Carried-lot P&L | Non-carried body-short P&L | Total body-short P&L |
|---|---:|---:|---:|
| FIFO | ₹40.59 L | −₹16.01 L | ₹24.58 L |
| LIFO | ₹39.18 L | −₹14.60 L | ₹24.58 L |
| LOW_ENTRY_FIRST | ₹40.56 L | −₹15.98 L | ₹24.58 L |
| HIGH_ENTRY_FIRST | ₹38.75 L | −₹14.17 L | ₹24.58 L |

("Non-carried" = lots entered and closed on the same day, including D0-opened lots, as the carried split is entry-day based.) The split between carried and non-carried moves by ₹1.8 L (±2.3 %) across conventions; per-lot P&L differs for 79.7 % of lots (median ₹578, p90 ₹3,597). **No convention was selected.**

## 4. Costs and other assumptions
Gross P&L only. Costs/slippage are **not** included in this reconciliation (the ledger has no charges; brokerage ₹20/order and statutory rates are assumptions elsewhere). Settlement of lots held to expiry uses the Yahoo official close (a proxy for the exchange settlement price; earlier phases found the 15:30 bar differs by ~3 points). Wings and hedges are included in cycle totals; lump/stop-module lots are included in the all-role identity.

## 5. Per-cycle table
`outputs/cycle_reconciliation.csv` — ledger cash, settlement cash, Σ lot P&L for each convention, unrecorded-lot count and closing cash, identity residual, earlier gross, difference, anomalous long lots, short lot count.
