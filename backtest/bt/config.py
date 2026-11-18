"""Frozen specification of the backtest (everything that is a decision rather than a result). Evidence labels: OBSERVED (Algo 8 rulebook v0.6, not decoded), STATED (Info.txt), ASSUMED (mine), INFERRED (from data)."""
from datetime import date
DATA_COMMIT = 'eb4097308d47ccc75078ab73ba76d33bb1c7030b'; DATA_PREFIX = 'data/market_context_3yr_broad'
IS_START, IS_END = date(2023, 11, 8), date(2025, 11, 17)          # IS: first available session to the user's boundary
OOS_START, OOS_END = date(2025, 11, 18), date(2026, 11, 17)
EXPOSED_START, EXPOSED_END = date(2026, 6, 22), date(2026, 10, 22)   # sessions inspected while reverse-engineering Algo 8
CAPITAL_RS = 20_000_000                                               # STATED: Info.txt, Rs 2 crore (not a verified balance)
ENTRY_DECISION_HHMM = '09:16'; ENTRY_WINDOW_MIN = 5                   # OBSERVED: first paired sale in 09:16 on 31/32 dates; ASSUMED: wait up to 5 min for a traded bar
STEP = {'NIFTY': 50, 'SENSEX': 100}
def wing_points(und, d1):                                               # OBSERVED: NIFTY +-2000; SENSEX +-4000 earlier, +-2000 from 2026-09-16 (extrapolated to 2023-25: ASSUMED)
    return 2000 if und == 'NIFTY' else (2000 if d1 >= date(2026, 9, 16) else 4000)
LOTS_PER_LEG = 3                                                        # OBSERVED in 2026: 195 = 3 x 65 (NIFTY), 60 = 3 x 20 (SENSEX); ASSUMED to hold in earlier years
CAS_START = date(2026, 8, 3)
