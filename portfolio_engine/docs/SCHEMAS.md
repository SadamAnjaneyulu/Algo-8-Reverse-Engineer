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


---
# M2 additions (v1.1, DRAFT — additive only; M1 files and parity artifacts unchanged)

New optional files. `events.tsv`, `instruments.tsv`, `state_dump.tsv`, `roles.tsv` keep their v1 columns.

## `parents.tsv` — ParentOrder attributes (historical generator only)
`parent_order_id, module_tag, order_entry_minute_s, app_key, order_number, first_fill_ts, last_fill_ts, n_fills, filled_units, requested_units, parent_role`
`order_entry_minute_s` = epoch seconds of the order-entry minute (minute precision, **not** an execution time; `NA` if unavailable); `parent_role` ∈ `OPENING_ONLY | CLOSING_ONLY | MIXED` (derived from roles, convention-independent).

## `allocations.tsv` — L1 + L2 rows
`row_type` ∈ `OA | CP | CA`.
* `OA`: `oa_id, fill_id, parent_order_id, instrument_id, episode_id, timestamp_s, side, quantity, price_paise, module_tag, execution_mode, source_row_id, evidence_source`
* `CP`: `cp_id, fill_id, parent_order_id, instrument_id, episode_id, timestamp_s, side, quantity, price_paise, execution_mode, source_row_id`
* `CA` (per convention): `ca_id, convention, cp_id, oa_id | POOL:<episode_id>, allocated_qty, entry_price, exit_price, realized_pnl, remaining_oa_qty, ownership` (`IDENTIFIED_BY_CONVENTION` or `NOT_IDENTIFIABLE`), `allocation_uncertainty` (`NONE` / `CONVENTION_SENSITIVE`)

## `lifecycle.tsv` — PositionLifecycleEvent
`event_id, episode_id, seq, event_type, fill_id, parent_order_id, timestamp_s, quantity, inventory_after, terminal_status`

## `slices.tsv` — PositionSlice (per convention, as of end of replay and at requested times)
`slice_id, convention, kind(LOT|POOL), oa_id | episode_id, remaining_qty, avg_cost_paise (POOL), contributing_oa_ids (POOL, provenance only)`

## `baskets.tsv` and `basket_members.tsv` — Basket / BasketMembership
Basket: `basket_id, kind(CYCLE|OPENING_COHORT|CLOSING_BATCH), grouping_convention, parameter_hash, underlying, expiry, session, start_ts, end_ts, membership_provenance, evidence_class, claim_type`
Member: `basket_id, member_type(EPISODE|OA|CP), member_id, quantity, provenance, evidence_class`

## `wing_body.tsv` — WingBodyAssociation
`link_id, method(W1..W5), level(OPENING|CLOSING), wing_id, body_id, time_diff_s, units_ratio, right, strike_distance, wing_px_paise, body_px_paise, weight, alternatives, unmatched_wing_qty, evidence_class, provenance`

Compatibility rule: any later change to an existing v1/v1.1 column is a **breaking change and needs review**.
