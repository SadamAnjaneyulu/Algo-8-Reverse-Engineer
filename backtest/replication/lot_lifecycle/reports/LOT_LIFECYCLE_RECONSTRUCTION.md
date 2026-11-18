# Lot Lifecycle Reconstruction (Phase 2)

**Result:** every one of the **63,652 lots** traded in the ledger (31,566 sold, 32,086 bought) is accounted for in a **unit-lot lifecycle dataset** with an identity, an entry fill, a disposition and a P&L: 100 % of units, no residual, per-cycle identity residual **0.000** over all 35 cycles. **Caveat added by review:** that identity is a cash-conservation check (it holds for any allocation, including a wrong one), so it proves bookkeeping, **not** correct lot ownership. **What is certain:** entry fills, prices, totals. **What is ambiguous:** which closing fill belongs to which lot (89 % of body shorts in the 30 complete cycles, §3) and how a body buy with no recorded short should be read (D1, `LOT_IDENTITY_METHODOLOGY.md` §6). Code: `lots.py`, `build_lots.py`, `reconcile.py`, `link_wings.py`; data: `outputs/lots.csv.gz` (primary), `lots_alt_unrecorded_short.csv.gz`, `lot_links.csv.gz`, `cycles.csv`. Pre-review outputs are preserved in `outputs/v1_pre_review/` (`DO_NOT_CITE.txt`).

## 1. What was built
`outputs/lots.csv.gz` — **33,172 unit lots** opened (one row per lot; FIFO fields + per-convention close/P&L columns), primary interpretation `excess_body_buy='long'`:

| Role | Side | Lots | Meaning |
|---|---|---:|---|
| body | SHORT | 15,805 (incl. 161 unrecorded carry-in) | sold by the body module (`num` tag) |
| body | LONG | 991 | body buys with no recorded short (flagged; reading unresolved, D1) |
| wing | LONG | 14,184 | `h_` wing buys |
| wing | SHORT | 20 | `h_` sells that opened shorts |
| lump | LONG | 1,503 | `v_` overnight hedges |
| stop | SHORT / LONG | 515 / 154 | `s_`/`m_` orders that opened positions after netting against existing stop lots (stop-module overshoot, RSK-12) |

**Accounting identities (CONFIRMED OBSERVATION, executed):** sell lots 31,566 = short lots opened 16,179 + long lots closed by sells 15,387; buy lots 32,086 = long lots opened 16,832 + short lots closed 15,254 (incl. 161 unrecorded). These split differently under the alternative D1 reading (34,110 lots); the **totals** are interpretation-free. All cycle totals equal ledger cash plus settlement to ₹0.000.

## 2. Dispositions of short lots (35 cycles, FIFO; ownership-dependent timing)
| Disposition | Lots | Comment |
|---|---:|---|
| Body buy-back | 13,363 | the body module bought the contract (13,202 recorded + 161 unrecorded-entry) |
| Held to settlement | 1,086 | of which 146 are an artefact (cycles with no D0 log); most are far-OTM worthless (earlier phase) |
| Stop-module order | 1,883 | closed by an `s_`/`m_` order |
| Hedge-module order | 8 | wing sells that closed a short |

(Pre-review counts — 13,369 / 2,796 / 1,380 — came from an engine that routed stop buys differently and left some stop lots un-netted; superseded.) For the carried lots the stop-module share is 14–17 % and held-to-settlement 8–9 % by convention (`CARRIED_LOT_BUYBACK_ANALYSIS.md`).

## 3. Ownership ambiguity (the central limitation)
Under four conventions the closing fill of 89 % of body shorts (30 complete cycles) changes (`LOT_IDENTITY_METHODOLOGY.md`). *Lifecycle statistics that depend on which lot closed* — holding time, per-lot P&L, carried-vs-fresh split, "bought back after k minutes" — are therefore **ranges**, not point values; *statistics about contracts or orders* (buy-back timing, quantities, prices) are exact.

## 4. Field-by-field (requested schema)
| Field | Available | Note |
|---|---|---|
| lot_id, cycle_id, index, instrument, option_type (`cp`), strike, expiry | yes | |
| source_trade_ids | `entry_trade_id`, `close_trade_id` | plus `entry_row`/`close_row` (unique fill keys) |
| entry_timestamp / price / quantity | `entry_day`+`entry_sec` (s), `entry_price` (per-fill tick), `entry_quantity_units` | `entry_order_lots` = size of the originating **order** (all its fills); `entry_fill_lots` = size of the originating fill |
| remaining_quantity | 0 for every lot at the end of the cycle (all lots closed or settled); intermediate remaining quantity is available from the event order | |
| close timestamp / price / reason | `close_day`+`close_sec`, `close_price`, `close_reason` (BODY_BUYBACK, BODY_SELL_CLOSING_LONG, STOP_MODULE, HEDGE_ORDER, LUMP_ORDER, CROSS_ROLE_EOD_WING_CLOSE_BY_BODY, MANUAL, SETTLEMENT) | settlement price = Yahoo official close (proxy) |
| replacement_lot_id | **not assigned**: replacements are order-level, classified in `lot_links.csv.gz` (`replacement_candidate_order_tag`, `replacement_class`) | no lot-level claim |
| wing_lot_id | `lot_links.csv.gz` (`POSSIBLE_TIMING_ONLY`) | 78 % linked |
| hedge_relationship | wing close reason in `lot_links`; lump hedges are role `lump` lots | not tied to body lots (no evidence) |
| realized_pnl | `realized_pnl` (FIFO) and `pnl_<convention>` | exact per fill |
| unrealized_pnl | at the cycle end 0 (all closed/settled); the D0-open mark of carried lots is in `carried_lots.csv.gz` (`d1_last_price`) | MFE/MAE there |
| holding_duration | `holding_seconds` (FIFO; **market seconds**, overnight excluded) | convention-dependent |
| allocation_method | `FIFO` primary; others in columns | never "original" |
| confidence / unresolved_flags | `ALLOCATION_(UN)AMBIGUOUS`, `ENTRY_UNRECORDED`; flags `UNRECORDED_CARRY_IN_SHORT`, `BODY_BUY_WITHOUT_RECORDED_SHORT_OPENED_AS_LONG`, `UNRECORDED_PRIOR_SHORT_INTERPRETATION` (alt), `CROSS_ROLE_EOD_WING_CLOSE`, `OPENED_BY_CLOSING_SIDE_ORDER` | |

## 5. Quality
Perturbation-free (the engine uses only ledger fields); adversarial fixtures (12 tests) and review-defect regressions (10 tests, `test_review_defects.py`) cover multiple entries, partial buy-backs, same-second fills, re-entry, hedge routing after a stop, missing carry-in, settlement ITM/OTM, duplicate trade ids and unit conservation; D1 both readings, stop netting, EOD wing close, order-vs-fill size, start-book immutability, `passive_at_stop` bounds, 09:15 perturbation of the panel, one-to-one replacement pairing, market-second holding, settlement proxy.
Figures (actual solid, inferred dashed/labelled): `figures/01…13_*.png`.
