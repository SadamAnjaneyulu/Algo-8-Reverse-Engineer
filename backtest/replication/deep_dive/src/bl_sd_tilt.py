"""Solo decode step 6 (post-hoc): tilt target. Per cycle-minute: open body short lots CE and PE, tilt = CE - PE, spot move from the reference (09:15 open, or the first scheduled ATM) in strike steps (positive = fall). Relation tilt ~ move (pooled, per cycle); deficit = k * move - tilt and its link with solo decisions (CE needs deficit > 0, PE deficit < 0).
Outputs bl_sd_tilt.pkl.gz, bl_summary_sd5.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy.stats import rankdata, spearmanr
import bl_ohlc
OH = bl_ohlc.load(); D = pd.read_pickle(f'{OUT}/bl_sd_orders.pkl.gz'); B = pd.read_pickle(f'{OUT}/bl_sd_bursts.pkl.gz'); CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); O = load_orders(); R = {}
rows = []
for i, r in enumerate(CY.itertuples()):
    u, e = r.und, r.expiry; o = OH[(u, e)]; step = ref.STEP[u]; c = o.close.values; ref0 = o.open.values[0]
    bod = O[(O.und == u) & (O.expiry == e) & (O.dayno == 0) & (O.module == 'num') & O.role.isin(['open_short', 'cover_short'])].sort_values(['te', 'row'])
    sl = np.where(bod.role == 'open_short', bod.lots, -bod.lots); tt = bod.te.values; cps = bod.cp.values
    bb = B[B.cid == i]; ce_b = set(bb[bb.cp == 'CE'].j); pe_b = set(bb[bb.cp == 'PE'].j)
    for j in range(2, 375):
        m = tt < 33300 + 60 * j; ce = int(sl[m & (cps == 'CE')].sum()); pe = int(sl[m & (cps == 'PE')].sum())
        rows.append(dict(cid=i, j=j, ce=ce, pe=pe, tilt=ce - pe, move=(ref0 - c[j - 1]) / step, y_ce=int(j in ce_b), y_pe=int(j in pe_b)))
X = pd.DataFrame(rows)
rho = spearmanr(X.tilt, X.move); R['pooled_spearman'] = [float(rho[0]), float(rho[1])]
k_cyc = X.groupby('cid').apply(lambda g: np.polyfit(g.move, g.tilt, 1)[0] if g.move.std() > 0 else np.nan); R['slope_per_cycle_q'] = k_cyc.quantile([.1, .25, .5, .75, .9]).round(2).tolist()
r_cyc = X.groupby('cid').apply(lambda g: spearmanr(g.tilt, g.move)[0]); R['within_cycle_spearman_q'] = r_cyc.quantile([.1, .25, .5, .75, .9]).round(2).tolist()
kp = np.polyfit(X.move, X.tilt, 1); R['pooled_slope'] = float(kp[0]); print('pooled Spearman', rho, 'pooled slope lots per step', kp, 'per-cycle slope q', R['slope_per_cycle_q'], 'within-cycle rho q', R['within_cycle_spearman_q'])
def auc(s, y): m = ~np.isnan(s); s = s[m]; yy = y[m]; n1 = yy.sum(); n0 = len(yy) - n1; return (rankdata(s)[yy == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
for k in (2, 4, 6, 8, 10, 15):
    dfc = k * X.move - X.tilt; R[f'auc_k{k}'] = dict(CE=float(auc(dfc.values, X.y_ce.values)), PE=float(auc(-dfc.values, X.y_pe.values)))
print({k: v for k, v in R.items() if k.startswith('auc')})
R['auc_move_only'] = dict(CE=float(auc(X.move.values, X.y_ce.values)), PE=float(auc(-X.move.values, X.y_pe.values))); R['auc_tilt_only'] = dict(CE=float(auc(-X.tilt.values.astype(float), X.y_ce.values)), PE=float(auc(X.tilt.values.astype(float), X.y_pe.values))); print(R['auc_move_only'], R['auc_tilt_only'])
X.to_pickle(f'{OUT}/bl_sd_tilt.pkl.gz'); rec('sd5', R)
