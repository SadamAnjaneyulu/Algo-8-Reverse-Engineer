"""One AUC for all D-1 selling (plan reports/D1_SELLING_AUC_PLAN.md). Panel cycle x minute (1..374) x right; label = any body open_short lot (all types).
Features: LOCO timetable share, decoded reactive machine (fire / favourable side / depth), solo-panel variables, option premium fresh lows, clock. Variants A (same-minute), B (causal, lagged 1 min), C (A + real order history, teacher-forced).
LOCO gradient boosting (fixed settings) and logistic; pooled AUC with cycle-bootstrap CI; AUC by sell type; AUC without timetable minutes.
Outputs bl_auc_all_panel.pkl.gz, bl_auc_all.csv, bl_auc_all_types.csv, bl_summary_auc1.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from sklearn.metrics import roc_auc_score
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
exec(open('bl_dq_final.py').read().split("rows = []\nfor nm, fn")[0])
import bl_sd_build
CYs = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); OP = bl_sd_build.load_opt(); D = pd.read_pickle(f'{OUT}/bl_sd_orders.pkl.gz'); SP = pd.read_pickle(f'{OUT}/bl_solo_panel.pkl.gz'); Rs = {}
D['typ2'] = np.where(D.deep, 'deep-OTM batch', np.where((D.typ == 'solo') & (D.te >= 54000), 'solo after 15:00', D.typ)); D = D[(D.j >= 1) & (D.j <= 374)]
cmap = {(d['und'], d['expiry']): d for d in CYC}; rows = []
for i, r in enumerate(CYs.itertuples()):
    d = cmap[(r.und, r.expiry)]; h, l, c = d['h'], d['l'], d['c']; st = ref.STEP[r.und]; fires = machv(d); op = OP[(r.und, r.expiry)]; K = op['K']; dd = D[D.cid == i]
    fr = {}
    for j, s in fires:
        H, L = chan_v(d, j, 2, 'hl'); fr.setdefault(j, []).append((s, ((h[j] - H) if s == 1 else (L - l[j])) / st))
    for j in range(1, 375):
        atm = K[np.argmin(np.abs(K - c[j - 1]))]
        for cp in ('CE', 'PE'):
            q = dd[(dd.j == j) & (dd.cp == cp)]; fs = fr.get(j, []); fav = -1 if cp == 'CE' else 1
            x = dict(cid=i, version=r.version, j=j, cp=cp, y=int(len(q) > 0), **{f'ty_{t}': int((q.typ2 == t).any()) for t in ('scheduled', 'reactive', 'solo', 'solo after 15:00', 'deep-OTM batch')},
                     sched_any=int(((dd.j == j) & (dd.cp == cp) & (dd.typ == 'scheduled')).any()), react_fire=int(len(fs) > 0), react_fav=int(any(s == fav for s, _ in fs)), react_depth=max([dp for _, dp in fs], default=np.nan))
            for nm, k in (('itm', atm - st if cp == 'CE' else atm + st), ('atm', atm)):
                w = np.where(np.abs(K - k) < 1)[0]
                for N in (5, 15, 30): x[f'pl{N}_{nm}'] = (float(op[(cp, 'low')][w[0]][j] < np.nanmin(op[(cp, 'low')][w[0]][j - N:j])) if (len(w) and j >= N) else np.nan)
            prev = dd[(dd.cp == cp) & (dd.j < j)]; x['hist_min_since'] = (j - prev.j.max()) if len(prev) else 400; x['hist_lots_today'] = prev.lots.sum(); rows.append(x)
X = pd.DataFrame(rows)
# LOCO timetable share: share of OTHER cycles of the same version with a scheduled sale on this right in this minute
g = X.groupby(['version', 'j', 'cp']).sched_any.agg(['sum', 'count']).rename(columns={'sum': 'ss', 'count': 'nn'}).reset_index(); X = X.merge(g, on=['version', 'j', 'cp']); X['sched_share'] = (X.ss - X.sched_any) / (X.nn - 1); X = X.drop(columns=['ss', 'nn'])
sp = SP.drop(columns=['und', 'y', 'lots', 'slot_minute'])
X = X.merge(sp, on=['cid', 'j', 'cp'], how='left').sort_values(['cid', 'cp', 'j']).reset_index(drop=True); X.to_pickle(f'{OUT}/bl_auc_all_panel.pkl.gz'); print(X.shape, 'positives', int(X.y.sum()), 'share', round(X.y.mean(), 3))
MKT = ['react_fire', 'react_fav', 'react_depth', 'pl5_itm', 'pl15_itm', 'pl30_itm', 'pl5_atm', 'pl15_atm', 'pl30_atm', 'own_ratio', 'other_ratio', 'own_lots', 'other_lots', 'fav5', 'bk5', 'bkhl5', 'fav15', 'bk15', 'bkhl15', 'fav30', 'bk30', 'bkhl30', 'fav60', 'bk60', 'bkhl60', 'pos15']
FIX = ['sched_share', 'j', 'hour']; HIST = ['hist_min_since', 'hist_lots_today']
XB = X.copy(); XB[MKT] = X.groupby(['cid', 'cp'])[MKT].shift(1)
VAR = {'A same-minute (primary)': (X, FIX + MKT), 'B causal (market lagged 1 min)': (XB, FIX + MKT), 'C A + real order history (teacher-forced)': (X, FIX + MKT + HIST)}
for df in (X, XB): df['is_ce'] = (df.cp == 'CE').astype(int)
y = X.y.values; cid = X.cid.values
def loco(df, cols, kind):
    M = df[cols + ['is_ce']].values.astype(float); p = np.zeros(len(df))
    for c_ in np.unique(cid):
        te = cid == c_; tr = ~te
        if kind == 'gb': p[te] = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=150, min_samples_leaf=20, l2_regularization=1.0, random_state=0).fit(M[tr], y[tr]).predict_proba(M[te])[:, 1]
        else:
            med = np.nanmedian(M[tr], 0); med = np.where(np.isnan(med), 0, med); Mt = np.where(np.isnan(M), med, M); sc = StandardScaler().fit(Mt[tr]); p[te] = LogisticRegression(C=0.3, max_iter=1000).fit(sc.transform(Mt[tr]), y[tr]).predict_proba(sc.transform(Mt[te]))[:, 1]
    return p
rng = np.random.default_rng(0); cyc = np.unique(cid); idx = {c_: np.where(cid == c_)[0] for c_ in cyc}
def ci(p, mask=None):
    m = np.ones(len(y), bool) if mask is None else mask; out = []
    for _ in range(1000):
        b = np.concatenate([idx[c_] for c_ in rng.choice(cyc, len(cyc))]); b = b[m[b]]
        if y[b].min() != y[b].max(): out.append(roc_auc_score(y[b], p[b]))
    return np.percentile(out, [2.5, 97.5])
res = []; typ = []; P_ = {}
nos = (X.sched_share <= 0.5).values
for v, (df, cols) in VAR.items():
    for kd in ('gb', 'lr'):
        p = loco(df, cols, kd); P_[(v, kd)] = p; a = roc_auc_score(y, p); lo, hi = ci(p) if kd == 'gb' else (np.nan, np.nan); a2 = roc_auc_score(y[nos], p[nos]); lo2, hi2 = ci(p, nos) if kd == 'gb' else (np.nan, np.nan)
        res.append(dict(variant=v, model=kd, AUC=a, CI_lo=lo, CI_hi=hi, AUC_without_timetable_minutes=a2, CI2_lo=lo2, CI2_hi=hi2)); print(res[-1])
        if kd == 'gb':
            for t in ('scheduled', 'reactive', 'solo', 'solo after 15:00', 'deep-OTM batch'):
                m = (X[f'ty_{t}'] == 1) | (X.y == 0); typ.append(dict(variant=v, sell_type=t, positive_cells=int(X[f'ty_{t}'].sum()), AUC=roc_auc_score(y[m.values], p[m.values])))
R = pd.DataFrame(res); T = pd.DataFrame(typ); R.round(4).to_csv(f'{OUT}/bl_auc_all.csv', index=False); T.round(4).to_csv(f'{OUT}/bl_auc_all_types.csv', index=False); print(T.round(3).to_string(index=False))
# timetable alone (no model) as a reference
Rs['timetable_only_AUC'] = float(roc_auc_score(y, X.sched_share.values)); Rs['cells'] = len(X); Rs['positives'] = int(y.sum()); Rs['cells_without_timetable'] = int(nos.sum()); Rs['positives_without_timetable'] = int(y[nos].sum())
pd.DataFrame({'p_A': P_[('A same-minute (primary)', 'gb')], 'p_B': P_[('B causal (market lagged 1 min)', 'gb')]}).to_pickle(f'{OUT}/bl_auc_all_pred.pkl.gz')
Rs['results'] = R.round(4).to_dict('records'); Rs['types'] = T.round(4).to_dict('records'); print(Rs['timetable_only_AUC']); rec('auc1', Rs)
