# Data quality report - 3yr NIFTY/SENSEX expiry acquisition
*generated 2026-11-18 08:16*

Acquisition run: 648.0 min, 103,776 contracts in checkpoint. Planned: NIFTY 158 expiries, SENSEX 124.

## NIFTY
- expiries in discovered calendar: 159
- expiries with at least one session file on disk: 158
- expiries with ZERO files (not attempted - e.g. no D-2 available, or SENSEX pre-data-boundary): 1 (2023-11-02)
- expiries with only 1 of 2 sessions on disk: 0
- sessions found: 316, with a normalized CSV: 316 (100.0%) - the gap is sessions where every single contract legitimately had zero trades (raw file exists, normalized CSV is correctly empty)
- total option rows: 18,978,233
- duplicate (datetime,strike,right) rows: 0
- invalid OHLC rows: 0
- sessions with incomplete CE+PE coverage: 0
- strikes with data per session: min=20, median=85, max=91 (expected universe=91, far-OTM strikes legitimately have 0 rows)
- distinct minute-marks per session: min=80, median=376, max=385 (full session = 375-390 depending on exact open/close prints)
- spot rows: 123,027 (missing files: 0)
- futures rows: 119,361 (missing files: 0)

## SENSEX
- expiries in discovered calendar: 124
- expiries with at least one session file on disk: 124
- expiries with only 1 of 2 sessions on disk: 0
- sessions found: 248, with a normalized CSV: 248 (100.0%) - the gap is sessions where every single contract legitimately had zero trades (raw file exists, normalized CSV is correctly empty)
- total option rows: 12,928,723
- duplicate (datetime,strike,right) rows: 0
- invalid OHLC rows: 0
- sessions with incomplete CE+PE coverage: 0
- strikes with data per session: min=71, median=91, max=91 (expected universe=91, far-OTM strikes legitimately have 0 rows)
- distinct minute-marks per session: min=62, median=377, max=385 (full session = 375-390 depending on exact open/close prints)
- spot rows: 95,627 (missing files: 0)
- futures rows: 88,670 (missing files: 0)

## Known, documented gaps (not silent)
- SENSEX: zero data before 2024-05-27 - confirmed via direct probe against both futures and options (Breeze has no F&O history for SENSEX earlier than this date). 35 weeks (2023-W44 through 2024-W21) excluded from the SENSEX expiry calendar for this reason.
- NIFTY: earliest calendar week (2023-W44, expiry 2023-11-02) excluded - no D-2 trading day exists before it to compute the ATM strike reference without look-ahead.
- Both: today's (2026-11-17) in-progress week was excluded from calendar discovery since the daily cash candle for a still-open session is not yet final.

## Storage
- raw: 9.51 GB
- normalized: 2.73 GB
