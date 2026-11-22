"""Buy-back decode step 8: what triggers the LOW-ratio buy-backs (first ratio < 1.45; half of the events)?
Contract-minute panel without stop-like rows. Label = a low-ratio buy-back event starts on the contract in the minute. Candidate variables:
whole-book delta (all modules, Black-Scholes from the ATM straddle) signed so that + means the book is short in this right's direction (buying it back reduces risk); |delta|;
strike breach (spot crossed the sold strike in the adverse direction within the last 1/3/5 minutes); ITM depth and |ITM|; own ratio; premium speed; minute; right lot imbalance; time since the last sale on the contract.
AUC, out-of-fold threshold F1 (+-1 min), depth-3 tree. Outputs bl_bb_low.csv, bl_summary_bb8.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy.stats import rankdata
from sklearn.tree import DecisionTreeClassifier, export_text
src = open('bl_bk_build.py').read().split('def feats')[0]; exec(src)
import bl_ohlc
OH = bl_ohlc.load(); CYs = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); X = pd.read_pickle(f'{OUT}/bl_bb_panel.pkl.gz'); G = pd.read_csv(f'{OUT}/bl_bb_eventlevel.csv'); R = {}
G['j'] = ((G.te - 33300) // 60).astype(int); low = set(zip(G[G.r_first < 1.45].cid, G[G.r_first < 1.45].cp, G[G.r_first < 1.45].strike, G[G.r_first < 1.45].j))
X['y_low'] = [int((c_, cp, k, j) in low) for c_, cp, k, j in zip(X.cid, X.cp, X.strike, X.j)]; X = X[~((X.y == 1) & (X.y_low == 0))].copy()
dl = {}
for i, r in enumerate(CYs.itertuples()):
    cb = CycleBook(r.und, r.expiry, r.unit); c = OH[(r.und, r.expiry)].close.values
    for j in range(2, 375): st_ = cb.state(33300 + 60 * j, c[j - 1], j - 1); dl[(i, j)] = st_.get('delta', np.nan)
X['delta_book'] = [dl.get((c_, j), np.nan) for c_, j in zip(X.cid, X.j)]; sg = np.where(X.cp == 'CE', 1, -1); X['delta_short_dir'] = -sg * X.delta_book   # + = book loses if spot moves toward this right's ITM side
for n in (1, 3, 5):
    X[f'breach{n}'] = 0
    for i, r in enumerate(CYs.itertuples()):
        m = (X.cid == i).values
        if not m.any(): continue
        c = OH[(r.und, r.expiry)].close.values; jj = X.j.values[m]; k = X.strike.values[m]; s = sg[m]
        now = s * (c[jj - 1] - k) > 0; before = s * (c[np.maximum(jj - 1 - n, 0)] - k) > 0; X.loc[m, f'breach{n}'] = (now & ~before).astype(int)
X['abs_itm'] = X.itm.abs(); y = X.y_low.values; h = X.cid.values % 2 == 0; print(X.shape, 'low events', int(y.sum()))
def auc(s, yy): m = ~np.isnan(s); s, yy = s[m], yy[m]; n1 = yy.sum(); n0 = len(yy) - n1; return (rankdata(s)[yy == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
VARS = ['delta_short_dir', 'delta_book', 'breach1', 'breach3', 'breach5', 'itm', 'abs_itm', 'rc_min', 'rh_min', 'vel_h3', 'vel_h5', 'spot_adv3', 'minute', 'n_open', 'min_since_last_sale', 'right_ratio']
U = pd.DataFrame([dict(variable=v, AUC=auc(X[v].values.astype(float), y), AUC_even=auc(X[v].values[h].astype(float), y[h]), AUC_odd=auc(X[v].values[~h].astype(float), y[~h])) for v in VARS]); U['s'] = (U.AUC - .5).abs(); U = U.sort_values('s', ascending=False).drop(columns='s'); print(U.round(3).to_string(index=False))
for v, b in (('delta_short_dir', [-99, -20, -10, -5, 0, 5, 10, 20, 99]), ('abs_itm', [0, .25, .5, 1, 2, 99])): hz = X.groupby(pd.cut(X[v], b), observed=True).y_low.agg(['mean', 'size']); R[f'hz_{v}'] = {str(k): [round(float(a), 4), int(n)] for k, (a, n) in hz.iterrows()}; print(v, R[f'hz_{v}'])
print('breach3 hazard', X.groupby('breach3').y_low.mean().round(4).to_dict())
Xm = X[VARS].fillna(-99).values; pr = np.zeros(len(y))
for tr in (h, ~h): pr[~tr] = DecisionTreeClassifier(max_depth=3, min_samples_leaf=300, class_weight={0: 1, 1: 15}, random_state=0).fit(Xm[tr], y[tr]).predict(Xm[~tr])
tp = (pr.astype(bool) & (y == 1)).sum(); R['tree'] = dict(F1=float(2 * tp / (pr.sum() + y.sum())), precision=float(tp / max(pr.sum(), 1)), recall=float(tp / y.sum())); print('tree OOF', R['tree'])
print(export_text(DecisionTreeClassifier(max_depth=3, min_samples_leaf=300, class_weight={0: 1, 1: 15}, random_state=0).fit(Xm, y), feature_names=VARS))
U.round(4).to_csv(f'{OUT}/bl_bb_low.csv', index=False); R['auc'] = U.round(4).to_dict('records'); rec('bb8', R)
