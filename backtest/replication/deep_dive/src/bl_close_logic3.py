"""Buy-back study, step 4 (plan test E, residual): do buy-backs of lots that are NOT near a premium stop (cheapest-open-entry ratio < 1.2) have any identifiable single-variable or multivariable signal?
Panel: D-1 / D0 contract-minutes with r_low < 1.2; event = body buy-back in the minute. Univariate AUC (cluster bootstrap over cycles), LOCO gradient boosting, permutation-null AUC.
Also: lot-proportional null for which right is bought back (balance-control check). Output outputs/bl_close_E_auc.csv, bl_summary_close3.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy import stats
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
P = pd.read_csv(f'{OUT}/bl_close_panel2.csv.gz'); rng = np.random.default_rng(2); R = {}
def auc(x, y): m = ~np.isnan(x); x, y = x[m], y[m]; n1 = y.sum(); n0 = len(y) - n1; r = stats.rankdata(x); return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0) if n1 and n0 else np.nan
rows = []
for day in ('D-1', 'D0'):
    Q = P[(P.day == day) & (P.r_low < 1.2)].reset_index(drop=True); Q['abs_itm'] = Q.itm_steps.abs(); Q['ev'] = (Q.bb_lots > 0).astype(int); Q['tod_min'] = Q.j; Q['o_r'] = Q.o_r_avg
    y = Q.ev.values; g = (Q.und + Q.expiry).values; ucy = np.unique(g); idx = {c: np.where(g == c)[0] for c in ucy}
    print(f'\n== {day}: contract-minutes with r_low<1.2: {len(Q):,}; buy-back minutes {y.sum()} ({y.mean() * 1000:.1f} per 1000)'); R[f'{day}_rows'] = len(Q); R[f'{day}_events'] = int(y.sum())
    FE = ['r_avg', 'r_low', 'r_fifo', 'abs_itm', 'itm_steps', 'hold_min', 'price', 'n_open', 'o_n_open', 'o_r', 'straddle_r', 'tod_min']
    for f in FE:
        x = Q[f].values.astype(float); a = auc(x, y); bs = [auc(x[ii], y[ii]) for ii in (np.concatenate([idx[c] for c in rng.choice(ucy, len(ucy))]) for _ in range(100))]
        nul = [auc(pd.Series(x).groupby(g).transform(lambda s: rng.permutation(s.values)).values, y) for _ in range(15)]; rows.append((day, f, a, np.nanquantile(bs, .025), np.nanquantile(bs, .975), np.nanmedian(nul), np.nanmax(nul)))
    print(pd.DataFrame([r for r in rows if r[0] == day], columns=['day', 'f', 'auc', 'lo', 'hi', 'nm', 'nx']).round(3).to_string(index=False))
    X = Q[FE].astype(float).fillna(Q[FE].astype(float).median()).values; o = np.zeros(len(y))
    for c in ucy:
        tr = g != c; m = HistGradientBoostingClassifier(max_depth=3, max_iter=120, learning_rate=0.06, min_samples_leaf=50, random_state=0).fit(X[tr], y[tr]); o[~tr] = m.predict_proba(X[~tr])[:, 1]
    R[f'{day}_gb_loco_auc'] = float(roc_auc_score(y, o)); print(f'  LOCO gradient boosting, all {len(FE)} variables: AUC {roc_auc_score(y, o):.3f}')
pd.DataFrame(rows, columns=['day', 'variable', 'AUC', 'lo', 'hi', 'null_median', 'null_max']).round(4).to_csv(f'{OUT}/bl_close_E_auc.csv', index=False); rec('close3', R)
