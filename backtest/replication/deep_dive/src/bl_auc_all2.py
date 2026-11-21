"""POST-HOC check for D1_SELLING_AUC_PLAN: the solo-panel book variables (own/other book ratio, own/other short lots) are built from the real past orders (te < minute start), i.e. teacher-forced state.
Variants A0 / B0 = A / B without them (market + timetable + decoded rules + clock only). Same LOCO gradient boosting, AUC with cycle-bootstrap CI, AUC without timetable minutes, AUC by type.
Outputs bl_auc_all2.csv, bl_auc_all2_types.csv, bl_summary_auc2.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from sklearn.metrics import roc_auc_score
from sklearn.ensemble import HistGradientBoostingClassifier
X = pd.read_pickle(f'{OUT}/bl_auc_all_panel.pkl.gz').sort_values(['cid', 'cp', 'j']).reset_index(drop=True); X['is_ce'] = (X.cp == 'CE').astype(int)
BOOK = ['own_ratio', 'other_ratio', 'own_lots', 'other_lots']
MKT = ['react_fire', 'react_fav', 'react_depth', 'pl5_itm', 'pl15_itm', 'pl30_itm', 'pl5_atm', 'pl15_atm', 'pl30_atm', 'fav5', 'bk5', 'bkhl5', 'fav15', 'bk15', 'bkhl15', 'fav30', 'bk30', 'bkhl30', 'fav60', 'bk60', 'bkhl60', 'pos15']
FIX = ['sched_share', 'j', 'hour']; XB = X.copy(); XB[MKT + BOOK] = X.groupby(['cid', 'cp'])[MKT + BOOK].shift(1)
y = X.y.values; cid = X.cid.values; cyc = np.unique(cid); idx = {c_: np.where(cid == c_)[0] for c_ in cyc}; rng = np.random.default_rng(0); nos = (X.sched_share <= 0.5).values
def loco(df, cols):
    M = df[cols + ['is_ce']].values.astype(float); p = np.zeros(len(df))
    for c_ in cyc: te = cid == c_; p[te] = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=150, min_samples_leaf=20, l2_regularization=1.0, random_state=0).fit(M[~te], y[~te]).predict_proba(M[te])[:, 1]
    return p
def ci(p, m):
    out = []
    for _ in range(1000):
        b = np.concatenate([idx[c_] for c_ in rng.choice(cyc, len(cyc))]); b = b[m[b]]; out.append(roc_auc_score(y[b], p[b]))
    return np.percentile(out, [2.5, 97.5])
VAR = {'A0 same-minute, no book state': (X, FIX + MKT), 'B0 causal, no book state': (XB, FIX + MKT), 'timetable + clock only': (X, FIX)}
res = []; typ = []; allm = np.ones(len(y), bool)
for v, (df, cols) in VAR.items():
    p = loco(df, cols); lo, hi = ci(p, allm); lo2, hi2 = ci(p, nos)
    res.append(dict(variant=v, AUC=roc_auc_score(y, p), CI_lo=lo, CI_hi=hi, AUC_without_timetable_minutes=roc_auc_score(y[nos], p[nos]), CI2_lo=lo2, CI2_hi=hi2)); print({k: (round(x, 3) if isinstance(x, float) else x) for k, x in res[-1].items()})
    for t in ('scheduled', 'reactive', 'solo', 'solo after 15:00', 'deep-OTM batch'):
        m = ((X[f'ty_{t}'] == 1) | (X.y == 0)).values; typ.append(dict(variant=v, sell_type=t, positive_cells=int(X[f'ty_{t}'].sum()), AUC=roc_auc_score(y[m], p[m])))
R = pd.DataFrame(res); T = pd.DataFrame(typ); R.round(4).to_csv(f'{OUT}/bl_auc_all2.csv', index=False); T.round(4).to_csv(f'{OUT}/bl_auc_all2_types.csv', index=False); print(T.pivot(index='sell_type', columns='variant', values='AUC').round(3))
rec('auc2', dict(results=R.round(4).to_dict('records'), types=T.round(4).to_dict('records')))
