"""Breeze V2 historical client. Credentials come from the environment (BREEZE_API_KEY, BREEZE_API_SESSION) or a hidden prompt and are never written anywhere.
The transport is injectable so the whole pipeline can be tested without network access. Error bodies are never stored or printed."""
import json, os, re, time, urllib.error, urllib.parse, urllib.request
from . import config as C


class FetchError(Exception): pass
class AuthError(FetchError): pass            # stop the run: credentials / session
class RejectedError(FetchError): pass        # stop the run: broker edge rejected the request (HTML "Request Rejected")
class RateLimitError(FetchError): pass       # stop the run: HTTP 429 persisted
class TransientError(FetchError): pass       # retry later: connection errors, 5xx
class ResponseError(FetchError): pass        # this task is bad: schema / identity / validation


def default_transport(method, url, headers, body):
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r: return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        raise TransientError(f'connection failed: {type(e).__name__}') from None


class BreezeClient:
    def __init__(self, transport=None, api_key=None, session=None, sleep=time.sleep, clock=time.monotonic, min_interval=C.MIN_REQUEST_INTERVAL_S):
        self.transport = transport or default_transport; self.sleep = sleep; self.clock = clock; self.min_interval = min_interval
        self._key = api_key or os.environ.get('BREEZE_API_KEY'); self._session = session or os.environ.get('BREEZE_API_SESSION')
        self._token = None; self._last = None; self.calls = 0

    def __repr__(self): return 'BreezeClient(<credentials hidden>)'

    def _json(self, status, content, stage):
        if status in (401, 403): raise AuthError(f'{stage}: HTTP {status}')
        if status == 429: raise RateLimitError(f'{stage}: HTTP 429')
        if status >= 500: raise TransientError(f'{stage}: HTTP {status}')
        try: out = json.loads(content)
        except (ValueError, UnicodeError):
            if b'request rejected' in content.lower(): raise RejectedError(f'{stage}: HTML request-rejected page (broker edge)') from None
            raise ResponseError(f'{stage}: not JSON (HTTP {status})') from None
        if not isinstance(out, dict): raise ResponseError(f'{stage}: unexpected shape')
        return out

    def authenticate(self):
        if not self._key or not self._session: raise AuthError('BREEZE_API_KEY / BREEZE_API_SESSION not set')
        body = json.dumps({'SessionToken': self._session, 'AppKey': self._key}, separators=(',', ':')).encode()
        status, content = self.transport('GET', C.SESSION_URL, {'Content-Type': 'application/json'}, body)
        out = self._json(status, content, 'session')
        tok = (out.get('Success') or {}).get('session_token') if isinstance(out.get('Success'), dict) else None
        if out.get('Status') not in (200, '200') or not tok: raise AuthError('session exchange failed')
        self._token = tok

    def fetch(self, params):
        """One history request with spacing and bounded retries. Returns {'Status': 200, 'Success': [...]}. Counts each HTTP attempt in self.calls."""
        if self._token is None: self.authenticate()
        url = C.HISTORY_URL + '?' + urllib.parse.urlencode(params)
        headers = {'Content-Type': 'application/json', 'apikey': self._key, 'X-SessionToken': self._token}
        for attempt in range(3):
            if self._last is not None: self.sleep(max(0.0, self.min_interval - (self.clock() - self._last)))
            self._last = self.clock(); self.calls += 1
            try:
                status, content = self.transport('GET', url, headers, None)
                out = self._json(status, content, 'history')
            except (TransientError, RateLimitError):
                if attempt == 2: raise
                self.sleep(2 ** attempt * 2); continue
            if out.get('Status') not in (200, '200') or not isinstance(out.get('Success'), list): raise ResponseError('history: provider reported a non-success status (body suppressed)')
            return {'Status': 200, 'Success': out['Success']}
