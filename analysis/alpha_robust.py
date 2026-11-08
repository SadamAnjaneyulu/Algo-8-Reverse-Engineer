"""Robustness of the top development region (BTST afternoon short straddle). DEV diagnostics only; frozen as a supplement before OOS.
Execution stress (stop fill level/high/next_open; entry fill open/prevclose), costs, per-index, concentration, leave-one-out.
python3 analysis/alpha_robust.py"""
import sys, os, itertools, json, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from engine import Cycle, Config, run, COSTS
import alpha_grid as G, alpha_eval as E
C = G.C
idx = pd.read_pickle(os.path.join(C, 'idx_candles.pkl')); opt = pd.read_pickle(os.path.join(C, 'opt_candles.pkl'))
A = pd.read_pickle(os.path.join(C, 'alpha_split.pkl'))
cycles = []
for r in A.itertuples():
    e = pd.Timestamp(r.expiry); days = sorted(d for d in idx[idx.und == r.und].ts.dt.normalize().unique() if d <= e)
    cycles.append(Cycle(r.und, e, days[-2:], idx, opt))
rows = []
for entry, ex, leg, wing, sf, fill in itertools.product(['single1116', 'single1316', 'single1501', 'uniform15', 'ladder'], ['D0 09:16', 'D0 10:01', 'expiry'],
                                                       [None, 1.3, 1.55, 2.0], [None, 0.006], ['level', 'high', 'next_open'], ['open', 'prevclose']):
    cfg = Config(schedule=[(0, h, n) for h, n in G.ENTRY[entry]], wing_frac=wing, leg_stop=leg, stop_fill=sf, fill=fill,
                 exit_time=None if ex == 'expiry' else ex.split()[1])
    for k, cy in enumerate(cycles):
        r = run(cy, cfg); n = max(r['n_lots'], 1)
        rows.append(dict(entry=entry, exit=ex, leg=leg, wing=wing, stop_fill=sf, fill=fill, cycle=k, und=cy.und, expiry=cy.expiry,
                         pnl_lot=r['pnl'] / n, turn_lot=r['turnover'] / n, orders_lot=r['orders'] / n, units_lot=r['units'] / n))
M = pd.DataFrame(rows)
M.to_pickle(os.path.join(C, 'robust_cycle_pnl.pkl'))
keys = ['entry', 'exit', 'leg', 'wing', 'stop_fill', 'fill']
out = []
for scen in ['conservative', 'adverse']:
    M['net'] = E.net_lot(M, scen)
    for k, g in M.groupby(keys, dropna=False):
        x = g.sort_values(['expiry', 'und']).net.values; m = E.metrics(x)
        srt = np.sort(x)[::-1]
        m.update(dict(zip(keys, k)), scenario=scen, top1_share=srt[0] / x.sum() if x.sum() > 0 else np.nan, total_ex_top2=srt[2:].sum(),
                 loo_min_total=min(x.sum() - v for v in x), nifty_total=g[g.und == 'NIFTY'].net.sum(), sensex_total=g[g.und == 'SENSEX'].net.sum())
        out.append(m)
R = pd.DataFrame(out)
R.to_csv(os.path.join(C, 'robust_metrics.csv'), index=False)
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30)
focus = R[(R.entry.isin(['single1316', 'single1501'])) & (R.leg == 1.55) & (R.wing.isna())]
print('=== execution stress, entry 13:16/15:01, leg 1.55x, no wings (P&L per straddle lot, Rs) ===')
print(focus[['scenario', 'entry', 'exit', 'stop_fill', 'fill', 'win_rate', 'profit_factor', 'sharpe_ann', 'total', 'total_ex_top2', 'loo_min_total', 'nifty_total', 'sensex_total', 'max_dd']]
      .sort_values(['scenario', 'entry', 'exit', 'stop_fill', 'fill']).round(2).to_string(index=False))
print('\n=== region medians (annualised Sharpe) by stop_fill x scenario ===')
print(R.groupby(['scenario', 'stop_fill']).sharpe_ann.median().round(2).unstack())
print('\n=== no leg stop vs leg stops (median Sharpe, adverse costs, level fill) ===')
print(R[(R.scenario == 'adverse') & (R.stop_fill == 'level')].groupby(R.leg.astype(str)).sharpe_ann.median().round(2).to_dict())
