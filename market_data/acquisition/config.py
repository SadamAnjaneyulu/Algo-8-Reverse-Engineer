"""Constants. Each carries its evidence status: VERIFIED (observed in data already downloaded), DOCUMENTED (public broker documentation, not tested here), INFERRED, UNRESOLVED."""
from datetime import date, time

SESSION_URL = 'https://api.icicidirect.com/breezeapi/api/v1/customerdetails'      # VERIFIED: answers HTTP 415 to an unauthenticated GET from this environment (2026-11-17)
HISTORY_URL = 'https://breezeapi.icicidirect.com/api/v2/historicalcharts'         # VERIFIED: answers HTTP 401 unauthenticated; 3,243 contract-days + 170 index-days were downloaded through it
MAX_CANDLES_PER_REQUEST = 1000          # DOCUMENTED by the SDK example (secondary source); the existing downloader stays under it. The planner never exceeds it.
MIN_REQUEST_INTERVAL_S = 1.25           # VERIFIED in use by the existing downloader (48 requests/minute)
DOCUMENTED_RATE_LIMIT = dict(per_minute=100, per_day=5000)   # DOCUMENTED (ICICI Direct FAQ). Not measured. Our default daily cap is lower, see DEFAULT_DAILY_CAP.
DEFAULT_DAILY_CAP = 4500

UNDERLYING = {'NIFTY': dict(opt_exchange='NFO', stock_code='NIFTY', step=50, index_exchange='NSE', index_stock_code='NIFTY')}   # VERIFIED for 2026-06..10 (index + options)
CAS_START = date(2026, 8, 3)            # VERIFIED in data: derivatives bars run to 15:39 from this date (385 minutes), to 15:29 before (375)
SESSION_OPEN = time(9, 15)

# Target window: three years ending on the last date for which the session rules are verified (CAS snapshot ends 2026-10-22).
WINDOW_START, WINDOW_END = date(2023, 10, 23), date(2026, 10, 22)
# Chronological split (calendar dates, never shuffled). INFERRED from the request: first 24 months in-sample, last 12 months out-of-sample.
IS_START, IS_END = date(2023, 10, 23), date(2025, 10, 22)
OOS_START, OOS_END = date(2025, 10, 23), date(2026, 10, 22)
# Part of the out-of-sample year was already inspected while reverse-engineering Algo 8 (PRs #1-#5 used 2026-06-22..2026-10-22): see the report.
EXPOSED_START, EXPOSED_END = date(2026, 6, 22), date(2026, 10, 22)

# Weekly NIFTY expiry weekday by period (Mon=0). INFERRED from memory of exchange circulars for the pre-2026 part and VERIFIED for 2026 (17 Tuesdays + 1 Monday holiday shift in the data).
# It is only a PROBE ORDER: a week's expiry is accepted only when an ATM option request returns candles for it.
WEEKLY_EXPIRY_WEEKDAY = [(date(2000, 1, 1), date(2025, 8, 31), 3), (date(2025, 9, 1), date(2099, 1, 1), 1)]

BAND_CORE_STEPS = 20       # tier 1: ATM +-20 strikes (+-1,000 points)
BAND_WING_STEPS = 45       # tier 2: out to +-45 strikes (+-2,250 points); VERIFIED sufficient for Algo 8: 99 % of its NIFTY contracts lie within +-40.6 steps of the open
