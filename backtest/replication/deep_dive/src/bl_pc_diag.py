"""Post-auction rebuild, step 1 (diagnosis only, no rule changes): real vs simulator per cycle and day, by module and time of day, before / after the closing auction (3 Aug 2026).
Output outputs/postcas/diag_cycles.csv, diag_modules.csv, diag_time.csv."""
import sys, os, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
import bl_bt3_sim as S
OUT = S.OUT; PC = f'{OUT}/postcas'; os.makedirs(PC, exist_ok=True); CAS = '2026-08-03'
T = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv'); T = T[T.ok].set_index(['und', 'expiry'])
O = pd.read_pickle(f'{OUT}/bl_all_orders.pkl.gz'); O = O[O.status_last.isin(['Filled', 'PartiallyFilled'])]
R = pd.DataFrame(dict(und=O.und, expiry=O.expiry, day=O.dayno.astype(int), j=(O.t_last // 60 - 555).astype(int), t=O.t_last, cp=O.cp, strike=O.strike.astype(int), side=np.where(O.side == 'Buy', 1, -1), lots=O.lots.astype(float), price=O.px_avg, cls=O.cls.astype(str), module=O.module.astype(str)))
F = pd.read_csv(f'{OUT}/bt3_results/ablate_full_fills.csv.gz'); F['t'] = (F.j + 555) * 60 + 30; F['module'] = F.cls
def pnl_by_day(f, c, unit):
    """D-1: cash + carried book marked at the D-1 15:29 close; D0: cash + end book at the D0 last close minus the D-1 mark"""
    out = {}; pos = {}
    def mark(o, j, cp, k):
        i = int(np.searchsorted(o['K'], k)); v = o[(cp, 'close')][i, j] if i < len(o['K']) and o['K'][i] == k else np.nan; return float(v) if v == v else 0.0
    cash = {0: 0.0, 1: 0.0}
    for q in f.itertuples(): cash[q.day] += -q.side * q.price * q.lots * unit; pos[(q.cp, q.strike)] = pos.get((q.cp, q.strike), 0) + (q.side * q.lots if q.day == 0 else 0)
    m1 = sum(n * mark(c['opt1'], 374, cp, k) * unit for (cp, k), n in pos.items()); endpos = {}
    for q in f.itertuples(): endpos[(q.cp, q.strike)] = endpos.get((q.cp, q.strike), 0) + q.side * q.lots
    S0 = float(c['spot0'].close.iloc[374]); m0 = sum(n * (max(S0 - k, 0) if cp == 'CE' else max(k - S0, 0)) * unit for (cp, k), n in endpos.items())
    return dict(d1=cash[0] + m1, d0=cash[1] + m0 - m1, total=cash[0] + cash[1] + m0, carried_short=-sum(min(n, 0) for n in pos.values()), carried_long=sum(max(n, 0) for n in pos.values()),
                d1_sold=float(f[(f.day == 0) & (f.side < 0)].lots.sum()), d0_sold=float(f[(f.day == 1) & (f.side < 0)].lots.sum()), d0_bought=float(f[(f.day == 1) & (f.side > 0)].lots.sum()),
                last_d0_j=int(f[f.day == 1].j.max()) if (f.day == 1).any() else -1, d0_after_1514=float(f[(f.day == 1) & (f.j > 359)].lots.sum()))
rows = []; mods = []; tim = []
for (u, e), g in R.groupby(['und', 'expiry']):
    if (u, e) not in T.index: continue
    t = T.loc[(u, e)]; c = S.load(u, e); unit = float(t.unit); era = 'after' if t.d0 >= CAS else 'before'; fs = F[(F.und == u) & (F.expiry == e)]
    if not len(fs): continue
    for src, f in (('real', g), ('sim', fs)):
        rows.append(dict(und=u, expiry=e, era=era, src=src, **pnl_by_day(f, c, unit)))
        for (d, m), h in f.groupby(['day', 'module']): mods.append(dict(und=u, expiry=e, era=era, src=src, day=d, module=m, sold=float(h[h.side < 0].lots.sum()), bought=float(h[h.side > 0].lots.sum()), cash=float((-h.side * h.price * h.lots).sum() * unit)))
        for d in (0, 1):
            h = f[f.day == d]; hb = pd.cut(h.j, [-1, 59, 179, 299, 344, 359, 374, 1000], labels=['09:15-10:14', '10:15-12:14', '12:15-14:14', '14:15-14:59', '15:00-15:14', '15:15-15:29', 'after 15:29'])
            for b, hh in h.groupby(hb): tim.append(dict(und=u, expiry=e, era=era, src=src, day=d, bucket=str(b), lots=float(hh.lots.sum()), sold=float(hh[hh.side < 0].lots.sum())))
D = pd.DataFrame(rows); M = pd.DataFrame(mods); TI = pd.DataFrame(tim); D.to_csv(f'{PC}/diag_cycles.csv', index=False); M.to_csv(f'{PC}/diag_modules.csv', index=False); TI.to_csv(f'{PC}/diag_time.csv', index=False)
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30)
print(D.groupby(['era', 'src'])[['d1', 'd0', 'total', 'carried_short', 'carried_long', 'd1_sold', 'd0_sold', 'd0_bought', 'last_d0_j', 'd0_after_1514']].mean().round(0).to_string())
print(TI.groupby(['era', 'src', 'day', 'bucket']).lots.sum().unstack('bucket').round(0).to_string())
