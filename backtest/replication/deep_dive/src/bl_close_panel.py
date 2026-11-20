"""Contract-minute panel for the BUY-BACK (close) decision of body shorts. Row = (cycle, day, minute j >= 5, contract with a net short position before minute j). Event = a body buy-back of that contract inside minute j.
Features (causal): ratio (price / average body entry), price_chg_pct, loss_inr_lot (₹ per lot), delta (BS, signed as seen by the short: |delta| of the option), itm_steps (+ = ITM), abs_steps (distance from spot), spot_move_since_entry % (adverse to the short = +), hold_min (since the first body sale of the contract), gamma, lots, time of day, book-level (net delta, book price ratio, other-right ratio).
Output outputs/bl_close_panel.csv"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from bl_greeks import surface, CAP
O = load_orders(); cyc = pd.read_csv(ref.CYCLES); ch = Chain(); LOT = ref.LOT; rows = []
for d, flag in ((0, 'has_d1'), (1, 'has_d0')):
    for u, e, h in zip(cyc.und, cyc.expiry, cyc[flag]):
        if not h: continue
        c = ch.cyc(u, e); K = np.array(c['strikes'], dtype=float); si = c['_si']; spot = np.array(c[(d, 'spot')], dtype=float); step = ref.STEP[u]; T = np.maximum(((1 if d == 0 else 0) + (375 - np.arange(375)) / 375) / 252.0, 1e-4)
        P = {'CE': np.array(c[(d, 'CE', 'close')], dtype=float), 'PE': np.array(c[(d, 'PE', 'close')], dtype=float)}; sf = {}
        for cp in ('CE', 'PE'): iv, de, ga, ve = surface(P[cp], spot, K, T, cp); sf[cp] = (de, ga)
        E = O[(O.und == u) & (O.expiry == e)].sort_values(['te', 'row']); ev_te = E.te.values; ev = list(zip(E.cp, E.strike.map(lambda k: si.get(int(k), -1)), E.sl, E.module, E.side, E.lots, E.px_avg, E.role, E.tod, E.dayno)); ptr = 0
        nk = len(K); net = {'CE': np.zeros(nk), 'PE': np.zeros(nk)}; ent_v = {'CE': np.zeros(nk), 'PE': np.zeros(nk)}; ent_l = {'CE': np.zeros(nk), 'PE': np.zeros(nk)}; first_j = {'CE': np.full(nk, -1), 'PE': np.full(nk, -1)}
        cov = {}; 
        for cp_, kk, sl, mod, side, lots, pxa, role, tod, dn in ev:
            if mod == 'num' and role == 'cover_short' and dn == d and kk >= 0: cov[(int((tod - ref.OPEN_SEC) // 60), cp_, kk)] = cov.get((int((tod - ref.OPEN_SEC) // 60), cp_, kk), 0) + lots
        for j in range(5, 374):
            thr = d * 100000 + ref.OPEN_SEC + j * 60
            while ptr < len(ev_te) and ev_te[ptr] < thr:
                cp_, kk, sl, mod, side, lots, pxa, role, tod, dn = ev[ptr]; ptr += 1
                if kk < 0: continue
                net[cp_][kk] += sl
                if mod == 'num' and side == 'Sell':
                    ent_v[cp_][kk] += lots * pxa; ent_l[cp_][kk] += lots
                    if first_j[cp_][kk] < 0: first_j[cp_][kk] = j - 1 if dn == d else 0
            s1 = spot[j - 1]
            if not np.isfinite(s1): continue
            nd = sum(np.nansum(net[cp] * sf[cp][0][:, j - 1]) for cp in ('CE', 'PE')); Sh = {cp: np.where(net[cp] < 0, -net[cp], 0.0) for cp in ('CE', 'PE')}
            for cp in ('CE', 'PE'):
                sel = np.where((Sh[cp] > 0) & (ent_l[cp] > 0))[0]
                if not len(sel): continue
                now = P[cp][sel, j - 1]; avg = ent_v[cp][sel] / ent_l[cp][sel]; ok = np.isfinite(now) & (avg > 0)
                if not ok.any(): continue
                sel = sel[ok]; now = now[ok]; avg = avg[ok]; sgn = 1 if cp == 'CE' else -1; ks = K[sel]; fj = first_j[cp][sel]; s0 = np.where(fj >= 0, spot[np.maximum(fj, 0)], np.nan)
                for q in range(len(sel)):
                    kk = sel[q]; rows.append((['D-1', 'D0'][d], u, e, cp, j, ks[q], int(cov.get((j, cp, kk), 0) > 0), now[q] / avg[q], now[q] / avg[q] - 1, (now[q] - avg[q]) * LOT[u], abs(sf[cp][0][kk, j - 1]) if np.isfinite(sf[cp][0][kk, j - 1]) else np.nan, sgn * (s1 - ks[q]) / step, abs(s1 - ks[q]) / step,
                        sgn * (s1 / s0[q] - 1) * 100 if np.isfinite(s0[q]) else np.nan, (j - 1 - fj[q]) if fj[q] >= 0 else np.nan, sf[cp][1][kk, j - 1], Sh[cp][kk], nd, now[q]))
Pn = pd.DataFrame(rows, columns=['day', 'und', 'expiry', 'cp', 'j', 'strike', 'event', 'ratio', 'price_chg', 'loss_inr_lot', 'abs_delta', 'itm_steps', 'abs_steps', 'spot_move_adv', 'hold_min', 'gamma', 'lots', 'book_nd', 'price']); Pn['itm'] = (Pn.itm_steps > 0).astype(int)
Pn.to_csv(f'{OUT}/bl_close_panel.csv.gz', index=False); print(Pn.groupby('day').agg(rows=('event', 'size'), events=('event', 'sum')).to_string()); print(Pn[['ratio', 'abs_delta', 'itm_steps', 'hold_min', 'loss_inr_lot']].describe().round(2).T.to_string())
