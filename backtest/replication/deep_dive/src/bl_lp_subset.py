"""Lump study step 4 (EXPLORATORY): which subset of heavy-side open shorts does the main lump cover?
Open heavy-side body shorts at the decision are rebuilt lot by lot (FIFO per contract: buy-backs close the oldest lot), each lot labelled by sell type (scheduled / reactive / solo / deep), moneyness at the decision (strike vs spot, steps, + = ITM) and hour sold.
Non-negative least squares lots ~ sum_g w_g x count_g (no intercept, and with intercept), leave-one-cycle-out; also simple counts S_h - c and a x S_h. Output bl_lp_subset.csv, bl_summary_lp4.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy.optimize import nnls
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); O = load_orders(); SD = pd.read_pickle(f'{OUT}/bl_sd_orders.pkl.gz'); Dd = pd.read_csv(f'{OUT}/bl_lp_dec.csv'); R = {}; rows = []
for x in Dd[Dd.main == 1].itertuples():
    r = CY.iloc[x.cid]; st = ref.STEP[r.und]; sg = 1 if x.cp == 'CE' else -1
    z = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 0) & (O.module == 'num') & (O.cp == x.cp) & (O.te < x.t) & O.role.isin(['open_short', 'cover_short'])].sort_values(['te', 'row'])
    lab = SD[(SD.cid == x.cid) & (SD.cp == x.cp)].assign(t2=lambda d: np.where(d.deep, 'deep', d.typ)).set_index(['te', 'strike', 'lots']).t2.to_dict(); q = {}
    for o in z.itertuples():
        k = int(o.strike)
        if o.role == 'open_short':
            t2 = lab.get((o.te, k, o.lots), 'solo')
            for _ in range(int(o.lots)): q.setdefault(k, []).append((o.te, t2))
        else:
            for _ in range(int(o.lots)):
                if q.get(k): q[k].pop(0)
    lots = [(k, te, t2) for k, v in q.items() for te, t2 in v]; d = dict(cid=x.cid, und=x.und, y=x.lots, S_h=len(lots))
    for t2 in ('scheduled', 'reactive', 'solo', 'deep'): d[f'type_{t2}'] = sum(1 for _, _, t in lots if t == t2)
    for nm, lo, hi in (('itm_gt2', 2, 99), ('itm_0_2', 0.5, 2), ('atm', -0.5, 0.5), ('otm_0_2', -2, -0.5), ('otm_gt2', -99, -2)): d[f'mny_{nm}'] = sum(1 for k, _, _ in lots if lo < sg * (x.spot - k) / st <= hi)
    for nm, lo, hi in (('h09_11', 0, 39600), ('h11_13', 39600, 46800), ('h13_15', 46800, 54000), ('h15', 54000, 99999)): d[f'time_{nm}'] = sum(1 for _, te, _ in lots if lo <= te < hi)
    rows.append(d)
X = pd.DataFrame(rows); X.to_csv(f'{OUT}/bl_lp_subset.csv', index=False); y = X.y.values.astype(float); cid = X.cid.values
def loco(cols, intercept=False):
    M = X[cols].values.astype(float); p = np.zeros(len(y)); W = []
    for i in range(len(y)):
        tr = np.arange(len(y)) != i; A = np.c_[M[tr], np.ones(tr.sum())] if intercept else M[tr]; w, _ = nnls(A, y[tr]); W.append(w)
        p[i] = (np.r_[M[i], 1] if intercept else M[i]) @ w
    Af = np.c_[M, np.ones(len(y))] if intercept else M; wf, _ = nnls(Af, y); return p, wf
res = []
fams = {'S_h': ['S_h'], 'type': ['type_scheduled', 'type_reactive', 'type_solo', 'type_deep'], 'moneyness': ['mny_itm_gt2', 'mny_itm_0_2', 'mny_atm', 'mny_otm_0_2', 'mny_otm_gt2'], 'time sold': ['time_h09_11', 'time_h11_13', 'time_h13_15', 'time_h15']}
for nm, cols in fams.items():
    for ic in (False, True):
        p, w = loco(cols, ic); err = np.abs(p - y); res.append(dict(family=nm, intercept=ic, MAE_lots=err.mean(), median_abs_err_pct=float(np.median(err / np.maximum(y, 1)) * 100), within_5_lots=float((err <= 5).mean()), weights=dict(zip(cols + (['const'] if ic else []), np.round(w, 2)))))
for und in ('NIFTY', 'SENSEX'):
    m = X.und == und; res.append(dict(family=f'ratio median {und} (in-sample)', intercept=False, MAE_lots=float(np.abs(X.y[m] - X.S_h[m] * (X.y[m] / X.S_h[m]).median()).mean()), median_abs_err_pct=np.nan, within_5_lots=np.nan, weights={'ratio': round(float((X.y[m] / X.S_h[m]).median()), 3)}))
T = pd.DataFrame(res); T.to_csv(f'{OUT}/bl_lp_subset.csv'.replace('.csv', '_fit.csv'), index=False); pd.set_option('display.width', 250); pd.set_option('display.max_colwidth', 120); print(T.round(2).to_string(index=False))
print(X.round(0).to_string(index=False)); rec('lp4', dict(table=T.astype({'weights': str}).round(4).to_dict('records')))
