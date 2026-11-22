"""B6 (post-hoc, after B3/B5): lookback window of the premium breakout, for sales (premium makes a new low) and buy-backs (premium makes a new high, crossing-present cells), bar j.
Outputs bl_d0p_b6.csv, bl_summary_d0p4.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from sklearn.metrics import roc_auc_score
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); PN = pd.read_pickle(f'{OUT}/bl_d0n_panel.pkl.gz'); LP = pd.read_pickle(f'{OUT}/bl_d0p_lotpanel.pkl.gz'); SP = pd.read_pickle(f'{OUT}/bl_d0_spot.pkl.gz'); OPT = pd.read_pickle(f'{OUT}/bl_d0_opt.pkl.gz')
rng = np.random.default_rng(181); WS = (5, 15, 30, 60, 120, 999)
def conds(df, kind, prev=False):
    out = {w: np.zeros(len(df), bool) for w in WS}; cache = {}
    for n, q in enumerate(df.itertuples()):
        i = q.cid; r = CY.iloc[i]
        if i not in cache: cache[i] = (OPT[(r.und, r.expiry)], SP[(r.und, r.expiry)].close.values)
        op, c = cache[i]; Kk = op['K']; j = int(q.j); ai = int(np.argmin(np.abs(Kk - c[j - 1])))
        arr = op[(q.cp, 'low' if kind == 'sale' else 'high')][ai]; cl = op[(q.cp, 'close')][ai]
        for w in WS:
            if prev: prior = cl[max(j - 1 - w, 0):j - 1]; out[w][n] = (cl[j - 1] < np.nanmin(prior)) if kind == 'sale' else (cl[j - 1] > np.nanmax(prior)) if len(prior) else False
            else: prior = arr[max(j - w, 0):j]; out[w][n] = (arr[j] < np.nanmin(prior)) if kind == 'sale' else (arr[j] > np.nanmax(prior))
    return out
rows = []
cs = conds(PN, 'sale')
for w in WS: m = cs[w]; rows.append(dict(side='sale: premium of the sold right makes a new low', window_min=('day' if w == 999 else w), cells=len(PN), share_cells=float(m.mean()), rate_when_on=float(PN.y[m].mean()), rate_when_off=float(PN.y[~m].mean()), auc=float(roc_auc_score(PN.y, m))))
SUB = LP[LP['n_cross_1.4'] > 0].reset_index(drop=True); cb = conds(SUB, 'buy')
for w in WS: m = cb[w]; rows.append(dict(side='buy-back: premium of the stopped right makes a new high (cells with a lot ≥1.4×)', window_min=('day' if w == 999 else w), cells=len(SUB), share_cells=float(m.mean()), rate_when_on=float(SUB.y_bb[m].mean()), rate_when_off=float(SUB.y_bb[~m].mean()), auc=float(roc_auc_score(SUB.y_bb, m))))
cb2 = conds(LP, 'buy')
for w in WS: m = cb2[w]; rows.append(dict(side='buy-back: premium of the stopped right makes a new high (all cells)', window_min=('day' if w == 999 else w), cells=len(LP), share_cells=float(m.mean()), rate_when_on=float(LP.y_bb[m].mean()), rate_when_off=float(LP.y_bb[~m].mean()), auc=float(roc_auc_score(LP.y_bb, m))))
for nm, df, kind, yy in (('sale (decision-time, close of j-1 below the prior closes)', PN, 'sale', 'y'), ('buy-back (decision-time, close of j-1 above the prior closes; cells with a lot ≥1.4×)', SUB, 'buy', 'y_bb')):
    cp_ = conds(df, kind, prev=True)
    for w in WS: m = cp_[w]; rows.append(dict(side=nm, window_min=('day' if w == 999 else w), cells=len(df), share_cells=float(m.mean()), rate_when_on=float(df[yy][m].mean()), rate_when_off=float(df[yy][~m].mean()), auc=float(roc_auc_score(df[yy], m))))
B6 = pd.DataFrame(rows); B6.to_csv(f'{OUT}/bl_d0p_b6.csv', index=False); print(B6.round(3).to_string(index=False)); rec('d0p4', dict(b6=B6.round(4).to_dict('records')))
