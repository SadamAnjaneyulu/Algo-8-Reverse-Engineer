# Broad market-context dataset (NOT the exact-traded-contract pipeline)

**Read this before using anything in this folder.** This is a SEPARATE
dataset from `data/breeze/{raw,normalized,metadata}/{indices,options}/` and
was NOT produced by `research/fetch_breeze_options.py` or validated by the
smoke-check / fill-agreement process documented in `LOCAL_BREEZE_OPTIONS.md`.
It has NOT been cross-checked against `Trades_GKOHNP140.csv`.

## What this is

A blanket pull of every NIFTY and SENSEX weekly-options expiry, Nov 2023 -
Nov 2026: the expiry day itself (D0) plus the trading day immediately before
it (D-1), ATM +/- 45 strikes (both CE and PE), plus the corresponding spot
and near-month futures 1-minute bars. It was built to answer a DIFFERENT
question than this repo's existing work (whether a generic market-intraday-
momentum-style signal exists), not to reconstruct Algo 8's specific fills.

**It was NOT selected based on which contracts Algo 8 actually traded.** The
existing exact-traded-contract plan (1,445 NIFTY + 1,798 SENSEX contract-days,
`fetch_breeze_options.py --scope all`) is the right dataset for reconstructing
or validating specific fills. Use THAT for anything touching
`Trades_GKOHNP140.csv` directly. This folder is offered as broader market
context (e.g. "what did the wider option chain look like that week") that
may be useful alongside it, not a replacement.

## Schema differences from `data/breeze/`

| | `data/breeze/options/` (existing) | this folder |
|---|---|---|
| Scope | exact traded contracts + neighbors | every expiry, ATM+/-45, regardless of trades |
| Validated against fills | yes (smoke check, >=80% OHLC agreement) | no |
| Filenames | `<date>.<content-hash>.json/csv` | `exp<expiry>_<day>.json/csv` |
| Raw format | `{"request": {...}, "response": {...}}` | `{"rows": [...], "status": ..., "atm_ref": ...}` |
| CSV columns | `timestamp_ist, underlying, expiry_date, strike, option_type, ...` | `datetime, expiry_date, strike, right, ...` |
| Missing-minute policy | explicit missing-minute list per contract/day | no fabricated values, but no explicit gap list either |

## Known gaps (documented, not silent)

- **SENSEX has zero data before 2024-05-27** - confirmed by direct probe
  against both futures and options; Breeze has no F&O history for SENSEX
  earlier than this date. 35 weeks excluded for this reason.
- NIFTY's earliest calendar week (2023-11-02 expiry) excluded - no D-2
  trading day exists before it to compute an ATM strike reference without
  look-ahead.
- Two session files (`exp2024-04-18_2024-04-18.csv`,
  `exp2024-02-01_2024-01-31.csv`) originally contained ~25.3k duplicate rows
  from a hard process-kill during acquisition (lost checkpoint flush,
  contract refetched on resume). Deduplicated before this was moved here -
  see `manifests/checkpoint.csv` and `reports/data_quality_report.md`.

## Structure

```
raw/{nifty,sensex}/options/exp<expiry>_<day>.json          # immutable, exact API response
raw/{nifty,sensex}/underlying/{spot,futures}/<day>.json
normalized/{nifty,sensex}/options/exp<expiry>_<day>.csv    # cleaned long-format
normalized/{nifty,sensex}/underlying/{spot,futures}/<day>.csv
metadata/expiry_calendar/expiry_calendar_{nifty,sensex}.csv # empirically discovered, not assumed
manifests/checkpoint.csv, download_status.json
reports/data_quality_report.md, acquisition_summary.md
```

**Totals**: 18,978,233 NIFTY + 12,928,723 SENSEX option rows (31.9M total),
103,776 contracts fetched over 10.8 hours, 9.5GB raw + 2.7GB normalized.
Full detail in `reports/acquisition_summary.md` and `reports/data_quality_report.md`.

Source session: Quant Research Lab worktree `matlab-backtesting-products-00b312`,
scripts `research/breeze_discover_expiry_calendar.py`,
`research/breeze_3yr_acquisition.py`, `research/breeze_3yr_validate.py`
(not copied here - ask if you want them moved too).
