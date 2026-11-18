from datetime import date, datetime, timedelta, time
from zoneinfo import ZoneInfo
from . import config as C
IST = ZoneInfo('Asia/Kolkata')


def expected_option_minutes(day):
    """375 bars (09:15..15:29) before the closing auction session, 385 (..15:39) from 2026-08-03. VERIFIED in the downloaded data."""
    return 385 if day >= C.CAS_START else 375


def expected_minute_stamps(day):
    start = datetime.combine(day, C.SESSION_OPEN, IST)
    return [(start + timedelta(minutes=i)).isoformat() for i in range(expected_option_minutes(day))]


def nominal_weekly_expiry(week_monday):
    for lo, hi, wd in C.WEEKLY_EXPIRY_WEEKDAY:
        if lo <= week_monday <= hi: return week_monday + timedelta(days=wd)
    raise ValueError(week_monday)


def mondays(start, end):
    d = start - timedelta(days=start.weekday())
    while d <= end:
        yield d; d += timedelta(days=7)


def expiry_probe_order(nominal, trading_days=None):
    """Dates to probe for the true expiry of a week: the nominal date, then earlier dates (an exchange holiday moves expiry to the previous trading day)."""
    out = []; d = nominal
    for _ in range(5):
        if d.weekday() < 5 and (trading_days is None or d in trading_days): out.append(d)
        d -= timedelta(days=1)
    return out


def previous_trading_day(day, trading_days, n=1):
    days = sorted(d for d in trading_days if d < day)
    return days[-n] if len(days) >= n else None


def split_of(day):
    if C.IS_START <= day <= C.IS_END: return 'IN_SAMPLE'
    if C.OOS_START <= day <= C.OOS_END: return 'OUT_OF_SAMPLE'
    return 'OUTSIDE_WINDOW'
