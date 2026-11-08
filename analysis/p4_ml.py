"""P4c: ML strike selector (candidate-choice model).   python3 analysis/p4_ml.py
One row per (order, candidate strike K0-3..K0+3). Label = candidate is the strike actually sold.
Chronological split by session date (first 60% train / last 40% test). Models: LightGBM ranker-as-binary, shallow decision tree.
Score = per-order top-1 accuracy on test. Baseline = nearest ATM from previous-minute index close."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
import lightgbm as lgb
from sklearn.tree import DecisionTreeClassifier, export_text
C = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_cache')
f = pd.read_pickle(os.path.join(C, 'p4_orders_prem.pkl')).sort_values('t').reset_index(drop=True)
op = pd.read_pickle(os.path.join(C, 'opt_candles.pkl'))
pc = op.assign(m=op.ts + pd.Timedelta(minutes=1)).set_index(['und', 'expiry', 'cp', 'm', 'strike']).c.sort_index()
bb = pd.read_pickle(os.path.join(C, 'buyback_events.pkl')).sort_values('t')   # body/stop buy-backs with cheapest-entry info
bb = bb[bb.tp == 'num']
# previous body sale strike of same leg (sticky strike) and last same-leg buy-back within 15 min
f['prevK'] = f.groupby(['date', 'cp']).strike.shift(1)
f['prevK_other'] = np.nan
rows = []
for r in f.itertuples():
    b = bb[(bb.und == r.und) & (bb.date == r.date) & (bb.cp == r.cp) & (bb.t < r.t) & (bb.t >= r.t - pd.Timedelta(minutes=15))]
    bK = b.strike.iloc[-1] if len(b) else np.nan; bE = b.min_e.iloc[-1] if len(b) else np.nan
    bdt = (r.t - b.t.iloc[-1]).total_seconds() / 60 if len(b) else 99
    for j in range(-3, 4):
        K = r.K0 + j * r.step
        p = pc.get((r.und, r.expiry, r.cp, r.m, K), np.nan)
        if not np.isfinite(p): continue
        mono = 1 if r.cp == 'CE' else -1   # +1 step = further OTM for CE, further ITM for PE
        rows.append(dict(oid=r.oid, date=r.date, und=r.und, cp=r.cp, day=r.day, grid=int(r.grid), label=int(K == r.strike),
                         j=j, j_otm=j * mono, frac=r.frac * mono, mv3=r.mv3 / r.prev_close * 1e4 * mono, mv10=r.mv10 / r.prev_close * 1e4 * mono,
                         mv15=r.mv15 / r.prev_close * 1e4 * mono,
                         prem=p, prem_rel_atm=p / r.p_atm if r.p_atm else np.nan,
                         d_Tprev=abs(p - r.T_prev) / r.T_prev if np.isfinite(r.T_prev) and r.T_prev else np.nan,
                         d_Thalf=abs(p - r.T_half) / r.T_half if np.isfinite(r.T_half) and r.T_half else np.nan,
                         d_bbE=abs(p - bE) / bE if np.isfinite(bE) and bE else np.nan,
                         is_prevK=int(K == r.prevK), is_bbK=int(K == bK), bb_dt=bdt, mins=(r.t.hour * 60 + r.t.minute) - 555))
X = pd.DataFrame(rows)
# rank features within order
for c in ['d_Tprev', 'd_Thalf', 'd_bbE']:
    X['rk_' + c] = X.groupby('oid')[c].rank(method='min')
dates = sorted(X.date.unique()); cut = dates[int(len(dates) * 0.6)]
tr, te = X[X.date < cut], X[X.date >= cut]
feats = ['j', 'j_otm', 'frac', 'mv3', 'mv10', 'mv15', 'prem_rel_atm', 'd_Tprev', 'd_Thalf', 'd_bbE', 'rk_d_Tprev', 'rk_d_Thalf', 'rk_d_bbE',
         'is_prevK', 'is_bbK', 'bb_dt', 'grid', 'mins']
X['day01'] = (X.day == 'D0').astype(int); feats.append('day01')
tr, te = X[X.date < cut], X[X.date >= cut]
def top1(df, score):
    df = df.assign(s=score); best = df.loc[df.groupby('oid').s.idxmax()]
    return best.label.mean(), best
m = lgb.LGBMClassifier(n_estimators=400, learning_rate=0.05, num_leaves=31, min_child_samples=40, subsample=0.8, colsample_bytree=0.8, verbose=-1)
m.fit(tr[feats], tr.label)
acc, best = top1(te, m.predict_proba(te[feats])[:, 1])
base, _ = top1(te, -te.j.abs() + 0.001 * np.random.RandomState(0).rand(len(te)))
print(f'train dates < {cut.date()}  | test orders {te.oid.nunique()}')
print(f'baseline nearest-ATM top-1 on test: {base:.3f}   LightGBM top-1 on test: {acc:.3f}')
best = best.assign(seg=best.day + np.where(best.grid == 1, '-grid', '-offgrid'))
print('LightGBM test accuracy by segment:', best.groupby('seg').label.mean().round(3).to_dict())
imp = pd.Series(m.booster_.feature_importance('gain'), index=feats).sort_values(ascending=False)
print('gain importance:', (imp / imp.sum()).round(3).head(10).to_dict())
for depth in [3, 4, 5]:
    t = DecisionTreeClassifier(max_depth=depth, min_samples_leaf=50, class_weight='balanced').fit(tr[feats].fillna(-1), tr.label)
    a, _ = top1(te, t.predict_proba(te[feats].fillna(-1))[:, 1] + 1e-6 * -te.j.abs())
    print(f'decision tree depth {depth}: test top-1 {a:.3f}')
    if depth == 4: print(export_text(t, feature_names=feats, decimals=3))
X.to_pickle(os.path.join(C, 'p4_candidates.pkl'))
