"""Part A follow-up (post-hoc, after the leak fix): (1) hazard of the first sale after the buy-back by lag; (2) does the minute's own bar (contemporaneous) predict whether/when the sale comes?
Outputs bl_d0p_a5_hazard.csv, bl_d0p_a5_cont.csv, bl_summary_d0p2.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from sklearn.ensemble import HistGradientBoostingClassifier as HGB
from sklearn.metrics import roc_auc_score
E = pd.read_pickle(f'{OUT}/bl_d0p_events.pkl.gz'); PN = pd.read_pickle(f'{OUT}/bl_d0n_panel.pkl.gz'); SO = pd.read_pickle(f'{OUT}/bl_d0n_orders.pkl.gz'); rng = np.random.default_rng(163); R = {}; other = lambda c: 'PE' if c == 'CE' else 'CE'
# ---- hazard of the first sale at or after the buy-back
first = []
for q in E.itertuples():
    d = SO[(SO.cid == q.cid) & (SO.cp == other(q.cp))].tod.values - q.tod; d = d[d >= 0]; first.append(d.min() if len(d) else np.nan)
E['first_after_s'] = first; edges = [0, 1, 2, 5, 10, 20, 30, 60, 120, 300, 900]; rows = []; alive = E.first_after_s.notna() | True
for a, b in zip(edges[:-1], edges[1:]):
    at_risk = (E.first_after_s.isna() | (E.first_after_s >= a)); n = int(at_risk.sum()); ev = int(((E.first_after_s >= a) & (E.first_after_s < b)).sum()); rows.append(dict(lag=f'{a}-{b} s', at_risk=n, first_sales=ev, hazard_per_second=ev / max(n, 1) / (b - a), share_of_at_risk=ev / max(n, 1)))
H = pd.DataFrame(rows); H.to_csv(f'{OUT}/bl_d0p_a5_hazard.csv', index=False); print(H.round(4).to_string(index=False))
# ---- contemporaneous bar
cont = ['fav_ret_1_c', 'fav_ret_3_c', 'fresh_60_c', 'range_c', 'prem_chg_1_c', 'phx_prem_newlow_c', 'phx_plow_bar_c']
other_rows = PN.set_index(['cid', 'j', 'cp'])
for c_ in cont: E[c_] = [other_rows.loc[(q.cid, q.j, other(q.cp)), c_] for q in E.itertuples()]
dec = ['phx_prem_low_60', 'prem_vs_daymin', 'prem_chg_1', 'prem_chg_3', 'prem_chg_5', 'ladder_same_contract', 'ladder_atm_vs_last_sale', 'ladder_same_contract_solo', 'R_solo_sales_prev60s', 'secs_since_any_R_sale', 'secs_since_solo_R_sale', 'sell_own_5', 'sell_own_15', 'n_own', 'n_other', 'share_own', 'expo_share_own', 'lots_bought', 'fav_ret_1', 'fav_ret_5', 'fav_ret_15', 'min_in_15', 'hour', 'und_nifty', 'v2']
mk = lambda: HGB(max_iter=200, max_depth=3, learning_rate=0.05, min_samples_leaf=50, l2_regularization=1.0, random_state=0)
def loco(cols, y):
    p = np.full(len(E), np.nan); Xm = E[cols].values
    for c_ in E.cid.unique():
        te = (E.cid == c_).values; p[te] = mk().fit(Xm[~te], E[y].values[~te]).predict_proba(Xm[te])[:, 1]
    u = E.cid.unique(); idx = {c_: np.where(E.cid.values == c_)[0] for c_ in u}; b = []
    for _ in range(300):
        k = np.concatenate([idx[c_] for c_ in rng.choice(u, len(u))]); 
        if E[y].values[k].min() != E[y].values[k].max(): b.append(roc_auc_score(E[y].values[k], p[k]))
    return roc_auc_score(E[y], p), np.percentile(b, 2.5), np.percentile(b, 97.5)
rows = []
for y in ('sale_2', 'sale_10', 'sale_60'):
    for nm, cols in (('decision-time factors', dec), ('minute-j bar only', cont), ('decision-time + minute-j bar', dec + cont)):
        a = loco(cols, y); rows.append(dict(outcome=y, model=nm, auc=a[0], lo=a[1], hi=a[2]))
C = pd.DataFrame(rows); C.to_csv(f'{OUT}/bl_d0p_a5_cont.csv', index=False); print(C.round(3).to_string(index=False))
R['hazard'] = H.round(5).to_dict('records'); R['cont'] = C.round(4).to_dict('records'); rec('d0p2', R)
