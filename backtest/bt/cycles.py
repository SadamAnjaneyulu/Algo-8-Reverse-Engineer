"""Cycle list (independent expiry calendar + validation status) and per-cycle data cache built from the pinned dataset commit."""
import math, os, pickle, sys
from datetime import date, datetime
from functools import reduce
from multiprocessing import Pool
import numpy as np, pandas as pd
from . import config as C
from .gitdata import Src
VAL = '/home/user/Algo-8-Reverse-Engineer/data_validation'; CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cache')
_S = None


def cycle_list():
    """All expected expiries with their validation status; split label by D0 date (embargo = D-1 in IS and D0 in OOS)."""
    rows = []
    for und in ('NIFTY', 'SENSEX'):
        t = pd.read_csv(f'{VAL}/reports/tables/{und.lower()}_expiry_coverage.csv'); t['notes'] = t.notes.fillna('')
        for r in t.itertuples():
            d0, d1 = date.fromisoformat(r.d0_expected), date.fromisoformat(r.d1_expected)
            if d0 <= C.IS_END: split = 'IS'
            elif d1 <= C.IS_END: split = 'EMBARGO'
            elif d0 <= C.OOS_END: split = 'OOS'
            else: split = 'OUT_OF_RANGE'
            sub = 'IS' if split == 'IS' else ('OOS_EXPOSED' if C.EXPOSED_START <= d0 <= C.EXPOSED_END else ('OOS_CLEAN_BEFORE' if d0 < C.EXPOSED_START else 'OOS_CLEAN_AFTER')) if split == 'OOS' else split
            rows.append(dict(und=und, expiry=r.expected_expiry, d1=r.d1_expected, d0=r.d0_expected, status=r.status, notes=r.notes, split=split, subset=sub))
    return pd.DataFrame(rows)


def _init():
    global _S; _S = Src()


def official_close(und, d0, spot0):
    b = spot0[spot0.datetime.str.slice(11, 16) >= '15:30']
    if len(b): return float(b.close.iloc[0]), 'SPOT_1530_BAR'
    y = pd.read_csv(f'{VAL}/reference/yahoo_daily_{"NSEI" if und == "NIFTY" else "BSESN"}.csv'); y = y[y.date_ist == d0]
    if len(y) and pd.notna(y.close.iloc[0]): return float(y.close.iloc[0]), 'YAHOO_DAILY_CLOSE'
    s = spot0[spot0.datetime.str.slice(11, 16) <= '15:29']; return float(s.close.iloc[-1]), 'SPOT_1529_CLOSE_FALLBACK'


def lot_of(f):
    v = f.volume[(f.volume > 0) & (f.volume < 2 ** 31)].astype('int64').values
    return int(reduce(math.gcd, v[:200000])) if len(v) else 0


def build(args):
    und, expiry, d1, d0 = args; idx = und.lower(); out = dict(und=und, expiry=expiry, d1=d1, d0=d0, feasible=False, reason='')
    f1 = _S.csv(f'normalized/{idx}/options/exp{expiry}_{d1}.csv'); f0 = _S.csv(f'normalized/{idx}/options/exp{expiry}_{d0}.csv')
    sp1 = _S.csv(f'normalized/{idx}/underlying/spot/{d1}.csv'); sp0 = _S.csv(f'normalized/{idx}/underlying/spot/{d0}.csv')
    out['lot_d1'], out['lot_d0'] = lot_of(f1), lot_of(f0); step = C.STEP[und]
    r = sp1[sp1.datetime == f'{d1} 09:15:00']
    if not len(r): out['reason'] = 'NO_SPOT_0915_BAR'; return out
    S = float(r.close.iloc[0]); K = step * math.floor(S / step + 0.5); W = C.wing_points(und, date.fromisoformat(d1)); out.update(spot_0915=S, K=K, W=W)
    keep = ['datetime', 'hm', 'open', 'high', 'low', 'close', 'volume', 'open_interest']; frames = {}; ent = {}
    def entry_bar(a):
        a = a.assign(hm=a.datetime.str.slice(11, 16)); win = a[(a.hm >= C.ENTRY_DECISION_HHMM) & (a.hm <= '09:%02d' % (16 + C.ENTRY_WINDOW_MIN - 1)) & (a.volume > 0) & (a.volume < 2 ** 31)]
        return a, (win.iloc[0] if len(win) else None)
    def pick(lid, k0, cp, side, inward):
        """short legs: exactly K. long wings: the nominal strike if it has a traded bar in the entry window, else the nearest strike toward ATM that has one (pre-registered fallback; the substitution is recorded)."""
        k = k0
        while True:
            a = f1[(f1.strike == k) & (f1.right == cp)]
            if len(a):
                a, e = entry_bar(a)
                if e is not None: return k, a, e
            if not inward: return None
            k += inward * step
            if (inward > 0 and k >= K) or (inward < 0 and k <= K): return None
    for lid, (k0, cp, side, inward) in {'SCE': (K, 'CE', -1, 0), 'SPE': (K, 'PE', -1, 0), 'WCE': (K + W, 'CE', 1, -1), 'WPE': (K - W, 'PE', 1, 1)}.items():
        r_ = pick(lid, k0, cp, side, inward)
        if r_ is None: out['reason'] = f'NO_TRADED_BAR_IN_ENTRY_WINDOW:{lid}:{cp}{k0}'; return out
        k, a, e = r_; b = f0[(f0.strike == k) & (f0.right == cp)].copy(); b['hm'] = b.datetime.str.slice(11, 16)
        ent[lid] = dict(strike=int(k), nominal_strike=int(k0), cp=cp, side=side, hm=e.hm, open=float(e.open), close=float(e.close), volume=int(e.volume), substituted=bool(k != k0)); frames[lid] = (a[keep].reset_index(drop=True), b[keep].reset_index(drop=True))
    oc, src = official_close(und, d0, sp0)
    out.update(feasible=True, legs=ent, frames=frames, official_close=oc, official_close_src=src, spot_d1=sp1[['datetime', 'close']], spot_d0=sp0[['datetime', 'close']])
    return out


def build_all(cyc, procs=4):
    os.makedirs(CACHE, exist_ok=True); jobs = [(r.und, r.expiry, r.d1, r.d0) for r in cyc.itertuples() if not os.path.exists(f'{CACHE}/{r.und}_{r.expiry}.pkl')]
    with Pool(procs, initializer=_init) as p:
        for res in p.imap_unordered(build, jobs, chunksize=2): pickle.dump(res, open(f'{CACHE}/{res["und"]}_{res["expiry"]}.pkl', 'wb'))
    return len(jobs)


def load(und, expiry): return pickle.load(open(f'{CACHE}/{und}_{expiry}.pkl', 'rb'))


if __name__ == '__main__':
    cyc = cycle_list(); use = cyc[(cyc.status == 'Complete') & cyc.split.isin(['IS', 'OOS'])]; print(len(cyc), 'expected;', len(use), 'Complete and inside IS/OOS'); print(cyc.groupby(['und', 'split', 'status']).size().to_string())
    print('built', build_all(use))
