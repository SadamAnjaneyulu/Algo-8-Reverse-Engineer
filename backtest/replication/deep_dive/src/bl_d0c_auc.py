"""AUC gate for D0 counter-sell cells (plan reports/D0_CAUC_PLAN.md). Outputs bl_d0c_auc.csv, bl_d0c_auc_cyc.csv, bl_summary_d0c1.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from sklearn.ensemble import HistGradientBoostingClassifier as HGB
from sklearn.metrics import roc_auc_score, average_precision_score
PN = pd.read_pickle(f'{OUT}/bl_d0n_panel.pkl.gz'); SO = pd.read_pickle(f'{OUT}/bl_d0n_orders.pkl.gz'); rng = np.random.default_rng(191); R = {}
cn = SO[(SO.row >= 0) & (SO.type == 'counter-sell solo')].groupby('row').lots.sum(); PN['y_counter'] = PN.row.map(cn).fillna(0).gt(0).astype(float); PN['y_counter_lots'] = PN.row.map(cn).fillna(0)
print('cells', len(PN), 'counter cells', int(PN.y_counter.sum()), 'any-solo cells', int(PN.y.sum()))
G = dict(base=['hour', 'min_in_15', 'min_in_5', 'is_ce', 'und_nifty', 'v2', 'j'],
    spot=['fav_ret_1', 'fav_ret_3', 'fav_ret_5', 'fav_ret_15', 'fav_ret_30', 'fav_ret_60', 'fresh_15', 'fresh_30', 'fresh_60', 'fresh_120', 'fresh_day', 'dist_day_ext', 'from_open', 'vol15', 'bars_since_fresh60'],
    prem=['atm_px', 'prem_chg_1', 'prem_chg_3', 'prem_chg_5', 'prem_chg_15', 'prem_vs_daymax', 'prem_vs_daymin', 'prem_vs_open', 'mark_own', 'mark_other', 'phx_prem_low_15', 'phx_prem_low_30', 'phx_prem_low_60', 'phx_prem_low_day'],
    book=['n_own', 'n_other', 'share_own', 'expo_own', 'expo_other', 'expo_share_own', 'mtm_lakh', 'mtm_to_stop', 'sell_own_1', 'sell_own_5', 'sell_own_15', 'sell_other_1', 'sell_other_5', 'sell_other_15', 'since_sale_own'],
    bb=['bb_other_1', 'bb_other_5', 'bb_other_15', 'bb_own_1', 'bb_own_5', 'bb_own_15', 'sl_other_1', 'sl_other_5', 'sl_other_15', 'sl_own_1', 'sl_own_5', 'sl_own_15', 'since_bb_other'],
    cont=['fav_ret_1_c', 'fav_ret_3_c', 'fresh_60_c', 'range_c', 'prem_chg_1_c', 'phx_prem_newlow_c', 'phx_plow_bar_c'], same=['bb_other_same_min', 'sl_other_same_min', 'bb_own_same_min'])
VAR = {'V1 causal (bars to j-1, orders before minute j)': ['base', 'spot', 'prem', 'book', 'bb'], 'V2 + the minute\'s own bar': ['base', 'spot', 'prem', 'book', 'bb', 'cont'], 'V3 + same-minute buy-backs (partly definitional)': ['base', 'spot', 'prem', 'book', 'bb', 'cont', 'same']}
mk = lambda: HGB(max_iter=200, max_depth=3, learning_rate=0.05, min_samples_leaf=50, l2_regularization=1.0, random_state=0)
def loco(df, cols, y, perm=False):
    Xm = df[cols].values.copy(); yv = df[y].values; p = np.full(len(df), np.nan)
    if perm:
        for c_ in df.cid.unique(): m = np.where((df.cid == c_).values)[0]; Xm[m] = Xm[rng.permutation(m)]
    for c_ in df.cid.unique():
        te = (df.cid == c_).values
        if len(set(yv[~te])) < 2: continue
        p[te] = mk().fit(Xm[~te], yv[~te]).predict_proba(Xm[te])[:, 1]
    return p
def score(df, p, y, nb=300):
    ok = ~np.isnan(p); d = df[ok].reset_index(drop=True); pp = p[ok]; u = d.cid.unique(); idx = {c_: np.where(d.cid.values == c_)[0] for c_ in u}; a = []; b = []
    for _ in range(nb):
        k = np.concatenate([idx[c_] for c_ in rng.choice(u, len(u))]); v = d[y].values[k]
        if v.min() != v.max(): a.append(roc_auc_score(v, pp[k])); b.append(average_precision_score(v, pp[k]))
    cyc = []
    for c_ in u:
        i = idx[c_]; v = d[y].values[i]
        if v.sum() >= 5 and v.sum() < len(v): cyc.append(roc_auc_score(v, pp[i]))
    return dict(auc=roc_auc_score(d[y], pp), lo=np.percentile(a, 2.5), hi=np.percentile(a, 97.5), prauc=average_precision_score(d[y], pp), within_cycle_auc=float(np.mean(cyc)), within_cycle_cycles=len(cyc), positive_rate=float(d[y].mean()))
rows = []; PP = {}
for y in ('y_counter', 'y'):
    for nm, gs in VAR.items():
        cols = sum([G[g] for g in gs], []); p = loco(PN, cols, y); PP[(y, nm)] = p; sc = score(PN, p, y); rows.append(dict(outcome='counter-sell cell' if y == 'y_counter' else 'any solo-sale cell', variant=nm, features=len(cols), **sc)); print(rows[-1]['outcome'], nm, round(sc['auc'], 3), 'within', round(sc['within_cycle_auc'], 3))
    cols = sum([G[g] for g in VAR['V1 causal (bars to j-1, orders before minute j)']], []); sc = score(PN, loco(PN, cols, y, perm=True), y); rows.append(dict(outcome='counter-sell cell' if y == 'y_counter' else 'any solo-sale cell', variant='placebo (V1 features shuffled within cycle)', features=len(cols), **sc))
A = pd.DataFrame(rows)
# forward check, V1
order = PN.groupby('cid').expiry.first().sort_values(); tr = list(order.index[:int(len(order) * 2 / 3)]); te = list(order.index[int(len(order) * 2 / 3):]); fw = []
for y in ('y_counter', 'y'):
    for nm, gs in VAR.items():
        cols = sum([G[g] for g in gs], []); m = mk().fit(PN[PN.cid.isin(tr)][cols].values, PN[PN.cid.isin(tr)][y].values); d = PN[PN.cid.isin(te)]; fw.append(dict(outcome=y, variant=nm, auc=roc_auc_score(d[y], m.predict_proba(d[cols].values)[:, 1]), train_cycles=len(tr), test_cycles=len(te)))
FW = pd.DataFrame(fw); A.round(4).to_csv(f'{OUT}/bl_d0c_auc.csv', index=False); FW.round(4).to_csv(f'{OUT}/bl_d0c_auc_fwd.csv', index=False); print(A.round(3).to_string(index=False)); print(FW.round(3).to_string(index=False))
R['auc'] = A.round(4).to_dict('records'); R['fwd'] = FW.round(4).to_dict('records'); rec('d0c1', R)
