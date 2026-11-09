"""Causal book state at the START of every minute m (lots entered in an earlier minute, marks = closes of m-1, indicators completed before m).
Two tables per cycle (cut at the cycle-stop minute):
  CM  contract-minute rows for every open SHORT contract  (features + actions taken on that contract in minute m)
  BM  book-minute rows                                    (portfolio features + actions in minute m)
Lot identity for age / carried features uses the 'cheap' closing convention (stated in common.py).
python3 analysis/exit_engine/bookstate.py -> _cache/exit_cm.pkl, _cache/exit_bm.pkl"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); AN = os.path.dirname(HERE); sys.path.insert(0, AN); sys.path.insert(0, HERE)
import numpy as np, pandas as pd
from common import orders, markets, replay_book, cycle_stop_minute, LOT, split_of, C, minute_index
from a7_lean import bs_vec, iv_vec
STEP = {'NIFTY': 50, 'SENSEX': 100}

def greeks(m):
    keys = m['keys']; grid = m['grid']; S = m['S']; e = m['expiry']
    K = np.array([k for _, k in keys], float); isc = np.array([c == 'CE' for c, _ in keys])
    T = ((e + pd.Timedelta('15:30:00') - grid).total_seconds().values / (365 * 86400)).clip(min=1 / 525600)
    Cf = m['Cf'].astype(float)
    intr = np.where(isc[:, None], np.maximum(S[None] - K[:, None], 0), np.maximum(K[:, None] - S[None], 0))
    Pc = np.maximum(np.nan_to_num(Cf, nan=0.05), intr + 0.05); shp = Pc.shape
    bS = np.broadcast_to(S[None], shp); bK = np.broadcast_to(K[:, None], shp); bT = np.broadcast_to(T[None], shp); bc = np.broadcast_to(isc[:, None], shp)
    IV = iv_vec(bc, bS, bK, bT, Pc); _, DEL = bs_vec(bc, bS, bK, bT, IV)
    sq = IV * np.sqrt(bT); d1 = (np.log(bS / bK) + 0.5 * IV * IV * bT) / sq; pdf = np.exp(-d1 * d1 / 2) / np.sqrt(2 * np.pi)
    GAM = pdf / (bS * sq); VEG = bS * pdf * np.sqrt(bT) / 100; THE = -(bS * pdf * IV / (2 * np.sqrt(bT))) / 365
    return IV, DEL, GAM, VEG, THE, T

def build(mk=None, save=True):
    """mk: optional market dict (e.g. damaged bars for stress tests); save=False keeps the caches untouched"""
    o = orders(); mk = mk if mk is not None else markets(); Lt = replay_book('cheap'); cs = cycle_stop_minute()
    CM, BM = [], []
    for (u, e), m in mk.items():
        grid = m['grid']; n = len(grid); cut = cs.get((u, e), n); lot = LOT[u]; S = m['S']; day = m['day']
        d0 = int(day.argmax()) if day.any() else None
        IV, DEL, GAM, VEG, THE, T = greeks(m)
        Lc = Lt[(Lt.und == u) & (Lt.expiry == e)]
        oc = o[(o.und == u) & (o.expiry == e)].copy(); oc['mi'] = [minute_index(grid, t) for t in oc.t_dec_lo]
        nk = len(m['keys'])
        # per-contract position arrays from lots (state at start of minute: entry_mi < m <= exit_mi)
        sc = np.zeros((nk, n)); ssum = np.zeros((nk, n)); scheap = np.full((nk, n), np.inf); scheap_mi = np.zeros((nk, n)); snew = np.full((nk, n), -1.0)
        sold = np.full((nk, n), 1e9); scar = np.zeros((nk, n)); sre = np.zeros((nk, n)); lc = np.zeros((nk, n))
        realised = np.zeros(n)
        for r in Lc.itertuples():
            kk = m['k2i'][(r.cp, r.strike)]; a = r.entry_mi + 1; b = min(r.exit_mi, n - 1) + 1
            if r.exit_oid is not None and b < n: realised[b:] += r.sgn * (r.exit_px - r.entry_px) * lot
            if b <= a: continue
            if r.sgn > 0: lc[kk, a:b] += 1; continue
            sc[kk, a:b] += 1; ssum[kk, a:b] += r.entry_px
            upd = r.entry_px < scheap[kk, a:b]; scheap[kk, a:b] = np.where(upd, r.entry_px, scheap[kk, a:b]); scheap_mi[kk, a:b] = np.where(upd, r.entry_mi, scheap_mi[kk, a:b])
            snew[kk, a:b] = np.maximum(snew[kk, a:b], r.entry_mi); sold[kk, a:b] = np.minimum(sold[kk, a:b], r.entry_mi)
            if r.carried and d0 is not None: scar[kk, max(a, d0):b] += 1
            sre[kk, a:b] += r.reentry
        ent_long = {}
        for r in Lc[Lc.sgn > 0].itertuples(): ent_long.setdefault(m['k2i'][(r.cp, r.strike)], []).append((r.entry_mi, min(r.exit_mi, n - 1), r.entry_px))
        mark = np.vstack([np.concatenate([[np.nan], m['Cf'][i, :-1].astype(float)]) for i in range(nk)])     # close of m-1
        Hp = np.vstack([np.concatenate([[np.nan], m['H'][i, :-1].astype(float)]) for i in range(nk)])
        # unrealised: shorts (sum entry - cnt*mark)*lot ; longs from per-lot list
        fin = np.isfinite(mark); mk_ = np.nan_to_num(mark, nan=0.0)
        up_s = np.where(fin, (ssum - sc * mk_) * lot, 0.0); up_s[sc == 0] = 0          # no print yet -> marked at entry (zero unrealised)
        up_l = np.zeros((nk, n))
        for kk, lst in ent_long.items():
            for a0, b0, p in lst:
                a, b = a0 + 1, b0 + 1
                if b > a: up_l[kk, a:b] += np.where(fin[kk, a:b], mk_[kk, a:b] - p, 0.0) * lot
        mtm = realised + up_s.sum(0) + up_l.sum(0)
        # book Greeks (position-weighted, per index point, Rs)
        pos = (lc - sc) * lot
        gD = np.nan_to_num(np.vstack([np.concatenate([[np.nan], DEL[i, :-1]]) for i in range(nk)])); gG = np.nan_to_num(np.vstack([np.concatenate([[np.nan], GAM[i, :-1]]) for i in range(nk)]))
        gV = np.nan_to_num(np.vstack([np.concatenate([[np.nan], VEG[i, :-1]]) for i in range(nk)])); gT = np.nan_to_num(np.vstack([np.concatenate([[np.nan], THE[i, :-1]]) for i in range(nk)]))
        ivp = np.vstack([np.concatenate([[np.nan], IV[i, :-1]]) for i in range(nk)])
        isce = np.array([c == 'CE' for c, _ in m['keys']]); Kk = np.array([k for _, k in m['keys']], float)
        Sp = np.concatenate([[S[0]], S[:-1]]); atr = m['atr1']
        def mv(h): return (Sp - np.concatenate([np.full(h, Sp[0]), Sp[:-h]])) / atr
        mv1, mv5, mv15, mv30 = mv(1), mv(5), mv(15), mv(30)
        sd0 = (Sp - (S[d0] if d0 is not None else np.nan)) / atr if d0 is not None else np.full(n, np.nan)
        spc = (Sp - S[d0 - 1]) / atr if (d0 is not None and d0 > 0) else np.full(n, np.nan)
        sale_mi = {}; bb_mi = {}
        for r in oc.itertuples():
            if r.side == 'Sell' and r.label == 'open': sale_mi.setdefault((r.cp, r.strike), []).append(r.mi)
            if r.closing_short == True: bb_mi.setdefault((r.cp, r.strike), []).append(r.mi)
        def last_before(lst, i):
            if not lst: return np.nan
            a = np.asarray(lst); a = a[a < i]; return float(i - a.max()) if len(a) else np.nan
        hh = grid.hour * 60 + grid.minute
        ph = ((grid - grid.normalize() - pd.Timedelta('09:15:00')).total_seconds().values // 60) % 15        # minute-in-quarter (0 = :15/:30/:45/:00)
        clockB = (day == 1) & (ph == 14) & (hh >= 9 * 60 + 29); gridA = (ph == 1); grid00 = (grid.minute == 0) & (hh >= 13 * 60 + 30)
        # actions in minute m
        act = oc.groupby('mi')
        for i in range(1, min(cut, n)):
            opn = np.where(sc[:, i] > 0)[0]
            ce_l = sc[isce, i].sum(); pe_l = sc[~isce, i].sum(); tot = ce_l + pe_l
            side_up = {'CE': up_s[isce, i].sum(), 'PE': up_s[~isce, i].sum()}
            g_i = act.get_group(i) if i in act.groups else None
            bb_i = g_i[g_i.closing_short == True] if g_i is not None else None
            sl_i = g_i[(g_i.side == 'Sell') & (g_i.label == 'open')] if g_i is not None else None
            allS = [x for v in sale_mi.values() for x in v]; allB = [x for v in bb_mi.values() for x in v]
            BM.append(dict(und=u, expiry=e, mi=i, m=grid[i], day=day[i], tte_min=T[i] * 525600, hhmm=hh[i], clockB=bool(clockB[i]), gridA=bool(gridA[i]), grid00=bool(grid00[i]),
                           n_contracts=len(opn), lots_ce=ce_l, lots_pe=pe_l, lots_tot=tot, imbalance=(ce_l - pe_l) / tot if tot else np.nan,
                           max_share=(sc[opn, i].max() / tot) if tot else np.nan, up_ce=side_up['CE'], up_pe=side_up['PE'], up_basket=side_up['CE'] + side_up['PE'],
                           mtm=mtm[i - 1], mtm_peak=np.max(mtm[:i]), mtm_dd=mtm[i - 1] - np.max(mtm[:i]),
                           net_delta=(pos[:, i] * gD[:, i]).sum(), net_gamma=(pos[:, i] * gG[:, i]).sum(), net_vega=(pos[:, i] * gV[:, i]).sum(), net_theta=(pos[:, i] * gT[:, i]).sum(),
                           atr=atr[i], mv1=mv1[i], mv5=mv5[i], mv15=mv15[i], mv30=mv30[i], mv_d0open=sd0[i], mv_prevclose=spc[i], rv1=m['rv1'][i],
                           since_sale=last_before(allS, i), since_bb=last_before(allB, i),
                           n_bb_contracts=bb_i.groupby(['cp', 'strike']).ngroups if bb_i is not None and len(bb_i) else 0,
                           bb_sides=''.join(sorted(set(bb_i.cp))) if bb_i is not None and len(bb_i) else '',
                           bb_lots=int(bb_i.lots.sum()) if bb_i is not None and len(bb_i) else 0,
                           bb_labels='|'.join(sorted(set(bb_i.label))) if bb_i is not None and len(bb_i) else '',
                           sale_lots=int(sl_i.lots.sum()) if sl_i is not None and len(sl_i) else 0,
                           sale_sides=''.join(sorted(set(sl_i.cp))) if sl_i is not None and len(sl_i) else ''))
            for kk in opn:
                k = m['keys'][kk]; px = mark[kk, i]
                if not np.isfinite(px): continue
                cnt = sc[kk, i]; avg = ssum[kk, i] / cnt; ch = scheap[kk, i]
                bbk = bb_i[(bb_i.cp == k[0]) & (bb_i.strike == k[1])] if bb_i is not None and len(bb_i) else None
                slk = sl_i[(sl_i.cp == k[0]) & (sl_i.strike == k[1])] if sl_i is not None and len(sl_i) else None
                sgn = 1 if k[0] == 'CE' else -1
                CM.append(dict(und=u, expiry=e, mi=i, m=grid[i], cp=k[0], strike=k[1], day=day[i], n_lots=cnt, n_carried=scar[kk, i], n_reentry=sre[kk, i],
                               e_cheap=ch, e_avg=avg, px=px, quote=np.nan, r_cheap=px / ch, r_avg=px / avg, rh_prev=Hp[kk, i] / ch if np.isfinite(Hp[kk, i]) else np.nan,
                               r_prevclose=(px / m['Cf'][kk, d0 - 1]) if (d0 is not None and d0 > 0 and i >= d0 and np.isfinite(m['Cf'][kk, d0 - 1]) and m['Cf'][kk, d0 - 1] > 0) else np.nan,
                               age_cheap=i - scheap_mi[kk, i], age_oldest=i - sold[kk, i], age_newest=i - snew[kk, i],
                               upnl=up_s[kk, i], upnl_side=side_up[k[0]], share_side=cnt / (ce_l if k[0] == 'CE' else pe_l),
                               delta=gD[kk, i], gamma=gG[kk, i], vega=gV[kk, i], theta=gT[kk, i], iv=ivp[kk, i],
                               dexp=abs(gD[kk, i]) * cnt * lot, gexp=gG[kk, i] * cnt * lot, vexp=gV[kk, i] * cnt * lot,
                               otm_atr=sgn * (Kk[kk] - Sp[i]) / atr[i] if atr[i] > 0 else np.nan, otm_pts=sgn * (Kk[kk] - Sp[i]),
                               adv_mv5=sgn * mv5[i], adv_mv15=sgn * mv15[i], adv_mv30=sgn * mv30[i], adv_d0open=sgn * sd0[i], adv_prevclose=sgn * spc[i],
                               since_sale_k=last_before(sale_mi.get(k, []), i), since_bb_k=last_before(bb_mi.get(k, []), i),
                               tte_min=T[i] * 525600, clockB=bool(clockB[i]), gridA=bool(gridA[i]), grid00=bool(grid00[i]), hhmm=hh[i],
                               closed=int(bbk.lots.sum()) if bbk is not None and len(bbk) else 0, close_label=bbk.label.iloc[0] if bbk is not None and len(bbk) else 'none',
                               close_L=bbk.L.iloc[0] if bbk is not None and len(bbk) else np.nan, sold=int(slk.lots.sum()) if slk is not None and len(slk) else 0))
    CMd = pd.DataFrame(CM); BMd = pd.DataFrame(BM)
    for D in (CMd, BMd): D['split'] = D.expiry.map(split_of)
    if save: CMd.to_pickle(os.path.join(C, 'exit_cm.pkl')); BMd.to_pickle(os.path.join(C, 'exit_bm.pkl'))
    return CMd, BMd

def load():
    p1, p2 = os.path.join(C, 'exit_cm.pkl'), os.path.join(C, 'exit_bm.pkl')
    if not (os.path.exists(p1) and os.path.exists(p2)): return build()
    return pd.read_pickle(p1), pd.read_pickle(p2)

if __name__ == '__main__':
    CMd, BMd = build()
    print('contract-minutes', CMd.shape, '| book-minutes', BMd.shape)
    print(CMd.close_label.value_counts().to_string())
