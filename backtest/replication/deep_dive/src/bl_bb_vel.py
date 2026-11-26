"""Buy-back decode step 5: velocity variables on the contract-minute panel: own premium rise over the last n minutes (previous close / close n minutes earlier; current high / close n minutes earlier), spot move against over n minutes (steps), for n = 1, 2, 3, 5.
Univariate AUC and out-of-fold threshold F1 (contract-minute, same minute and +-1 minute), then OR-combinations of the entry stop (rh_min >= a) with one velocity condition (>= b), (a, b) chosen on the other cycle half.
Outputs bl_bb_vel.csv, bl_bb_combo.csv, bl_summary_bb5.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy.stats import rankdata
import bl_sd_build, bl_ohlc
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); OP = bl_sd_build.load_opt(); OH = bl_ohlc.load(); X = pd.read_pickle(f'{OUT}/bl_bb_panel.pkl.gz'); R = {}
for i, r in enumerate(CY.itertuples()):
    m = (X.cid == i).values
    if not m.any(): continue
    op = OP[(r.und, r.expiry)]; K = op['K']; ki = {int(k): x for x, k in enumerate(K)}; c = OH[(r.und, r.expiry)].close.values; st = ref.STEP[r.und]
    xi = np.array([ki[int(k)] for k in X.strike.values[m]]); jj = X.j.values[m]; isce = (X.cp.values[m] == 'CE'); sg = np.where(isce, 1, -1)
    C = np.where(isce[:, None], op[('CE', 'close')][xi], op[('PE', 'close')][xi]); H = np.where(isce[:, None], op[('CE', 'high')][xi], op[('PE', 'high')][xi]); ar = np.arange(len(xi))
    for n in (1, 2, 3, 5):
        base = C[ar, np.maximum(jj - 1 - n, 0)]
        X.loc[m, f'vel_c{n}'] = C[ar, jj - 1] / base; X.loc[m, f'vel_h{n}'] = H[ar, jj] / base; X.loc[m, f'spot_adv{n}'] = sg * (c[jj - 1] - c[np.maximum(jj - 1 - n, 0)]) / st
y = X.y.values; h = X.cid.values % 2 == 0
def auc(s, y): m = ~np.isnan(s); s, yy = s[m], y[m]; n1 = yy.sum(); n0 = len(yy) - n1; return (rankdata(s)[yy == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
key = X.cid.astype(np.int64) * 10**8 + X.strike.astype(np.int64) * 10 + (X.cp == 'CE').astype(int); X['key'] = key; pos = set(zip(X.key[X.y == 1], X.j[X.y == 1]))
def f1_tol(fire, idx):
    f = set(zip(X.key.values[idx][fire[idx]], X.j.values[idx][fire[idx]])); p = {(k, j) for (k, j) in pos if True}; ys = set(zip(X.key.values[idx][y[idx] == 1], X.j.values[idx][y[idx] == 1]))
    tp_f = sum(1 for (k, j) in f if (k, j) in ys or (k, j - 1) in ys or (k, j + 1) in ys); tp_y = sum(1 for (k, j) in ys if (k, j) in f or (k, j - 1) in f or (k, j + 1) in f)
    pr = tp_f / max(len(f), 1); rc = tp_y / max(len(ys), 1); return 2 * pr * rc / max(pr + rc, 1e-9)
VARS = [f'{a}{n}' for a in ('vel_c', 'vel_h', 'spot_adv') for n in (1, 2, 3, 5)] + ['rh_min', 'rc_min']; out = []
for v in VARS:
    s = X[v].values.astype(float); s = np.where(np.isnan(s), -1e9, s); grid = np.unique(np.quantile(s[s > -1e9], np.linspace(0.9, 0.999, 60))); oof = []
    for tr in (h, ~h):
        t = max(grid, key=lambda t: f1_tol(s >= t, tr)); oof.append((t, f1_tol(s >= t, ~tr)))
    out.append(dict(variable=v, AUC=auc(X[v].values.astype(float), y), thr=f'{oof[0][0]:.3f}/{oof[1][0]:.3f}', F1_pm1_oof=np.mean([o[1] for o in oof]))); print(out[-1])
T = pd.DataFrame(out).sort_values('F1_pm1_oof', ascending=False); T.round(4).to_csv(f'{OUT}/bl_bb_vel.csv', index=False)
# OR combos: entry stop (rh_min >= a) OR velocity (v >= b)
A = np.arange(1.45, 1.80, 0.025); best_rows = []
for v in [x for x in T.variable if x not in ('rh_min', 'rc_min')][:4]:
    s = X[v].values.astype(float); s = np.where(np.isnan(s), -1e9, s); B = np.unique(np.quantile(s[s > -1e9], np.linspace(0.95, 0.999, 25))); rh = X.rh_min.values; oof = []
    for tr in (h, ~h):
        ab = max(((a, b) for a in A for b in B), key=lambda ab: f1_tol((rh >= ab[0]) | (s >= ab[1]), tr)); oof.append((ab, f1_tol((rh >= ab[0]) | (s >= ab[1]), ~tr)))
    best_rows.append(dict(rule=f'rh_min >= a OR {v} >= b', params=str([(round(o[0][0], 3), round(o[0][1], 3)) for o in oof]), F1_pm1_oof=np.mean([o[1] for o in oof]))); print(best_rows[-1])
CB = pd.DataFrame(best_rows); CB.round(4).to_csv(f'{OUT}/bl_bb_combo.csv', index=False); X.to_pickle(f'{OUT}/bl_bb_panel.pkl.gz'); R['vars'] = T.round(4).to_dict('records'); R['combos'] = CB.round(4).to_dict('records'); rec('bb5', R)
