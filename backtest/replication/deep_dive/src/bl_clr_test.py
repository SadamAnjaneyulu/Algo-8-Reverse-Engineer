"""D0 clearance-timing test (reports/D0_CLEAR_AND_LATE_TRIGGER.md, pre-registered in that file's plan section).
Teacher-forced: D0 simulated from the REAL carried book (as bl_d0x_diag). Variants: clear_j 359 (15:14, current) vs 364 (15:19). The only parameter is an era
constant; for pre-auction cycles it is re-estimated leave-one-cycle-out as the median of the other cycles' real 90%-clearance minute (real_clear_times.csv).
Decision metric: share of the real post-15:00 covers executed by the clearance minute. P&L metric last: teacher-forced total vs real total, stop flips separated.
Output outputs/clr/clr_cycles.csv, clr_summary.json."""
import sys, os, json, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from collections import defaultdict
import bl_bt3_sim as S, bl_d0x_diag as DG
OUT = S.OUT; CL = f'{OUT}/clr'; CAS = '2026-08-03'
def total(c, vd0, d1, unit, P):
    book = DG.real_book(d1, unit); S0 = float(c['spot0'].close.iloc[374]); f, info = S.sim_d0(c, vd0, P, book, unit, True); endpos = defaultdict(int); cash = book['cash']
    for cp, k, e in book['lots']: endpos[(cp, int(k))] -= 1
    for (m, cp, k), n in book['longs'].items(): endpos[(cp, int(k))] += n
    for day, j, cp, k, sd, n, p, cls, no in f: cash += -sd * p * n * unit; endpos[(cp, int(k))] += sd * n
    return cash + sum(n * (max(S0 - k, 0) if cp == 'CE' else max(k - S0, 0)) * unit for (cp, k), n in endpos.items()), info['stop_j'] is not None
if __name__ == '__main__':
    O = DG.real_orders(); T = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv'); T = T[T.ok]; RT = pd.read_csv(f'{CL}/real_clear_times.csv').set_index(['und', 'expiry'])
    real = pd.read_csv(f'{OUT}/postcas/diag_cycles.csv'); real = real[real.src == 'real'].set_index(['und', 'expiry']).total
    ctl = pd.read_csv('../../../../risk_rule_validation/results/cycle_stop_control.csv').set_index(['und', 'expiry']).stop; rows = []
    for r in T.itertuples():
        g = O[(O.und == r.und) & (O.expiry == r.expiry)]; d1 = g[g.dayno == 0]; d0 = g[g.dayno == 1]
        if not len(d1) or not len(d0): continue
        era = 'after' if r.d0 >= CAS else 'before'; c = S.load(r.und, r.expiry); _, vd0 = S.versions_for(r.d1, r.d0, 'B/V2'); unit = float(r.unit)
        cv = d0[(d0.role == 'cover_short') & (d0.t_last >= 15 * 3600)]; jj = (cv.t_last // 60 - 555).astype(int)
        out = dict(und=r.und, expiry=r.expiry, era=era, real=float(real.loc[(r.und, r.expiry)]), real_stop=bool(ctl.loc[(r.und, r.expiry)]), real_cover_lots=int(cv.lots.sum()))
        for cj in (359, 364): out[f'real_share_by_{cj}'] = float(cv.lots[jj <= cj].sum() / cv.lots.sum()) if cv.lots.sum() else np.nan
        loco = np.nan
        if era == 'before' and (r.und, r.expiry) in RT.index:
            oth = RT[(RT.era == 'before')].drop(index=(r.und, r.expiry), errors='ignore'); loco = int(oth.j90.median())
        out['clear_loco'] = loco
        variants = {'c359': 359, 'c364': 364}
        for nm, cj in variants.items():
            tot, st = total(c, vd0, d1, unit, dict(S.P_FROZEN, clear_j=cj)); out.update({f'{nm}_total': tot, f'{nm}_stop': st})
        if loco == loco:
            tot, st = total(c, vd0, d1, unit, dict(S.P_FROZEN, clear_j=int(loco))); out.update(loco_total=tot, loco_stop=st)
        rows.append(out)
    R = pd.DataFrame(rows); R.to_csv(f'{CL}/clr_cycles.csv', index=False); res = {}
    for era, g in R.groupby('era'):
        d = g.c364_total - g.c359_total; fl = g.c359_stop != g.c364_stop
        res[era] = dict(n=int(len(g)), real_share_by_359=float(g.real_share_by_359.mean()), real_share_by_364=float(g.real_share_by_364.mean()),
                        mae_359=float((g.c359_total - g.real).abs().mean()), mae_364=float((g.c364_total - g.real).abs().mean()), median_abs_359=float((g.c359_total - g.real).abs().median()), median_abs_364=float((g.c364_total - g.real).abs().median()),
                        bias_359=float((g.c359_total - g.real).mean()), bias_364=float((g.c364_total - g.real).mean()), pnl_mean_364_vs_359=float(d.mean()), pnl_median=float(d.median()), flips=int(fl.sum()), flip_sum=float(d[fl].sum()),
                        nonflip_mean=float(d[~fl].mean()), stops_agree_359=int((g.c359_stop == g.real_stop).sum()), stops_agree_364=int((g.c364_stop == g.real_stop).sum()),
                        loco_mae=float((g.loco_total - g.real).abs().mean()) if g.loco_total.notna().any() else None)
    json.dump(res, open(f'{CL}/clr_summary.json', 'w'), indent=1, default=float); print(json.dumps(res, indent=1, default=lambda z: round(float(z), 3)))
