"""Run the combined D-1 + D0 backtest on one split with one timetable run (plan reports/BACKTEST3Y_PLAN.md).
usage: OMP_NUM_THREADS=1 python bl_bt3_run.py <IS|OOS|LIVE_FITTED> <A/V1|B/V2>   (OOS is run ONCE, after the freeze; see the plan)
Outputs outputs/bt3_results/<split>_<run>_cycles.csv (cycle summary with gross and net accounting) and <split>_<run>_fills.csv.gz (git-ignored)."""
import sys, os, time, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
import bl_bt3_sim as S
from multiprocessing import Pool
RES = f'{S.OUT}/bt3_results'; os.makedirs(RES, exist_ok=True)
def job(args):
    row, run, hold = args
    try:
        f, info = S.run_cycle(row, run, dict(S.P_FROZEN, ow=0, hold=True) if hold else None); a = S.account(f, row['und'], row['d1'], row['d0'], float(row['unit'])); info.update(a)
        info['gross_check_diff'] = abs(a['gross'] - info['gross']); info['sessions'] = 2; info['ok'] = True; return f, info
    except Exception as e: return None, dict(und=row['und'], expiry=row['expiry'], run=run, ok=False, why=str(e)[:150])
if __name__ == '__main__':
    split, run = sys.argv[1], sys.argv[2]; hold = len(sys.argv) > 3 and sys.argv[3] == 'hold'; T = pd.read_csv(f'{S.OUT}/bl_bt3_cycles.csv'); T = T[(T.split3 == split) & T.ok].reset_index(drop=True); t0 = time.time(); rows = [r._asdict() for r in T.itertuples(index=False)]
    with Pool(4) as p: res = list(p.imap(job, [(r, run, hold) for r in rows], chunksize=2))
    C = pd.DataFrame([i for _, i in res]); F = pd.concat([f for f, _ in res if f is not None], ignore_index=True); tag = f'{split}_{run.replace("/", "-")}' + ('_HOLD' if hold else '')
    C.to_csv(f'{RES}/{tag}_cycles.csv', index=False); F.to_csv(f'{RES}/{tag}_fills.csv.gz', index=False)
    print(tag, 'cycles', len(C), 'ok', int(C.ok.sum()), 'in', round(time.time() - t0), 's'); print(C[~C.ok].head(5).to_string() if (~C.ok).any() else 'no failures'); print(C[C.ok][['gross', 'net', 'costs', 'slippage', 'orders']].describe().round(0).T[['mean', '50%', 'min', 'max']].to_string()); print('gross check max diff', C.gross_check_diff.max())
