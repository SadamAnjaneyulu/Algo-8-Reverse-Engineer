"""Buy-back decode step 4 (right-level controller hypothesis): per D-1 right-minute: all open body short lots of the right (entry decision price, current price = previous close and current high), right ratio = sum price / sum entry, right MTM loss (Rs) = sum(price - entry) x unit, its share of premium.
Hazard of any buy-back on the right vs each right-level variable; at buy-back minutes: ratio before vs after removing the bought lots (highest own-ratio first); and whether the lots bought are the highest-ratio ones.
Outputs bl_bb_right.pkl.gz, bl_summary_bb4.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy.stats import rankdata
import bl_sd_build
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); O = load_orders(); OP = bl_sd_build.load_opt(); R = {}; rows = []; sel = []
for i, r in enumerate(CY.itertuples()):
    z = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 0) & (O.module == 'num') & O.role.isin(['open_short', 'cover_short'])].sort_values(['te', 'row']); zl = list(z.itertuples()); p = 0
    op = OP[(r.und, r.expiry)]; K = op['K']; ki = {int(k): x for x, k in enumerate(K)}; book = {}
    cov = z[z.role == 'cover_short'].assign(j=lambda d: ((d.te - 33300) // 60).astype(int))
    for j in range(2, 375):
        T0 = 33300 + 60 * j
        while p < len(zl) and zl[p].te < T0:
            o = zl[p]; k = (o.cp, int(o.strike))
            if o.role == 'open_short': book.setdefault(k, []).extend([o.ref_px] * int(o.lots))
            elif book.get(k): book[k].pop(int(np.argmin(book[k])))
            p += 1
        for cp in ('CE', 'PE'):
            L = [(kk, e, op[(cp, 'close')][ki[kk], j - 1], op[(cp, 'high')][ki[kk], j]) for (c2, kk), v in book.items() if c2 == cp and kk in ki for e in v]
            if not L: continue
            e = np.array([x[1] for x in L]); pc = np.array([x[2] for x in L]); ph = np.array([x[3] for x in L]); cv = cov[(cov.cp == cp) & (cov.j == j)]; n = int(cv.lots.sum())
            d = dict(cid=i, j=j, cp=cp, y=int(n > 0), n_y=n, n_open=len(L), ratio_c=pc.sum() / e.sum(), ratio_h=ph.sum() / e.sum(), loss_rs=(pc - e).sum() * r.unit, loss_pct_prem=(pc - e).sum() / e.sum(), max_lot_c=(pc / e).max(), max_lot_h=(ph / e).max(), n_lot_ge15_h=int((ph / e >= 1.5).sum()))
            if n:
                order = np.argsort(-(pc / e)); keep = np.ones(len(L), bool); keep[order[:n]] = False; d['ratio_c_after'] = pc[keep].sum() / e[keep].sum() if keep.any() else np.nan
                # are the bought contracts the ones holding the highest-ratio lots?
                topk = set(L[x][0] for x in order[:n]); sel.append(dict(cid=i, j=j, cp=cp, n=n, bought_in_topn=float(np.mean([int(s) in topk for s in cv.strike.repeat(cv.lots.astype(int))])), chance=float(len({L[x][0] for x in order[:n]})) / max(len({x[0] for x in L}), 1)))
            rows.append(d)
X = pd.DataFrame(rows); X.to_pickle(f'{OUT}/bl_bb_right.pkl.gz'); S_ = pd.DataFrame(sel); y = X.y.values; print(X.shape, 'right-minutes with buy-back', int(y.sum()))
def auc(s, y): m = ~np.isnan(s); s, yy = s[m], y[m]; n1 = yy.sum(); n0 = len(yy) - n1; return (rankdata(s)[yy == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
for v in ('ratio_c', 'ratio_h', 'loss_rs', 'loss_pct_prem', 'max_lot_c', 'max_lot_h', 'n_lot_ge15_h'): R[f'auc_{v}'] = float(auc(X[v].values.astype(float), y)); print(v, round(R[f'auc_{v}'], 3))
for v, bins in (('ratio_c', [0, .8, 1, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 9]), ('max_lot_h', [0, 1.2, 1.4, 1.5, 1.55, 1.6, 1.65, 1.7, 1.8, 9])):
    hz = X.groupby(pd.cut(X[v], bins), observed=True).y.agg(['mean', 'size']); R[f'hz_{v}'] = {str(k): [round(float(a), 3), int(b)] for k, (a, b) in hz.iterrows()}; print(v, R[f'hz_{v}'])
b = X[X.y == 1]; R['ratio_c_before_q'] = b.ratio_c.quantile([.1, .25, .5, .75, .9]).round(3).to_dict(); R['ratio_c_after_q'] = b.ratio_c_after.quantile([.1, .25, .5, .75, .9]).round(3).to_dict(); print('before', R['ratio_c_before_q'], 'after', R['ratio_c_after_q'])
R['bought_from_topn'] = float(S_.bought_in_topn.mean()); R['topn_chance'] = float(S_.chance.mean()); print('bought contract among the n highest-ratio lots:', round(R['bought_from_topn'], 3), 'chance', round(R['topn_chance'], 3)); rec('bb4', R)
