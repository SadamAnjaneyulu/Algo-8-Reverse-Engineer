"""D0 bursts, lot level (plan reports/D0_BURST_LONG_PLAN.md, Part 1): given a burst minute (>= 5 lots bought back on a right), which open lots does it take, and how many?
Single-feature AUC and precision@m of rankings (within cell), leave-one-cycle-out boosting on lot features, threshold rules 'take every lot ITM >= k steps' / 'ratio >= r' (fitted on training cycles), count rule.
Outputs bl_d0w_burstlots_auc.csv, bl_d0w_burstlots_rules.csv, bl_summary_d0w2b.json"""
import sys, json, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy import stats
from sklearn.ensemble import HistGradientBoostingClassifier as HGB
L = pd.read_pickle(f'{OUT}/bl_d0w_burstlots.pkl.gz'); R = {}; L = L.replace([np.inf, -np.inf], np.nan); L['cell'] = L.cid.astype(str) + '_' + L.j.astype(str) + '_' + L.cp
L['lot_loss'] = L.loss; L['rank_age'] = L.groupby('cell').lid.rank(); L['ratio_rank'] = L.groupby('cell').ratio_prev.rank(pct=True); L['itm_rank'] = L.groupby('cell').itm.rank(pct=True); L['prem_rank'] = L.groupby('cell').px_prev.rank(pct=True)
R['cells'] = int(L.cell.nunique()); R['lots'] = len(L); R['taken'] = int(L.taken.sum()); R['taken_share'] = float(L.taken.mean())
def auc(y, p):
    r = stats.rankdata(p); n1 = y.sum(); n0 = len(y) - n1; return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
FEATS = {'ITM depth (steps)': 'itm', 'price / entry (prev close)': 'ratio_prev', 'premium now': 'px_prev', 'entry price': 'entry', 'unrealised loss (lakh)': 'loss', 'carried from D-1': 'carried', 'strike': 'strike', 'lot id (older = lower)': 'lid'}
rows = []
for nm, col in FEATS.items():
    x = L[col].values.astype(float); ok = np.isfinite(x); y = L.taken.values[ok]; pooled = auc(y, x[ok]); wc = []; pm = []
    for cell, z in L[ok].groupby('cell'):
        k = int(z.taken.sum())
        if 0 < k < len(z): wc.append(auc(z.taken.values, z[col].values)); top = z.sort_values(col, ascending=False).head(k); pm.append(top.taken.mean())
    rows.append(dict(feature=nm, pooled_auc=pooled, within_cell_auc=float(np.mean(wc)), precision_at_m_desc=float(np.mean(pm)), cells=len(wc)))
    # ascending ranking too
    pm2 = []
    for cell, z in L[ok].groupby('cell'):
        k = int(z.taken.sum())
        if 0 < k < len(z): pm2.append(z.sort_values(col, ascending=True).head(k).taken.mean())
    rows[-1]['precision_at_m_asc'] = float(np.mean(pm2))
base_p = float(L.groupby('cell').taken.mean().mean()); R['chance_precision_at_m'] = base_p
# LOCO boosting on lot features
cols = ['itm', 'ratio_prev', 'px_prev', 'entry', 'loss', 'carried', 'itm_rank', 'ratio_rank', 'prem_rank', 'rank_age', 'strike', 'j']; X = L[cols].values.astype(float); y = L.taken.values; cid = L.cid.values; p = np.full(len(L), np.nan)
for c in np.unique(cid):
    tr = cid != c; m = HGB(max_iter=200, max_depth=3, learning_rate=0.05, min_samples_leaf=50, l2_regularization=1.0, random_state=0); m.fit(X[tr], y[tr]); p[~tr] = m.predict_proba(X[~tr])[:, 1]
L['p'] = p; wc = []; pm = []
for cell, z in L.groupby('cell'):
    k = int(z.taken.sum())
    if 0 < k < len(z): wc.append(auc(z.taken.values, z.p.values)); pm.append(z.sort_values('p', ascending=False).head(k).taken.mean())
rows.append(dict(feature='ALL lot features (LOCO boosting)', pooled_auc=auc(y, p), within_cell_auc=float(np.mean(wc)), precision_at_m_desc=float(np.mean(pm)), precision_at_m_asc=np.nan, cells=len(wc)))
pd.DataFrame(rows).round(4).to_csv(f'{OUT}/bl_d0w_burstlots_auc.csv', index=False)
# threshold rules: take every open lot with itm >= k (or ratio >= r), k fitted on training cycles to maximise cell-level F1; also exact fit of the count
def cell_f1(df, col, th):
    tp = fp = fn = 0
    for cell, z in df.groupby('cell'):
        pred = (z[col] >= th).values; t = z.taken.values == 1; tp += (pred & t).sum(); fp += (pred & ~t).sum(); fn += (~pred & t).sum()
    return 2 * tp / max(2 * tp + fp + fn, 1)
rr = []; fit_rows = []
for nm, col, grid in (('take every lot ITM >= k steps', 'itm', np.arange(-3, 12.1, 0.5)), ('take every lot with price/entry >= r', 'ratio_prev', np.arange(0.5, 2.51, 0.1)), ('take every lot with premium >= p (Rs)', 'px_prev', np.array([0.5, 1, 2, 3, 5, 10, 20, 40, 80]))):
    tp = fp = fn = 0; picks = []; exact = 0; ncell = 0; cnt_err = []
    for c in np.unique(cid):
        tr = L[L.cid != c]; te = L[L.cid == c]; g = max(grid, key=lambda t: cell_f1(tr, col, t)); picks.append(float(g))
        for cell, z in te.groupby('cell'):
            pred = (z[col] >= g).values; t = z.taken.values == 1; tp += (pred & t).sum(); fp += (pred & ~t).sum(); fn += (~pred & t).sum(); ncell += 1; exact += int((pred == t).all()); cnt_err.append(abs(pred.sum() - t.sum()))
    rr.append(dict(rule=nm, f1=2 * tp / max(2 * tp + fp + fn, 1), precision=tp / max(tp + fp, 1), recall=tp / max(tp + fn, 1), cells_exact_set=exact / ncell, count_mae=float(np.mean(cnt_err)), param_median=float(np.median(picks)), cells=ncell))
# placebo: random choice of the same number of lots in the cell
rng = np.random.default_rng(5); f = []
for _ in range(20):
    tp = fp = fn = 0
    for cell, z in L.groupby('cell'):
        k = int(z.taken.sum()); idx = rng.choice(len(z), k, replace=False); pred = np.zeros(len(z), bool); pred[idx] = True; t = z.taken.values == 1; tp += (pred & t).sum(); fp += (pred & ~t).sum(); fn += (~pred & t).sum()
    f.append(2 * tp / max(2 * tp + fp + fn, 1))
rr.append(dict(rule='placebo: a random set of the true size', f1=float(np.mean(f)), precision=np.nan, recall=np.nan, cells_exact_set=np.nan, count_mae=0.0, param_median=np.nan, cells=R['cells']))
pd.DataFrame(rr).round(4).to_csv(f'{OUT}/bl_d0w_burstlots_rules.csv', index=False)
rec('d0w2b', R); pd.set_option('display.width', 250); print(json.dumps(R)); print(pd.DataFrame(rows).round(3).to_string()); print(pd.DataFrame(rr).round(3).to_string())
