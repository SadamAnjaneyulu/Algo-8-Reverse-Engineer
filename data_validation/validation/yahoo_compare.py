"""Index-level comparison with an independent vendor (Yahoo daily OHLC): the dataset's 09:15-15:29 spot minutes are aggregated to a daily bar and compared."""
import json, sys
from datetime import date
import pandas as pd, numpy as np
from . import calendar_evidence as CE


def run(tab):
    u = pd.DataFrame(json.load(open(f'{tab}/underlying_scan.json'))); sp = u[u.kind == 'spot']; out = {}; rows = []
    for und in ('NIFTY', 'SENSEX'):
        y = CE.yahoo_daily(und); s = sp[sp['index'] == und.lower()].copy()
        for c, yc in (('day_open', 'open'), ('day_high', 'high'), ('day_low', 'low'), ('day_close', 'close')): s[c + '_y'] = [y.get(date.fromisoformat(d), {}).get(yc) for d in s.day]
        s['in_yahoo'] = s.day_open_y.notna(); s['post_cas'] = s.day >= '2026-08-03'
        for per, g in (('pre_CAS', s[~s.post_cas & s.in_yahoo]), ('post_CAS', s[s.post_cas & s.in_yahoo])):
            r = dict(index=und, period=per, sessions=len(g))
            for c in ('day_open', 'day_high', 'day_low', 'day_close'):
                d = (g[c] - g[c + '_y']).abs(); rel = d / g[c + '_y']; r[c + '_median_abs_pts'] = round(float(d.median()), 2); r[c + '_p95_abs_pts'] = round(float(d.quantile(.95)), 2); r[c + '_sessions_gt_0.3pct'] = int((rel > .003).sum())
            rows.append(r)
        out[und] = dict(sessions=len(s), not_in_yahoo=[d for d, i in zip(s.day, s.in_yahoo) if not i])
    pd.DataFrame(rows).to_csv(f'{tab}/index_vs_yahoo.csv', index=False); return out, rows


if __name__ == '__main__':
    o, r = run(sys.argv[1]); print(o); print(pd.DataFrame(r).to_string(index=False))
