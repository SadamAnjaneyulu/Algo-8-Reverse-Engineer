"""Audit of the late D-1 / overnight-book gap (reports/LATE_D1_RULE.md). Reads saved outputs only, plus the real order log and the engine signals:
(1) sensitivity of the real-vs-sim book comparison to NIFTY D-1 2026-10-16 (a 240-lot deep-OTM call ratio, not seen in any other cycle);
(2) share of the overnight-book P&L gap and of the Fix A change that comes from cycle-stop flips; (3) value of real late sales (bl_late_value.py)
split by stop flips; (4) attribution of real late short lots to timetable / breakout / ladder / unexplained (+-1 minute).
Output outputs/late/audit.json, late_attribution.csv."""
import sys, json, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
import bl_bt3_sim as S, bl_d0x_diag as DG, algo8_d1 as A
OUT = S.OUT; LT = f'{OUT}/late'; DX = f'{OUT}/d0x'; OUTLIER = ('NIFTY', '2026-10-16')
def split_flips(diff, flip):
    return dict(n=int(len(diff)), mean=float(diff.mean()), median=float(diff.median()), flips=int(flip.sum()), flip_sum=float(diff[flip].sum()),
                share_from_flips=float(diff[flip].sum() / diff.sum()) if diff.sum() else np.nan, nonflip_mean=float(diff[~flip].mean()), nonflip_median=float(diff[~flip].median()))
if __name__ == '__main__':
    T = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv'); key = T[['und', 'expiry', 'd1']]; res = {}
    B = pd.read_csv(f'{DX}/book_compare.csv').merge(key, on=['und', 'expiry']); G = pd.read_csv(f'{DX}/gap_decomposition.csv')
    M = B.merge(G, on=['und', 'expiry', 'era']); a = M[M.era == 'after'].copy(); out = (a.und == OUTLIER[0]) & (a.d1 == OUTLIER[1])
    a['dshort'] = a.short_total_real - a.short_total_sim; a['doff'] = a.short_offset_mean_real - a.short_offset_mean_sim
    res['book'] = {nm: dict(n=int(len(x)), dshort_mean=float(x.dshort.mean()), dshort_median=float(x.dshort.median()), doffset_mean=float(x.doff.mean()), gap_d1_book_mean=float(x.gap_d1_book.mean()),
                            gap_d1_book_median=float(x.gap_d1_book.median()), real_total_mean=float(x.real_total.mean())) for nm, x in (('all', a), ('ex_outlier', a[~out]))}
    x = a[~out]; res['gap_d1_book_flips'] = split_flips(x.gap_d1_book, x.freerun_stop != x.hybrid_stop)
    F = pd.read_csv(f'{DX}/fixA_cycles.csv'); f = F[F.era == 'after']; res['fixA_flips'] = split_flips(f.fixA_gross - f.base_gross, f.base_stop != f.fixA_stop)
    V = pd.read_csv(f'{LT}/late_value.csv'); W = V.pivot_table(index=['und', 'd1', 'era'], columns='cut', values=['total', 'stop']).reset_index(); W.columns = ['_'.join(c).strip('_') for c in W.columns]
    for era in ('after', 'before'):
        w = W[(W.era == era) & ~((W.und == OUTLIER[0]) & (W.d1 == OUTLIER[1]))]
        res[f'late_value_{era}'] = {k: split_flips(w.total_none - w[f'total_{k}'], w.stop_none != w[f'stop_{k}']) for k in ('15:15', '15:00', '14:15')}
    O = DG.real_orders(); T = T[T.ok]; rows = []
    for r in T.itertuples():
        g = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 0) & (O.role == 'open_short')]
        if not len(g) or (r.und, r.d1) == OUTLIER: continue
        c = S.load(r.und, r.expiry); s = c['spot1']; h, l, cl = (s[k].values.astype(float) for k in ('high', 'low', 'close')); vd1, _ = S.versions_for(r.d1, r.d0, 'B/V2'); cfg = S.d1_config(r.und, r.d1, vd1)
        tt = {A.minute_of(x) for x in cfg.timetable}; bo = {j for j, sd, dp in A.breakout_fires(h, l, cfg)}
        ev = {'CE': sorted(tt | bo), 'PE': sorted(tt | bo)}; lp = {(j, cp) for j, cps in A.ladder_fires(cl, h, l, ev, cfg).items() for cp in cps}
        for q in g.itertuples():
            j = int(q.t_last // 60 - 555)
            if j < 300: continue
            near = lambda Z: any((j + d) in Z for d in (-1, 0, 1))
            src = 'timetable' if near(tt) else 'breakout' if near(bo) else 'ladder' if any((j + d, q.cp) in lp for d in (-1, 0, 1)) else ('15:30-15:40 (no data)' if j > 374 else 'unexplained')
            rows.append(dict(und=r.und, d1=r.d1, era='after' if r.d0 >= '2026-08-03' else 'before', source=src, lots=int(q.lots),
                             bucket='14:15-14:59' if j < 345 else '15:00-15:14' if j < 360 else '15:15-15:29' if j < 375 else '15:30-15:40'))
    R = pd.DataFrame(rows); R.to_csv(f'{LT}/late_attribution.csv', index=False)
    P = R.pivot_table(index=['era', 'bucket'], columns='source', values='lots', aggfunc='sum', fill_value=0)
    ncyc = R.groupby('era').apply(lambda g: g.groupby(['und', 'd1']).ngroups).to_dict(); res['attribution_cycles'] = ncyc; res['attribution'] = {f'{e}|{b}': v for (e, b), v in P.to_dict('index').items()}
    json.dump(res, open(f'{LT}/audit.json', 'w'), indent=1, default=float)
    print(json.dumps({k: v for k, v in res.items() if k != 'attribution'}, indent=1, default=lambda z: round(float(z), 1))); print(P.to_string())
