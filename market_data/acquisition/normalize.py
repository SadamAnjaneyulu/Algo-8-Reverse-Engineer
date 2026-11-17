"""Request construction, response validation and per-day normalisation. Nothing is filled, interpolated or defaulted: a missing bar stays missing, missing open interest stays empty."""
import csv, io, math
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo
from . import config as C
from .store import canonical, sha256_bytes
from .client import ResponseError
IST = ZoneInfo('Asia/Kolkata')
COLS = {'index': ['timestamp_ist', 'underlying', 'open', 'high', 'low', 'close', 'provider_volume', 'source_id'],
        'option': ['timestamp_ist', 'underlying', 'expiry_date', 'strike', 'option_type', 'open', 'high', 'low', 'close', 'volume', 'open_interest', 'source_id'],
        'future': ['timestamp_ist', 'underlying', 'expiry_date', 'open', 'high', 'low', 'close', 'volume', 'open_interest', 'source_id']}
BAR_FIELDS = {'datetime', 'stock_code', 'exchange_code', 'product_type', 'expiry_date', 'right', 'strike_price', 'open', 'high', 'low', 'close', 'volume', 'open_interest', 'count'}


def request_params(kind, und, from_day, to_day, expiry=None, strike=None, right=None):
    u = C.UNDERLYING[und]; base = dict(interval='1minute', from_date=f'{from_day}T03:30:00.000Z', to_date=f'{to_day}T15:45:00.000Z')
    if kind == 'index': return dict(base, stock_code=u['index_stock_code'], exch_code=u['index_exchange'], product_type='cash')
    if kind == 'option': return dict(base, stock_code=u['stock_code'], exch_code=u['opt_exchange'], product_type='options', expiry_date=f'{expiry}T07:00:00.000Z', right='call' if right == 'CE' else 'put', strike_price=str(strike))
    if kind == 'future': return dict(base, stock_code=u['stock_code'], exch_code=u['opt_exchange'], product_type='futures', expiry_date=f'{expiry}T07:00:00.000Z')       # UNVERIFIED request form
    raise ValueError(kind)


def task_id(params): return sha256_bytes(canonical(params))[:16]


def sessions_in_span(from_day, to_day, trading_days=None):
    d, out = from_day, []
    while d <= to_day:
        if d.weekday() < 5 and (trading_days is None or d in trading_days): out.append(d)
        d += timedelta(days=1)
    return out


def check_span_size(n_sessions):
    if n_sessions * 385 > C.MAX_CANDLES_PER_REQUEST: raise ValueError('request span would exceed the documented candle cap')


def _parse_expiry(v):
    s = str(v)
    for fmt, n in (('%Y-%m-%d', 10), ('%d-%b-%Y', 11), ('%d-%b-%y', 9)):
        try: return datetime.strptime(s[:n], fmt).date()
        except ValueError: pass
    raise ResponseError('unrecognised expiry format')


def parse_rows(kind, response, und, from_day, to_day, expiry=None, strike=None, right=None):
    """-> {date: [row dicts]} for days inside [from_day, to_day]. Raises ResponseError on any identity / validity violation (the raw response stays on disk)."""
    if not isinstance(response, dict) or response.get('Status') != 200 or not isinstance(response.get('Success'), list): raise ResponseError('unexpected response schema')
    u = C.UNDERLYING[und]; days = {}; seen = set()
    for r in response['Success']:
        if not isinstance(r, dict) or set(r) - BAR_FIELDS: raise ResponseError('unexpected bar fields')
        if kind == 'index': ok = str(r.get('stock_code', '')).upper() == u['index_stock_code'] and str(r.get('exchange_code', '')).upper() == u['index_exchange']
        else:
            ok = str(r.get('stock_code', '')).upper() == u['stock_code'] and str(r.get('exchange_code', '')).upper() == u['opt_exchange'] and str(r.get('product_type', '')).lower() == ('options' if kind == 'option' else 'futures')
            ok = ok and _parse_expiry(r.get('expiry_date', '')) == expiry
            if kind == 'option': ok = ok and str(r.get('right', '')).lower() == ('call' if right == 'CE' else 'put') and float(r.get('strike_price', 'nan')) == strike
        if not ok: raise ResponseError('returned instrument differs from the requested one')
        try:
            t = datetime.fromisoformat(str(r['datetime']).replace('Z', '+00:00'))
            t = t.replace(tzinfo=IST) if t.tzinfo is None else t.astimezone(IST)
            px = {k: float(r[k]) for k in ('open', 'high', 'low', 'close')}; vol = r.get('volume'); oi = r.get('open_interest')
            vol = float(vol) if vol not in (None, '') else None; oi = float(oi) if oi not in (None, '') else None
        except (KeyError, ValueError, TypeError): raise ResponseError('cannot parse bar') from None
        vals = list(px.values()) + [v for v in (vol, oi) if v is not None]
        if not all(math.isfinite(v) and v >= 0 for v in vals) or px['high'] < max(px.values()) or px['low'] > min(px.values()) or (kind == 'index' and min(px.values()) <= 0): raise ResponseError('invalid price / volume values')
        if t.second or t.microsecond: raise ResponseError('bar is off the one-minute grid')
        if not from_day <= t.date() <= to_day or not time(9, 15) <= t.time() < time(15, 40): continue         # outside the requested sessions / derivatives session: not retained
        if t in seen: raise ResponseError('duplicate bar timestamp')
        seen.add(t)
        row = dict(timestamp_ist=t.isoformat(), underlying=und, open=px['open'], high=px['high'], low=px['low'], close=px['close'])
        if kind == 'index': row['provider_volume'] = '' if vol is None else int(vol)
        else:
            row['expiry_date'] = expiry.isoformat(); row['volume'] = '' if vol is None else int(vol); row['open_interest'] = '' if oi is None else int(oi)
            if kind == 'option': row['strike'] = strike; row['option_type'] = right
        days.setdefault(t.date(), []).append(row)
    for d in days: days[d].sort(key=lambda x: x['timestamp_ist'])
    return days


def csv_bytes(kind, rows, source_id):
    f = io.StringIO(newline=''); w = csv.DictWriter(f, fieldnames=COLS[kind], lineterminator='\n'); w.writeheader()
    for r in rows: w.writerow(dict(r, source_id=source_id))
    return f.getvalue().encode()
