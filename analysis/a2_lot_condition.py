"""A2b: fungible-lot count test at D0 clock events. For condition C(theta) on each open lot (price/own-entry <= theta  [profit target]
or >= theta [stop]), predicted lots closed in a contract = #lots meeting C. Score vs actual numeric buys in the event window.
python3 analysis/a2_lot_condition.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from load import load_tagged
C = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_cache')
d = load_tagged().sort_values(['t', 'row'])
op = pd.read_pickle(os.path.join(C, 'opt_candles.pkl')).set_index(['und', 'expiry', 'cp', 'strike', 'ts']).c.sort_index()
stop_t = d[d.tp == 's_'].groupby('date').t.min()
recs = []
for date, g in d[d.dte == 0].groupby('date'):
    und = g.und.iloc[0]; exp = g.expiry.iloc[0]; cyc = d[(d.und == und) & (d.expiry == exp)]
    for q in range(1, 25):
        for kind, off, win in [('A', 60, 120), ('B', -10, 70)]:
            t0 = date + pd.Timedelta('09:15:00') + pd.Timedelta(seconds=900 * q + off)
            if not ('09:16' <= t0.strftime('%H:%M') <= '15:09'): continue
            if date in stop_t.index and t0 >= stop_t[date]: continue
            pre = cyc[(cyc.t < t0) & (cyc.tp == 'num')]
            book = {}
            for r in pre.itertuples():
                k = (r.cp, r.strike); n = int(round(r.lots))
                if r.side == 'Sell': book.setdefault(k, []).extend([r.px_fill] * n)
                elif book.get(k): book[k] = sorted(book[k])[n:]
            ev = cyc[(cyc.t >= t0) & (cyc.t < t0 + pd.Timedelta(seconds=win)) & (cyc.tp == 'num') & (cyc.side == 'Buy')]
            bought = ev.groupby(['cp', 'strike']).lots.sum()
            m = t0.floor('min') - pd.Timedelta(minutes=1)
            for (cp, K), e in book.items():
                if not e: continue
                p = op.get((und, exp, cp, K, m), np.nan)
                if not np.isfinite(p): continue
                recs.append(dict(date=date, clock=kind, t0=t0, ratios=np.array(p / np.array(e)), price=p, actual=int(round(bought.get((cp, K), 0)))))
R = pd.DataFrame(recs)
print('contract-events', len(R), 'with any buy', int((R.actual > 0).sum()), 'lots bought', int(R.actual.sum()))
res = []
for mode in ['target(<=)', 'stop(>=)']:
    for th in ([0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.7] if mode.startswith('t') else [1.2, 1.3, 1.4, 1.5, 1.6, 1.8, 2.0]):
        pred = np.array([(r <= th).sum() if mode.startswith('t') else (r >= th).sum() for r in R.ratios])
        act = R.actual.values
        tp = np.minimum(pred, act).sum()
        res.append(dict(rule=mode, theta=th, pred_lots=int(pred.sum()), matched_lots=int(tp), precision=round(tp / max(pred.sum(), 1), 3), recall=round(tp / act.sum(), 3),
                        exact_events=round(((pred == act) & (act > 0)).sum() / (act > 0).sum(), 3)))
print(pd.DataFrame(res).to_string(index=False))
