"""Buy-back third pass, step 2: holding-time structure. For each buy-back order (all, in loss and in profit), the lot bought (cheapest open lot convention, and FIFO convention as a check): its sell type (scheduled / reactive / solo / deep), its own minutes held, ratio at buy-back; histogram of holding times (fixed-time exits would show spikes); ratio by holding time and sell type.
Outputs bl_bt_fresh.csv, bl_summary_bt2.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); O = load_orders(); SD = pd.read_pickle(f'{OUT}/bl_sd_orders.pkl.gz'); R = {}; rows = []
SD['t2'] = np.where(SD.deep, 'deep', SD.typ)
for i, r in enumerate(CY.itertuples()):
    z = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 0) & (O.module == 'num') & O.role.isin(['open_short', 'cover_short'])].sort_values(['te', 'row']); sd = SD[SD.cid == i]
    lab = {(round(x.te, 3), x.cp, int(x.strike)): x.t2 for x in sd.itertuples()}; book = {}
    for q in z.itertuples():
        k = (q.cp, int(q.strike))
        if q.role == 'open_short': book.setdefault(k, []).extend([(q.ref_px, q.te, lab.get((round(q.te, 3), q.cp, int(q.strike)), 'solo'))] * int(q.lots)); continue
        lots = book.get(k, [])
        if not lots: continue
        a = int(np.argmin([l_[0] for l_ in lots])); e, te0, t2 = lots[a]; ef, tf, t2f = lots[0]
        rows.append(dict(cid=i, und=r.und, te=q.te, cp=q.cp, strike=q.strike, ratio=q.ref_px / e, mins_held=(q.te - te0) / 60, typ=t2, ratio_fifo=q.ref_px / ef, mins_held_fifo=(q.te - tf) / 60, typ_fifo=t2f, n_open=len(lots), hhmm=q.te / 3600))
        lots.pop(a); book[k] = lots
X = pd.DataFrame(rows); X['state'] = np.where(X.ratio > 1, 'in loss', 'in profit'); X.to_csv(f'{OUT}/bl_bt_fresh.csv', index=False)
X['held_bin'] = pd.cut(X.mins_held, [0, 2, 5, 10, 15, 20, 30, 45, 60, 120, 400])
print(pd.crosstab(X.held_bin, X.state).to_string())
print('ratio median by holding time and state'); print(X.groupby(['held_bin', 'state']).ratio.median().unstack().round(3).to_string())
print('lot type of bought lot (in loss), share by holding time'); print(pd.crosstab(X[X.state == 'in loss'].held_bin, X[X.state == 'in loss'].typ, normalize='index').round(2).to_string())
print('sold-lot type mix overall', SD.t2.value_counts(normalize=True).round(3).to_dict())
h = X.mins_held.round().astype(int); vc = h[h <= 60].value_counts().sort_index(); print('minutes-held counts 0-60:', vc.to_dict())
R['crosstab'] = pd.crosstab(X.held_bin, X.state).astype(int).to_dict(); rec('bt2', {'n': len(X)})
