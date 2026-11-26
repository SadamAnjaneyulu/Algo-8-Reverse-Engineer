"""Buy-back third pass, step 3: lot-level panel (every open real body short lot x D-1 minute) with its own sell type (scheduled / reactive / solo-attached-extra / solo / late / deep), entry decision price, minutes held, ratio (minute high, previous close) and label = this lot bought back in the minute (on a buy-back, the lot removed is the highest-ratio open lot on the contract).
Hazard by ratio bin per type; out-of-fold per-type threshold F1 (+-1 min, lot level) vs one common threshold. Outputs bl_bt_lot.pkl.gz, bl_bt_type.csv, bl_summary_bt3.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
import bl_sd_build
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); O = load_orders(); OP = bl_sd_build.load_opt(); SD = pd.read_pickle(f'{OUT}/bl_sd_orders.pkl.gz'); R = {}; rows = []
SD['t2'] = np.where(SD.deep, 'deep', np.where((SD.typ == 'solo') & (SD.te >= 54000), 'late', SD.typ))
lid = 0; bb = {}
for i, r in enumerate(CY.itertuples()):
    z = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 0) & (O.module == 'num') & O.role.isin(['open_short', 'cover_short'])].sort_values(['te', 'row']); sd = SD[SD.cid == i]
    lab = {(round(x.te, 3), x.cp, int(x.strike)): x.t2 for x in sd.itertuples()}; op = OP[(r.und, r.expiry)]; ki = {int(k): x for x, k in enumerate(op['K'])}
    zl = list(z.itertuples()); p = 0; book = {}
    for j in range(2, 376):
        T0 = 33300 + 60 * j; ev = []
        while p < len(zl) and zl[p].te < T0:
            q = zl[p]; k = (q.cp, int(q.strike))
            if q.role == 'open_short':
                for _ in range(int(q.lots)): book.setdefault(k, []).append([lid, q.ref_px, int((q.te - 33300) // 60), lab.get((round(q.te, 3), q.cp, int(q.strike)), 'solo')]); lid += 1
            elif book.get(k):
                jb = int((q.te - 33300) // 60); a = int(np.argmin([l_[1] for l_ in book[k]])); bb[book[k][a][0]] = jb; book[k].pop(a)
            p += 1
        if j > 374: break
        for (cp, kk), lots in book.items():
            if kk not in ki: continue
            x = ki[kk]; pc = op[(cp, 'close')][x, j - 1]; ph = op[(cp, 'high')][x, j]
            for (lid_, e, je, t2) in lots:
                if je >= j: continue
                rows.append((i, j, cp, kk, lid_, t2, e, j - je, pc / e, ph / e))
X = pd.DataFrame(rows, columns=['cid', 'j', 'cp', 'strike', 'lid', 'typ', 'entry', 'held', 'ratio_c', 'ratio_h'])
# label: lot bought back in minute j (bb holds the buy-back minute of each removed lot)
BB = pd.Series(bb); X['y'] = (X.lid.map(BB) == X.j).astype(int); X['bb_j'] = X.lid.map(BB); X.to_pickle(f'{OUT}/bl_bt_lot.pkl.gz'); print(X.shape, 'labelled lot buy-backs', int(X.y.sum()), 'of', len(BB))
for t, g in X.groupby('typ'):
    hz = g.groupby(pd.cut(g.ratio_h, [0, .9, 1, 1.05, 1.1, 1.15, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 9]), observed=True).y.agg(['mean', 'size']); print(t, 'lots bought back', int(g.y.sum()), {str(k).replace('(', '').replace(']', ''): (round(a * 100, 1), int(n)) for k, (a, n) in hz.iterrows()})
X.to_pickle(f'{OUT}/bl_bt_lot.pkl.gz')
