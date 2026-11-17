"""Plans tasks. A task = one request = one contract (or the index) over one or two consecutive sessions (<= 1,000 candles). Contract-days already held (DONE / EMPTY / NO_BARS, including imported legacy files) are never planned again."""
import csv, json, os
from datetime import date, timedelta
from . import config as C, normalize as N
from .calendar_rules import mondays, nominal_weekly_expiry, expiry_probe_order, previous_trading_day

HELD = ('DONE', 'EMPTY', 'NO_BARS')


def _task(kind, und, days, tier, priority, expiry=None, strike=None, right=None, meta=None):
    p = N.request_params(kind, und, days[0], days[-1], expiry, strike, right)
    meta = dict(meta or {}, days=[d.isoformat() for d in days])
    return dict(task_id=N.task_id(p), kind=kind, und=und, expiry=expiry.isoformat() if expiry else None, strike=strike, right=right, from_day=days[0].isoformat(), to_day=days[-1].isoformat(),
                tier=tier, priority=priority, params=dict(request=p, meta=meta))


def weekdays(start, end):
    d = start
    while d <= end:
        if d.weekday() < 5: yield d
        d += timedelta(days=1)


def plan_index(store, und, start=C.WINDOW_START, end=C.WINDOW_END):
    """Every weekday of the window, one request each (375-385 candles). Weekdays that come back empty are the exchange holidays (recorded, to be reviewed, never assumed)."""
    n = 0
    for d in weekdays(start - timedelta(days=7), end):                       # one week of lead-in gives the previous close needed by the first expiry's band
        k = dict(kind='index', und=und, expiry=None, strike=None, right=None, trade_day=d.isoformat())
        if store.day_status(k) in HELD: continue
        store.add_task(_task('index', und, [d], 0, int(d.strftime('%Y%m%d')), meta={})); n += 1
    store.commit(); return n


def trading_days(store, und):
    return {date.fromisoformat(r[0]) for r in store.db.execute("SELECT trade_day FROM contract_days WHERE kind='index' AND und=? AND status='DONE'", (und,))}


def index_ohlc(store, und, day):
    p = store.path('normalized', 'index', und, '-', f'{day}.csv')
    if not os.path.exists(p): return None
    rows = list(csv.DictReader(open(p)))
    return dict(open=float(rows[0]['open']), close=float(rows[-1]['close']), low=min(float(r['low']) for r in rows), high=max(float(r['high']) for r in rows)) if rows else None


def atm(price, step): return int(round(price / step)) * step


def plan_expiry_probes(store, und, start=C.WINDOW_START, end=C.WINDOW_END):
    """One ATM-call request on the nominal weekly expiry date; if it returns nothing the next earlier trading day is probed in a later round. An expiry is accepted only when candles come back."""
    td = trading_days(store, und); added = 0; confirmed = confirmed_expiries(store, und)
    for m in mondays(start, end):
        nominal = nominal_weekly_expiry(m)
        if not start <= nominal <= end + timedelta(days=7) or any(m <= e <= m + timedelta(days=6) for e in confirmed): continue
        for cand in expiry_probe_order(nominal, td):
            if store.db.execute("SELECT 1 FROM tasks WHERE kind='option' AND tier=0 AND expiry=? AND from_day=?", (cand.isoformat(), cand.isoformat())).fetchone(): continue   # already probed (any outcome): try the next candidate
            ohlc = index_ohlc(store, und, cand)
            if ohlc is None: continue
            store.add_task(_task('option', und, [cand], 0, int(cand.strftime('%Y%m%d')), cand, atm(ohlc['open'], C.UNDERLYING[und]['step']), 'CE', dict(purpose='expiry_probe'))); added += 1
            break
    store.commit(); return added


def confirmed_expiries(store, und):
    return sorted({date.fromisoformat(r[0]) for r in store.db.execute("SELECT expiry FROM contract_days WHERE kind='option' AND und=? AND status='DONE' AND trade_day=expiry", (und,))})


def strikes_for(center, step, core=C.BAND_CORE_STEPS, wing=C.BAND_WING_STEPS):
    return [(center + k * step, 1 if abs(k) <= core else 2, abs(k)) for k in range(-wing, wing + 1)]


