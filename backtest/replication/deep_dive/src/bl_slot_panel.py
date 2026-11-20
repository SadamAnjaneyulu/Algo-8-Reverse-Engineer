"""Slot-level panel: one row per (cycle, day, slot k = 09:16 + 15 k, right) with the paired-sale outcome in [slot - 10 s, slot + 90 s) and the state variables known at the slot (same library as bl_feat_panel, computed at EVERY slot, no event selection).
Output outputs/bl_slot_panel.csv"""
import sys; sys.path.insert(0, '.')
from bl_common import *
from bl_greeks import R_, CAP, surface
O = load_orders(); cyc = pd.read_csv(ref.CYCLES); ch = Chain(); ALL = pd.read_pickle(f'{OUT}/bl_move_solo_sales.pkl.gz'); rows = []; LOT = ref.LOT
G = lambda a, i: a[i] if i >= 0 else np.nan
for d, flag in ((0, 'has_d1'), (1, 'has_d0')):
    for u, e, h in zip(cyc.und, cyc.expiry, cyc[flag]):
        if not h: continue
        c = ch.cyc(u, e); K = np.array(c['strikes'], dtype=float); si = c['_si']; spot = np.array(c[(d, 'spot')], dtype=float); step = ref.STEP[u]
        T = np.maximum(((1 if d == 0 else 0) + (375 - np.arange(375)) / 375) / 252.0, 1e-4); Pc = np.array(c[(d, 'CE', 'close')], dtype=float); Pp = np.array(c[(d, 'PE', 'close')], dtype=float)
        ivc, dec, gac, vec = surface(Pc, spot, K, T, 'CE'); ivp, dep, gap, vep = surface(Pp, spot, K, T, 'PE'); atm_i = np.array([np.argmin(np.abs(K - s)) if np.isfinite(s) else 0 for s in spot]); jj = np.arange(375)
        atm_iv = np.nanmean(np.vstack([ivc[atm_i, jj], ivp[atm_i, jj]]), axis=0); strd = (Pc[atm_i, jj] + Pp[atm_i, jj]) / spot * 100
        lr = np.diff(np.log(spot), prepend=np.nan); runhi = np.maximum.accumulate(np.nan_to_num(spot, nan=0)); runlo = np.minimum.accumulate(np.where(np.isnan(spot), 1e12, spot))
        E = O[(O.und == u) & (O.expiry == e)].sort_values(['te', 'row']); ev_te = E.te.values; ev = list(zip(E.cp, E.strike.map(lambda k: si.get(int(k), -1)), E.sl, E.module, E.side, E.lots, E.px_avg, E.role, E.tod, E.dayno)); ptr = 0
        nk = len(K); net = {'CE': np.zeros(nk), 'PE': np.zeros(nk)}; ent_v = {'CE': np.zeros(nk), 'PE': np.zeros(nk)}; ent_l = {'CE': np.zeros(nk), 'PE': np.zeros(nk)}; covers = {'CE': [], 'PE': []}
        sales = {cp: ALL[(ALL.und == u) & (ALL.expiry == e) & (ALL.cp == cp) & (ALL.dayno == d)].sort_values('tod') for cp in ('CE', 'PE')}
        for k in range(0, 25):
            j = 1 + 15 * k
            if j > 372: break
            thr = d * 100000 + ref.OPEN_SEC + j * 60
            while ptr < len(ev_te) and ev_te[ptr] < thr:
                cp, kk, sl, mod, side, lots, pxa, role, tod, dn = ev[ptr]; ptr += 1
                if kk < 0: continue
                net[cp][kk] += sl
                if mod == 'num' and side == 'Sell': ent_v[cp][kk] += lots * pxa; ent_l[cp][kk] += lots
                if mod == 'num' and role == 'cover_short' and dn == d: covers[cp].append((tod, lots))
            s1 = G(spot, j - 1)
            if not np.isfinite(s1): continue
            jm = max(j - 1, 0); nd_ce = np.nansum(net['CE'] * dec[:, jm]); nd_pe = np.nansum(net['PE'] * dep[:, jm]); nd = nd_ce + nd_pe; gam = np.nansum(net['CE'] * gac[:, jm]) + np.nansum(net['PE'] * gap[:, jm]); veg = np.nansum(net['CE'] * vec[:, jm]) + np.nansum(net['PE'] * vep[:, jm])
            Sh = {cp: np.where(net[cp] < 0, -net[cp], 0.0) for cp in ('CE', 'PE')}; Lg = {cp: np.where(net[cp] > 0, net[cp], 0.0) for cp in ('CE', 'PE')}; nowp = {'CE': Pc[:, jm], 'PE': Pp[:, jm]}; ratio = {}; mtm = {}
            for cp in ('CE', 'PE'):
                avg = np.where(ent_l[cp] > 0, ent_v[cp] / np.maximum(ent_l[cp], 1e-9), np.nan); ok = (Sh[cp] > 0) & np.isfinite(avg) & np.isfinite(nowp[cp]) & (avg > 0)
                ratio[cp] = (Sh[cp][ok] * nowp[cp][ok]).sum() / (Sh[cp][ok] * avg[ok]).sum() if ok.any() else np.nan; mtm[cp] = (Sh[cp][ok] * (avg[ok] - nowp[cp][ok])).sum() * LOT[u]
            rv30 = np.nanstd(lr[max(j - 30, 0):j]) * np.sqrt(375 * 252) * 100 if j > 3 else np.nan; T0 = ref.OPEN_SEC + j * 60
            for cp in ('CE', 'PE'):
                oth = 'PE' if cp == 'CE' else 'CE'; sgn = 1 if cp == 'CE' else -1; sd = sales[cp]; win = sd[(sd.tod >= T0 - 10) & (sd.tod < T0 + 90)]; prevw = sd[(sd.tod >= T0 - 900 - 10) & (sd.tod < T0 - 900 + 90)]
                last_slot = T0 - 900; cov_own = sum(l for t, l in covers[cp] if t >= last_slot); cov_oth = sum(l for t, l in covers[oth] if t >= last_slot)
                f = dict(day=['D-1', 'D0'][d], und=u, expiry=e, cp=cp, k=k, j=j, lots_paired=win[win.paired].lots.sum(), lots_any=win.lots.sum(), lots_solo=win[~win.paired].lots.sum(), prev_paired=prevw[prevw.paired].lots.sum(),
                    own_ratio=ratio[cp], other_ratio=ratio[oth], S_own=Sh[cp].sum(), S_other=Sh[oth].sum(), L_own=Lg[cp].sum(), L_other=Lg[oth].sum(), imb=Sh[cp].sum() - Sh[oth].sum(), mtm_own=mtm[cp] / CAP * 100, mtm_other=mtm[oth] / CAP * 100, mtm_tot=(mtm[cp] + mtm[oth]) / CAP * 100,
                    book_ratio=(Sh['CE'].sum() * (ratio['CE'] if np.isfinite(ratio['CE']) else 1) + Sh['PE'].sum() * (ratio['PE'] if np.isfinite(ratio['PE']) else 1)) / max(Sh['CE'].sum() + Sh['PE'].sum(), 1),
                    nd=nd, delta_need=sgn * nd, nd_per_short=sgn * nd / max(Sh['CE'].sum() + Sh['PE'].sum(), 1), gamma=gam, vega=veg, atm_iv=atm_iv[jm] * 100, d_iv15=(atm_iv[jm] - G(atm_iv, j - 16)) * 100, d_iv30=(atm_iv[jm] - G(atm_iv, j - 31)) * 100, iv_rel=atm_iv[jm] / atm_iv[1] if np.isfinite(atm_iv[1]) else np.nan,
                    straddle=strd[jm], d_str15=strd[jm] - G(strd, j - 16), d_str30=strd[jm] - G(strd, j - 31), rv30=rv30, fav_open=-sgn * (s1 / spot[0] - 1) * 100, abs15=abs(s1 / G(spot, j - 16) - 1) * 100,
                    dd_ext=(runhi[jm] - s1) / runhi[jm] * 100 if cp == 'CE' else (s1 - runlo[jm]) / runlo[jm] * 100, cov_own=cov_own, cov_oth=cov_oth, solo_own_since=sd[(~sd.paired) & (sd.tod >= last_slot) & (sd.tod < T0)].lots.sum(), mins=j)
                for kk in (5, 15, 30, 60): f[f'fav{kk}'] = -sgn * (s1 / G(spot, j - 1 - kk) - 1) * 100
                f['asym'] = f['other_ratio'] - f['own_ratio']; rows.append(f)
Pn = pd.DataFrame(rows); Pn.to_csv(f'{OUT}/bl_slot_panel.csv', index=False); print(Pn.groupby('day').agg(rows=('k', 'size'), executed=('lots_paired', lambda s: (s > 0).mean()), mean_lots=('lots_paired', 'mean')).round(3).to_string())
print(Pn[Pn.day == 'D-1'].groupby('k').agg(n=('k', 'size'), executed=('lots_paired', lambda s: (s > 0).mean()), mean_lots=('lots_paired', 'mean')).round(2).T.to_string())
