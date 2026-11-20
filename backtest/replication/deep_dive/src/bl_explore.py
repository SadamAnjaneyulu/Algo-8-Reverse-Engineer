"""Exploratory checks that shaped the D-1/D0 analysis (all reproducible from outputs/bl_all_orders.pkl.gz):
 E1 parity-implied spot (K + C_ref - P_ref for CE+PE sold at the same strike within 2 s) vs minute spot closes
 E2 reference-lag scan: hit rate of 'sold strike == nearest strike to spot close of minute j-k' by day and class
 E3 seconds-from-slot-start table for D-1 sells (hit rate vs previous-close ATM)
 E4 candidate rules for non-scheduled sells (repeat previous strike, largest short, weighted mean, last cover, ATM)"""
import sys; sys.path.insert(0, '.')
from bl_common import *
O = load_orders(); ch = Chain(); S = O[(O.module == 'num') & (O.role == 'open_short')].copy(); S['hit_prev'] = S.strike == S.atm_prev
# ---- E1
pairs = []
for (u, e, d, k), g in S.groupby(['und', 'expiry', 'dayno', 'strike']):
    ce = g[g.cp == 'CE']; pe = g[g.cp == 'PE']
    if not len(ce) or not len(pe): continue
    for r in ce.itertuples():
        m = pe[(pe.tt_first - r.tt_first).abs() <= 2]
        if len(m): q = m.iloc[(m.tt_first - r.tt_first).abs().argmin()]; pairs.append((u, e, d, k, r.ref_px, q.ref_px, r.spot_prev, r.spot_cur, r.step))
P = pd.DataFrame(pairs, columns=['und', 'expiry', 'dayno', 'K', 'c_ref', 'p_ref', 'spot_prev', 'spot_cur', 'step']).dropna(); P['s_imp'] = P.K + P.c_ref - P.p_ref
r1 = []
for nm, col in (('parity-implied', P.s_imp), ('previous-minute close', P.spot_prev), ('current-minute close', P.spot_cur)):
    o = (P.K - col) / P.step; r1.append(dict(reference=nm, n=len(P), within_half_step=(o.abs() <= .5).mean(), within_1_step=(o.abs() <= 1).mean(), median_offset=o.median()))
E1 = pd.DataFrame(r1).round(3); E1.to_csv(f'{OUT}/bl_E1_parity_reference.csv', index=False); print(E1.to_string(index=False)); print('implied minus prev close (steps): median %.3f IQR %s ; median |.| %.3f' % (((P.s_imp - P.spot_prev) / P.step).median(), ((P.s_imp - P.spot_prev) / P.step).quantile([.25, .75]).round(2).tolist(), ((P.s_imp - P.spot_prev).abs() / P.step).median()))
# ---- E2
rows = []
for r in S.itertuples():
    st = ch.strikes(r.und, r.expiry); j = int(r.j)
    for k in range(0, 26):
        if j - k < 0: continue
        sp = ch.spot(r.und, r.expiry, r.dayno, j - k)
        if sp == sp: rows.append((r.dayno, r.cls, k, st[np.argmin(np.abs(st - sp))] == r.strike))
Z = pd.DataFrame(rows, columns=['day', 'cls', 'k', 'hit']); T = Z.groupby(['day', 'cls', 'k']).hit.mean().unstack('k').round(3); T.to_csv(f'{OUT}/bl_E2_reflag_scan.csv'); print('E2 best lag k per (day, class):', T.idxmax(axis=1).to_dict()); print(T.iloc[:, :4].to_string())
# ---- E3
d1 = S[(S.dayno == 0)].copy(); d1['slot_off'] = d1.tod - (9 * 3600 + 16 * 60); d1['slot'] = np.round(d1.slot_off / 900).astype(int); d1['rel'] = d1.slot_off - d1.slot * 900; d1 = d1[(d1.slot >= 0) & (d1.slot <= 16) & (d1.rel >= -30) & (d1.rel < 210)]
d1['rb'] = pd.cut(d1.rel, [-31, -1, 0, 1, 2, 3, 5, 10, 20, 30, 60, 90, 120, 150, 181, 211]); E3 = d1.groupby('rb').agg(n=('hit_prev', 'size'), exact_prev=('hit_prev', 'mean')).round(3); E3.to_csv(f'{OUT}/bl_E3_seconds_from_slot_start.csv'); print(E3.to_string())
# ---- E4
Bn = O[(O.module == 'num')]; bk = Book(order_table()); out = []
for d in (0, 1):
    Sd = S[S.dayno == d].sort_values(['und', 'expiry', 'cp', 'te', 'row']).copy(); Sd['h_last'] = Sd.groupby(['und', 'expiry', 'cp']).strike.shift(1); Cd = Bn[(Bn.role == 'cover_short') & (Bn.dayno == d)]
    mx = []; wa = []; cv = []
    for r in Sd.itertuples():
        _, _, net = bk.state(r.und, r.expiry, r.cp, r.tt_first, inclusive=False); sh = {k: -v for k, v in net.items() if v < 0}
        if sh: ks = np.array(list(sh)); w = np.array(list(sh.values())); mx.append(ks[np.argmax(w)]); m = (ks * w).sum() / w.sum(); wa.append(ks[np.argmin(np.abs(ks - m))])
        else: mx.append(np.nan); wa.append(np.nan)
        c = Cd[(Cd.und == r.und) & (Cd.expiry == r.expiry) & (Cd.cp == r.cp) & (Cd.tt_first < r.tt_first) & (Cd.tt_first >= r.tt_first - 300)]; cv.append(c.strike.iloc[-1] if len(c) else np.nan)
    Sd['h_max'] = mx; Sd['h_wavg'] = wa; Sd['h_cover'] = cv
    for cls, g in list(Sd.groupby('cls')) + [('ALL', Sd)]:
        row = dict(day=['D-1', 'D0'][d], cls=cls, n=len(g))
        for nm in ('h_last', 'h_max', 'h_wavg', 'h_cover', 'atm_prev'): v = g[nm]; row[nm] = (g.strike == v)[v.notna()].mean() if v.notna().any() else np.nan
        row['new_strike'] = ((g.net_after - g.sl) >= 0).mean(); out.append(row)
E4 = pd.DataFrame(out).round(3); E4.to_csv(f'{OUT}/bl_E4_sell_strike_candidates.csv', index=False); print(E4.to_string(index=False))
