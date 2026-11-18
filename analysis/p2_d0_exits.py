"""P2: expiry-day (D0) body buy-back hazard at contract-minute level.   python3 analysis/p2_d0_exits.py
Rows: each D0 minute 09:16-15:08 x each contract with open body short at minute start (stop-module period excluded).
Label: numeric-tag buy of that contract in the minute. Features causal (bars to m-1, fills before m). 60/40 chronological split."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
import lightgbm as lgb
from sklearn.tree import DecisionTreeClassifier, export_text
from sklearn.metrics import precision_recall_curve, average_precision_score
from load import load_tagged
C = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_cache')
d = load_tagged().sort_values(['t', 'row']); d['m'] = d.t.dt.floor('min')
ix = pd.read_pickle(os.path.join(C, 'idx_candles.pkl')); op = pd.read_pickle(os.path.join(C, 'opt_candles.pkl'))
stop_t = d[d.tp == 's_'].groupby('date').t.min()
rows = []
for date, g in d[d.dte == 0].groupby('date'):
    und = g.und.iloc[0]; exp = g.expiry.iloc[0]; step = 50 if und == 'NIFTY' else 100
    cyc = d[(d.und == und) & (d.expiry == exp)].assign(key=lambda z: z.cp + '|' + z.strike.astype(int).astype(str))
    s = ix[(ix.und == und) & (ix.ts.dt.normalize() == date)].set_index('ts').close
    if len(s) < 100: continue
    grid = pd.date_range(date + pd.Timedelta('09:16:00'), date + pd.Timedelta('15:08:00'), freq='min')
    if date in stop_t.index: grid = grid[grid < stop_t[date].floor('min')]
    if len(grid) < 5: continue
    S1 = s.shift(1).reindex(grid)
    body = cyc[cyc.tp == 'num']
    # body short inventory per contract and cost basis (cheapest & mean entry of open lots) via running per-lot book
    book = {}; snap_min = {}; snap_mean = {}; snap_lots = {}; snap_carry = {}; recs = []
    bl = body.sort_values(['t', 'row'])
    events = {m: grp for m, grp in bl.groupby('m')}
    mins_all = sorted(set(bl.m) | set(grid))
    for m in mins_all:
        if m in set(grid):
            for k, lots in book.items():
                if lots:
                    e = np.array([x[0] for x in lots]); cr = np.mean([x[1] < date for x in lots])
                    recs.append((m, k, len(lots), e.min(), e.mean(), cr))
        if m in events:
            for r in events[m].itertuples():
                n = int(round(r.lots)); k = r.key
                if r.side == 'Sell': book.setdefault(k, []).extend([(r.px_fill, r.date)] * n)
                elif book.get(k): book[k] = sorted(book[k])[n:]
    R = pd.DataFrame(recs, columns=['m', 'key', 'nlots', 'emin', 'emean', 'carried'])
    if R.empty: continue
    R['cp'] = R.key.str[:2]; R['K'] = R.key.str[3:].astype(float)
    oc = op[(op.und == und) & (op.expiry == exp)].assign(m=lambda z: z.ts + pd.Timedelta(minutes=1), key=lambda z: z.cp + '|' + z.strike.astype(int).astype(str))
    R = R.merge(oc[['m', 'key', 'c', 'h']].rename(columns={'c': 'px', 'h': 'hi'}), on=['m', 'key'], how='left')
    R['S'] = R.m.map(S1); sg = np.where(R.cp == 'CE', 1, -1)
    R['mny'] = (R.S - R.K) / step * sg          # >0 = ITM steps
    for L in [1, 5, 15]: R[f'mv{L}'] = R.m.map(((s.shift(1) - s.shift(1 + L)) / s.shift(1) * 1e4)) * sg
    R['r_min'] = R.px / R.emin; R['r_mean'] = R.px / R.emean; R['rh_min'] = R.hi / R.emin
    R['mins'] = (R.m.dt.hour * 60 + R.m.dt.minute) - 555
    buys = body[body.side == 'Buy'].groupby(['m', 'key']).size()
    R['label'] = [int((m, k) in buys.index) for m, k in zip(R.m, R.key)]
    R['date'] = date; R['ux'] = int(und == 'SENSEX'); R['ce'] = (R.cp == 'CE').astype(int)
    rows.append(R)
X = pd.concat(rows, ignore_index=True).dropna(subset=['px'])
feats = ['nlots', 'emin', 'emean', 'carried', 'px', 'r_min', 'r_mean', 'rh_min', 'mny', 'mv1', 'mv5', 'mv15', 'mins', 'ux', 'ce']
dates = sorted(X.date.unique()); cut = dates[int(len(dates) * 0.6)]
tr, te = X[X.date < cut], X[X.date >= cut]
print('contract-minutes', len(X), 'exit minutes', int(X.label.sum()), 'base', round(X.label.mean(), 4))
m = lgb.LGBMClassifier(n_estimators=600, learning_rate=0.03, num_leaves=31, min_child_samples=100, subsample=0.8, subsample_freq=1, colsample_bytree=0.8, verbose=-1).fit(tr[feats], tr.label)
p = m.predict_proba(te[feats])[:, 1]
pr, rc, th = precision_recall_curve(te.label, p); f1 = 2 * pr * rc / np.maximum(pr + rc, 1e-9); i = np.nanargmax(f1)
print(f'LightGBM test AP {average_precision_score(te.label, p):.3f} | best F1 {f1[i]:.3f} (P {pr[i]:.3f} R {rc[i]:.3f}) | base {te.label.mean():.4f}')
imp = pd.Series(m.booster_.feature_importance('gain'), index=feats); print('importance', (imp / imp.sum()).sort_values(ascending=False).round(3).to_dict())
t = DecisionTreeClassifier(max_depth=4, min_samples_leaf=300, class_weight='balanced').fit(tr[feats], tr.label)
print('tree test AP', round(average_precision_score(te.label, t.predict_proba(te[feats])[:, 1]), 3)); print(export_text(t, feature_names=feats, decimals=2))
X.to_pickle(os.path.join(C, 'p2_contract_minutes.pkl'))
