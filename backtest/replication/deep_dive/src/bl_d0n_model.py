"""N1 (label vs population) and N2 (trigger search, LOCO gradient boosting) of reports/D0_CTRIG_PLAN.md. Fixed settings: HistGradientBoosting 200 iters, depth 3, lr 0.05, min leaf 50, l2 1.0.
Outputs bl_d0n_n2.csv (groups), bl_d0n_n2_abl.csv, bl_d0n_n2_imp.csv, bl_d0n_n1.csv, bl_d0n_n2_fwd.csv, bl_summary_d0n1.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from sklearn.ensemble import HistGradientBoostingClassifier as HGB
from sklearn.metrics import roc_auc_score, average_precision_score
PN = pd.read_pickle(f'{OUT}/bl_d0n_panel.pkl.gz'); SO = pd.read_pickle(f'{OUT}/bl_d0n_orders.pkl.gz'); R = {}; rng = np.random.default_rng(71)
G = dict(
    base=['hour', 'min_in_15', 'min_in_5', 'is_ce', 'und_nifty', 'v2', 'j'],
    spot=['fav_ret_1', 'fav_ret_3', 'fav_ret_5', 'fav_ret_15', 'fav_ret_30', 'fav_ret_60', 'fresh_15', 'fresh_30', 'fresh_60', 'fresh_120', 'fresh_day', 'dist_day_ext', 'from_open', 'vol15', 'bars_since_fresh60'],
    prem=['atm_px', 'prem_chg_1', 'prem_chg_3', 'prem_chg_5', 'prem_chg_15', 'prem_vs_daymax', 'prem_vs_daymin', 'prem_vs_open', 'mark_own', 'mark_other'],
    book=['n_own', 'n_other', 'share_own', 'expo_own', 'expo_other', 'expo_share_own', 'mtm_lakh', 'mtm_to_stop', 'sell_own_1', 'sell_own_5', 'sell_own_15', 'sell_other_1', 'sell_other_5', 'sell_other_15', 'since_sale_own'],
    bb=['bb_other_1', 'bb_other_5', 'bb_other_15', 'bb_own_1', 'bb_own_5', 'bb_own_15', 'sl_other_1', 'sl_other_5', 'sl_other_15', 'sl_own_1', 'sl_own_5', 'sl_own_15', 'since_bb_other'],
    cont=['fav_ret_1_c', 'fav_ret_3_c', 'fresh_60_c', 'range_c', 'prem_chg_1_c'])
mk = lambda: HGB(max_iter=200, max_depth=3, learning_rate=0.05, min_samples_leaf=50, l2_regularization=1.0, random_state=0)
def loco(df, cols, y, perm=False, folds=None):
    """out-of-fold probability, leave-one-cycle-out (or the given list of (train_idx, test_idx))"""
    p = np.full(len(df), np.nan); Xm = df[cols].values.copy(); yv = df[y].values
    if perm:
        for c_ in df.cid.unique():
            m = (df.cid == c_).values; Xm[m] = Xm[rng.permutation(np.where(m)[0])]
    for c_ in df.cid.unique():
        te = (df.cid == c_).values
        if len(set(yv[~te])) < 2: continue
        m = mk().fit(Xm[~te], yv[~te]); p[te] = m.predict_proba(Xm[te])[:, 1]
    return p
def boot(df, p, y, nb=300):
    u = df.cid.unique(); idx = {c_: np.where(df.cid.values == c_)[0] for c_ in u}; a = []; b = []
    for _ in range(nb):
        k = np.concatenate([idx[c_] for c_ in rng.choice(u, len(u))]); yy = df[y].values[k]
        if yy.min() != yy.max(): a.append(roc_auc_score(yy, p[k])); b.append(average_precision_score(yy, p[k]))
    return np.percentile(a, [2.5, 97.5]), np.percentile(b, [2.5, 97.5])
def score(df, p, y):
    ok = ~np.isnan(p); lo, pr = boot(df[ok].reset_index(drop=True), p[ok], y); return dict(auc=roc_auc_score(df[y][ok], p[ok]), auc_lo=lo[0], auc_hi=lo[1], prauc=average_precision_score(df[y][ok], p[ok]), pr_lo=pr[0], pr_hi=pr[1])
# ---------------- N2 groups
combos = {'baseline (time, right, underlying)': ['base'], '+ spot': ['base', 'spot'], '+ premium': ['base', 'prem'], '+ book': ['base', 'book'], '+ buy-backs (past)': ['base', 'bb'], 'spot + premium': ['base', 'spot', 'prem'], 'all decision-time': ['base', 'spot', 'prem', 'book', 'bb'], 'all + bar j (contemporaneous)': ['base', 'spot', 'prem', 'book', 'bb', 'cont']}
n2 = []; PP = {}
for nm, gs in combos.items():
    cols = sum([G[g] for g in gs], []); p = loco(PN, cols, 'y'); PP[nm] = p; sc = score(PN, p, 'y'); n2.append(dict(model=nm, features=len(cols), **sc)); print(nm, {k: round(v, 3) for k, v in sc.items()})
N2 = pd.DataFrame(n2); b0 = N2.auc.iloc[0]; N2['gain_over_baseline'] = N2.auc - b0; N2.to_csv(f'{OUT}/bl_d0n_n2.csv', index=False)
# placebo: cycle-permuted features, all decision-time
colsA = sum([G[g] for g in ('base', 'spot', 'prem', 'book', 'bb')], []); pp = loco(PN, colsA, 'y', perm=True); R['placebo_all'] = score(PN, pp, 'y'); print('placebo', R['placebo_all'])
# ablation: all minus one group
ab = []
for g in ('spot', 'prem', 'book', 'bb'):
    cols = [c_ for c_ in colsA if c_ not in G[g]]; p = loco(PN, cols, 'y'); sc = score(PN, p, 'y'); ab.append(dict(dropped=g, **sc)); print('minus', g, round(sc['auc'], 3))
pd.DataFrame(ab).to_csv(f'{OUT}/bl_d0n_n2_abl.csv', index=False)
# forward check: first 20 cycles by expiry -> last 10 (those in panel)
order = PN.groupby('cid').expiry.first().sort_values(); tr = list(order.index[:int(len(order) * 2 / 3)]); te = list(order.index[int(len(order) * 2 / 3):]); fw = []
for nm, gs in combos.items():
    cols = sum([G[g] for g in gs], []); m = mk().fit(PN[PN.cid.isin(tr)][cols].values, PN[PN.cid.isin(tr)].y.values); d = PN[PN.cid.isin(te)]; p = m.predict_proba(d[cols].values)[:, 1]; fw.append(dict(model=nm, train_cycles=len(tr), test_cycles=len(te), auc=roc_auc_score(d.y, p), prauc=average_precision_score(d.y, p)))
FW = pd.DataFrame(fw); FW.to_csv(f'{OUT}/bl_d0n_n2_fwd.csv', index=False); print(FW.round(3).to_string(index=False))
# permutation importance (LOCO AUC drop when one feature is shuffled in the test fold), decision-time model
imp = {c_: [] for c_ in colsA}
for c_cid in PN.cid.unique():
    te_m = (PN.cid == c_cid).values; m = mk().fit(PN[~te_m][colsA].values, PN[~te_m].y.values); Xt = PN[te_m][colsA].values.copy(); yt = PN[te_m].y.values
    if yt.min() == yt.max(): continue
    base_auc = roc_auc_score(yt, m.predict_proba(Xt)[:, 1])
    for k, f_ in enumerate(colsA):
        Xs = Xt.copy(); Xs[:, k] = rng.permutation(Xs[:, k]); imp[f_].append(base_auc - roc_auc_score(yt, m.predict_proba(Xs)[:, 1]))
IM = pd.DataFrame([dict(feature=f_, drop_in_auc=np.mean(v), se=np.std(v) / np.sqrt(len(v)), group=[g for g in G if f_ in G[g]][0]) for f_, v in imp.items()]).sort_values('drop_in_auc', ascending=False); IM.to_csv(f'{OUT}/bl_d0n_n2_imp.csv', index=False); print(IM.head(15).round(4).to_string(index=False))
# ---------------- N1: counter-labelled vs other solo, no buy-back features
D = SO[(SO.row >= 0) & (SO.type != 'late solo')].copy(); D = D.merge(PN.drop(columns=['cid', 'j', 'cp']).rename(columns={'row': 'row'}), on='row', how='left', suffixes=('', '_p')); D['is_counter'] = (D.type == 'counter-sell solo').astype(float)
Dp = PN.set_index('row').loc[D.row.values].reset_index(); Dp['is_counter'] = D.is_counter.values; Dp['cid'] = D.cid.values
nb_cols = G['base'] + G['spot'] + G['prem'] + G['book']; n1 = []
for nm, cols in {'time + right (baseline)': G['base'], '+ spot': G['base'] + G['spot'], '+ premium': G['base'] + G['prem'], '+ book': G['base'] + G['book'], 'all market/book (no buy-back features)': nb_cols, 'all + past buy-backs': nb_cols + G['bb']}.items():
    p = loco(Dp, cols, 'is_counter'); sc = score(Dp, p, 'is_counter'); n1.append(dict(model=nm, orders=len(Dp), counter_share=Dp.is_counter.mean(), **sc)); print('N1', nm, round(sc['auc'], 3), round(sc['auc_lo'], 3))
pn = loco(Dp, nb_cols, 'is_counter', perm=True); R['n1_placebo'] = score(Dp, pn, 'is_counter'); pd.DataFrame(n1).to_csv(f'{OUT}/bl_d0n_n1.csv', index=False)
R['n2'] = N2.round(4).to_dict('records'); R['ablation'] = ab; R['panel'] = dict(cells=len(PN), cycles=int(PN.cid.nunique()), positive_rate=float(PN.y.mean()), solo_orders_in_panel=int((SO.row >= 0).sum()))
R['top_features'] = IM.head(12).round(4).to_dict('records'); R['n1'] = n1; rec('d0n1', R)
