"""P4d: add book-state features to the candidate strike model.   python3 analysis/p4_book.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
import lightgbm as lgb
from sklearn.tree import DecisionTreeClassifier, export_text
from load import load_tagged
from math import erf, sqrt
C = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_cache')
X = pd.read_pickle(os.path.join(C, 'p4_candidates.pkl'))
f = pd.read_pickle(os.path.join(C, 'p4_orders_cons.pkl')).set_index('oid'); f['K0'] = (f.prev_close / f.step).round() * f.step
d = load_tagged().sort_values(['t', 'row'])
# snapshot book before each body sell order (oid in f)
want = set(f.index); snaps = {}; pos = {}; cur = None
for r in d.itertuples():
    ck = (r.und, r.expiry)
    if ck != cur: pos = {}; cur = ck
    if r.oid in want and r.oid not in snaps:
        snaps[r.oid] = {k: v for k, v in pos.items() if abs(v) > 1e-9}
    pos[(r.cp, r.strike)] = pos.get((r.cp, r.strike), 0.0) + r.sl
def ncdf(x): return 0.5 * (1 + erf(x / sqrt(2)))
def delta(cp, K, S, sig):   # crude BS delta, 1-day vol scale; sig = daily move fraction
    z = np.log(S / K) / max(sig, 1e-6)
    return ncdf(z) if cp == 'CE' else ncdf(z) - 1
feat = []
for oid, g in X.groupby('oid'):
    r = f.loc[oid]; book = snaps.get(oid, {}); S = r.prev_close; sig = 0.007 if r.day == 'D-1' else 0.004
    shortCE = -sum(v for (cp, k), v in book.items() if cp == 'CE' and v < 0); shortPE = -sum(v for (cp, k), v in book.items() if cp == 'PE' and v < 0)
    sk = [(k, -v) for (cp, k), v in book.items() if v < 0 and cp == r.cp]
    avgK = (sum(k * w for k, w in sk) / sum(w for _, w in sk)) if sk else S
    netdelta = sum(v * delta(cp, k, S, sig) for (cp, k), v in book.items())
    for idx, row in g.iterrows():
        K = r.K0 + row.j * r.step
        inv = -book.get((r.cp, K), 0.0)
        dK = delta(r.cp, K, S, sig)
        feat.append(dict(idx=idx, inv_at_K=inv, imb=(shortCE - shortPE) * (1 if r.cp == 'CE' else -1), avgK_dev=(avgK - S) / r.step * (1 if r.cp == 'CE' else -1),
                         netdelta=netdelta, nd_after=abs(netdelta - dK), nd_improve=abs(netdelta) - abs(netdelta - dK), booksize=shortCE + shortPE))
F = pd.DataFrame(feat).set_index('idx'); X = X.join(F)
X['rk_nd_after'] = X.groupby('oid').nd_after.rank(method='min')
dates = sorted(X.date.unique()); cut = dates[int(len(dates) * 0.6)]
base_feats = ['j', 'j_otm', 'frac', 'mv3', 'mv10', 'mv15', 'prem_rel_atm', 'd_Tprev', 'd_Thalf', 'd_bbE', 'rk_d_Tprev', 'rk_d_Thalf', 'rk_d_bbE', 'is_prevK', 'is_bbK', 'bb_dt', 'grid', 'mins', 'day01']
book_feats = ['inv_at_K', 'imb', 'avgK_dev', 'netdelta', 'nd_after', 'nd_improve', 'booksize', 'rk_nd_after']
tr, te = X[X.date < cut], X[X.date >= cut]
def top1(df, s):
    b = df.assign(s=s).loc[lambda z: z.groupby('oid').s.idxmax()]; return b.label.mean(), b
for name, fs in [('base', base_feats), ('base+book', base_feats + book_feats), ('book+clock only', ['j', 'j_otm', 'frac', 'grid', 'mins', 'day01'] + book_feats)]:
    m = lgb.LGBMClassifier(n_estimators=500, learning_rate=0.04, num_leaves=31, min_child_samples=40, subsample=0.8, subsample_freq=1, colsample_bytree=0.8, verbose=-1).fit(tr[fs], tr.label)
    a, b = top1(te, m.predict_proba(te[fs])[:, 1])
    seg = b.assign(seg=b.day01.map({0: 'D-1', 1: 'D0'}) + np.where(b.grid == 1, '-grid', '-off')).groupby('seg').label.mean().round(3).to_dict()
    imp = pd.Series(m.booster_.feature_importance('gain'), index=fs); imp = (imp / imp.sum()).sort_values(ascending=False).round(3)
    print(f'{name:16s} test top-1 {a:.3f}  {seg}\n   top features {imp.head(8).to_dict()}')
X.to_pickle(os.path.join(C, 'p4_candidates_book.pkl'))
