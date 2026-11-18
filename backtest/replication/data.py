"""Per-cycle full-chain minute arrays (both days) built from the pinned dataset commit through bt.gitdata.Src. Cached locally (git-ignored)."""
import os, pickle
from common import *
from bt.gitdata import Src
CACHE = os.path.join(HERE, 'cache'); os.makedirs(CACHE, exist_ok=True)
_S = None
MIN = [f'{h:02d}:{m:02d}' for h in range(9, 16) for m in range(60) if '09:15' <= f'{h:02d}:{m:02d}' <= '15:29']
NM = len(MIN); MI = {m: i for i, m in enumerate(MIN)}


def _arr(f, strikes, right, col):
    sub = f[f.right == right]; out = np.full((len(strikes), NM), np.nan)
    si = {k: i for i, k in enumerate(strikes)}
    hm = sub.datetime.str.slice(11, 16).map(MI)
    ok = hm.notna() & sub.strike.isin(si)
    for k, g in sub[ok].assign(h=hm[ok].astype(int)).groupby('strike'): out[si[k], g.h.values] = g[col].values
    return out


def load_cycle(und, expiry, d1, d0):
    global _S
    fn = f'{CACHE}/{und}_{expiry}.pkl'
    if os.path.exists(fn): return pickle.load(open(fn, 'rb'))
    if _S is None: _S = Src()
    idx = und.lower(); days = (d1, d0); out = dict(und=und, expiry=expiry, d1=d1, d0=d0)
    fs = [_S.csv(f'normalized/{idx}/options/exp{expiry}_{d}.csv') for d in days]; sp = [_S.csv(f'normalized/{idx}/underlying/spot/{d}.csv') for d in days]
    strikes = sorted(set(fs[0].strike) | set(fs[1].strike)); out['strikes'] = np.array(strikes)
    for di, (f, s) in enumerate(zip(fs, sp)):
        for right in ('CE', 'PE'):
            for col in ('open', 'close', 'volume'):
                out[(di, right, col)] = _arr(f, strikes, right, col)
        h = s.datetime.str.slice(11, 16).map(MI); o = np.full(NM, np.nan); ok = h.notna(); o[h[ok].astype(int).values] = s.close[ok].values; out[(di, 'spot')] = o
    pickle.dump(out, open(fn, 'wb')); return out
