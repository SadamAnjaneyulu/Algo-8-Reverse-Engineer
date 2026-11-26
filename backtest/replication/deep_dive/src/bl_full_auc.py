"""Complete D-1 activity (body + hedge) vs the real ledger: one panel, six activity classes + any activity, LOCO gradient boosting, AUC (plan reports/D1_FULL_AUC_PLAN.md).
Outputs bl_full_panel.pkl.gz, bl_full_auc.csv, bl_full_overall.csv, bl_summary_full1.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from sklearn.metrics import roc_auc_score
from sklearn.ensemble import HistGradientBoostingClassifier
import bl_sd_build, bl_ohlc
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); O = load_orders(); OP = bl_sd_build.load_opt(); OH = bl_ohlc.load(); R = {}; JMAX = 390
SELL = pd.read_pickle(f'{OUT}/bl_auc_all_panel.pkl.gz').sort_values(['cid', 'cp', 'j']).reset_index(drop=True); PS = pd.read_pickle(f'{OUT}/bl_auc_all_pred.pkl.gz'); SELL['p_sell'] = PS.p_A.values
SF = ['sched_share', 'react_fire', 'react_fav', 'react_depth', 'pl5_itm', 'pl15_itm', 'pl30_itm', 'pl5_atm', 'pl15_atm', 'pl30_atm', 'fav5', 'bk5', 'bkhl5', 'fav15', 'bk15', 'bkhl15', 'fav30', 'bk30', 'bkhl30', 'fav60', 'bk60', 'bkhl60', 'pos15']
CLS = {'body_sell': lambda z: (z.module == 'num') & (z.role == 'open_short'), 'body_buyback': lambda z: (z.module == 'num') & (z.role == 'cover_short'), 'wing_buy': lambda z: (z.module == 'h_') & (z.role == 'open_long'),
       'wing_sell': lambda z: (z.module == 'h_') & (z.role == 'close_long'), 'body_long': lambda z: (z.module == 'num') & z.role.isin(['open_long', 'close_long']), 'lump': lambda z: (z.module == 'v_') & (z.role == 'open_long')}
def win(d1):
    return (6, 14) if d1 <= '2026-08-05' else ((23, 24) if d1 <= '2026-08-19' else (30, 35))
rows = []
for i, r in enumerate(CY.itertuples()):
    z = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 0)].sort_values(['te', 'row']).copy(); z['j'] = ((z.te - 33300) // 60).astype(int); z['sg'] = np.where(z.side == 'Buy', 1, -1)
    op = OP[(r.und, r.expiry)]; K = op['K']; ki = {int(k): x for x, k in enumerate(K)}; c = OH[(r.und, r.expiry)].close.values; st = ref.STEP[r.und]; w0, w1 = win(r.d1)
    net = {}; ent = {}; numlong = {'CE': 0, 'PE': 0}; zl = list(z.itertuples()); p = 0
    lab = {k: z[f(z)].groupby(['j', 'cp']).size() for k, f in CLS.items()}; anyl = z.groupby(['j', 'cp']).size()
    bs = z[CLS['body_sell'](z)].groupby(['j', 'cp']).lots.sum(); bb = z[CLS['body_buyback'](z)].groupby(['j', 'cp']).lots.sum()
    for j in range(0, JMAX):
        T0 = 33300 + 60 * j
        while p < len(zl) and zl[p].te < T0:
            q = zl[p]; k = (q.cp, int(q.strike)); n0 = net.get(k, 0); n1 = n0 + q.sg * q.lots
            if q.sg < 0 and n1 < 0: sold = min(q.lots, -n1); old = max(-n0, 0); ent[k] = (ent.get(k, 0) * old + q.px_avg * sold) / max(old + sold, 1)
            net[k] = n1
            if q.module == 'num' and q.role == 'open_long': numlong[q.cp] += q.lots
            if q.module == 'num' and q.role == 'close_long': numlong[q.cp] -= q.lots
            p += 1
        jj = min(max(j, 1), 374)
        for cp in ('CE', 'PE'):
            oth = 'PE' if cp == 'CE' else 'CE'; S = -sum(v for (c2, _), v in net.items() if c2 == cp and v < 0); L = sum(v for (c2, _), v in net.items() if c2 == cp and v > 0); So = -sum(v for (c2, _), v in net.items() if c2 == oth and v < 0)
            rc, rh = [], []
            for (c2, k), v in net.items():
                if c2 != cp or v >= 0 or k not in ki or ent.get((c2, k), 0) <= 0: continue
                rc.append((-v, op[(cp, 'close')][ki[k], jj - 1] / ent[(c2, k)])); rh.append((-v, op[(cp, 'high')][ki[k], jj] / ent[(c2, k)]))
            d = dict(cid=i, und=r.und, j=j, cp=cp, minute=j, S=S, L=L, gap=S - L, excess=L - S, S_other=So, heavy=int(S > So), numlong=numlong[cp], opening=int(j <= 2), lump_win=int(w0 <= j - 360 <= w1), after_1530=int(j >= 375))
            for nm, rr in (('c', rc), ('h', rh)):
                arr = [(n, x) for n, x in rr if x == x]
                d[f'maxratio_{nm}'] = max([x for _, x in arr], default=np.nan)
                for th in (1.2, 1.4, 1.5, 1.6, 1.7): d[f'n_ge{th}_{nm}'] = sum(n for n, x in arr if x >= th)
            sg = 1 if cp == 'CE' else -1; d['adv1'] = sg * (c[jj - 1] - c[max(jj - 2, 0)]) / st if j <= 374 else np.nan; d['adv5'] = sg * (c[jj - 1] - c[max(jj - 6, 0)]) / st if j <= 374 else np.nan
            d['real_sell_now'] = bs.get((j, cp), 0); d['real_sell_prev'] = bs.get((j - 1, cp), 0); d['real_bb_now'] = bb.get((j, cp), 0); d['real_bb_prev'] = bb.get((j - 1, cp), 0)
            for k_ in CLS: d[f'y_{k_}'] = int(lab[k_].get((j, cp), 0) > 0)
            d['y_any'] = int(anyl.get((j, cp), 0) > 0); rows.append(d)
X = pd.DataFrame(rows).merge(SELL[['cid', 'j', 'cp', 'p_sell'] + SF], on=['cid', 'j', 'cp'], how='left').sort_values(['cid', 'cp', 'j']).reset_index(drop=True)
X['is_ce'] = (X.cp == 'CE').astype(int); X.to_pickle(f'{OUT}/bl_full_panel.pkl.gz')
print(X.shape, {c: int(X[c].sum()) for c in X.columns if c.startswith('y_')})
STATE = ['S', 'L', 'gap', 'excess', 'S_other', 'heavy', 'numlong', 'maxratio_c', 'maxratio_h'] + [f'n_ge{t}_{m}' for t in (1.2, 1.4, 1.5, 1.6, 1.7) for m in ('c', 'h')]
CLK = ['minute', 'opening', 'lump_win', 'after_1530', 'is_ce']; MOVE = ['adv1', 'adv5']; LINK_REAL = ['real_sell_now', 'real_sell_prev', 'real_bb_now', 'real_bb_prev']; LINK_CH = ['p_sell', 'p_sell_prev', 'p_bb', 'p_bb_prev']
SAME_MIN = [c for c in SF if c != 'sched_share'] + ['maxratio_h'] + [f'n_ge{t}_h' for t in (1.2, 1.4, 1.5, 1.6, 1.7)]
cid = X.cid.values; cyc = np.unique(cid); idx = {c_: np.where(cid == c_)[0] for c_ in cyc}; rng = np.random.default_rng(0)
def loco(df, cols, y):
    M = df[cols].values.astype(float); p = np.zeros(len(df))
    for c_ in cyc: te = cid == c_; p[te] = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=150, min_samples_leaf=20, l2_regularization=1.0, random_state=0).fit(M[~te], y[~te]).predict_proba(M[te])[:, 1]
    return p
def ci(y, p):
    out = []
    for _ in range(1000):
        b = np.concatenate([idx[c_] for c_ in rng.choice(cyc, len(cyc))])
        if y[b].min() != y[b].max(): out.append(roc_auc_score(y[b], p[b]))
    return np.percentile(out, [2.5, 97.5])
base = SF + STATE + CLK + MOVE
# stage 1: out-of-cycle sell / buy-back probabilities that never use real orders of the current minute (variant A: same-minute sell model; variant B: causal sell model, lagged market)
X['p_sell_prev'] = X.groupby(['cid', 'cp']).p_sell.shift(1)
XB = X.copy(); XB[SAME_MIN + MOVE] = X.groupby(['cid', 'cp'])[SAME_MIN + MOVE].shift(1); XB['p_sell'] = XB.merge(SELL[['cid', 'j', 'cp']].assign(pB=PS.p_B.values), on=['cid', 'j', 'cp'], how='left').pB.values; XB['p_sell_prev'] = XB.groupby(['cid', 'cp']).p_sell.shift(1)
for df in (X, XB): df['p_bb'] = loco(df, base + ['p_sell', 'p_sell_prev'], df.y_body_buyback.values); df['p_bb_prev'] = df.groupby(['cid', 'cp']).p_bb.shift(1)
VAR = {'A same-minute, hedge given real body (primary)': (X, LINK_REAL), 'A-chained (no real orders in the minute)': (X, LINK_CH), 'B causal (market lagged 1 min), real body link': (XB, LINK_REAL)}
def cols_for(k_, link):
    if k_ == 'body_sell': return base                                  # sell model: decoded sell features only
    if k_ == 'body_buyback': return base + ['p_sell', 'p_sell_prev']    # never its own real orders
    if k_ in ('wing_buy', 'wing_sell'): return base + link              # hedge module: given the real body (A, B) or the predicted body (A-chained)
    return base + LINK_CH                                               # body-stream longs, lump, any activity: predicted body only
res = []; P = {}
for v, (df, link) in VAR.items():
    for k_ in list(CLS) + ['any']:
        y = df[f'y_{k_}'].values; p = loco(df, cols_for(k_, link), y); P[(v, k_)] = p; lo, hi = ci(y, p); res.append(dict(variant=v, activity=k_, positive_cells=int(y.sum()), AUC=roc_auc_score(y, p), CI_lo=lo, CI_hi=hi)); print(res[-1])
T = pd.DataFrame(res); T.round(4).to_csv(f'{OUT}/bl_full_auc.csv', index=False)
ov = []
for v in VAR:
    t = T[(T.variant == v) & (T.activity != 'any')]; ys = np.concatenate([VAR[v][0][f'y_{k_}'].values for k_ in CLS]); ps = np.concatenate([P[(v, k_)] for k_ in CLS])
    ov.append(dict(variant=v, AUC_any_activity=float(T[(T.variant == v) & (T.activity == 'any')].AUC.iloc[0]), AUC_macro_6_classes=float(t.AUC.mean()), AUC_pooled_class_cells=float(roc_auc_score(ys, ps))))
OV = pd.DataFrame(ov); OV.round(4).to_csv(f'{OUT}/bl_full_overall.csv', index=False); print(OV.round(3).to_string(index=False)); print(T.pivot(index='activity', columns='variant', values='AUC').round(3).to_string())
R['classes'] = T.round(4).to_dict('records'); R['overall'] = OV.round(4).to_dict('records'); R['cells'] = len(X); pd.to_pickle(P, f'{OUT}/bl_full_pred.pkl.gz'); rec('full1', R)
