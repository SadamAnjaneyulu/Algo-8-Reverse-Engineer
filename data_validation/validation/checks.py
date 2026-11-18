"""Pure, independently testable data-quality checks. Each returns plain counts / lists so that corrupted samples can prove the check fires."""
from datetime import date, time, timedelta
import numpy as np, pandas as pd

CAS_START = date(2026, 8, 3)


def last_expected_time(day): return time(15, 39) if day >= CAS_START else time(15, 29)


def ohlc_flags(x):
    o, h, l, c = x.open, x.high, x.low, x.close
    return dict(nan=int(x[['open', 'high', 'low', 'close']].isna().any(axis=1).sum()), nonpositive=int(((o <= 0) | (h <= 0) | (l <= 0) | (c <= 0)).sum()), high_lt_open_or_close=int((h < np.maximum(o, c)).sum()),
                low_gt_open_or_close=int((l > np.minimum(o, c)).sum()), high_lt_low=int((h < l).sum()), off_tick=int((((x[['open', 'high', 'low', 'close']] * 20).round(6) % 1) != 0).any(axis=1).sum()))


def volume_oi_flags(x):
    out = {}
    for c in ('volume', 'open_interest'):
        out[c + '_nan'] = int(x[c].isna().sum()); out[c + '_negative'] = int((x[c] < 0).sum()); out[c + '_non_integer'] = int((x[c].dropna() % 1 != 0).sum())
    return out


def duplicate_flags(x, keys=('datetime', 'strike', 'right')):
    return dict(duplicate_keys=int(x.duplicated(list(keys)).sum()), duplicate_full_rows=int(x.duplicated().sum()))


def timestamp_flags(x, day):
    """x.datetime strings. Timezone-aware strings (+05:30 / Z) are reported: the dataset convention is naive exchange-local (IST) time."""
    ts = pd.to_datetime(x.datetime, errors='coerce'); tm = ts.dt.time
    return dict(unparseable=int(ts.isna().sum()), has_timezone_suffix=int(x.datetime.astype(str).str.contains(r'(?:[+-]\d\d:?\d\d|Z)$').sum()), other_date=int((ts.dt.date != day).sum()), weekend=int((ts.dt.weekday >= 5).sum()),
                before_0915=int((tm < time(9, 15)).sum()), after_expected_last=int((tm > last_expected_time(day)).sum()), nonzero_seconds=int((ts.dt.second != 0).sum()))


def ordering_flags(x):
    bad = 0
    for _, d in x.groupby(['strike', 'right'], sort=False):
        t = pd.to_datetime(d.datetime).values.astype('int64')
        bad += int((np.diff(t) <= 0).sum()) if len(t) > 1 else 0
    return dict(out_of_order_or_repeated_within_contract=bad)


def expiry_flags(x, expiry):
    ed = pd.to_datetime(x.expiry_date, format='%d-%b-%Y', errors='coerce')
    return dict(expiry_unparseable=int(ed.isna().sum()), expiry_mismatch=int((ed.dt.date != expiry).sum()))


def strike_flags(x, step, planned):
    """planned: set of (strike, 'CE'|'PE') that should exist as a download plan; rows outside the plan or off the strike grid are reported."""
    have = set(zip(x.strike.astype(int), x.right))
    ce, pe = {s for s, r in have if r == 'CE'}, {s for s, r in have if r == 'PE'}
    return dict(off_grid_rows=int((x.strike % step != 0).sum()), rows_outside_plan=len(have - planned), planned_without_rows=len(planned - have), has_ce=len(ce) > 0, has_pe=len(pe) > 0, ce_strikes=len(ce), pe_strikes=len(pe))


def plan_step_flags(planned, step):
    s = sorted({k for k, _ in planned}); d = set(np.diff(s)) if len(s) > 1 else set()
    return dict(plan_strikes=len(s), plan_steps_ok=(d == {step}), plan_steps=sorted(int(v) for v in d), plan_symmetric=(len(s) > 0 and (s[0] + s[-1]) % (2 * step) == 0))


def d1_mapping(expiry, d1, trading_days):
    """True when d1 is exactly the trading day immediately before the expiry."""
    prev = [d for d in trading_days if d < expiry]
    return bool(prev) and max(prev) == d1


def atm_centre(close, step): return int(round(close / step)) * step


def underlying_alignment(option_minutes, spot_minutes):
    """option and spot minute sets for one session: option minutes with no spot bar are a problem for ATM / alignment work."""
    return dict(option_minutes_without_spot=len(set(option_minutes) - set(spot_minutes)))


def raw_vs_norm(raw_rows, norm, cols=('datetime', 'strike', 'right', 'open', 'high', 'low', 'close', 'volume', 'open_interest')):
    R = pd.DataFrame(raw_rows)[list(cols)].drop_duplicates(); m = R.merge(norm[list(cols)], on=['datetime', 'strike', 'right'], how='outer', suffixes=('_r', '_n'), indicator=True)
    b = m[m._merge == 'both']
    return dict(raw_only=int((m._merge == 'left_only').sum()), norm_only=int((m._merge == 'right_only').sum()), value_mismatch=int(sum(((b[c + '_r'] != b[c + '_n']) & ~(b[c + '_r'].isna() & b[c + '_n'].isna())).sum() for c in cols[3:])))


def manifest_flags(planned_sessions, files):
    planned, files = set(planned_sessions), set(files)
    return dict(planned_without_file=sorted(planned - files), file_not_planned=sorted(files - planned))


def candle_coverage(x, day, grid=None):
    grid = grid or (375 if day < CAS_START else 385); m = (pd.to_datetime(x.datetime).dt.hour * 60 + pd.to_datetime(x.datetime).dt.minute - 555)
    inside = np.unique(m[(m >= 0) & (m < grid)]); return dict(grid=grid, observed=len(inside), missing=grid - len(inside), coverage=len(inside) / grid)


def session_report(x, day, expiry, step, planned):
    out = {}
    for f in (ohlc_flags(x), volume_oi_flags(x), duplicate_flags(x), timestamp_flags(x, day), ordering_flags(x), expiry_flags(x, expiry), strike_flags(x, step, planned), plan_step_flags(planned, step)): out.update(f)
    return out


def problems(report):
    """Names of flags that indicate a defect (non-zero counts / False booleans)."""
    bad = [k for k, v in report.items() if k in ('nan', 'nonpositive', 'high_lt_open_or_close', 'low_gt_open_or_close', 'high_lt_low', 'duplicate_keys', 'duplicate_full_rows', 'unparseable', 'has_timezone_suffix', 'other_date', 'weekend', 'before_0915',
                                                       'after_expected_last', 'nonzero_seconds', 'out_of_order_or_repeated_within_contract', 'expiry_unparseable', 'expiry_mismatch', 'off_grid_rows', 'rows_outside_plan', 'volume_negative', 'open_interest_negative') and v]
    if not report.get('has_ce', True) or not report.get('has_pe', True): bad.append('missing_option_type')
    if report.get('plan_steps_ok') is False: bad.append('plan_step_interval')
    return bad
