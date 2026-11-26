"""[full D0 variant: bl_d0f_panel.py: all cycles with D0 sells, minutes from 09:15, gap features] D0 counter-sell trigger search: builds the minute panel (plan reports/D0_CTRIG_PLAN.md).
One row = (cycle, minute j, right cp) for minutes 4 .. min(354, minute before the cycle's first stop-module order). cp = the right that might be sold.
Decision-time features use bars up to j-1 and orders strictly before minute j. Contemporaneous features (suffix _c) use bar j and are diagnostic only.
Outputs bl_d0n_panel.pkl.gz, bl_d0n_orders.pkl.gz (solo sale orders with panel row id and the D0_SELL_TYPES label)"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); S = pd.read_pickle(f'{OUT}/bl_d0s_orders.pkl.gz'); T = pd.read_pickle(f'{OUT}/bl_d0t_orders.pkl.gz'); X = pd.read_pickle(f'{OUT}/bl_d0y_lots.pkl.gz')
import bl_ohlc; OH1 = bl_ohlc.load(); SP = pd.read_pickle(f'{OUT}/bl_d0_spot.pkl.gz'); OPT = pd.read_pickle(f'{OUT}/bl_d0_opt.pkl.gz'); MT = pd.read_pickle(f'{OUT}/bl_d0x_mtm.pkl.gz')['MT']; O = load_orders()
S = S.assign(type=T.type.values); assert (S.cid.values == T.cid.values).all() and (S.tod.values == T.tod.values).all()
other = lambda c: 'PE' if c == 'CE' else 'CE'
def rsum(a, j, k): return a[max(j - k, 0):j].sum()                     # sum over minutes j-k .. j-1
rows = []; cids = sorted(S.cid.unique())
for i in cids:
    r = CY.iloc[i]; und = r.und; st = float(ref.STEP[und]); sp = SP[(und, r.expiry)]; c = sp.close.values; hi = sp.high.values; lo = sp.low.values; op = OPT[(und, r.expiry)]; K = op['K']; kidx = {int(k): n for n, k in enumerate(K)}
    z = O[(O.und == und) & (O.expiry == r.expiry)]; stop_t = z[(z.dayno == 1) & (z.module == 's_')].tod.min(); je = int(min(354, ((stop_t - 33300) // 60 - 1) if stop_t == stop_t else 354))
    body = z[(z.module == 'num') & z.role.isin(['open_short', 'cover_short'])].sort_values(['dayno', 'tod']); body['mj'] = np.where(body.dayno == 0, -1, ((body.tod - 33300) // 60).astype(int))
    # per-minute event counts on D0 (body)
    bb = {cp: np.zeros(375) for cp in ('CE', 'PE')}; sl = {cp: np.zeros(375) for cp in ('CE', 'PE')}; sell = {cp: np.zeros(375) for cp in ('CE', 'PE')}; solo = {cp: np.zeros(375) for cp in ('CE', 'PE')}
    for q in body[(body.dayno == 1) & (body.mj >= 0) & (body.mj <= 374)].itertuples():
        (bb if q.role == 'cover_short' else sell)[q.cp][int(q.mj)] += q.lots
    for q in X[X.cid == i].itertuples():
        if q.type == '3 stop-loss': sl[q.cp][int(q.j)] += 1
    for q in S[(S.cid == i) & (S.lab == 'solo')].itertuples(): solo[q.cp][int(q.j)] += q.lots
    # running book: per right, per strike: lots n and average cost; state before minute j
    book = {cp: {} for cp in ('CE', 'PE')}; ptr = 0; bl = body.reset_index(drop=True)
    def apply(q):
        b = book[q.cp].setdefault(int(q.strike), [0.0, 0.0])
        if q.role == 'open_short': tot = b[0] * b[1] + q.lots * q.px_avg; b[0] += q.lots; b[1] = tot / b[0] if b[0] else 0.0
        else: b[0] = max(b[0] - q.lots, 0.0)
    while ptr < len(bl) and bl.mj[ptr] < 0: apply(bl.iloc[ptr]); ptr += 1
    P = {cp: op[(cp, 'close')] for cp in ('CE', 'PE')}
    last_sale = {cp: -999 for cp in ('CE', 'PE')}; last_bb = {cp: -999 for cp in ('CE', 'PE')}
    d1c = float(OH1[(und, r.expiry)].close.values[-1]); gap_steps = (float(sp.open.values[0]) - d1c) / st; carried = {}
    pj = 0                                                            # pointer to minute whose orders have been applied
    for j in range(0, je + 1):
        while ptr < len(bl) and bl.mj[ptr] < j: apply(bl.iloc[ptr]); ptr += 1
        for cp in ('CE', 'PE'):
            if sell[cp][j - 1] > 0 and j > 0: last_sale[cp] = j - 1
            if bb[cp][j - 1] > 0 and j > 0: last_bb[cp] = j - 1
        if j == 0:                                                       # opening minute: only the gap, the carried book and the clock are known
            carried = {cp: float(sum(v[0] for v in book[cp].values() if v[0] > 0)) for cp in ('CE', 'PE')}
            for cp in ('CE', 'PE'):
                o = other(cp); sgf = -1.0 if cp == 'CE' else 1.0
                rows.append(dict(cid=i, j=0, cp=cp, und=und, version=r.version, expiry=r.expiry, n_own=carried[cp], n_other=carried[o], share_own=carried[cp] / max(carried[cp] + carried[o], 1e-9), hour=9, min_in_15=0, min_in_5=0, is_ce=float(cp == 'CE'), und_nifty=float(und == 'NIFTY'), v2=float(r.version != 'V1'),
                                 gap_fav=sgf * gap_steps, carried_own=carried[cp], carried_other=carried[o], y_lots=solo[cp][0], y=float(solo[cp][0] > 0), sell_all_lots=sell[cp][0], bb_own_same_min=bb[cp][0], bb_other_same_min=bb[o][0], sl_other_same_min=sl[o][0]))
            continue
        j1 = j - 1; atm = int(K[np.argmin(np.abs(K - c[j1]))]); ai = kidx[atm]
        n = {}; ex = {}; rt = {}
        for cp in ('CE', 'PE'):
            nn = 0.0; e = 0.0; cost = 0.0
            for k_, (lots_, avg) in book[cp].items():
                if lots_ <= 0 or k_ not in kidx: continue
                p_ = P[cp][kidx[k_], j1]
                if p_ != p_: continue
                nn += lots_; e += lots_ * p_; cost += lots_ * avg
            n[cp] = nn; ex[cp] = e; rt[cp] = e / cost if cost > 0 else np.nan
        mtm = MT[i]['close'][j1] / 1e5
        for cp in ('CE', 'PE'):
            o = other(cp); sg = -1.0 if cp == 'CE' else 1.0; f = {}
            f['cid'] = i; f['j'] = j; f['cp'] = cp; f['und'] = und; f['version'] = r.version; f['expiry'] = r.expiry
            for k in (1, 3, 5, 15, 30, 60): f[f'fav_ret_{k}'] = sg * (c[j1] - c[max(j1 - k, 0)]) / st
            for w in (15, 30, 60, 120): f[f'fresh_{w}'] = float((lo[j1] < lo[max(j1 - w, 0):j1].min()) if cp == 'CE' else (hi[j1] > hi[max(j1 - w, 0):j1].max())) if j1 > 0 else 0.0
            f['fresh_day'] = float((lo[j1] <= lo[:j1 + 1].min()) if cp == 'CE' else (hi[j1] >= hi[:j1 + 1].max()))
            ext = lo[:j1 + 1].min() if cp == 'CE' else hi[:j1 + 1].max(); f['dist_day_ext'] = sg * (c[j1] - ext) / st * -1 if False else abs(c[j1] - ext) / st
            f['from_open'] = sg * (c[j1] - sp.open.values[0]) / st
            f['vol15'] = float(np.abs(np.diff(c[max(j1 - 15, 0):j1 + 1])).mean() / st) if j1 > 0 else 0.0
            f['bars_since_fresh60'] = next((m for m in range(0, 61) if j1 - m > 0 and ((lo[j1 - m] < lo[max(j1 - m - 60, 0):j1 - m].min()) if cp == 'CE' else (hi[j1 - m] > hi[max(j1 - m - 60, 0):j1 - m].max()))), 61)
            pc = P[cp][ai]; f['atm_px'] = pc[j1]
            for k in (1, 3, 5, 15): f[f'prem_chg_{k}'] = pc[j1] / pc[max(j1 - k, 0)] - 1 if pc[max(j1 - k, 0)] > 0 else np.nan
            f['prem_vs_daymax'] = pc[j1] / np.nanmax(pc[:j1 + 1]) if np.nanmax(pc[:j1 + 1]) > 0 else np.nan; f['prem_vs_daymin'] = pc[j1] / np.nanmin(pc[:j1 + 1]) if np.nanmin(pc[:j1 + 1]) > 0 else np.nan; f['prem_vs_open'] = pc[j1] / pc[0] if pc[0] > 0 else np.nan
            f['n_own'] = n[cp]; f['n_other'] = n[o]; f['share_own'] = n[cp] / (n[cp] + n[o]) if n[cp] + n[o] > 0 else np.nan; f['expo_own'] = ex[cp]; f['expo_other'] = ex[o]; f['expo_share_own'] = ex[cp] / (ex[cp] + ex[o]) if ex[cp] + ex[o] > 0 else np.nan
            f['mark_own'] = rt[cp]; f['mark_other'] = rt[o]; f['mtm_lakh'] = mtm; f['mtm_to_stop'] = mtm + 1.2
            for k in (1, 5, 15):
                f[f'bb_other_{k}'] = rsum(bb[o], j, k); f[f'bb_own_{k}'] = rsum(bb[cp], j, k); f[f'sl_other_{k}'] = rsum(sl[o], j, k); f[f'sl_own_{k}'] = rsum(sl[cp], j, k); f[f'sell_own_{k}'] = rsum(sell[cp], j, k); f[f'sell_other_{k}'] = rsum(sell[o], j, k)
            f['since_sale_own'] = min(j - last_sale[cp], 99); f['since_bb_other'] = min(j - last_bb[o], 99)
            f['hour'] = (33300 + 60 * j) // 3600; f['min_in_15'] = j % 15; f['min_in_5'] = j % 5; f['is_ce'] = float(cp == 'CE'); f['und_nifty'] = float(und == 'NIFTY'); f['v2'] = float(r.version != 'V1')
            # contemporaneous (bar j)
            f['fav_ret_1_c'] = sg * (c[j] - c[j1]) / st; f['fav_ret_3_c'] = sg * (c[j] - c[max(j - 3, 0)]) / st; f['fresh_60_c'] = float((lo[j] < lo[max(j - 60, 0):j].min()) if cp == 'CE' else (hi[j] > hi[max(j - 60, 0):j].max())); f['range_c'] = (hi[j] - lo[j]) / st
            f['prem_chg_1_c'] = pc[j] / pc[j1] - 1 if pc[j1] > 0 else np.nan
            for w in (15, 30, 60): f[f'phx_prem_low_{w}'] = float(pc[j1] <= np.nanmin(pc[max(j1 - w, 0):j1])) if j1 > 0 else 0.0   # post-hoc (after N2): ATM contract close at j-1 at or below its previous w closes
            f['phx_prem_low_day'] = float(pc[j1] <= np.nanmin(pc[:j1 + 1])); f['phx_prem_newlow_c'] = float(pc[j] < np.nanmin(pc[:j])); f['phx_plow_bar_c'] = float(op[(cp, 'low')][ai][j] < np.nanmin(op[(cp, 'low')][ai][:j]))   # bar j (contemporaneous)
            f['gap_fav'] = (-1.0 if cp == 'CE' else 1.0) * gap_steps; f['carried_own'] = carried.get(cp, np.nan); f['carried_other'] = carried.get(o, np.nan)
            f['y_lots'] = solo[cp][j]; f['y'] = float(solo[cp][j] > 0); f['sell_all_lots'] = sell[cp][j]; f['bb_own_same_min'] = bb[cp][j]; f['bb_other_same_min'] = bb[o][j]; f['sl_other_same_min'] = sl[o][j]
            rows.append(f)
PN = pd.DataFrame(rows).reset_index(drop=True); PN['row'] = np.arange(len(PN)); print(PN.shape, PN.y.mean().round(3), PN.cid.nunique())
print(PN.groupby('j').size().head(3).to_dict(), PN.cid.nunique(), 'cycles')
PN.to_pickle(f'{OUT}/bl_d0f_panel.pkl.gz')
