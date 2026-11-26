"""Value of the real late D-1 sales, teacher-forced: the D0 simulator is started from the REAL carried book with the real D-1 short-side orders
(open_short and cover_short) after a cutoff removed (cutoffs 14:15, 15:00, 15:15). Longs (wings, lump, hedges) are kept. Difference vs the full real
book = what the late short-side behaviour is worth inside the simulator. Output outputs/late/late_value.csv."""
import sys, os, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from collections import defaultdict
import bl_bt3_sim as S, bl_d0x_diag as DG
OUT = S.OUT; LT = f'{OUT}/late'; CUTS = {'none': 10**9, '15:15': 54900, '15:00': 54000, '14:15': 51300}
def cycle_total(c, vd0, d1, unit):
    book = DG.real_book(d1, unit); S0 = float(c['spot0'].close.iloc[374])
    f, info = S.sim_d0(c, vd0, S.P_FROZEN, book, unit, True); endpos = defaultdict(int); cash = book['cash']
    for cp, k, e in book['lots']: endpos[(cp, int(k))] -= 1
    for (m, cp, k), n in book['longs'].items(): endpos[(cp, int(k))] += n
    for day, j, cp, k, sd, n, p, cls, no in f: cash += -sd * p * n * unit; endpos[(cp, int(k))] += sd * n
    tot = cash + sum(n * (max(S0 - k, 0) if cp == 'CE' else max(k - S0, 0)) * unit for (cp, k), n in endpos.items())
    return tot, len(book['lots']), info['stop_j'] is not None and info['stop_j'] >= 0
if __name__ == '__main__':
    O = DG.real_orders(); T = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv'); T = T[T.ok]; rows = []
    for r in T.itertuples():
        g = O[(O.und == r.und) & (O.expiry == r.expiry)]; d1 = g[g.dayno == 0]; d0 = g[g.dayno == 1]
        if not len(d1) or not len(d0): continue
        c = S.load(r.und, r.expiry); _, vd0 = S.versions_for(r.d1, r.d0, 'B/V2'); unit = float(r.unit)
        for nm, cut in CUTS.items():
            keep = d1[~((d1.t_last >= cut) & d1.role.isin(['open_short', 'cover_short']))]
            tot, ns, st = cycle_total(c, vd0, keep, unit)
            rows.append(dict(und=r.und, expiry=r.expiry, d1=r.d1, era='after' if r.d0 >= '2026-08-03' else 'before', cut=nm, total=tot, carried_short=ns, stop=st))
    V = pd.DataFrame(rows); V.to_csv(f'{LT}/late_value.csv', index=False)
    W = V.pivot_table(index=['und', 'expiry', 'd1', 'era'], columns='cut', values='total').reset_index()
    for k in ('15:15', '15:00', '14:15'): W[f'value_after_{k}'] = W['none'] - W[k]
    out = W[~((W.und == 'NIFTY') & (W.d1 == '2026-10-16'))]
    for era, g in out.groupby('era'):
        print(era, 'n', len(g), {c: (round(g[c].mean()), round(g[c].median())) for c in g.columns if c.startswith('value')})
    print('NIFTY 2026-10-16:', W[(W.und == 'NIFTY') & (W.d1 == '2026-10-16')].filter(like='value').round(0).to_dict('records'))
