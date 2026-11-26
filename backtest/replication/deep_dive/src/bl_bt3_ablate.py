"""Ablations and placebos of the combined backtest (plan reports/ALPHA_SOURCE_PLAN.md, Methods 2 and 3): each variant removes or breaks ONE rule, everything else frozen.
All 275 cycles (IS, OOS, rule-fitted live window), B/V2 point line (observed versions in the live window). Output outputs/bt3_results/ablate_<name>_cycles.csv, ablate_summary.csv, ablate_diffs.csv"""
import sys, os, time, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
import bl_bt3_sim as S
from multiprocessing import Pool
RES = f'{S.OUT}/bt3_results'; P0 = S.P_FROZEN; W0 = P0['W']; Wsh = W0.copy(); Wsh['t'] = Wsh.t + 2220
VAR = {'full': ({}, {}), 'd1_no_timetable': ({'d1_no_sched': 1}, {}), 'd1_no_breakout': ({'d1_no_brk': 1}, {}), 'd1_no_ladder': ({'d1_no_lad': 1}, {}), 'd1_no_stops': ({'d1_no_stop': 1}, {}), 'd1_no_wings': ({'d1_no_wings': 1}, {}), 'd1_no_lump': ({'d1_no_lump': 1}, {}),
       'd0_no_new_sells': ({}, {'hold': True, 'ow': 0}), 'd0_no_waves': ({}, {'W': W0.iloc[0:0]}), 'd0_no_breakout': ({}, {'no_fires': True}), 'd0_no_ladder': ({}, {'m1': (1e6, P0['m1'][1], P0['m1'][2])}), 'd0_no_counter': ({}, {'r': 0.0}),
       'd0_no_stop_tp': ({}, {'k3': dict(theta=1e9, price='high', tp=None, tp_gate=0)}), 'd0_no_hedge': ({}, {'no_hedge': True}), 'no_cycle_stop': ({}, {'no_cycle_stop': True}),
       'd0_only (no D-1 selling)': ({'d1_no_sched': 1, 'd1_no_brk': 1, 'd1_no_lad': 1, 'd1_no_wings': 1}, {}), 'P1_flip_ladder_direction': ({'flip_ladder': 1}, {'flip_ladder': True}), 'P2_shift_waves_37min': ({'shift_waves': 1}, {'W': Wsh})}
SAVE = {'full', 'd1_no_ladder', 'd0_no_ladder', 'd0_no_waves', 'd1_no_timetable', 'P1_flip_ladder_direction', 'd0_no_new_sells', 'd1_no_wings', 'no_cycle_stop', 'd0_no_stop_tp', 'd1_no_stops', 'd0_no_counter', 'd0_no_hedge', 'd1_no_lump'}
def job(a):
    row, name = a; v, po = VAR[name]
    try:
        f, info = S.run_cycle(row, 'B/V2', dict(P0, **po), True, v); acc = S.account(f, row['und'], row['d1'], row['d0'], float(row['unit'])); info.update(acc); info['ok'] = True; return info, (f if name in SAVE else None)
    except Exception as e: return dict(und=row['und'], expiry=row['expiry'], ok=False, why=str(e)[:120]), None
if __name__ == '__main__':
    T = pd.read_csv(f'{S.OUT}/bl_bt3_cycles.csv'); T = T[T.split3.isin(['IS', 'OOS', 'LIVE_FITTED']) & T.ok]; rows = [r._asdict() for r in T.itertuples(index=False)]; t0 = time.time()
    with Pool(4) as p:
        for name in VAR:
            out = p.map(job, [(r, name) for r in rows], chunksize=4); res = [o for o, _ in out]; D = pd.DataFrame(res)
            if name in SAVE: pd.concat([f for _, f in out if f is not None], ignore_index=True).to_csv(f'{RES}/ablate_{name.split(" ")[0]}_fills.csv.gz', index=False)
            D.to_csv(f'{RES}/ablate_{name.split(" ")[0]}_cycles.csv', index=False); print(name, 'ok', int(D.ok.sum()), 'of', len(D), 'net mean', round(D[D.ok].net.mean()), 'gross mean', round(D[D.ok].gross.mean()), round(time.time() - t0), 's', flush=True)
