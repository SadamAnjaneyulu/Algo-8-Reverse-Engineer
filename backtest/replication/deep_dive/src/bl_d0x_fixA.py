"""Fix A (structural, no fitted parameter): after the closing auction session (D-1 >= 3 Aug 2026) the D-1 breakout window runs to the end of the
data session (15:29) instead of stopping at 15:15, because options now trade until 15:40. Evaluated on the complete real cycles against the real log:
carried book, late D-1 short lots, cycle P&L error, stop agreement. Output outputs/d0x/fixA_eval.csv, fixA_cycles.csv."""
import sys, os, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
import bl_bt3_sim as S, bl_pp_costs as PC, bl_d0x_diag as DG
OUT = S.OUT; DX = f'{OUT}/d0x'; CAS = '2026-08-03'
T = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv'); T = T[T.ok]; B = pd.read_csv(f'{DX}/book_compare.csv'); keep = set(zip(B.und, B.expiry))
real = pd.read_csv(f'{OUT}/postcas/diag_cycles.csv'); real = real[real.src == 'real'].set_index(['und', 'expiry']).total
ctl = pd.read_csv('../../../../risk_rule_validation/results/cycle_stop_control.csv').set_index(['und', 'expiry']).stop
rows = []
for r in T.itertuples():
    if (r.und, r.expiry) not in keep: continue
    row = r._asdict(); out = dict(und=r.und, expiry=r.expiry, era='after' if r.d0 >= CAS else 'before', real=float(real.loc[(r.und, r.expiry)]), real_stop=bool(ctl.loc[(r.und, r.expiry)]))
    for name, v in (('base', {}), ('fixA', {'d1_set': {'breakout_end_min': 374}} if r.d1 >= CAS else {})):
        f, info = S.run_cycle(row, 'B/V2', S.P_FROZEN, True, v); F = pd.DataFrame(f, columns=['day', 'j', 'cp', 'strike', 'side', 'lots', 'price', 'cls', 'n_orders'])
        acc = PC.account(F, r.und, r.d1, r.d0, float(r.unit)); d1 = F[F.day == 0]; pos = d1.assign(q=d1.side * d1.lots).groupby(['cp', 'strike']).q.sum()
        out.update({f'{name}_gross': acc['gross'], f'{name}_stop': info.get('stop_j') is not None, f'{name}_carried_short': float(-pos[pos < 0].sum()), f'{name}_late_short': float(d1[(d1.side < 0) & (d1.j >= 345) & (d1.cls == 'body_sell')].lots.sum())})
    rows.append(out)
R = pd.DataFrame(rows).merge(B[['und', 'expiry', 'short_total_real']], on=['und', 'expiry']); R.to_csv(f'{DX}/fixA_cycles.csv', index=False)
real_late = DG.real_orders(); real_late = real_late[(real_late.dayno == 0) & (real_late.role == 'open_short') & ((real_late.t_last // 60 - 555) >= 345) & ((real_late.t_last // 60 - 555) <= 374)].groupby(['und', 'expiry']).lots.sum()
R['real_late_short'] = [float(real_late.get((u, e), 0)) for u, e in zip(R.und, R.expiry)]; ev = []
for era, g in R.groupby('era'):
    for n in ('base', 'fixA'):
        ev.append(dict(era=era, sim=n, cycles=len(g), real_mean=g.real.mean(), sim_mean=g[f'{n}_gross'].mean(), mae=float((g[f'{n}_gross'] - g.real).abs().mean()), spearman=float(g[[f'{n}_gross', 'real']].corr('spearman').iloc[0, 1]),
                       stops_agree=int((g[f'{n}_stop'] == g.real_stop).sum()), carried_short_sim=g[f'{n}_carried_short'].mean(), carried_short_real=g.short_total_real.mean(), late_short_sim=g[f'{n}_late_short'].mean(), late_short_real=g.real_late_short.mean()))
E = pd.DataFrame(ev); E.to_csv(f'{DX}/fixA_eval.csv', index=False); pd.set_option('display.width', 250); print(E.round(1).to_string())
