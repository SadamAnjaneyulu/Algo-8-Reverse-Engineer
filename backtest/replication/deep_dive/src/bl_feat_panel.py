"""Feature library panel for the solo-sell variable search (see reports/BODY_SOLO_VARIABLE_SEARCH_PLAN.md). Same event/risk-set definition as bl_move_panel.py plus Greeks, volatility proxies, inventory and activity features.
Black-Scholes with IV implied from each contract's minute close (r = 6.5 %/yr, no dividends, T in trading days / 252). Output outputs/bl_feat_panel.csv"""
import sys; sys.path.insert(0, '.')
from bl_common import *
from scipy.special import ndtr
from bl_greeks import R_, CAP, bs_price, surface
O = load_orders(); cyc = pd.read_csv(ref.CYCLES); ch = Chain(); ALL = pd.read_pickle(f'{OUT}/bl_move_solo_sales.pkl.gz'); rows = []; LOT = ref.LOT
for d, flag in ((0, 'has_d1'), (1, 'has_d0')):
    for u, e, h in zip(cyc.und, cyc.expiry, cyc[flag]):
        if not h: continue
        c = ch.cyc(u, e); K = np.array(c['strikes'], dtype=float); si = c['_si']; spot = np.array(c[(d, 'spot')], dtype=float); step = ref.STEP[u]
        T = (((1 if d == 0 else 0) + (375 - np.arange(375)) / 375) / 252.0); T = np.maximum(T, 1e-4)
        Pc = np.array(c[(d, 'CE', 'close')], dtype=float); Pp = np.array(c[(d, 'PE', 'close')], dtype=float)
        ivc, dec, gac, vec = surface(Pc, spot, K, T, 'CE'); ivp, dep, gap, vep = surface(Pp, spot, K, T, 'PE')
        # ATM vol / straddle series
        atm_i = np.array([np.argmin(np.abs(K - s)) if np.isfinite(s) else 0 for s in spot]); jj = np.arange(375)
        atm_iv = np.nanmean(np.vstack([ivc[atm_i, jj], ivp[atm_i, jj]]), axis=0); strd = (Pc[atm_i, jj] + Pp[atm_i, jj]) / spot * 100
        lr = np.diff(np.log(spot), prepend=np.nan); runhi = np.maximum.accumulate(np.nan_to_num(spot, nan=0)); runlo = np.minimum.accumulate(np.where(np.isnan(spot), 1e12, spot))
        E = O[(O.und == u) & (O.expiry == e)].sort_values(['te', 'row']); ev_te = E.te.values; ev = list(zip(E.cp, E.strike.map(lambda k: si.get(int(k), -1)), E.sl, E.module, E.side, E.lots, E.px_avg)); ptr = 0
        nk = len(K); net = {'CE': np.zeros(nk), 'PE': np.zeros(nk)}; ent_v = {'CE': np.zeros(nk), 'PE': np.zeros(nk)}; ent_l = {'CE': np.zeros(nk), 'PE': np.zeros(nk)}
        sales = {cp: ALL[(ALL.und == u) & (ALL.expiry == e) & (ALL.cp == cp) & (ALL.dayno == d)].sort_values('tod') for cp in ('CE', 'PE')}
        starts = {}; smin = {}; blocked = {}
        for cp in ('CE', 'PE'):
            st = sales[cp][~sales[cp].paired].tod.values; s_ = []; last = -1e9
            for t in st:
                if t - last > 300: s_.append(t)
                last = t
            starts[cp] = set(int((t - ref.OPEN_SEC) // 60) for t in s_); smin[cp] = set(int((t - ref.OPEN_SEC) // 60) for t in st); b = set()
            for t in s_: j0 = int((t - ref.OPEN_SEC) // 60); b.update(range(j0 + 1, j0 + 6))
            blocked[cp] = b
        for j in range(61, 374):
            thr = d * 100000 + ref.OPEN_SEC + j * 60
            while ptr < len(ev_te) and ev_te[ptr] < thr:
                cp, k, sl, mod, side, lots, pxa = ev[ptr]; ptr += 1
                if k < 0: continue
                net[cp][k] += sl
                if mod == 'num' and side == 'Sell': ent_v[cp][k] += lots * pxa; ent_l[cp][k] += lots
            slotm = ((j - 1) % 15 == 0); s1 = spot[j - 1]
            if not np.isfinite(s1): continue
            nd_ce = np.nansum(net['CE'] * dec[:, j - 1]); nd_pe = np.nansum(net['PE'] * dep[:, j - 1]); nd = nd_ce + nd_pe; gam = np.nansum(net['CE'] * gac[:, j - 1]) + np.nansum(net['PE'] * gap[:, j - 1]); veg = np.nansum(net['CE'] * vec[:, j - 1]) + np.nansum(net['PE'] * vep[:, j - 1])
            Sh = {cp: np.where(net[cp] < 0, -net[cp], 0.0) for cp in ('CE', 'PE')}; Lg = {cp: np.where(net[cp] > 0, net[cp], 0.0) for cp in ('CE', 'PE')}
            nowp = {'CE': Pc[:, j - 1], 'PE': Pp[:, j - 1]}; ratio = {}; mtm = {}; wk = {}
            for cp in ('CE', 'PE'):
                avg = np.where(ent_l[cp] > 0, ent_v[cp] / np.maximum(ent_l[cp], 1e-9), np.nan); ok = (Sh[cp] > 0) & np.isfinite(avg) & np.isfinite(nowp[cp]) & (avg > 0)
                ratio[cp] = (Sh[cp][ok] * nowp[cp][ok]).sum() / (Sh[cp][ok] * avg[ok]).sum() if ok.any() else np.nan; mtm[cp] = (Sh[cp][ok] * (avg[ok] - nowp[cp][ok])).sum() * LOT[u]; wk[cp] = (K * Sh[cp]).sum() / Sh[cp].sum() if Sh[cp].sum() > 0 else np.nan
            rv30 = np.nanstd(lr[j - 30:j]) * np.sqrt(375 * 252) * 100; rvd = np.nanstd(lr[1:j]) * np.sqrt(375 * 252) * 100
            for cp in ('CE', 'PE'):
                oth = 'PE' if cp == 'CE' else 'CE'; sgn = 1 if cp == 'CE' else -1
                if j in blocked[cp] and j not in starts[cp]: continue
                if slotm and j not in smin[cp]: continue
                if Sh[cp].sum() <= 0: continue
                sd = sales[cp]; so = sales[oth]; T0 = ref.OPEN_SEC + j * 60; prev = sd[sd.tod < T0]; prevo = so[so.tod < T0]; w30 = T0 - 1800
                f = dict(day=['D-1', 'D0'][d], und=u, expiry=e, cp=cp, j=j, ep=int(j in starts[cp]), solo=int(j in smin[cp]),
                    own_ratio=ratio[cp], other_ratio=ratio[oth], S_own=Sh[cp].sum(), S_other=Sh[oth].sum(), L_own=Lg[cp].sum(), L_other=Lg[oth].sum(), n_strikes=int((Sh[cp] > 0).sum()),
                    imb=Sh[cp].sum() - Sh[oth].sum(), own_share=Sh[cp].sum() / max(Sh[cp].sum() + Sh[oth].sum(), 1), dev_book=sgn * (s1 - wk[cp]) / step if np.isfinite(wk[cp]) else np.nan,
                    mtm_own=mtm[cp] / CAP * 100, mtm_other=mtm[oth] / CAP * 100, mtm_tot=(mtm[cp] + mtm[oth]) / CAP * 100,
                    fav_open=-sgn * (s1 / spot[0] - 1) * 100, dd_ext=(runhi[j - 1] - s1) / runhi[j - 1] * 100 if cp == 'CE' else (s1 - runlo[j - 1]) / runlo[j - 1] * 100, abs15=abs(s1 / spot[j - 16] - 1) * 100, rv30=rv30, rv_rel=rv30 / rvd if rvd > 0 else np.nan,
                    nd=nd, delta_need=sgn * nd, delta_own=nd_ce if cp == 'CE' else nd_pe, delta_oth=nd_pe if cp == 'CE' else nd_ce, nd_per_short=sgn * nd / max(Sh['CE'].sum() + Sh['PE'].sum(), 1), delta_need_pct=sgn * nd * LOT[u] * s1 / CAP * 100, gamma=gam, vega=veg,
                    atm_iv=atm_iv[j - 1] * 100, d_iv15=(atm_iv[j - 1] - atm_iv[j - 16]) * 100, d_iv30=(atm_iv[j - 1] - atm_iv[j - 31]) * 100, iv_rel=atm_iv[j - 1] / atm_iv[1] if np.isfinite(atm_iv[1]) else np.nan,
                    straddle=strd[j - 1], d_str15=strd[j - 1] - strd[j - 16], d_str30=strd[j - 1] - strd[j - 31],
                    mins=j, tslot=(j - 1) % 15, tsl_own=(T0 - prev.tod.max()) / 60 if len(prev) else np.nan, tsl_other=(T0 - prevo.tod.max()) / 60 if len(prevo) else np.nan,
                    solo_own30=prev[(~prev.paired) & (prev.tod >= w30)].lots.sum(), solo_oth30=prevo[(~prevo.paired) & (prevo.tod >= w30)].lots.sum(), sched30=prev[prev.paired & (prev.tod >= w30)].lots.sum() + prevo[prevo.paired & (prevo.tod >= w30)].lots.sum())
                for k in (5, 15, 30, 60): f[f'fav{k}'] = -sgn * (s1 / spot[j - 1 - k] - 1) * 100
                f['asym'] = f['other_ratio'] - f['own_ratio']; rows.append(f)
F = pd.DataFrame(rows); F.to_csv(f'{OUT}/bl_feat_panel.csv', index=False); print(F.groupby('day').agg(rows=('ep', 'size'), episode_starts=('ep', 'sum')).to_string()); print(F[['atm_iv', 'nd', 'delta_need', 'nd_per_short', 'delta_need_pct', 'straddle']].describe().round(2).T.to_string())
