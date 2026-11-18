"""Executes pending tasks: request (if no raw file exists yet) -> immutable raw write -> validation + per-day normalisation -> manifest. Restartable at every step."""
import json, os
from datetime import date, datetime
from . import config as C, normalize as N
from .client import AuthError, RejectedError, RateLimitError, TransientError, ResponseError, FetchError
from .store import canonical, now_utc, sha256_bytes, write_once, Store
from .calendar_rules import IST


class StopRun(Exception): pass


def ist_today(): return datetime.now(IST).date().isoformat()


def raw_relpath(t):
    p = json.loads(t['params_json'])['request']
    ident = '-' if t['kind'] == 'index' else f"{t['expiry']}/{t['strike']}{t['right']}" if t['kind'] == 'option' else f"{t['expiry']}/FUT"
    return os.path.join('raw', t['kind'], t['und'], ident, f"{t['from_day']}_{t['to_day']}.{t['task_id']}.json")


def key_of(t, day): return dict(kind=t['kind'], und=t['und'], expiry=t['expiry'], strike=t['strike'], right=t['right'], trade_day=day)


def normalized_relpath(t, day):
    ident = '-' if t['kind'] == 'index' else f"{t['expiry']}/{t['strike']}{t['right']}" if t['kind'] == 'option' else f"{t['expiry']}/FUT"
    return os.path.join('normalized', t['kind'], t['und'], ident, f'{day}.csv')


def derive(store, t, payload, raw_sha):
    meta = json.loads(t['params_json'])['meta']; fd, td = date.fromisoformat(t['from_day']), date.fromisoformat(t['to_day'])
    exp = date.fromisoformat(t['expiry']) if t['expiry'] else None
    rows = N.parse_rows(t['kind'], payload['response'], t['und'], fd, td, exp, t['strike'], t['right'])
    want = [date.fromisoformat(d) for d in meta['days']]
    for d in want:
        k = key_of(t, d.isoformat())
        if d in rows:
            content = N.csv_bytes(t['kind'], rows[d], t['task_id']); rel = normalized_relpath(t, d.isoformat())
            write_once(store.path(rel), content)
            store.set_day(k, status='DONE', source='breeze_v2', task_id=t['task_id'], normalized_relpath=rel, normalized_sha256=sha256_bytes(content), bars=len(rows[d]))
        else:
            store.set_day(k, status='EMPTY' if not payload['response']['Success'] else 'NO_BARS', source='breeze_v2', task_id=t['task_id'], bars=0)
    extra = set(rows) - set(want)
    if extra: raise ResponseError('bars returned for days that were not requested')
    return len(payload['response']['Success'])


def run(store, client, kinds=None, max_tier=None, max_requests=None, daily_cap=C.DEFAULT_DAILY_CAP, log=print, today=None, only_ids=None):
    stats = dict(requests=0, done=0, empty=0, failed=0, retryable=0, reused_raw=0); transients = 0; today = today or ist_today()
    for t in store.pending(kinds, max_tier):
        if only_ids and t['task_id'] not in only_ids: continue
        raw_abs = store.path(raw_relpath(t))
        try:
            if os.path.exists(raw_abs):
                payload = json.loads(open(raw_abs, 'rb').read()); stats['reused_raw'] += 1
            else:
                if max_requests is not None and stats['requests'] >= max_requests: log('stop: --max-requests reached'); break
                if store.requests_today(today) >= daily_cap: log(f'stop: daily cap {daily_cap} reached for {today} (IST)'); break
                try: resp = client.fetch(json.loads(t['params_json'])['request'])
                finally:
                    stats['requests'] += 1
                    store.log_request(t['task_id'], 'sent', today)
                payload = dict(request=json.loads(t['params_json'])['request'], response=resp, retrieved_at_utc=now_utc())
                write_once(raw_abs, canonical(payload)); transients = 0
            raw_sha = sha256_bytes(open(raw_abs, 'rb').read())
            n = derive(store, t, payload, raw_sha)
            st = 'DONE' if n else 'EMPTY'; stats['done' if n else 'empty'] += 1
            store.set_task(t['task_id'], status=st, raw_relpath=os.path.relpath(raw_abs, store.root), raw_sha256=raw_sha, response_rows=n, last_error=None); store.commit()
        except (AuthError, RejectedError, RateLimitError) as e:
            store.set_task(t['task_id'], last_error=type(e).__name__); store.commit(); raise StopRun(f'{type(e).__name__}: {e}') from None
        except TransientError as e:
            a = (t['attempts'] or 0) + 1; transients += 1
            store.set_task(t['task_id'], attempts=a, status='FAILED_RETRYABLE' if a < 4 else 'FAILED', last_error='TransientError'); store.commit(); stats['retryable'] += 1
            if transients >= 5: raise StopRun('5 consecutive transient failures') from None
        except (ResponseError, FileExistsError, ValueError) as e:
            store.set_task(t['task_id'], status='FAILED', last_error=f'{type(e).__name__}: {str(e)[:120]}'); store.commit(); stats['failed'] += 1
    return stats
