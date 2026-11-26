"""Solo decode step 4 (post-hoc hypothesis from step 3): premium balancing. At each solo decision vs control minutes: marked value of the right's open shorts V_own = sum(lots x price), of the other right V_other, ratio V_other/V_own, and the same after the decision. Outputs bl_sd_balance.pkl.gz, bl_summary_sd3.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy.stats import rankdata
import bl_ohlc, bl_sd_build
OH = bl_ohlc.load(); OP = bl_sd_build.load_opt(); D = pd.read_pickle(f'{OUT}/bl_sd_orders.pkl.gz'); B = pd.read_pickle(f'{OUT}/bl_sd_bursts.pkl.gz'); CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); O = load_orders(); R = {}; rng = np.random.default_rng(7)
def book_at(bod, t, op, ki, j, all_modules=False):
    pos = {}
    for q in bod[bod.te < t - 0.5].itertuples():
        key = (q.cp, int(q.strike)); n = pos.get(key, 0); pos[key] = n + (-q.lots if q.side == 'Buy' else q.lots) if not all_modules else n + (q.lots if q.side == 'Sell' else -q.lots)
    V = {'CE': 0.0, 'PE': 0.0}; L = {'CE': 0, 'PE': 0}
    for (c_, k), n in pos.items():
        if n > 0 and k in ki: V[c_] += n * op[(c_, 'close')][ki[k], j - 1]; L[c_] += n
    return V, L
rows = []
for i, r in enumerate(CY.itertuples()):
    u, e = r.und, r.expiry; op = OP[(u, e)]; K = op['K']; ki = {int(k): x for x, k in enumerate(K)}
    bod = O[(O.und == u) & (O.expiry == e) & (O.dayno == 0) & (O.module == 'num') & O.role.isin(['open_short', 'cover_short'])].sort_values(['te', 'row'])
    bb = B[B.cid == i]; qs = [(t, cp, 1, n) for t, cp, n in zip(bb.te, bb.cp, bb.lots)]
    for cp in ('CE', 'PE'):
        for t in rng.uniform(33360, 55800, 300): qs.append((t, cp, 0, 0))
    for t, cp, y, n in qs:
        j = int((t - 33300) // 60)
        if j < 2 or j > 374: continue
        V, L = book_at(bod, t, op, ki, j); oth = 'PE' if cp == 'CE' else 'CE'
        rows.append(dict(cid=i, cp=cp, y=y, lots=n, t=t, V_own=V[cp], V_other=V[oth], ratio_V=V[oth] / V[cp] if V[cp] > 0 else np.nan, L_own=L[cp], L_other=L[oth], ratio_L=L[oth] / L[cp] if L[cp] > 0 else np.nan))
X = pd.DataFrame(rows); X.to_pickle(f'{OUT}/bl_sd_balance.pkl.gz')
def auc(s, y): m = ~np.isnan(s); s = s[m]; yy = y[m]; n1 = yy.sum(); n0 = len(yy) - n1; return (rankdata(s)[yy == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
y = X.y.values; half = X.cid.values % 2 == 0
for v in ('ratio_V', 'ratio_L', 'V_own', 'V_other'): x = X[v].values.astype(float); print(v, 'AUC %.3f (even %.3f odd %.3f) median events %.3f controls %.3f' % (auc(x, y), auc(x[half], y[half]), auc(x[~half], y[~half]), np.nanmedian(x[y == 1]), np.nanmedian(x[y == 0]))); R[v] = float(auc(x, y))
bins = [0, .6, .8, .9, 1, 1.1, 1.2, 1.3, 1.5, 2, 3, 100]; H = pd.DataFrame({'events': np.histogram(X[X.y == 1].ratio_V.dropna(), bins)[0], 'controls': np.histogram(X[X.y == 0].ratio_V.dropna(), bins)[0]}, index=[f'{a}-{b}' for a, b in zip(bins[:-1], bins[1:])]); H['events_per_control'] = (H.events / H.controls).round(3); print(H.T.to_string()); R['hist'] = H.to_dict()
rec('sd3', R)
