"""P1b: which short lots are subject to the ~1.5x leg stop? Classify crossed lots: stopped (bought back within 15 min of first crossing) vs survived.
python3 analysis/p1_exempt.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from sklearn.tree import DecisionTreeClassifier, export_text
import lightgbm as lgb
from sklearn.metrics import roc_auc_score
from leg_stop import load_tagged, lots_and_exits, simulate
C = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_cache')
d = load_tagged()
o = pd.read_pickle(os.path.join(C, 'opt_candles.pkl')).set_index(['und', 'expiry', 'cp', 'strike']).sort_index()
rows = []
for lab, flt, end in [('D-1', lambda r: r.dte >= 1, '15:40'), ('D0', lambda r: r.dte == 0, '15:09')]:
    lots, exits = lots_and_exits(d, flt)
    if lab == 'D0': exits = exits[exits.t.dt.strftime('%H:%M') < '15:10']
    pl = simulate(lots, o, 1.55, 'h', end_time=end).dropna(subset=['pred'])
    ex = {k: sorted(g.t.tolist()) for k, g in exits.groupby('ks')}
    for r in pl.itertuples():
        nxt = [a for a in ex.get(r.ks, []) if a >= r.pred - pd.Timedelta(minutes=2)]
        dl = (nxt[0] - r.pred).total_seconds() / 60 if nxt else np.inf
        mins = (r.t0.hour * 60 + r.t0.minute) - 556
        rows.append(dict(day=lab, date=r.date, ks=r.ks, und=r.ks.split('|')[0], cp=r.ks.split('|')[2], entry_px=r.e,
                         entry_min=mins, entry_slot=mins // 15, entry_off=mins % 15, grid=int(mins % 15 <= 2 and mins >= 0), opening=int(mins <= 2),
                         trig_min=(r.pred.hour * 60 + r.pred.minute) - 555, hold_min=(r.pred - r.t0).total_seconds() / 60,
                         stopped=int(dl <= 15)))
X = pd.DataFrame(rows)
X['ux'] = (X.und == 'SENSEX').astype(int); X['ce'] = (X.cp == 'CE').astype(int); X['d0'] = (X.day == 'D0').astype(int)
X['entry_px_rel'] = X.entry_px / X.groupby(['date', 'cp']).entry_px.transform('median')
print('crossed lots:', len(X), X.groupby('day').stopped.agg(['size', 'mean']).round(3).to_dict())
for c in ['opening', 'grid', 'ce', 'ux']:
    print(c, X.groupby(['day', c]).stopped.agg(['size', 'mean']).round(3).to_dict())
feats = ['entry_px', 'entry_px_rel', 'entry_min', 'entry_slot', 'entry_off', 'grid', 'opening', 'trig_min', 'hold_min', 'ux', 'ce', 'd0']
dates = sorted(X.date.unique()); cut = dates[int(len(dates) * 0.6)]
tr, te = X[X.date < cut], X[X.date >= cut]
m = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.05, num_leaves=15, min_child_samples=20, verbose=-1).fit(tr[feats], tr.stopped)
print('LightGBM test AUC', round(roc_auc_score(te.stopped, m.predict_proba(te[feats])[:, 1]), 3))
imp = pd.Series(m.booster_.feature_importance('gain'), index=feats); print('importance', (imp / imp.sum()).sort_values(ascending=False).round(3).to_dict())
t = DecisionTreeClassifier(max_depth=3, min_samples_leaf=40).fit(tr[feats], tr.stopped)
print('tree test AUC', round(roc_auc_score(te.stopped, t.predict_proba(te[feats])[:, 1]), 3)); print(export_text(t, feature_names=feats, decimals=1, show_weights=True))
X.to_pickle(os.path.join(C, 'p1_crossed_lots.pkl'))
