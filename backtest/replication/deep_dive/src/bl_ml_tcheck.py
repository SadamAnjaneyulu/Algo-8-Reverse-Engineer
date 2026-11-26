"""Learned policies, step 3 (check): the solo-sell threshold was chosen at the grid edge (0.15). Inner cross-fit lot F1 of the sell model for t in 0.02..0.30 on the first out-of-fold training half; and the same cell-level F1 for the decoded spot ladder (1 lot per fire) on those cells, for comparison. Output bl_summary_ml2.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from sklearn.ensemble import HistGradientBoostingClassifier
XS = pd.read_pickle(f'{OUT}/bl_ml_sell.pkl.gz'); MK = pd.read_pickle(f'{OUT}/bl_ml_mkt.pkl.gz'); SC = ['is_ce'] + MK['cols'] + ['own_ratio', 'other_ratio', 'own_lots', 'other_lots']; XS['yc'] = XS.y.clip(upper=5); R = {}
train = [i for i in range(32) if i % 2 == 0]; d = XS[XS.cid.isin(train)]; pos = {c: n % 2 for n, c in enumerate(sorted(train))}; inner = d.cid.map(pos).values; oof = np.zeros((len(d), 6))
for h_ in (0, 1):
    tr = inner == h_; m = HistGradientBoostingClassifier(max_depth=4, learning_rate=0.05, max_iter=200, min_samples_leaf=20, l2_regularization=1.0, random_state=0).fit(d.loc[tr, SC].values.astype(float), d.yc.values[tr]); pr = m.predict_proba(d.loc[~tr, SC].values.astype(float)); f = np.zeros((len(pr), 6)); f[:, m.classes_] = pr; oof[~tr] = f
for t in (0.02, 0.04, 0.06, 0.08, 0.1, 0.125, 0.15, 0.2, 0.3):
    cum = np.stack([oof[:, k:].sum(1) for k in range(1, 6)], 1); n = (cum >= t).sum(1); tp = np.minimum(n, d.y.values).sum(); R[str(t)] = float(2 * tp / (n.sum() + d.y.sum())); print('t', t, 'lots placed', int(n.sum()), 'real', int(d.y.sum()), 'cell lot F1', round(R[str(t)], 3))
n = d.ladder_fire.values.astype(int); tp = np.minimum(n, d.y.values).sum(); R['ladder_rule'] = float(2 * tp / (n.sum() + d.y.sum())); print('decoded ladder (1 lot per fire), same cells: F1', round(R['ladder_rule'], 3)); rec('ml2', R)
