"""Learned policies, step 1 (plan D1_ML_PLAN.md): training tables.
(1) Solo-sell cells (cycle x minute x right, j = 1..380): market features (no orders): from bl_full_panel (extremes, moves, premium lows, range position, reactive break/side/depth, minute) + depth beyond the 15/60-min extremes + spot-ladder fire (decoded ladder, events = timetable + reactive fires) + late R3 condition; book features from the real book (own/other short premium ratio and lots, bl_solo_panel); target = real solo lots (non-deep).
(2) Buy-back lot panel (bl_bt_lot) + premium speed, 30-min breakout against, right premium ratio, open lots on the contract.
Outputs bl_ml_sell.pkl.gz, bl_ml_mkt.pkl.gz (per-cycle market feature arrays for the simulator), bl_ml_bb.pkl.gz"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
import bl_fr_sim as S
FP = pd.read_pickle(f'{OUT}/bl_full_panel.pkl.gz'); SP = pd.read_pickle(f'{OUT}/bl_solo_panel.pkl.gz'); SD = pd.read_pickle(f'{OUT}/bl_sd_orders.pkl.gz'); CY = S.CY
MK = ['react_fire', 'react_fav', 'react_depth', 'pl5_itm', 'pl15_itm', 'pl30_itm', 'pl5_atm', 'pl15_atm', 'pl30_atm', 'fav5', 'bk5', 'bkhl5', 'fav15', 'bk15', 'bkhl15', 'fav30', 'bk30', 'bkhl30', 'fav60', 'bk60', 'bkhl60', 'pos15']
def ladder_and_depth(i):
    d = S.prep(i); r = d['r']; h, l, c, K, step = d['h'], d['l'], d['c'], d['K'], d['step']; atm = lambda x: float(K[np.argmin(np.abs(K - x))])
    ev = {'CE': [], 'PE': []}
    for w in S.W[S.W.version == r.version].itertuples():
        j = int((33360 + w.sec_after_0916 - 33300) // 60); ev['CE'].append(j); ev['PE'].append(j)
    for j, s, dep in S.react_fires(i, d): ev['CE'].append(j); ev['PE'].append(j)
    out = {}; st = step * 0.2
    for cp in ('CE', 'PE'):
        evs = sorted(set(ev[cp])); ptr = 0; refp = None; lad = np.zeros(390)
        for j in range(1, 375):
            while ptr < len(evs) and evs[ptr] < j: refp = c[max(evs[ptr] - 1, 0)]; ptr += 1
            if refp is None: continue
            if not ((l[j] < l[max(j - 60, 0):j].min()) if cp == 'CE' else (h[j] > h[max(j - 60, 0):j].max())): continue
            if cp == 'CE' and l[j] < refp - st: lad[j] = 1; refp = refp - st * max(1, int((refp - l[j]) // st))
            elif cp == 'PE' and h[j] > refp + st: lad[j] = 1; refp = refp + st * max(1, int((h[j] - refp) // st))
        d60 = np.zeros(390); d15 = np.zeros(390)
        for j in range(1, 375):
            for N, arr in ((60, d60), (15, d15)):
                a = max(j - N, 0); arr[j] = ((l[a:j].min() - l[j]) if cp == 'CE' else (h[j] - h[a:j].max())) / step
        out[cp] = (lad, d60, d15)
    return out
rows = []; MKT = {}
for i in range(len(CY)):
    ld = ladder_and_depth(i); f = FP[FP.cid == i].set_index(['j', 'cp'])
    arr = np.full((390, 2, len(MK) + 5), np.nan)
    for ci, cp in enumerate(('CE', 'PE')):
        lad, d60, d15 = ld[cp]
        for j in range(1, 390):
            m = f.loc[(j, cp), MK].values.astype(float) if (j, cp) in f.index else np.full(len(MK), np.nan)
            late = float(345 <= j <= 374 and ((f.loc[(j, cp), 'bk15'] == 1) or (f.loc[(j, cp), 'pl15_itm'] == 1))) if (j, cp) in f.index else 0.0
            arr[j, ci] = np.r_[m, lad[j], d60[j], d15[j], late, j]
    MKT[i] = arr
COLS_M = MK + ['ladder_fire', 'depth60', 'depth15', 'late_r3', 'minute']; COLS_B = ['own_ratio', 'other_ratio', 'own_lots', 'other_lots']
sp = SP.set_index(['cid', 'j', 'cp']); tgt = SD[(SD.typ == 'solo') & ~SD.deep].groupby(['cid', 'j', 'cp']).lots.sum()
for i in range(len(CY)):
    for ci, cp in enumerate(('CE', 'PE')):
        for j in range(1, 381):
            b = sp.loc[(i, j, cp), COLS_B].values.astype(float) if (i, j, cp) in sp.index else np.full(4, np.nan)
            rows.append([i, j, cp, int(tgt.get((i, j, cp), 0)), int(cp == 'CE')] + list(MKT[i][j, ci]) + list(b))
X = pd.DataFrame(rows, columns=['cid', 'j', 'cp', 'y', 'is_ce'] + COLS_M + COLS_B); X.to_pickle(f'{OUT}/bl_ml_sell.pkl.gz'); pd.to_pickle(dict(arr=MKT, cols=COLS_M), f'{OUT}/bl_ml_mkt.pkl.gz')
print('sell cells', X.shape, 'cells with solo lots', int((X.y > 0).sum()), 'lots', int(X.y.sum()), X.y.value_counts().sort_index().head(8).to_dict())
# buy-back lot panel extras
L = pd.read_pickle(f'{OUT}/bl_bt_lot.pkl.gz'); import bl_sd_build, bl_ohlc
OP = bl_sd_build.load_opt(); OH = bl_ohlc.load(); vel = np.full(len(L), np.nan); don = np.zeros(len(L)); ci_ = L.cid.values; jj = L.j.values; isce = L.cp.values == 'CE'
for i, r in enumerate(CY.itertuples()):
    m = np.where(ci_ == i)[0]
    if not len(m): continue
    op = OP[(r.und, r.expiry)]; ki = {int(k): x for x, k in enumerate(op['K'])}; xi = np.array([ki[int(k)] for k in L.strike.values[m]]); o = OH[(r.und, r.expiry)]; h, l, c = o.high.values, o.low.values, o.close.values
    H = np.where(isce[m][:, None], op[('CE', 'high')][xi], op[('PE', 'high')][xi]); Cc = np.where(isce[m][:, None], op[('CE', 'close')][xi], op[('PE', 'close')][xi]); a = np.arange(len(m)); jm = jj[m]
    base = Cc[a, np.maximum(jm - 4, 0)]; vel[m] = np.where(base > 0, H[a, jm] / base, np.nan)
    hi30 = np.array([h[max(j - 31, 0):j - 1].max() if j > 2 else np.inf for j in jm]); lo30 = np.array([l[max(j - 31, 0):j - 1].min() if j > 2 else -np.inf for j in jm])
    don[m] = np.where(isce[m], c[jm - 1] > hi30, c[jm - 1] < lo30)
L['vel3'] = vel; L['don30'] = don.astype(int); L['typ_code'] = L.typ.map({'scheduled': 0, 'reactive': 1, 'solo': 2, 'late': 3, 'deep': 4}).fillna(2)
g = L.assign(pe=L.ratio_c * L.entry).groupby(['cid', 'j', 'cp']); rr = (g.pe.sum() / g.entry.sum()).rename('right_ratio'); L = L.merge(rr.reset_index(), on=['cid', 'j', 'cp'], how='left')
L['n_open'] = L.groupby(['cid', 'j', 'cp', 'strike']).lid.transform('size'); L.to_pickle(f'{OUT}/bl_ml_bb.pkl.gz'); print('buy-back lot panel', L.shape, 'positives', int(L.y.sum()))
