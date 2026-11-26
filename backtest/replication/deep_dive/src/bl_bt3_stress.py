"""Stress tests on a split (plan reports/BACKTEST3Y_PLAN.md): slippage x3 / x6, costs x2, execution delay 1 and 3 minutes, fills at the real in-bar position. Re-priced from the saved fills; no re-simulation.
usage: python bl_bt3_stress.py <split> <run>   -> outputs/bt3_results/<split>_<run>_stress.csv"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
import bl_bt3_sim as S
from multiprocessing import Pool
RES = f'{S.OUT}/bt3_results'
def one(args):
    row, f = args; cyc = S.load(row['und'], row['expiry']); u = float(row['unit']); out = {}
    for nm, (sm, cm, mode, d) in {'base': (1, 1, None, 0), 'slippage x3': (3, 1, None, 0), 'slippage x6': (6, 1, None, 0), 'costs x2': (1, 2, None, 0), 'delay 1 min': (1, 1, 'delay', 1), 'delay 3 min': (1, 1, 'delay', 3), 'real in-bar position': (0, 1, 'barpos', 0)}.items():
        g = f if mode is None else S.reprice(f, cyc, mode, d); a = S.account(g, row['und'], row['d1'], row['d0'], u, sm, cm); out[nm] = a['net']
    out['gross'] = S.account(f, row['und'], row['d1'], row['d0'], u)['gross']; out.update(und=row['und'], expiry=row['expiry'], d0=row['d0']); return out
if __name__ == '__main__':
    split, run = sys.argv[1], sys.argv[2]; tag = f'{split}_{run.replace("/", "-")}'; T = pd.read_csv(f'{S.OUT}/bl_bt3_cycles.csv'); T = T[(T.split3 == split) & T.ok]; F = pd.read_csv(f'{RES}/{tag}_fills.csv.gz'); G = {k: v for k, v in F.groupby(['und', 'expiry'])}
    jobs = [(r._asdict(), G[(r.und, r.expiry)]) for r in T.itertuples(index=False) if (r.und, r.expiry) in G]
    with Pool(4) as p: res = p.map(one, jobs, chunksize=2)
    D = pd.DataFrame(res); D.to_csv(f'{RES}/{tag}_stress.csv', index=False); s = D.drop(columns=['und', 'expiry', 'd0']); print(tag); print(pd.DataFrame({'mean per cycle (Rs)': s.mean().round(0), 'total (Rs lakh)': (s.sum() / 1e5).round(1), 'win rate': (s > 0).mean().round(2)}).to_string())
