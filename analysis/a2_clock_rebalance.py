"""A2: D0 scheduled rebalance. At each clock event (A = :16/:31/:46/:01 window, B = :14/:29/:44/:59 window), which open short contracts
does the scheduler buy back?   python3 analysis/a2_clock_rebalance.py
Rows: (event, open body-short contract at event start). Label: numeric-tag buy of that contract inside the event window."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd, lightgbm as lgb
from sklearn.tree import DecisionTreeClassifier, export_text
from sklearn.metrics import roc_auc_score, precision_score, recall_score, f1_score
from load import load_tagged
C = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_cache')
d = load_tagged().sort_values(['t', 'row'])
ix = pd.read_pickle(os.path.join(C, 'idx_candles.pkl')).set_index(['und', 'ts']).close.sort_index()
op = pd.read_pickle(os.path.join(C, 'opt_candles.pkl')).set_index(['und', 'expiry', 'cp', 'strike', 'ts']).c.sort_index()
stop_t = d[d.tp == 's_'].groupby('date').t.min()
rows = []
for date, g in d[d.dte == 0].groupby('date'):
    und = g.und.iloc[0]; exp = g.expiry.iloc[0]; step = 50 if und == 'NIFTY' else 100
    cyc = d[(d.und == und) & (d.expiry == exp)]
    for kind, off_s, win in [('A', 60, 120), ('B', 13 * 60 + 50, 70)]:
        for q in range(1, 25):
            t0 = date + pd.Timedelta('09:15:00') + pd.Timedelta(seconds=900 * q + off_s - 900 * (kind == 'B'))
            if kind == 'B': t0 = date + pd.Timedelta('09:15:00') + pd.Timedelta(seconds=900 * q - 10)
            if t0.strftime('%H:%M') > '15:15' or t0.strftime('%H:%M') < '09:16': continue
            if date in stop_t.index and t0 >= stop_t[date]: continue
            pre = cyc[cyc.t < t0]
            # body short lots per contract with entry prices
            book = {}
            for r in pre[pre.tp == 'num'].itertuples():
                k = (r.cp, r.strike); n = int(round(r.lots))
                if r.side == 'Sell': book.setdefault(k, []).extend([(r.px_fill, r.date < date)] * n)
                elif book.get(k): book[k] = sorted(book[k])[n:]
            m = t0.floor('min') - pd.Timedelta(minutes=1)
            S = ix.get((und, m), np.nan)
            ev = cyc[(cyc.t >= t0) & (cyc.t < t0 + pd.Timedelta(seconds=win)) & (cyc.tp == 'num')]
            bought = ev[ev.side == 'Buy'].groupby(['cp', 'strike']).lots.sum(); sold = ev[ev.side == 'Sell']
            sold_K = sold.strike.mode().iloc[0] if len(sold) else np.nan
            for (cp, K), lots in book.items():
                if not lots: continue
                p = op.get((und, exp, cp, K, m), np.nan); e = np.array([x[0] for x in lots]); sg = 1 if cp == 'CE' else -1
                rows.append(dict(date=date, und=und, clock=kind, tmin=(t0.hour * 60 + t0.minute) - 555, cp=cp, K=K, nl=len(lots),
                                 carried=np.mean([x[1] for x in lots]), itm=(S - K) / step * sg, absdist=abs(S - K) / step,
                                 px=p, r_min=p / e.min(), r_mean=p / e.mean(), event_sells=len(sold), dist_to_sold=abs(K - sold_K) / step if np.isfinite(sold_K) else np.nan,
                                 label=int(bought.get((cp, K), 0) > 0)))
X = pd.DataFrame(rows).dropna(subset=['px'])
X['ux'] = (X.und == 'SENSEX').astype(int); X['ce'] = (X.cp == 'CE').astype(int); X['isB'] = (X.clock == 'B').astype(int)
X['has_sells'] = (X.event_sells > 0).astype(int)
print('rows', len(X), 'buyback rate', round(X.label.mean(), 3)); print(X.groupby('clock').label.mean().round(3).to_dict())
print('\nbuy-back rate by |K - spot| (steps) and ITM sign:')
X['db'] = pd.cut(X.itm, [-20, -4, -3, -2, -1, -0.5, 0.5, 1, 2, 3, 20])
print(X.groupby(['clock', 'db'], observed=True).label.agg(['size', 'mean']).round(3).unstack(0).to_string())
feats = ['tmin', 'nl', 'carried', 'itm', 'absdist', 'px', 'r_min', 'r_mean', 'has_sells', 'dist_to_sold', 'ux', 'ce', 'isB']
dates = sorted(X.date.unique()); cut = dates[int(len(dates) * 0.6)]
tr, te = X[X.date < cut], X[X.date >= cut]
m = lgb.LGBMClassifier(n_estimators=400, learning_rate=0.03, num_leaves=15, min_child_samples=40, verbose=-1).fit(tr[feats], tr.label)
p = m.predict_proba(te[feats])[:, 1]; thr = max(np.arange(0.1, 0.9, 0.05), key=lambda t: f1_score(tr.label, m.predict_proba(tr[feats])[:, 1] >= t))
print(f'\nLightGBM test AUC {roc_auc_score(te.label, p):.3f}  P {precision_score(te.label, p >= thr):.3f} R {recall_score(te.label, p >= thr):.3f} F1 {f1_score(te.label, p >= thr):.3f}')
imp = pd.Series(m.booster_.feature_importance('gain'), index=feats); print('importance', (imp / imp.sum()).sort_values(ascending=False).round(3).to_dict())
t = DecisionTreeClassifier(max_depth=3, min_samples_leaf=60).fit(tr[feats].fillna(-9), tr.label); yh = t.predict(te[feats].fillna(-9))
print(f'tree depth3 test P {precision_score(te.label, yh):.3f} R {recall_score(te.label, yh):.3f} F1 {f1_score(te.label, yh):.3f}'); print(export_text(t, feature_names=feats, decimals=2, show_weights=True))
X.to_pickle(os.path.join(C, 'a2_clock_rows.pkl'))