def plan_options(store, und, max_tier=2, start=C.WINDOW_START, end=C.WINDOW_END):
    """For each confirmed weekly expiry E: sessions D-1 and E. Band centre = ATM of the close of D-2 (known before D-1 opens, so contract existence carries no hindsight about the two sessions).
    The same strike set is requested for both sessions and both rights."""
    td = sorted(trading_days(store, und)); step = C.UNDERLYING[und]['step']; added = 0
    for e in confirmed_expiries(store, und):
        if not start <= e <= end: continue
        d1 = previous_trading_day(e, td); d2 = previous_trading_day(d1, td, 1) if d1 else None
        if not d1 or not d2: continue
        ref = index_ohlc(store, und, d2)
        if ref is None: continue
        center = atm(ref['close'], step)
        for strike, tier, dist in strikes_for(center, step):
            if tier > max_tier: continue
            for right in ('CE', 'PE'):
                pend = [d for d in (d1, e) if store.day_status(dict(kind='option', und=und, expiry=e.isoformat(), strike=strike, right=right, trade_day=d.isoformat())) not in HELD]
                if not pend: continue
                span = pend if len(pend) == 1 else [d1, e]; N.check_span_size(len(span))
                store.add_task(_task('option', und, span, tier, int(e.strftime('%Y%m%d')) * 100 + dist, e, strike, right, dict(band_center=center, ref_close_day=d2.isoformat(), ref_close=ref['close'], dist_steps=dist))); added += 1
    store.commit(); return added


def plan_range_cover(store, und, margin_steps=5):
    """Reactive extension: strikes the sessions' actual index range reached beyond the band (+margin). Hindsight-based coverage only; the backtest must not read the band edges as information."""
    td = sorted(trading_days(store, und)); step = C.UNDERLYING[und]['step']; added = 0
    for e in confirmed_expiries(store, und):
        d1 = previous_trading_day(e, td)
        if not d1: continue
        hi = max(x['high'] for x in (index_ohlc(store, und, d1), index_ohlc(store, und, e)) if x); lo = min(x['low'] for x in (index_ohlc(store, und, d1), index_ohlc(store, und, e)) if x)
        for strike in range(atm(lo, step) - margin_steps * step, atm(hi, step) + margin_steps * step + 1, step):
            for right in ('CE', 'PE'):
                pend = [d for d in (d1, e) if store.day_status(dict(kind='option', und=und, expiry=e.isoformat(), strike=strike, right=right, trade_day=d.isoformat())) not in HELD]
                if pend and not store.db.execute('SELECT 1 FROM tasks WHERE kind=? AND expiry=? AND strike=? AND right=? AND from_day=? AND to_day=?', ('option', e.isoformat(), strike, right, (pend[0]).isoformat(), pend[-1].isoformat())).fetchone():
                    store.add_task(_task('option', und, pend, 3, int(e.strftime('%Y%m%d')) * 100, e, strike, right, dict(purpose='range_cover'))); added += 1
    store.commit(); return added


def plan_futures(store, und):
    """Near and next monthly NIFTY futures for sessions D-1 and E of every confirmed weekly expiry. Monthly expiry = the last confirmed weekly expiry of the month (INFERRED). Request form UNVERIFIED."""
    exps = confirmed_expiries(store, und); td = sorted(trading_days(store, und)); months = {}
    for e in exps: months[(e.year, e.month)] = max(months.get((e.year, e.month), e), e)
    monthly = sorted(months.values()); added = 0
    for e in exps:
        d1 = previous_trading_day(e, td)
        if not d1: continue
        for fe in [m for m in monthly if m >= e][:2]:
            pend = [d for d in (d1, e) if store.day_status(dict(kind='future', und=und, expiry=fe.isoformat(), strike=None, right=None, trade_day=d.isoformat())) not in HELD]
            if pend: store.add_task(_task('future', und, pend, 1, int(e.strftime('%Y%m%d')), fe)); added += 1
    store.commit(); return added


def estimate(start=C.WINDOW_START, end=C.WINDOW_END, core=C.BAND_CORE_STEPS, wing=C.BAND_WING_STEPS, held_contract_days=0):
    """Credential-free projection on the NOMINAL calendar (no holidays known): an upper bound for index requests, expiry probes, and option / futures requests."""
    wd = sum(1 for _ in weekdays(start, end)); exps = [nominal_weekly_expiry(m) for m in mondays(start, end) if start <= nominal_weekly_expiry(m) <= end]
    t1 = (2 * core + 1) * 2; t2 = (2 * wing + 1) * 2 - t1
    return dict(window=[str(start), str(end)], weekdays=wd, nominal_weekly_expiries=len(exps), index_requests=wd + 5, expiry_probe_requests=int(len(exps) * 1.15), option_tier1_requests=len(exps) * t1, option_tier2_requests=len(exps) * t2,
                futures_requests=len(exps) * 2, per_expiry_contracts=dict(tier1=t1, tier2=t2), note='one request per contract covers both sessions D-1 and D0 (<= 770 candles); existing legacy contract-days reduce this only marginally')
