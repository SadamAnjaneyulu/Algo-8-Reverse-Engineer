"""Free-run (D-1 + D0) effect of the era clearance regime (364 before 3 Aug 2026, 359 after) on the complete real-log cycles. Output outputs/clr/clr_full.csv."""
import sys, os, json, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
import bl_bt3_sim as S, bl_pp_costs as PC
OUT = S.OUT
if __name__ == '__main__':
    T = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv'); T = T[T.ok]; C = pd.read_csv(f'{OUT}/clr/clr_cycles.csv'); keep = set(zip(C.und, C.expiry)); real = C.set_index(['und', 'expiry']); rows = []
    for r in T.itertuples():
        if (r.und, r.expiry) not in keep or r.d0 >= '2026-08-03': continue
        row = r._asdict(); out = dict(und=r.und, expiry=r.expiry, real=float(real.loc[(r.und, r.expiry), 'real']), real_stop=bool(real.loc[(r.und, r.expiry), 'real_stop']))
        for nm, P in (('base', S.P_FROZEN), ('era', dict(S.P_FROZEN, clear_era=True))):
            f, info = S.run_cycle(row, 'B/V2', P, True, None); a = PC.account(f[['day', 'j', 'cp', 'strike', 'side', 'lots', 'price', 'cls', 'n_orders']], r.und, r.d1, r.d0, float(r.unit)); out.update({f'{nm}_gross': a['gross'], f'{nm}_net': a['net'], f'{nm}_stop': info.get('stop_j') is not None})
        rows.append(out)
    R = pd.DataFrame(rows); R.to_csv(f'{OUT}/clr/clr_full.csv', index=False); d = R.era_gross - R.base_gross; fl = R.era_stop != R.base_stop
    print('n', len(R), 'base mean', R.base_gross.mean().round(0), 'era mean', R.era_gross.mean().round(0), 'real mean', R.real.mean().round(0)); print('MAE base', (R.base_gross - R.real).abs().mean().round(0), 'era', (R.era_gross - R.real).abs().mean().round(0))
    print('diff mean', d.mean().round(0), 'median', d.median().round(0), 'flips', int(fl.sum()), 'flip sum', d[fl].sum().round(0), 'non-flip mean', d[~fl].mean().round(0), '| net diff mean', (R.era_net - R.base_net).mean().round(0))
