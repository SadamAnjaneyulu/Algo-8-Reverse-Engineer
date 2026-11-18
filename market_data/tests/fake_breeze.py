"""Deterministic in-memory Breeze stand-in for tests (no network). Mimics the response shapes seen in the real raw files."""
import json, random, urllib.parse
from datetime import date, datetime, timedelta

SECRET_KEY, SECRET_SESSION, SECRET_TOKEN = 'KEY-abc123-SECRET', 'SESSION-xyz789-SECRET', 'TOKEN-qqq456-SECRET'


class FakeBreeze:
    def __init__(self, holidays=(), expiry_weekday=3, unlisted=lambda strike, right: False, no_oi=False, fail_after=None, bad_identity=False):
        self.calls = []; self.holidays = {date.fromisoformat(h) for h in holidays}; self.wd = expiry_weekday; self.unlisted = unlisted; self.no_oi = no_oi; self.fail_after = fail_after; self.bad_identity = bad_identity

    def spot(self, d): return 22000 + (d.toordinal() % 40) * 13

    def trading(self, d): return d.weekday() < 5 and d not in self.holidays

    def expiries_ok(self, e):
        w = e                                   # the real expiry: nominal weekday, else the previous trading day when that is a holiday
        nominal = e - timedelta(days=e.weekday()) + timedelta(days=self.wd)
        while not self.trading(nominal): nominal -= timedelta(days=1)
        return e == nominal

    def __call__(self, method, url, headers, body):
        if 'customerdetails' in url:
            if json.loads(body)['AppKey'] != SECRET_KEY: return 401, b'{}'
            return 200, json.dumps({'Status': 200, 'Success': {'session_token': SECRET_TOKEN}}).encode()
        assert headers['X-SessionToken'] == SECRET_TOKEN and headers['apikey'] == SECRET_KEY
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query)); self.calls.append(q)
        if self.fail_after is not None and len(self.calls) > self.fail_after: return 503, b'{}'
        d0 = date.fromisoformat(q['from_date'][:10]); d1 = date.fromisoformat(q['to_date'][:10]); rows = []
        for i in range((d1 - d0).days + 1):
            d = d0 + timedelta(days=i)
            if not self.trading(d): continue
            n = 375
            if q['product_type'] == 'cash': ok = True
            else:
                e = date.fromisoformat(q['expiry_date'][:10]); strike = int(float(q.get('strike_price', 0) or 0)); right = {'call': 'CE', 'put': 'PE'}.get(q.get('right'))
                ok = d <= e and (q['product_type'] == 'futures' or (self.expiries_ok(e) and strike % 50 == 0 and not self.unlisted(strike, right)))
            if not ok: continue
            rnd = random.Random(f"{q['stock_code']}{q.get('strike_price')}{q.get('right')}{d}"); px = self.spot(d) if q['product_type'] == 'cash' else max(1.0, 100 - abs(int(float(q.get('strike_price', 0) or 0)) - self.spot(d)) / 10)
            for m in range(n):
                t = datetime(d.year, d.month, d.day, 9, 15) + timedelta(minutes=m); o = round(px + rnd.random(), 2); c = round(px + rnd.random(), 2)
                if q['product_type'] != 'cash': o, c = round(round(o * 20) / 20, 2), round(round(c * 20) / 20, 2)
                row = dict(datetime=t.strftime('%Y-%m-%d %H:%M:%S'), stock_code=q['stock_code'] if not self.bad_identity else 'OTHER', exchange_code=q['exch_code'], open=o, high=max(o, c) + .05, low=min(o, c) - .05 if min(o, c) > .1 else min(o, c), close=c, volume=int(rnd.random() * 1000) * 75)
                if q['product_type'] == 'cash': row['product_type'] = 'Cash'
                else:
                    row.update(product_type=q['product_type'].capitalize(), expiry_date=date.fromisoformat(q['expiry_date'][:10]).strftime('%d-%b-%Y').upper(), open_interest=None if self.no_oi else int(rnd.random() * 1e6))
                    if q['product_type'] == 'options': row.update(right=q['right'].capitalize(), strike_price=float(q['strike_price']))
                if q['product_type'] == 'cash': row['open_interest'] = 0
                rows.append(row)
        return 200, json.dumps({'Status': 200, 'Success': rows}).encode()
