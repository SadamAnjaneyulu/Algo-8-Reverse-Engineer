# Shared schemas (v1)

Language-neutral tab-separated files. Header line required; lines starting with `#` are comments; no quoting; fields never contain a tab or newline. Integers are base-10 `int64`.

## Common types
| Type | Representation | Why |
|---|---|---|
| quantity | int64 **units** | export quantities are units; lot size reporting only |
| price | int64 **paise** = `round(price_rupees × 100)` | every export price is on the 0.05 grid, so exact |
| time | int64 UTC epoch seconds (export resolution is whole seconds); date = IST calendar date (`+05:30`) | no sub-second data exist |
| side | `+1` buy / `-1` sell | |
| execution_mode | `HISTORICAL_OBSERVED_REPLAY`, `RESEARCH_POLICY_SIMULATION`, `SYNTHETIC_TEST` | contamination guard |

## `instruments.tsv` — Instrument
`instrument_id, underlying, exchange_segment, instrument_type, option_type, strike, expiry, lot_size, tick_size_paise, lot_size_source`
`instrument_id = UNDERLYING|YYYY-MM-DD|CE|strike` (TP-01 identity). `lot_size` 65 NIFTY / 20 SENSEX, source `TP01_config_units_verified_multiples` (every exported quantity is a multiple; **not** an exchange-circular lookup, so it may change over time: never hardcode in policies). `tick_size_paise = 5`.

## `events.tsv` — FillEvent (+ parent-order attributes)
| column | meaning |
|---|---|
| schema_version | `pe.fill.v1` |
| execution_mode | one of the three modes; must equal the run mode |
| fill_id | unique id of the fill (historical: `F` + zero-padded raw row) |
| source_row_id | raw-file row (0-based) or generator sequence; final tie-breaker |
| parent_order_id | broker order tag (raw col 163) |
| module_tag | prefix of the tag: `num` body, `h_`, `s_`, `v_`, `m_` — **attribution only, not a trigger** |
| instrument_id | see above |
| timestamp_s | execution second |
| side, quantity, price_paise | per-fill values (not the running order average) |
| requested_quantity | order quantity (raw col 19), for parent aggregation checks |
| order_status | `Filled` / `PartiallyFilled` |
| is_duplicate_fill | `1` → ignored and counted (TP-01 rule) |
| evidence_source | provenance string of the generator |

`signed_quantity = side × quantity` is derived.

## `state_dump.tsv` — canonical engine output (identical in Python and C++)
```
#PE_STATE_DUMP v1
META  key  value        (method, tie_order, mode, events_read, events_applied, duplicates_ignored, first_ts, last_ts, last_date)
TOTAL name value        (opened_units, closed_units, remaining_units, reversal_fills, reversal_units_reopened, realized_pnl_paise, cash_flow_paise, remaining_book_value_paise, remaining_expired_unclosed_units, remaining_open_at_end_units)
INSTR instrument_id inventory opened closed realized_paise book_value_paise status
EPISODE episode_id direction opened closed remaining realized_paise ended_by n_open_fills n_close_fills
SNAP  seq timestamp_s date open_instruments short_CE short_PE long_CE long_PE gross_units net_units realized_paise cash_flow_paise unrealized
PARENT parent_order_id fills filled_units requested_units status
WARN  code count
```
`realized_paise` is an integer for FIFO/LIFO and a decimal with 6 places for AVG. `unrealized` is `NA` unless marks are supplied (`MISSING_MARKS`).

## `roles.tsv` — per-fill role (parity and TP-01 reconciliation)
`fill_id, instrument_id, close_qty, open_qty, inventory_after, is_reversal, episode_closed, episode_opened`

## Later schemas (M2–M4, defined here so the data model is fixed early)
`ParentOrder, Position, Basket, PortfolioSnapshot, OrderIntent, DecisionProposal` follow the field lists in the project brief; `ownership_confidence`, `membership_provenance` and `evidence_class` are mandatory on `Position`/`Basket`; `DecisionProposal.confidence` is `null` unless statistically defined.
