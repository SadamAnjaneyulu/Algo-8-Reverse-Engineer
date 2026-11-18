"""Put-call parity plausibility at 11:00 and 14:00 for strikes within 2 steps of the spot: |C - P - (S - K)| should be small relative to spot (a swapped CE/PE label or a misaligned spot breaks it).
Uses only bars with volume > 0. Reports the median relative error per session; sessions above 0.3 % of spot are listed."""
import io, json, re, sys
from multiprocessing import Pool
import numpy as np, pandas as pd
from .gitsrc import GitSource
_G = None


def _init(c):
    global _G; _G = GitSource(c)


def one(a):
    idx, exp, day = a; x = pd.read_csv(io.BytesIO(_G.read(f'normalized/{idx}/options/exp{exp}_{day}.csv')), usecols=['datetime', 'strike', 'right', 'close', 'volume']); sp = pd.read_csv(io.BytesIO(_G.read(f'normalized/{idx}/underlying/spot/{day}.csv')))
    sm = dict(zip(sp.datetime, sp.close)); errs = []
    for hhmm in ('11:00', '14:00'):
        t = f'{day} {hhmm}:00'; S = sm.get(t); b = x[x.datetime == t]
        if S is None or not len(b): continue
        step = 50 if idx == 'nifty' else 100; c = b[(b.right == 'CE') & (b.volume > 0)].set_index('strike').close; p = b[(b.right == 'PE') & (b.volume > 0)].set_index('strike').close
        for k in c.index.intersection(p.index):
            if abs(k - S) <= 2 * step: errs.append(abs(c[k] - p[k] - (S - k)) / S * 100)
    return dict(index=idx, expiry=exp, day=day, n=len(errs), median_err_pct=float(np.median(errs)) if errs else None)


if __name__ == '__main__':
    commit, tab = sys.argv[1], sys.argv[2]; g = GitSource(commit); jobs = []
    for p in sorted(g.tree()):
        m = re.match(r'normalized/(nifty|sensex)/options/exp(\S{10})_(\S{10})\.csv', p)
        if m: jobs.append((m[1], m[2], m[3]))
    with Pool(4, initializer=_init, initargs=(commit,)) as pool: res = pool.map(one, jobs, chunksize=4)
    r = pd.DataFrame(res); r.to_csv(f'{tab}/put_call_parity.csv', index=False); print(r.groupby('index').median_err_pct.describe().round(4).to_string()); print('sessions > 0.3%:', r[r.median_err_pct > 0.3][['index', 'expiry', 'day', 'median_err_pct']].to_string(index=False)); print('sessions with no testable strikes:', int(r.median_err_pct.isna().sum()))
