# M2 data dictionary (M2-B files; extended in later M2 steps)

All files tab-separated, header line, `NA` for missing, integers exact (prices in paise, quantities in units). Identical in Python and C++ (byte-parity tested; AVG decimals have 6 places).

## Observed layer (convention-independent; identical under FIFO, LIFO, AVG)
**`observed_allocations.tsv`** — `row_type` (`OA` opening allocation / `CP` closing portion), `id` (`OA:<fill_id>` / `CP:<fill_id>`), `fill_id`, `parent_order_id`, `instrument_id`, `episode_id`, `timestamp_s`, `side`, `quantity` (the opening or closing PORTION of the fill), `price_paise` (per-fill price), `module_tag` (attribution only), `source_row_id`, `execution_mode`. A reversal fill yields one CP (old episode) and one OA (new episode).
**`lifecycle.tsv`** — `event_id` (`LE:<episode_id>:<seq>`), `episode_id`, `seq`, `event_type` (`CREATED`, `ADDED`, `PARTIALLY_REDUCED`, `CLOSED`, `REVERSED`), `fill_id`, `parent_order_id`, `timestamp_s`, `quantity` (portion), `inventory_after` (signed units of that episode), `started_by_reversal`.
**`episodes.tsv`** — `episode_id` (TP-01 identity `<instrument_id>#<n>`), `instrument_id`, `direction`, `started_by_reversal`, `opened`, `closed`, `remaining`, `ended_by` (`flat`/`reversal`/`open`), `terminal_status` (`CLOSED`, `REVERSED`, `EXPIRED_UNCLOSED`, `OPEN_AT_END_OF_DATA`; `INCOMPLETE_SOURCE_HISTORY` is reserved and never produced without external evidence), `first_ts`, `last_ts`, `n_open_fills`, `n_close_fills`.

## Analytical layer (per convention; NOT recorded facts)
**`ca_<CONV>.tsv`** (ClosingAllocation) — `ca_id` (`CA:<CONV>:<fill_id>:<n>`), `convention`, `cp_id`, `source_id` (`OA:<fill_id>` for FIFO/LIFO; `POOL:<episode_id>` for AVG), `allocated_qty`, `entry_price` (paise; AVG = pool average), `exit_price_paise`, `realized_pnl` (paise·units, gross), `source_remaining_qty` (lot or pool quantity left after the allocation), `ownership` (`IDENTIFIED_BY_CONVENTION` / `NOT_IDENTIFIABLE`).
**`slices_<CONV>.tsv`** (PositionSlice at end of replay) — `slice_id`, `convention`, `kind` (`LOT` per opening allocation with remaining quantity, or `POOL` per open episode under AVG), `source_id`, `episode_id`, `remaining_qty`, `price_paise`, `contributing_oa_ids` (AVG: the episode's opening allocations, listed as provenance only; `-` for LOT).

## Parent metadata
**`parents.tsv`** — see `SCHEMAS.md` (v1.1 refinement). Real export: 39,874 rows; only `algo_id` is missing (1 empty raw cell); no conflicts.
