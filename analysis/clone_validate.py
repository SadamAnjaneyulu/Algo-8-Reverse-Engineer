"""Validate the decoded-rule clone against Algo 8's actual cycle P&L (30 complete Jun-Oct 2026 cycles).  python3 analysis/clone_validate.py"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from engine import Cycle, Config, run, net
C = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_cache')
idx = pd.read_pickle(os.path.join(C, 'idx_candles.pkl')); opt = pd.read_pickle(os.path.join(C, 'opt_candles.pkl'))
A = pd.read_pickle(os.path.join(C, 'alpha_split.pkl'))
D1 = [('09:16', 3), ('09:31', 2), ('09:46', 3), ('10:01', 1), ('10:16', 3), ('10:31', 1), ('10:46', 2), ('11:01', 2), ('11:16', 1), ('11:31', 1), ('11:46', 3),
      ('12:01', 1), ('12:31', 2), ('13:16', 1), ('13:30', 1), ('13:45', 1), ('14:00', 1), ('14:15', 1), ('14:30', 1)]
D0 = [('09:16', 8), ('09:31', 4), ('09:46', 4), ('10:01', 1), ('10:16', 4), ('10:31', 3), ('10:46', 2), ('11:01', 3), ('11:16', 2), ('11:31', 2), ('11:46', 3),
      ('12:01', 1), ('12:31', 4), ('12:46', 2), ('13:01', 3), ('13:16', 1), ('13:31', 3), ('14:01', 2)]
CLONE = Config(name='clone', schedule=[(0, h, n) for h, n in D1] + [(1, h, n) for h, n in D0], wing_frac=0.012, leg_stop=1.55,
               stop_fill='level', cycle_stop=133000, exit_time='15:14')
def build_cycles():
    cy = []
    for r in A.itertuples():
        e = pd.Timestamp(r.expiry); days = sorted(d for d in idx[idx.und == r.und].ts.dt.normalize().unique() if d <= e)
        cy.append(Cycle(r.und, e, days[-2:], idx, opt))
    return cy
if __name__ == '__main__':
    t0 = time.time(); cycles = build_cycles(); print('cycles built', len(cycles), f'{time.time() - t0:.0f}s')
    t0 = time.time(); R = pd.DataFrame([run(c, CLONE) for c in cycles]); print(f'clone run {time.time() - t0:.1f}s')
    R['actual'] = A.total_actual.values
    pd.set_option('display.width', 200)
    print(R[['und', 'expiry', 'pnl', 'actual', 'cycle_stopped', 'n_lots', 'missing']].round(0).to_string(index=False))
    print(f"\nclone total {R.pnl.sum() / 1e5:.2f} L vs actual {R.actual.sum() / 1e5:.2f} L | corr per cycle {R.pnl.corr(R.actual):.2f} | Spearman {R.pnl.corr(R.actual, method='spearman'):.2f}")
    print('stop cycles agree (clone stopped vs actual stop cycle):', pd.crosstab(R.cycle_stopped, A.stop.values).to_dict())
    for s in ['zero', 'moderate', 'conservative', 'adverse']: print(s, 'clone net', round(sum(net(r, s) for r in R.to_dict('records')) / 1e5, 2), 'L')
    R.to_pickle(os.path.join(C, 'clone_validation.pkl'))
