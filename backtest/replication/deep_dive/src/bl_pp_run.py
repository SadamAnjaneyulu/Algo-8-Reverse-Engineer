"""Pre-paper-trading battery (reports/PREPAPER_PLAN.md), B2 parameter sensitivity + B3c random-timetable null: full re-simulation of 275 cycles per variant, constant lot, verified costs.
Resumable: a variant whose csv exists is skipped. Output outputs/prepaper/var_<name>.csv. Run: OMP_NUM_THREADS=1 python bl_pp_run.py"""
import sys, os, time, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
import bl_bt3_sim as S, bl_pp_costs as PC
from multiprocessing import Pool
PP = f"{S.OUT}/{os.environ.get('PP_DIR', 'prepaper')}"; os.makedirs(PP, exist_ok=True); L0 = float(os.environ.get('PP_LSTOP', S.L_STOP)); P0 = dict(S.P_FROZEN, L_STOP=L0); W0 = P0['W']                # PP_DIR / PP_LSTOP: rebuilt base (POSTCAS_REBUILD_PLAN.md)
def shiftW(sec): W = W0.copy(); W['t'] = W.t + sec; return W
def randW(seed):
    W = W0.copy(); rg = np.random.default_rng(seed)
    for (u, v), g in W.groupby(['und', 'version']): W.loc[g.index, 't'] = np.sort(rg.uniform(g.t.min(), g.t.max(), len(g))).round()
    return W
VAR = {'full': ({}, {})}
for a in (-0.4, -0.2, 0.2, 0.4):
    tag = f'{int(100 * a):+d}%'
    VAR[f'd1_stop_ratio {tag}'] = ({'d1_set': {'stop_ratio': 1 + 0.6 * (1 + a)}}, {})
    VAR[f'd1_ladder_step {tag}'] = ({'d1_set': {'ladder_step': 0.2 * (1 + a)}}, {})
    VAR[f'd1_wing_budget {tag}'] = ({'d1_set': {'wing_premium_frac': 0.025 * (1 + a)}}, {})
    VAR[f'd1_lump_ratio {tag}'] = ({'d1_set': {'lump_ratio': 0.827 * (1 + a)}}, {})
    VAR[f'd0_stop_theta {tag}'] = ({}, {'k3': dict(P0['k3'], theta=1 + 0.4 * (1 + a))})
    VAR[f'd0_take_profit {tag}'] = ({}, {'k3': dict(P0['k3'], tp=P0['k3']['tp'] * (1 + a))})
    VAR[f'd0_ladder_step {tag}'] = ({}, {'m1': (P0['m1'][0] * (1 + a), P0['m1'][1], P0['m1'][2])})
    VAR[f'd0_counter_ratio {tag}'] = ({}, {'r': P0['r'] * (1 + a)})
    VAR[f'cycle_stop {tag}'] = ({}, {'L_STOP': L0 * (1 + a)})
for m in (-15, -5, 5, 15): VAR[f'timing {m:+d}min'] = ({'shift_s': 60 * m}, {'W': shiftW(60 * m)})
for sd in range(20): VAR[f'null_random_timetable_{sd:02d}'] = ({'random_tt': sd}, {'W': randW(1000 + sd)})
def job(a):
    row, name = a; v, po = VAR[name]
    try:
        f, info = S.run_cycle(row, 'B/V2', dict(P0, **po), True, v); old = S.account(f, row['und'], row['d1'], row['d0'], float(row['unit'])); acc = PC.account(f, row['und'], row['d1'], row['d0'], PC.REFU[row['und']])
        return dict(und=row['und'], expiry=row['expiry'], d0=row['d0'], split=row['split3'], gross_actual_old=old['gross'], gross=acc['gross'], net=acc['net'], costs=acc['costs'], slippage=acc['slippage'], orders=acc['orders'], stop_j=info.get('stop_j'), ok=True, _fills=(f.assign(und=row['und'], expiry=row['expiry']) if name == 'full' else None))
    except Exception as e: return dict(und=row['und'], expiry=row['expiry'], ok=False, why=str(e)[:120])
if __name__ == '__main__':
    T = pd.read_csv(f'{S.OUT}/bl_bt3_cycles.csv'); T = T[T.split3.isin(['IS', 'OOS', 'LIVE_FITTED']) & T.ok]; rows = [r._asdict() for r in T.itertuples(index=False)]; t0 = time.time()
    only = sys.argv[1:] or list(VAR)
    with Pool(4) as p:
        for name in only:
            fn = f"{PP}/var_{name.replace(' ', '_').replace('%', 'pct').replace('+', 'p').replace('-', 'm')}.csv"
            if os.path.exists(fn): continue
            res = p.map(job, [(r, name) for r in rows], chunksize=4); fl = [x.pop('_fills', None) for x in res]
            if name == 'full': pd.concat([x for x in fl if x is not None], ignore_index=True).to_csv(f'{PP}/full_fills.csv.gz', index=False)
            D = pd.DataFrame(res); D['variant'] = name; D.to_csv(fn, index=False)
            print(name, 'ok', int(D.ok.sum()), 'net mean', round(D[D.ok].net.mean()), round(time.time() - t0), 's', flush=True)
