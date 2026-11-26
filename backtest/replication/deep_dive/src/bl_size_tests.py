"""Sizing study step 2 (plan tests 2-7). Uses outputs of bl_size_build.py. Cells = (block, in-block offset window) with >= 0.5 pairs per cycle in the version's modal timetable; per-cycle cell quantity = body open_short CE (PE) lots in the window (any strike).
Outputs bl_size_cells.csv, bl_size_cell_lots.csv, bl_size_scheduled_totals.csv, bl_size_buildup.csv, bl_size_solo_*.csv, bl_size_reactive.csv, bl_summary_size2.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy import stats
rng = np.random.default_rng(81); R = {}; O = load_orders(); CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); T = pd.read_csv(f'{OUT}/bl_size_timetable_raw.csv'); P = pd.read_csv(f'{OUT}/bl_size_pairs.csv'); So = pd.read_csv(f'{OUT}/bl_size_solo.csv')
nver = CY.groupby('version').size().to_dict(); S = O[(O.module == 'num') & (O.role == 'open_short') & (O.dayno == 0)].copy(); S['k'] = ((S.tod - 33360 + 30) // 900).astype(int); S['off'] = (S.tod - 33360 + 30) % 900 - 30; S = S.merge(CY[['und', 'expiry', 'version']], on=['und', 'expiry'], how='inner')
# ---- cells from the modal timetable (cluster offsets within a block, merge within 2 s)
cells = []
for v in ('V1', 'V2'):
    t = T[(T.version == v) & (T.k <= 22)].copy(); t['off'] = t.off.round(0).astype(int)
    for k, g in t.groupby('k'):
        g = g.sort_values('off'); cur = None
        for r in g.itertuples():
            if cur and r.off - cur['hi'] <= 2: cur['n'] += r.n; cur['hi'] = r.off
            else:
                if cur: cells.append(cur)
                cur = dict(version=v, k=int(k), lo=r.off, hi=r.off, n=r.n)
        if cur: cells.append(cur)
C = pd.DataFrame(cells); C['pairs_per_cycle'] = C.n / C.version.map(nver); C = C[C.pairs_per_cycle >= 0.5].reset_index(drop=True); C['cell'] = C.version + '|k' + C.k.astype(str) + '|' + C.lo.astype(str) + '..' + C.hi.astype(str)
# ---- per-cycle lots in each cell, CE and PE
rows = []
for c in C.itertuples():
    for (u, e), g in S[S.version == c.version].groupby(['und', 'expiry']):
        w = g[(g.k == c.k) & (g.off >= c.lo - 3) & (g.off <= c.hi + 3)]; rows.append((c.cell, c.version, c.k, c.lo, c.hi, u, e, int(w[w.cp == 'CE'].lots.sum()), int(w[w.cp == 'PE'].lots.sum())))
CL = pd.DataFrame(rows, columns=['cell', 'version', 'k', 'lo', 'hi', 'und', 'expiry', 'ce_lots', 'pe_lots']); CL.to_csv(f'{OUT}/bl_size_cell_lots.csv', index=False)
Q = CL.groupby(['cell', 'version', 'k', 'lo', 'hi']).agg(cycles=('ce_lots', 'size'), fire_ce=('ce_lots', lambda s: (s > 0).mean()), fire_pe=('pe_lots', lambda s: (s > 0).mean()), ce_mean=('ce_lots', 'mean'), pe_mean=('pe_lots', 'mean'), ce_mode=('ce_lots', lambda s: s.mode().iloc[0]), pe_mode=('pe_lots', lambda s: s.mode().iloc[0]), ce_eq_mode=('ce_lots', lambda s: (s == s.mode().iloc[0]).mean())).reset_index().sort_values(['version', 'k', 'lo']); Q.round(3).to_csv(f'{OUT}/bl_size_cells.csv', index=False)
print('cells (>=0.5 pairs/cycle):', len(Q), ' V1', int((Q.version == 'V1').sum()), ' V2', int((Q.version == 'V2').sum())); print('fire frequency of cells (CE & PE lots >0): V1 median', Q[Q.version == 'V1'].fire_ce.median(), ' share of cells with fire >= 0.95:', (Q[Q.version == 'V1'].fire_ce >= .95).mean().round(2), '| V2', Q[Q.version == 'V2'].fire_ce.median(), (Q[Q.version == 'V2'].fire_ce >= .95).mean().round(2)); R['cells'] = {v: int((Q.version == v).sum()) for v in ('V1', 'V2')}; R['fire_ge95'] = {v: float((Q[Q.version == v].fire_ce >= .95).mean()) for v in ('V1', 'V2')}; R['fire_median'] = {v: float(Q[Q.version == v].fire_ce.median()) for v in ('V1', 'V2')}
# ---- scheduled totals per cycle (sum over the version's cells) and in-cell quantity variance
TOT = CL.groupby(['version', 'und', 'expiry']).agg(ce=('ce_lots', 'sum'), pe=('pe_lots', 'sum')).reset_index().merge(CY[['und', 'expiry', 'd1', 'spot_d1_open', 'notional_per_lot']], on=['und', 'expiry']); TOT.to_csv(f'{OUT}/bl_size_scheduled_totals.csv', index=False)
print('\nscheduled lots per cycle (sum over modal cells), CE | PE:'); print(TOT.groupby('version')[['ce', 'pe']].agg(['count', 'mean', 'std', 'min', 'max']).round(2).to_string()); R['sched_total'] = {v: {c: [float(TOT[TOT.version == v][c].mean()), float(TOT[TOT.version == v][c].std())] for c in ('ce', 'pe')} for v in ('V1', 'V2')}; R['modal_cell_lots'] = {v: [int(Q[Q.version == v].ce_mode.sum()), int(Q[Q.version == v].pe_mode.sum())] for v in ('V1', 'V2')}
# ---- V1 -> V2 differences by (block, offset) in modal lots
A = Q[Q.version == 'V1'].set_index(['k', 'lo'])[['ce_mode']].rename(columns={'ce_mode': 'V1'}).join(Q[Q.version == 'V2'].set_index(['k', 'lo'])[['ce_mode']].rename(columns={'ce_mode': 'V2'}), how='outer').fillna(0).astype(int).reset_index(); A['diff'] = A.V2 - A.V1; print('\ncells whose modal CE lots differ V1 -> V2:'); print(A[A['diff'] != 0].to_string(index=False)); A.to_csv(f'{OUT}/bl_size_v1_v2_diff.csv', index=False); R['v_diff_cells'] = int((A['diff'] != 0).sum()); R['v_diff_net'] = int(A['diff'].sum())
# ---- misses: why do cells not fire?  (cycle stopped / missing logs)
stopt = O[(O.module == 's_') & (O.dayno == 0)].groupby(['und', 'expiry']).te.min(); CL['stop_before'] = [((u, e) in stopt.index) for u, e in zip(CL.und, CL.expiry)]; R['d1_cycles_with_s_order'] = int(CL.drop_duplicates(['und', 'expiry']).stop_before.sum())
miss = CL[(CL.ce_lots == 0) & (CL.pe_lots == 0)]; R['cell_misses'] = int(len(miss)); R['cell_obs'] = int(len(CL)); print(f'\ncell-cycle observations {len(CL)}; both legs empty in {len(miss)} ({len(miss) / len(CL):.3f}); share of misses in the first 6 blocks {float((miss.k <= 5).mean()):.2f}')
mc = miss.groupby('k').size(); print('misses by block:', mc.to_dict()); R['misses_by_block'] = {int(k): int(v) for k, v in mc.items()}
rec('size2', R)
