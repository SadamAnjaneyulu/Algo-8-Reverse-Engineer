"""B2e: is the per-leg stop evaluated on a candle CLOSE of some timeframe (1/3/5/15 min) instead of live LTP?
For each lot that first traded >= 1.55x entry (minute high), check whether a bar of timeframe TF (aligned to 09:15) CLOSED >= TH x entry
within the next 15 min; compare with whether the algo actually stopped it.   python3 analysis/b2_stop_timeframe.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from sklearn.metrics import roc_auc_score
C = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_cache')
L = pd.read_pickle(os.path.join(C, 'p1_crossed_lots.pkl'))
op = pd.read_pickle(os.path.join(C, 'opt_candles.pkl')).set_index(['und', 'expiry', 'cp', 'strike']).sort_index()
k = L.ks.str.split('|', expand=True); L['u'] = k[0]; L['e'] = pd.to_datetime(k[1]); L['cp'] = k[2]; L['K'] = k[3].astype(int)
L['mc'] = pd.to_datetime(L.date) + pd.Timedelta('09:15:00') + pd.to_timedelta(L.trig_min, unit='min')
res = {}
cache = {}
for r in L.itertuples():
    key = (r.u, r.e, r.cp, r.K)
    if key not in cache:
        try: cache[key] = op.loc[key].set_index('ts')[['h', 'c']]
        except KeyError: cache[key] = None
    s = cache[key]
    if s is None: continue
    w = s[(s.index >= r.mc) & (s.index < r.mc + pd.Timedelta(minutes=16))]
    for tf in [1, 3, 5, 15]:
        mins = ((w.index.hour * 60 + w.index.minute) - 555)
        bar_end = (mins % tf) == (tf - 1)                        # last 1-min bar of a tf-bar aligned to 09:15
        for th in [1.45, 1.55, 1.65]:
            res.setdefault((tf, th), []).append((r.Index, float((w.c[bar_end] >= th * r.entry_px).any()), r.stopped))
rows = []
for (tf, th), v in res.items():
    a = np.array(v); pred = a[:, 1]; y = a[:, 2]
    tp = ((pred == 1) & (y == 1)).sum(); prec = tp / max(pred.sum(), 1); rec = tp / y.sum()
    rows.append(dict(timeframe_min=tf, threshold=th, n=len(a), precision=round(prec, 3), recall=round(rec, 3), accuracy=round((pred == y).mean(), 3)))
R = pd.DataFrame(rows).sort_values(['threshold', 'timeframe_min'])
print('baseline (always stop):', round(L.stopped.mean(), 3)); print(R.to_string(index=False))
