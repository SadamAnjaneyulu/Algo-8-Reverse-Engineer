"""Clock-gate study: identify the block length L and the phase of the one-fire-per-block machine (range edge N-min AND first break in each clock block). In-sample F1 (+-1 min) over (L, phase, N); phase measured in minutes after the clock (hh:00). Outputs bl_clk_scan.csv, bl_summary_clk2.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
src = open('bl_clk_sim.py').read().split("CF = [")[0]; sys.argv = ['x']; exec(src)
ids = [d['cid'] for d in CYC]; rows = []
def f1_all(fn):
    tp = nf = na = 0
    for d in CYC: fi = fn(d); tp += match([f for f, _ in fi], d['A'], 1); nf += len(fi); na += len(d['A'])
    return 2 * tp / (nf + na), tp / nf, tp / na, nf
for N in (60, 70, 90):
    for L in (10, 15, 20, 25, 30, 40, 45, 60):
        for phi in sorted(set(range(0, L, 1 if L <= 30 else 3))):
            f, p, r, nf = f1_all(lambda d: runc(d, 'bar', N, L, L, 1, phi)); rows.append(dict(N=N, L=L, phase_min=phi, F1=f, precision=p, recall=r, fires=nf))
S = pd.DataFrame(rows); S.round(4).to_csv(f'{OUT}/bl_clk_scan.csv', index=False)
best = S.sort_values('F1', ascending=False).head(8); print(best.round(3).to_string(index=False))
b30 = S[(S.L == 30) & (S.N == 70)].sort_values('phase_min'); print('L=30 N=70 F1 by phase (min after hh:00):', dict(zip(b30.phase_min, b30.F1.round(3))))
bl = S.groupby('L').F1.max().round(3).to_dict(); print('best F1 by block length', bl); R['best_by_L'] = bl; R['best_rows'] = best.round(4).to_dict('records'); R['L30_N70_phase'] = {int(k): float(v) for k, v in zip(b30.phase_min, b30.F1)}
# null: shift each cycle's clock (random phase per cycle is not meaningful); instead compare phase 0 with the distribution of phases of L=30
f0 = float(b30[b30.phase_min == 0].F1.iloc[0]); oth = b30[b30.phase_min != 0].F1; R['phase0_F1'] = f0; R['other_phases_F1_mean'] = float(oth.mean()); R['other_phases_F1_max'] = float(oth.max()); print('phase 0 %.3f vs other phases mean %.3f max %.3f' % (f0, oth.mean(), oth.max())); rec('clk2', R)
