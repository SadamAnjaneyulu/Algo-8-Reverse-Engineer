"""Reactive-pair study, step 1 (plan BODY_REACTIVE_PAIR_PLAN.md): classify D-1 pairs as scheduled/reactive; build the D-1 cycle-minute panel (minutes 5..373 without a timetable wave) with causal features and targets R (reactive pair starts), S (solo sell), BB (body buy-back).
Outputs outputs/bl_react_pairs.csv, outputs/bl_react_panel.csv.gz"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
O = load_orders(); CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); Cc = pd.read_csv(f'{OUT}/bl_size_cells.csv'); Pr = pd.read_csv(f'{OUT}/bl_size_pairs.csv'); Pr = Pr[Pr.day == 'D-1'].merge(CY[['und', 'expiry', 'version']], on=['und', 'expiry']); So = pd.read_csv(f'{OUT}/bl_size_solo.csv'); So = So[So.day == 'D-1']
BB = pd.read_csv(f'{OUT}/bl_close_orders_clusters_D-1.csv')[['und', 'expiry', 'te', 'tod', 'r_low', 'lots']]; BK = pd.read_csv(f'{OUT}/bl_book_panel.csv.gz'); BK = BK[BK.day == 'D-1'].set_index(['und', 'expiry', 'j']); ch = Chain(); STEP = ref.STEP
def in_cell(v, k, off):
    c = Cc[(Cc.version == v) & (Cc.k == k)]; return bool(((off >= c.lo - 3) & (off <= c.hi + 3)).any())
Pr['sched'] = [in_cell(r.version, r.k, r.off) for r in Pr.itertuples()]; Pr['reactive'] = ~Pr.sched; Pr['j'] = ((Pr.tod - 33300) // 60).astype(int); Pr.to_csv(f'{OUT}/bl_react_pairs.csv', index=False)
print('D-1 pairs', len(Pr), 'scheduled', int(Pr.sched.sum()), 'reactive', int(Pr.reactive.sum()), f'({Pr.reactive.mean():.3f})')
rows = []
for r0 in CY.itertuples():
    u, e, v = r0.und, r0.expiry, r0.version; c = ch.cyc(u, e); K = np.array(c['strikes'], dtype=float); spot = pd.Series(np.array(c[(0, 'spot')], dtype=float)).ffill().bfill().values; step = STEP[u]
    px = {cp: pd.DataFrame(np.array(c[(0, cp, 'close')], dtype=float)).ffill(axis=1).values for cp in ('CE', 'PE')}
    p = Pr[(Pr.und == u) & (Pr.expiry == e)].sort_values('te'); s = So[(So.und == u) & (So.expiry == e)]; b = BB[(BB.und == u) & (BB.expiry == e)]; ss = O[(O.und == u) & (O.expiry == e) & (O.module == 'num') & (O.role == 'open_short') & (O.dayno == 0)]
    cells = Cc[Cc.version == v]
    sched_min = set()
    for cr in cells.itertuples():
        for t in range(int(cr.lo) - 3, int(cr.hi) + 4): sched_min.add(1 + int((900 * cr.k + t) // 60))
    te0 = 33360  # seconds of day at 09:16:00 -> tod
    Sinv = {}
    for cp in ('CE', 'PE'):
        z = O[(O.und == u) & (O.expiry == e) & (O.cp == cp) & (O.dayno == 0)].sort_values(['te', 'row']); Sinv[cp] = (z.te.values, z.S_after.values)
    day_hi = np.maximum.accumulate(spot); day_lo = np.minimum.accumulate(spot)
    for j in range(5, 374):
        if j in sched_min: continue
        thr = 33300 + j * 60; tt = lambda arr: arr[arr < thr]
        sell_t = tt(ss.tod.values); pair_t = tt(p.tod.values); react_t = tt(p[p.reactive].tod.values); sch_t = tt(p[p.sched].tod.values); bb_t = tt(b.tod.values); sl_t = tt(b[b.r_low >= 1.5].tod.values)
        age = lambda arr: (thr - arr.max()) / 60 if len(arr) else np.nan
        lb = lambda arr, w: float(b.lots.values[(b.tod.values < thr) & (b.tod.values >= thr - 60 * w)].sum())
        ls = lambda w: float(ss.lots.values[(ss.tod.values < thr) & (ss.tod.values >= thr - 60 * w)].sum())
        s1 = spot[j - 1]; ch_ = lambda w: (s1 / spot[max(j - 1 - w, 0)] - 1) * 100
        atm = K[np.argmin(np.abs(K - s1))]; lastp = p[p.tod < thr].strike.values; last_sell_strike = ss[ss.tod < thr].sort_values('tod').strike.values
        i = int(np.argmin(np.abs(K - s1))); strad = (px['CE'][i, j - 1] + px['PE'][i, j - 1]) / s1 * 100; i5 = int(np.argmin(np.abs(K - spot[max(j - 6, 0)]))); strad5 = (px['CE'][i5, max(j - 6, 0)] + px['PE'][i5, max(j - 6, 0)]) / spot[max(j - 6, 0)] * 100
        i15 = int(np.argmin(np.abs(K - spot[max(j - 16, 0)]))); strad15 = (px['CE'][i15, max(j - 16, 0)] + px['PE'][i15, max(j - 16, 0)]) / spot[max(j - 16, 0)] * 100
        k_ = (u, e, j); bk = BK.loc[k_] if k_ in BK.index else None
        sc = lambda cp: (lambda t, a: float(a[np.searchsorted(t, thr, side='left') - 1]) if np.searchsorted(t, thr, side='left') > 0 else 0.0)(*Sinv[cp])
        rows.append(dict(und=u, expiry=e, version=v, j=j, yR=int(((p.tod >= thr) & (p.tod < thr + 60) & p.reactive).any()), yS=int(((s.tod >= thr) & (s.tod < thr + 60)).any()), yBB=int(((b.tod >= thr) & (b.tod < thr + 60)).any()),
            nifty=int(u == 'NIFTY'), v2=int(v == 'V2'), age_sell=age(sell_t), age_pair=age(pair_t), age_react=age(react_t), age_sched=age(sch_t), age_bb=age(bb_t), age_stop=age(sl_t), lots_bb5=lb(None, 5) if False else lb(None, 5), lots_bb15=lb(None, 15), lots_sold5=ls(5), lots_sold15=ls(15), n_sched=len(sch_t), n_react=len(react_t),
            ch1=ch_(1), ch3=ch_(3), ch5=ch_(5), ch15=ch_(15), ch30=ch_(30), a1=abs(ch_(1)), a3=abs(ch_(3)), a5=abs(ch_(5)), a15=abs(ch_(15)), a30=abs(ch_(30)), dist_hi=(day_hi[j - 1] / s1 - 1) * 100, dist_lo=(s1 / day_lo[j - 1] - 1) * 100, new_hi=int(s1 >= day_hi[j - 1] - 1e-9), new_lo=int(s1 <= day_lo[j - 1] + 1e-9), range_pct=(day_hi[j - 1] / day_lo[j - 1] - 1) * 100,
            drift_pair=(atm - lastp[-1]) / step if len(lastp) else np.nan, drift_sell=(atm - last_sell_strike[-1]) / step if len(last_sell_strike) else np.nan, absdrift_pair=abs(atm - lastp[-1]) / step if len(lastp) else np.nan, strad=strad, d_strad5=strad - strad5, d_strad15=strad - strad15,
            B_total=bk.B_total if bk is not None else np.nan, B_day=bk.B_day if bk is not None else np.nan, DD=bk.DD if bk is not None else np.nan, S_CE=sc('CE'), S_PE=sc('PE')))
P = pd.DataFrame(rows); P['imb'] = P.S_CE - P.S_PE; P['S_tot'] = P.S_CE + P.S_PE; P['absimb'] = P.imb.abs(); P.to_csv(f'{OUT}/bl_react_panel.csv.gz', index=False)
print(P.shape, 'reactive-pair minutes', int(P.yR.sum()), 'solo minutes', int(P.yS.sum()), 'buy-back minutes', int(P.yBB.sum()), f'base rate R {P.yR.mean() * 1000:.1f} per 1000'); print(P.groupby('version').yR.agg(['size', 'sum']))
