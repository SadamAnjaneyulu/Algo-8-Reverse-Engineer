"""Per-lot leg stop hypothesis on D-1: each body short lot is bought back the first minute its option trades at >= TH x its own entry fill.
Simulated with Breeze minute candles; scored vs actual body (numeric-tag) buy-backs.   python3 analysis/leg_stop.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from load import load_tagged

def lots_and_exits(d, day_filter):
    d = d.sort_values(['t', 'row'])
    lots, exits = [], []
    for r in d.itertuples():
        if not day_filter(r): continue
        k = (r.und, r.expiry, r.cp, r.strike)
        ks = f'{r.und}|{r.expiry.date()}|{r.cp}|{int(r.strike)}'
        n = int(round(r.lots))
        if r.tp == 'num' and r.side == 'Sell':
            lots += [dict(key=k, ks=ks, e=r.px_fill, t0=r.t, date=r.date)] * n
        elif r.tp == 'num' and r.side == 'Buy':
            exits += [dict(ks=ks, t=r.t)] * n
    return pd.DataFrame(lots), pd.DataFrame(exits)

def simulate(lots, o, th, field, end_time='15:40'):
    """predicted trigger minute per lot (NaT if never)."""
    pred = pd.Series(pd.NaT, index=lots.index, dtype='datetime64[ns]')
    for ks, g in lots.groupby('ks'):
        k = g.key.iloc[0]
        try: s = o.loc[k]
        except KeyError: continue
        for r in g.itertuples():
            w = s[(s.ts > r.t0.floor('min')) & (s.ts.dt.normalize() == r.date) & (s.ts.dt.strftime('%H:%M') <= end_time)]
            hit = w[w[field] >= th * r.e]
            if len(hit): pred.at[r.Index] = hit.ts.iloc[0]
    lots = lots.copy(); lots['pred'] = pred
    return lots

def score(pred_lots, exits, tol_min=2):
    """greedy match predicted triggers to actual exit lots per contract within tol minutes."""
    mp = ma = 0
    P = pred_lots.dropna(subset=['pred'])
    ex = {k: sorted(g.t.dt.floor('min').tolist()) for k, g in exits.groupby('ks')}
    for k, g in P.groupby('ks'):
        pt = sorted(g.pred.tolist())
        at = ex.get(k, [])
        used = [False] * len(at)
        for p in pt:
            for i, a in enumerate(at):
                if not used[i] and abs((a - p).total_seconds()) <= tol_min * 60:
                    used[i] = True; mp += 1; break
    return mp, len(P), len(exits)

if __name__ == '__main__':
    d = load_tagged()
    o = pd.read_pickle(os.path.join(os.path.dirname(os.path.abspath(__file__)), '_cache', 'opt_candles.pkl')).set_index(['und', 'expiry', 'cp', 'strike']).sort_index()
    stop_days = set(d[d.tp == 's_'].date.unique())
    # D-1 only, exclude stop-module days' liquidation (s_ orders are not 'num' anyway); exclude lots opened on D0
    lots, exits = lots_and_exits(d, lambda r: r.dte >= 1)
    print('D-1 short lots:', len(lots), ' actual D-1 body buy-back lots:', len(exits))
    rows = []
    for field in ['h', 'c']:
        for th in [1.3, 1.4, 1.45, 1.5, 1.55, 1.6, 1.7]:
            pl = simulate(lots, o, th, field)
            m, npred, nact = score(pl, exits)
            rows.append(dict(trigger_on=field, threshold=th, predicted=npred, matched=m, precision=round(m / max(npred, 1), 3), recall=round(m / nact, 3)))
            print(rows[-1], flush=True)
    pd.DataFrame(rows).to_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '_cache', 'leg_stop_grid.csv'), index=False)
