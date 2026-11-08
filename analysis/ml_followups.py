"""Reproduces the follow-up checks quoted in FINDINGS §0b (run after p1-p5 scripts have built their caches).
python3 analysis/ml_followups.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd, lightgbm as lgb
from sklearn.model_selection import GroupKFold, LeaveOneOut, cross_val_predict
from sklearn.metrics import roc_auc_score
from sklearn.linear_model import RidgeCV
from sklearn.ensemble import RandomForestRegressor
from load import load_tagged
C = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_cache')
d = load_tagged(); d['m'] = d.t.dt.floor('min')

print('=== P4: strike consistent with nearest-to-live-index at some price in decision+previous minute ===')
f = pd.read_pickle(os.path.join(C, 'p4_orders_cons.pkl'))
print(f.groupby(['day', 'grid']).cons.mean().round(3).to_dict())

print('\n=== P3: leg-timer gating (D-1 minutes 13.5-15.5 min after previous same-side sale) ===')
X = pd.read_pickle(os.path.join(C, 'p3_minutes.pkl'))
x = X[(X.d0 == 0) & X.since_sale_same.between(13.5, 15.5)].copy()
feats = ['mins', 'ux', 'ce', 'mv1', 'mv3', 'mv5', 'mv10', 'mv15', 'rng15', 'dist_lastK', 'dist_avgK', 'since_sale_any', 'since_stop_same', 'since_stop_other', 'shortlots', 'imb', 'prem_chg']
p = np.zeros(len(x))
for trn, tst in GroupKFold(5).split(x, x.label, x.date.astype(str)):
    p[tst] = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.03, num_leaves=7, min_child_samples=20, verbose=-1).fit(x.iloc[trn][feats], x.iloc[trn].label).predict_proba(x.iloc[tst][feats])[:, 1]
print('n', len(x), 'fire rate', round(x.label.mean(), 3), 'grouped-CV AUC', round(roc_auc_score(x.label, p), 3))
print(x.groupby(pd.cut(x.mins, [0, 60, 120, 180, 240, 300, 360])).label.mean().round(2).to_dict())
w = x[(x.mins > 252) & (x.mins <= 320)]
print('13:28-14:36 & no sale on any side for >14.5 min: fire rate', round(w[w.since_sale_any > 14.5].label.mean(), 3), 'n', int((w.since_sale_any > 14.5).sum()))

print('\n=== P2: D0 exit clock, rolls, same-contract churn ===')
Y = pd.read_pickle(os.path.join(C, 'p2_contract_minutes.pkl'))
Y['off'] = ((Y.m.dt.hour * 60 + Y.m.dt.minute) - (9 * 60 + 15)) % 15
Y['blk'] = pd.cut(Y.mins, [0, 240, 300, 330, 360], labels=['<13:15', '13:15-14:15', '14:15-14:45', '14:45-15:15'])
print(Y.assign(is14=Y.off == 14).groupby(['blk', 'is14'], observed=True).label.mean().unstack().round(4).to_dict())
pos = Y[Y.label == 1].copy()
pos['mech'] = np.select([pos.r_min >= 1.45, (pos.r_mean <= 0.05) | (pos.px <= 1.0), (pos.off == 14) & (pos.mins >= 240)], ['stop', 'salvage', 'clock'], 'other')
print('mechanism shares', pos.mech.value_counts(normalize=True).round(3).to_dict())
sells = d[(d.tp == 'num') & (d.side == 'Sell') & (d.dte == 0) & (d.px_fill >= 5)]
sm1 = set((a, b + pd.Timedelta(minutes=k), c) for a, b, c in zip(sells.date, sells.m, sells.cp) for k in (-1, 0, 1))
neg = Y[Y.label == 0].sample(60000, random_state=0)
print('same-side sale within 1 min: exit minutes', round(np.mean([(a, b, c) in sm1 for a, b, c in zip(pos.date, pos.m, pos.cp)]), 3),
      'non-exit minutes', round(np.mean([(a, b, c) in sm1 for a, b, c in zip(neg.date, neg.m, neg.cp)]), 3))
b = d[(d.tp == 'num') & (d.dte == 0)].sort_values('t'); cnt = tot = 0
for _, z in b.groupby(['date', 'cp', 'strike']):
    bt = z[z.side == 'Buy'].t.values; st = z[z.side == 'Sell'].t.values; tot += len(bt)
    if len(bt) and len(st): cnt += sum(np.min(np.abs(st - t)) <= np.timedelta64(120, 's') for t in bt)
print(f'D0 body buy fills with same-contract sale within 2 min: {cnt}/{tot} = {cnt / tot:.3f}')

print('\n=== P5: lump-size predictability (leave-one-out) ===')
A = pd.read_pickle(os.path.join(C, 'p5_lumps.pkl')); B = pd.read_pickle(os.path.join(C, 'p5_budget.pkl'))
R = B.merge(A[['date', 'imb', 'short_tot', 'netD', 'dL', 'pL']], on='date', how='left'); R = R[R.lots >= 2].copy()
R['dlots'] = (R.netD.abs() / R.dL.abs()).replace([np.inf], np.nan)
Z = pd.DataFrame({'lc': np.log(R.credit.clip(lower=1)), 'lsv': np.log(R.short_val_side), 'lsp': np.log(R.sell_prem), 'imb': R.imb, 'st': R.short_tot,
                  'ldl': np.log1p(R.dlots.fillna(R.dlots.median())), 'lpL': np.log(R.pL.fillna(R.pL.median())), 'ux': (R.und == 'SENSEX').astype(int)})
y = np.log(R.lots)
for name, mdl in [('ridge', RidgeCV(alphas=np.logspace(-2, 3, 20))), ('random forest', RandomForestRegressor(300, min_samples_leaf=3, random_state=0))]:
    pr = cross_val_predict(mdl, Z, y, cv=LeaveOneOut()); print(name, 'LOO median abs % error', round(np.median(np.abs(np.exp(pr) - R.lots) / R.lots), 2))
print('naive per-index median: ', round(np.median(np.abs(R.groupby('und').lots.transform('median') - R.lots) / R.lots), 2))
for base in ['credit', 'sell_prem', 'short_val_side']:
    r = R.cost / R[base]; print(f'lump cost/{base}: median {r.median():.4f} CV {r.std() / r.mean():.2f}')
