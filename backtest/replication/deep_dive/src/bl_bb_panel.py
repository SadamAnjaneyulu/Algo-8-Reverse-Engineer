"""Buy-back decode step 3: contract-minute panel (every D-1 minute x contract with open body short lots before the minute; real ledger). Label = body buy-back on that contract in the minute.
Variables: ratio of previous close (c) or current high (h) to the cheapest / average / most expensive open entry (decision price); trailing ratio (c / lowest low since the oldest open lot); spot move against since the cheapest lot's sale (steps); ITM depth (steps);
right-level premium ratio (sum close / sum entry over all open lots of the right); minute; open lots; minutes since the last sale on the contract.
Univariate AUC, out-of-fold single-threshold F1 (halves), depth-3 tree out-of-fold. Outputs bl_bb_panel.pkl.gz, bl_bb_vars.csv, bl_summary_bb3.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy.stats import rankdata
from sklearn.tree import DecisionTreeClassifier
import bl_sd_build, bl_ohlc
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); O = load_orders(); OP = bl_sd_build.load_opt(); OH = bl_ohlc.load(); R = {}; rows = []
for i, r in enumerate(CY.itertuples()):
    z = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 0) & (O.module == 'num') & O.role.isin(['open_short', 'cover_short'])].sort_values(['te', 'row']); zl = list(z.itertuples()); p = 0
    op = OP[(r.und, r.expiry)]; K = op['K']; ki = {int(k): x for x, k in enumerate(K)}; c = OH[(r.und, r.expiry)].close.values; st = ref.STEP[r.und]; book = {}
    bbj = z[z.role == 'cover_short'].assign(j=lambda d: ((d.te - 33300) // 60).astype(int)).groupby(['cp', 'strike', 'j']).lots.sum().to_dict()
    for j in range(2, 375):
        T0 = 33300 + 60 * j
        while p < len(zl) and zl[p].te < T0:
            o = zl[p]; k = (o.cp, int(o.strike))
            if o.role == 'open_short': book.setdefault(k, []).extend([(o.te, o.ref_px, int((o.te - 33300) // 60))] * int(o.lots))
            elif book.get(k): book[k].pop(int(np.argmin([l_[1] for l_ in book[k]])))
            p += 1
        rr = {}
        for (cp, kk), lots in book.items():
            if not lots or kk not in ki: continue
            x = ki[kk]; pc = op[(cp, 'close')][x, j - 1]; rr.setdefault(cp, [0.0, 0.0])
            rr[cp][0] += pc * len(lots); rr[cp][1] += sum(l_[1] for l_ in lots)
        for (cp, kk), lots in book.items():
            if not lots or kk not in ki: continue
            x = ki[kk]; er = np.array([l_[1] for l_ in lots]); pc = op[(cp, 'close')][x, j - 1]; ph = op[(cp, 'high')][x, j]; sg = 1 if cp == 'CE' else -1
            a = int(np.argmin(er)); j_a = lots[a][2]; j0 = min(l_[2] for l_ in lots); lo = np.nanmin(op[(cp, 'low')][x, j0:j]) if j > j0 else pc
            rows.append(dict(cid=i, j=j, cp=cp, strike=kk, y=int(bbj.get((cp, kk, j), 0) > 0), n_y=int(bbj.get((cp, kk, j), 0)), n_open=len(lots), rc_min=pc / er.min(), rc_avg=pc / er.mean(), rc_max=pc / er.max(), rh_min=ph / er.min(),
                             trail=pc / lo if lo and lo > 0 else np.nan, mv_against=sg * (c[j - 1] - c[max(j_a - 1, 0)]) / st, itm=sg * (c[j - 1] - kk) / st, right_ratio=rr[cp][0] / rr[cp][1] if rr[cp][1] > 0 else np.nan, minute=j, min_since_last_sale=j - max(l_[2] for l_ in lots)))
X = pd.DataFrame(rows); X.to_pickle(f'{OUT}/bl_bb_panel.pkl.gz'); y = X.y.values; print(X.shape, 'positives', int(y.sum()), 'real buy-back lots in panel', int(X.n_y.sum()))
def auc(s, y): m = ~np.isnan(s); s, yy = s[m], y[m]; n1 = yy.sum(); n0 = len(yy) - n1; return (rankdata(s)[yy == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
def thr_f1(s, yy, t): p = s >= t; tp = (p & (yy == 1)).sum(); return 2 * tp / max(p.sum() + yy.sum(), 1)
VARS = ['rc_min', 'rc_avg', 'rc_max', 'rh_min', 'trail', 'mv_against', 'itm', 'right_ratio', 'minute', 'n_open', 'min_since_last_sale']; h = X.cid.values % 2 == 0; out = []
for v in VARS:
    s = X[v].values.astype(float); s = np.where(np.isnan(s), -1e9, s); grid = np.unique(np.quantile(s[s > -1e9], np.linspace(0.5, 0.999, 120)))
    oof = []
    for tr in (h, ~h):
        t = max(grid, key=lambda t: thr_f1(s[tr], y[tr], t)); oof.append((t, thr_f1(s[~tr], y[~tr], t)))
    out.append(dict(variable=v, AUC=auc(X[v].values.astype(float), y), thr_fold=f'{oof[0][0]:.3f}/{oof[1][0]:.3f}', F1_oof_half1=oof[0][1], F1_oof_half2=oof[1][1], F1_oof=float(np.mean([o[1] for o in oof]))))
T = pd.DataFrame(out).sort_values('F1_oof', ascending=False); print(T.round(3).to_string(index=False))
# hazard of the best ratio variable by bin
for v in ('rc_min', 'rh_min', 'right_ratio', 'trail'):
    b = pd.cut(X[v], [0, .8, 1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 2, 99]); hz = X.groupby(b, observed=True).y.agg(['mean', 'size']); R[f'hazard_{v}'] = {str(k): [round(float(a), 4), int(n)] for k, (a, n) in hz.iterrows()}; print(v, {str(k): (round(a, 3), int(n)) for k, (a, n) in hz.iterrows()})
# depth-3 tree out-of-fold
Xm = X[VARS].fillna(-1).values; pr = np.zeros(len(y))
for tr in (h, ~h): pr[~tr] = DecisionTreeClassifier(max_depth=3, min_samples_leaf=200, class_weight={0: 1, 1: 8}, random_state=0).fit(Xm[tr], y[tr]).predict(Xm[~tr])
tp = (pr.astype(bool) & (y == 1)).sum(); R['tree3_F1'] = float(2 * tp / (pr.sum() + y.sum())); R['tree3_precision'] = float(tp / max(pr.sum(), 1)); R['tree3_recall'] = float(tp / y.sum()); print('tree depth 3 OOF', {k: round(R[k], 3) for k in ('tree3_F1', 'tree3_precision', 'tree3_recall')})
from sklearn.tree import export_text; print(export_text(DecisionTreeClassifier(max_depth=3, min_samples_leaf=200, class_weight={0: 1, 1: 8}, random_state=0).fit(Xm, y), feature_names=VARS))
T.round(4).to_csv(f'{OUT}/bl_bb_vars.csv', index=False); R['vars'] = T.round(4).to_dict('records'); rec('bb3', R)
