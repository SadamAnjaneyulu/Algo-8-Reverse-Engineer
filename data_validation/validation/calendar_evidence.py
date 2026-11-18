"""Stage 3: independent expiry calendar. Evidence classes used (never the dataset's own calendar as proof):
  RULE      - exchange rule on the expiry weekday (public sources, see EVIDENCE below); transition dates beyond what the sources state are UNCONFIRMED
  CALENDAR  - trading days from an independent vendor (Yahoo daily index series for ^NSEI / ^BSESN, committed under reference/)
  DATA      - behaviour inside the dataset (e.g. deep in-the-money options settling to intrinsic value on D0)"""
import csv, os
from datetime import date, timedelta
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVIDENCE = {
    'NIFTY': [(date(2000, 1, 1), date(2025, 8, 31), 3, 'RULE: Thursday weekly expiry (NSE) until contracts expiring on or before 2025-08-31', 'CONFIRMED_BY_SECONDARY_SOURCES'),
              (date(2025, 9, 1), date(2099, 1, 1), 1, 'RULE: Tuesday weekly expiry (NSE) from 2025-09-01 (first Tuesday expiry 2025-09-02)', 'CONFIRMED_BY_SECONDARY_SOURCES')],
    'SENSEX': [(date(2000, 1, 1), date(2025, 1, 5), 4, 'RULE: Friday weekly expiry (BSE) since May 2023; moved to Tuesday in January 2025 (secondary sources give the month only; the dataset itself shows a Friday expiry on 2025-01-03 and a Tuesday one on 2025-01-07)', 'FRIDAY_PERIOD_CONFIRMED_SWITCH_DATE_DATA_ONLY'),
               (date(2025, 1, 6), date(2025, 8, 31), 1, 'RULE: Tuesday weekly expiry (BSE) from January 2025 until August 2025', 'TUESDAY_PERIOD_CONFIRMED_START_DATE_DATA_ONLY'),
               (date(2025, 9, 1), date(2099, 1, 1), 3, 'RULE: Thursday weekly expiry (BSE) from 2025-09-01', 'CONFIRMED_BY_SECONDARY_SOURCES')]}
UNCONFIRMED_WINDOWS = {'SENSEX': [(date(2024, 12, 30), date(2025, 1, 6))]}        # weeks in which the Friday -> Tuesday switch happened; the sources give "January 2025" only
# Diwali Muhurat sessions: short special sessions on days that are exchange holidays for regular trading (or weekends). They are NOT regular sessions and are never treated as D-1 / D0 of an expiry.
# 2026-11-08: confirmed by several broker / exchange-circular reports (Sunday, 14:20-15:30). 2023-11-12, 2024-11-01, 2025-10-21: NOT confirmed by my web search; supported by the data (short Breeze sessions, Yahoo bar present on a regular holiday).
SPECIAL_SESSIONS = {date(2023, 11, 12): 'DATA_AND_MEMORY_ONLY', date(2024, 11, 1): 'DATA_AND_MEMORY_ONLY', date(2025, 10, 21): 'DATA_AND_MEMORY_ONLY', date(2026, 11, 8): 'CONFIRMED_BY_SECONDARY_SOURCES'}
YAHOO = {'NIFTY': 'yahoo_daily_NSEI.csv', 'SENSEX': 'yahoo_daily_BSESN.csv'}
LAST_COMPLETE_SESSION = date(2026, 11, 17)          # validation was run on 2026-11-18; Yahoo's 2026-11-18 row is an unfinished session


def trading_days(und):
    days = set()
    for r in csv.DictReader(open(os.path.join(HERE, 'reference', YAHOO[und]))):
        d = date.fromisoformat(r['date_ist'])
        if r['close'] not in ('', 'None', 'nan') and d <= LAST_COMPLETE_SESSION and d.weekday() < 5 and d not in SPECIAL_SESSIONS: days.add(d)
    return days


def yahoo_daily(und):
    out = {}
    for r in csv.DictReader(open(os.path.join(HERE, 'reference', YAHOO[und]))):
        if r['close'] not in ('', 'None', 'nan'): out[date.fromisoformat(r['date_ist'])] = {k: float(r[k]) for k in ('open', 'high', 'low', 'close')}
    return out


def rule_weekday(und, week_monday):
    for lo, hi, wd, why, conf in EVIDENCE[und]:
        if lo <= week_monday <= hi: return wd, why, conf
    raise ValueError


def prev_trading_day(d, tdays, n=1):
    c = 0
    while True:
        d -= timedelta(days=1)
        if d in tdays:
            c += 1
            if c == n: return d
        if d < date(2023, 1, 1): return None


def expected_expiries(und, start=date(2023, 11, 1), end=LAST_COMPLETE_SESSION):
    """One row per calendar week whose rule-based expiry falls in [start, end]: nominal date, holiday-shifted date (previous trading day when the nominal day is not a trading day), evidence class."""
    td = trading_days(und); rows = []; d = date(2023, 10, 30)
    while d <= end:
        wd, why, conf = rule_weekday(und, d); nominal = d + timedelta(days=wd)
        if start <= nominal <= end:                                   # a nominal expiry after the last complete session has not happened yet
            shifted = nominal; basis = why
            while shifted not in td and shifted > d - timedelta(days=7): shifted -= timedelta(days=1)
            if shifted != nominal: basis += f'; nominal {nominal} is not a trading day in the independent calendar -> previous trading day'
            unconf = any(lo <= d <= hi for lo, hi in UNCONFIRMED_WINDOWS.get(und, []))
            if start <= shifted <= end:
                rows.append(dict(week_monday=d.isoformat(), nominal=nominal.isoformat(), expected_expiry=shifted.isoformat(), holiday_shifted=shifted != nominal, evidence=basis, evidence_status='UNCONFIRMED_TRANSITION_WEEK' if unconf else conf,
                                 d0=shifted.isoformat(), d1=(prev_trading_day(shifted, td) or date.min).isoformat(), d2=(prev_trading_day(shifted, td, 2) or date.min).isoformat()))
        d += timedelta(days=7)
    return rows
