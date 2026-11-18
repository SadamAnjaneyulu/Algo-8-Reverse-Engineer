"""Contract-minute hazard panel for ONE cycle (refactored from carried_lots.py so it can be perturbation-tested). State at minute j is built from fills strictly BEFORE minute j; prices/spot come from bar j-1 of the concatenated D-1+D0 arrays (D0 minute 0 therefore reads the last D-1 bar).
Limitation (review finding): a buy-back of a contract with no recorded short inventory is not in the panel (its inventory is unknown at minute j); 237 of 3,991 buy-back contract-minutes are lost this way (43 % of those in minutes 0-5)."""
from collections import defaultdict
import numpy as np, pandas as pd
from ledger import LOT
from data import NM


def px_arrays(c):
    a = {}
    for r in ('CE', 'PE'):
        x = np.concatenate([c[(0, r, 'close')], c[(1, r, 'close')]], axis=1).copy()
        for j in range(1, x.shape[1]): m = np.isnan(x[:, j]); x[m, j] = x[m, j - 1]
        a[r] = x
    return a


def panel_cycle(c, g, und, expiry, d1, d0):
    """c: cycle market dict; g: fills of the cycle sorted by (t,row). returns DataFrame"""
    ki = {int(k): i for i, k in enumerate(c['strikes'])}; P = px_arrays(c); step = 50 if und == 'NIFTY' else 100; spot = pd.Series(np.concatenate([c[(0, 'spot')], c[(1, 'spot')]])).ffill().values; panel = []
    books = defaultdict(list); ev = defaultdict(float); fl = list(g.itertuples()); last_bb_j = -999; ptr = 0
    for f in fl:
        if f.module == 'num' and f.side == 'Buy' and f.day == d0: ev[(f.cp, int(f.strike), f.sec // 60 - 555)] += f.n_lots
    for j in range(NM):
        tabs = 86400 + (555 + j) * 60
        while ptr < len(fl) and ((0 if fl[ptr].day == d1 else 86400) + fl[ptr].sec) < tabs:
            f = fl[ptr]; ptr += 1
            if f.module == 'num':
                B = books[(f.cp, int(f.strike))]
                if f.side == 'Sell': B.extend([[f.px, 0 if f.day == d1 else 1] for _ in range(f.n_lots)])
                else:
                    for _ in range(f.n_lots):
                        if B: B.pop(0)
                    if f.day == d0: last_bb_j = f.sec // 60 - 555
            elif f.module in ('s_', 'm_') and f.side == 'Buy':
                B = books[(f.cp, int(f.strike))]
                for _ in range(f.n_lots):
                    if B: B.pop(0)
        S = spot[NM + j - 1]; mm = (555 + j) % 60; hh = (555 + j) // 60; Tleft = (15.5 * 60 - (555 + j)) / 60
        for (cp, k), B in books.items():
            if not B: continue
            i = ki.get(k)
            if i is None: continue
            pj = P[cp][i, NM + j - 1]; ents = [b[0] for b in B]; avg = float(np.mean(ents)); cheap = float(min(ents)); n = len(B); carried = sum(1 for b in B if b[1] == 0); p5 = P[cp][i, max(NM + j - 6, 0)]
            panel.append(dict(und=und, expiry=expiry, j=j, cp=cp, strike=k, lots=n, carried_lots_FIFO=carried, price=pj, avg_entry=avg, cheapest=cheap, ratio_avg=pj / avg, ratio_cheapest=pj / cheap, off_steps=(k - S) / step, itm=bool((cp == 'CE' and k < S) or (cp == 'PE' and k > S)), hours_left=Tleft, minute_of_hour=mm, clockB=bool(mm % 15 == 14 and hh * 60 + mm >= 9 * 60 + 29),
                              d_price_5m=(pj / p5 - 1) if p5 else np.nan, mins_since_cycle_buyback=(j - last_bb_j) if last_bb_j > -999 else np.nan, buyback_lots=ev.get((cp, k, j), 0.0)))
    return pd.DataFrame(panel)
