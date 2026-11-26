"""D0 buy-back reasons, follow-up (plan reports/D0_BB_TYPES_PLAN.md Q3/Q4 + addendum): (1) block-minute association excluding clearance and the stop window, by type; (2) ratio concentration near 1.0 for roll-out / burst / other;
(3) adverse spot move at the buy-back minute (CE short: spot up, PE short: spot down; 5 and 15 minutes, in strike steps) vs random minutes in the same cycle and hour (50 draws per lot); (4) hour profile of 'other'.
Outputs bl_d0y_other.csv, bl_summary_d0y2.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); X = pd.read_pickle(f'{OUT}/bl_d0y_lots.pkl.gz'); SP = pd.read_pickle(f'{OUT}/bl_d0_spot.pkl.gz'); rng = np.random.default_rng(41); R = {}
core = X[~X.type.str.startswith(('1', '2'))].copy(); core['blk'] = ((core.tod - 33300) // 60) % 15
R['q3_core_lots'] = int(len(core)); R['q3_core_block_minute14'] = float((core.blk == 14).mean()); R['q3_core_block_minute0'] = float((core.blk == 0).mean()); R['q3_core_uniform'] = 1 / 15
R['q3_block14_by_type'] = {t: float((g.blk == 14).mean()) for t, g in core.groupby('type')}; R['q3_block0_by_type'] = {t: float((g.blk == 0).mean()) for t, g in core.groupby('type')}
# ratio near 1.0
t678 = core[core.type.isin(['6 roll-out', '7 burst member', '8 other'])]; r = t678.ratio
R['near1'] = dict(lots=int(len(t678)), in_0p95_1p05=float(((r >= .95) & (r <= 1.05)).mean()), in_0p85_0p95=float(((r >= .85) & (r < .95)).mean()), in_1p05_1p15=float(((r > 1.05) & (r <= 1.15)).mean()), in_1p0_1p4=float(((r >= 1.0) & (r < 1.4)).mean()), in_1p2_1p4=float(((r >= 1.2) & (r < 1.4)).mean()))
# adverse spot move
def adv(i, j, cp, n):
    r_ = CY.iloc[i]; c = SP[(r_.und, r_.expiry)].close.values; st = ref.STEP[r_.und]; jj = min(max(j, n), 374)
    mv = (c[jj - 1] - c[max(jj - 1 - n, 0)]) / st; return mv if cp == 'CE' else -mv
rows = []
for nm, g in [('3 stop-loss', core[core.type == '3 stop-loss']), ('4 take-profit', core[core.type == '4 take-profit']), ('5 partner', core[core.type == '5 partner']), ('6 roll-out', core[core.type == '6 roll-out']), ('7 burst member', core[core.type == '7 burst member']), ('8 other', core[core.type == '8 other'])]:
    for n in (5, 15):
        real = np.array([adv(i, j, cp, n) for i, j, cp in zip(g.cid, g.j, g.cp)]); nl = []
        for i, j, cp in zip(g.cid, g.j, g.cp):
            lo = max((j // 60) * 60, 20); hi = min(lo + 60, 360); nl.append(np.mean([adv(i, int(x), cp, n) for x in rng.integers(lo, max(hi, lo + 1), 20)]))
        nl = np.array(nl); rows.append(dict(type=nm, window_min=n, lots=len(g), adverse_move_steps_mean=float(real.mean()), null_mean=float(nl.mean()), share_adverse=float((real > 0).mean()), null_share_adverse=float((nl > 0).mean()), difference=float(real.mean() - nl.mean())))
A = pd.DataFrame(rows); A.to_csv(f'{OUT}/bl_d0y_other.csv', index=False); print(A.round(3).to_string(index=False))
o = core[core.type == '8 other']; R['other_hours'] = {int(k): int(v) for k, v in (o.tod // 3600).astype(int).value_counts().sort_index().items()}; R['other_entry_mix'] = o.typ.value_counts().to_dict(); R['other_cycles_top'] = {int(k): int(v) for k, v in o.cid.value_counts().head(6).items()}
R['adverse'] = A.round(4).to_dict('records'); rec('d0y2', R); print({k: v for k, v in R.items() if k != 'adverse'})
