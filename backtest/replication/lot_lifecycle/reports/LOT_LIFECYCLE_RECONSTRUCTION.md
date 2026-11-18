# Lot Lifecycle Reconstruction (Phase 2)

**Result:** every one of the **63,652 lots** traded in the ledger (31,566 sold, 32,086 bought) is accounted for in a **unit-lot lifecycle dataset** with an identity, an entry fill, a disposition and an exact P&L: 100 % of units, no residual, per-cycle P&L identity residual **0.000** over all 35 cycles. **What is certain:** the entry fill, the prices, the totals. **What is ambiguous:** which closing fill belongs to which lot (83 % of body shorts, §3). Code: `lots.py`, `build_lots.py`, `reconcile.py`, `link_wings.py`; data: `outputs/lots.csv.gz`, `lot_links.csv.gz`, `cycles.csv`.

## 1. What was built
`outputs/lots.csv.gz` — 34,882 unit lots opened (one row per lot; FIFO fields + per-convention close/P&L columns):

| Role | Side | Lots | Meaning |
|---|---|---:|---|
| body | SHORT | 16,748 (+153 unrecorded) | sold by the body module (`num` tag) |
| body | LONG | 985 | body buys with no short to close (flagged anomalies) |
| wing | LONG | 14,184 | `h_` wing buys |
| wing | SHORT | 11 | `h_` sells that opened shorts |
| lump | LONG | 1,503 | `v_` overnight hedges |
| stop | SHORT / LONG | 641 / 657 | `s_`/`m_` orders that opened positions (stop-module overshoot, RSK-12) |

**Accounting identities (CONFIRMED OBSERVATION, executed):** sell lots 31,566 = short lots opened 17,400 + long lots closed by sells 14,166; buy lots 32,086 = long lots opened 17,329 + short lots closed 14,757 (incl. 153 unrecorded). All cycle totals equal ledger cash plus settlement to ₹0.000.

## 2. Dispositions of short lots (35 cycles, FIFO; ownership-dependent timing)
| Disposition | Lots | Comment |
|---|---:|---|
| Body buy-back | 13,369 | the body module bought the contract |
| Held to settlement | 2,796 | of which 146 are an artefact (cycles with no D0 log); most are far-OTM worthless (98 %, earlier phase) |
| Stop-module order | 1,380 | closed by an `s_` order |
| Hedge-module order | 8 | wing sells that closed a short |

By convention the share of **carried** lots closed by stop-module orders is 14–17 % and held to settlement 8–9 % (`CARRIED_LOT_BUYBACK_ANALYSIS.md`).

## 3. Ownership ambiguity (the central limitation)
Under four conventions the closing fill of 83 % of body shorts changes (`LOT_IDENTITY_METHODOLOGY.md`). *Lifecycle statistics that depend on which lot closed* — holding time, per-lot P&L, carried-vs-fresh split, "bought back after k minutes" — are therefore **ranges**, not point values; *statistics about contracts or orders* (buy-back timing, quantities, prices) are exact.

## 4. Field-by-field (requested schema)
| Field | Available | Note |
|---|---|---|
| lot_id, cycle_id, index, instrument, option_type (`cp`), strike, expiry | yes | |
| source_trade_ids | `entry_trade_id`, `close_trade_id` | plus `entry_row`/`close_row` (unique fill keys) |
| entry_timestamp / price / quantity | `entry_day`+`entry_sec` (s), `entry_price` (per-fill tick), `entry_quantity_units` | `entry_order_lots` = size of the originating order |
| remaining_quantity | 0 for every lot at the end of the cycle (all lots closed or settled); intermediate remaining quantity is available from the event order | |
| close timestamp / price / reason | `close_day`+`close_sec`, `close_price`, `close_reason` (BODY_BUYBACK, STOP_MODULE, HEDGE_ORDER, LUMP_ORDER, MANUAL, SETTLEMENT) | settlement price = Yahoo official close (proxy) |
| replacement_lot_id | **not assigned**: replacements are order-level, classified in `lot_links.csv.gz` (`replacement_candidate_order_tag`, `replacement_class`) | no lot-level claim |
| wing_lot_id | `lot_links.csv.gz` (`POSSIBLE_TIMING_ONLY`) | 73 % linked |
| hedge_relationship | wing close reason in `lot_links`; lump hedges are role `lump` lots | not tied to body lots (no evidence) |
| realized_pnl | `realized_pnl` (FIFO) and `pnl_<convention>` | exact per fill |
| unrealized_pnl | at the cycle end 0 (all closed/settled); the D0-open mark of carried lots is in `carried_lots.csv.gz` (`d1_last_price`) | MFE/MAE there |
| holding_duration | `holding_seconds` (FIFO) | convention-dependent |
| allocation_method | `FIFO` primary; others in columns | never "original" |
| confidence / unresolved_flags | `ALLOCATION_(UN)AMBIGUOUS`, `ENTRY_UNRECORDED`; flags `UNRECORDED_CARRY_IN_SHORT`, `ANOMALOUS_OPEN_LONG_BY_BODY_BUY` | |

## 5. Quality
Perturbation-free (the engine uses only ledger fields); adversarial fixtures (12 tests) cover multiple entries, partial buy-backs, same-second fills, re-entry, hedge routing after a stop, missing carry-in, settlement ITM/OTM, duplicate trade ids and unit conservation.
Figures (actual solid, inferred dashed/labelled): `figures/01…13_*.png`.
