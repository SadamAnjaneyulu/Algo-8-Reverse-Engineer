"""Historical backtest of Algo 8 decision engine v1 on the 3-year NIFTY/SENSEX data: IN-SAMPLE = D0 <= 2025-11-17 (about 2 years), OUT-OF-SAMPLE = D0 >= 2025-11-18 (about 1 year), the same boundary as the earlier backtest.
IMPORTANT CAVEAT (stated in the report): the decision parameters were extracted from the 35 live cycles (2026-06-23..2026-10-22), which lie INSIDE the OOS year. So the IS period is out-of-time for the rules, and the OOS year contains the sample they were read from.
No parameter is tuned on IS or OOS; variants are pre-declared sensitivities, not a search. P&L figures are secondary diagnostics of the replica, not a performance claim about the original."""
import sys, os, warnings
import numpy as np, pandas as pd
from multiprocessing import Pool
warnings.filterwarnings('ignore')
import ref
sys.path.insert(0, ref.REPL)
import data, algo8_v1 as V
CAP = 20_000_000
REG = pd.read_csv(f'{ref.OUT}/historical_regime_register.csv'); REG = REG[REG.eligible].copy()
LH = pd.read_csv(f'{ref.ROOT}/backtest/results/cycle_feasibility.csv')[['und', 'expiry', 'lot1']]; REG = REG.merge(LH, on=['und', 'expiry'], how='left')
VARIANTS = {'V0_base': {}, 'V1_slippage_x0': dict(slip_mult=0.0), 'V2_slippage_x3': dict(slip_mult=3.0), 'V3_costs_x2': dict(cost_mult=2.0), 'V4_cycle_stop_mark_open': dict(cycle_mark='open'), 'V5_leg_k155': dict(leg_mult=1.55), 'V6_leg_k170': dict(leg_mult=1.70),
            'V7_cycle_limit_130k': dict(cycle_limit=130000.0), 'V8_fixed_rupee_cycle_stop': dict(stop_scaling='fixed'), 'A1_no_cycle_stop': dict(cycle_stop=False), 'A2_no_leg_stop': dict(leg_stop=False), 'A3_no_flatten_hold': dict(flatten=False), 'A4_D1_entries_only': dict(d0_entries=False), 'A5_no_wings': dict(wings=False), 'S1_2026_lot_sizes': dict(lots2026=True)}


def one(args):
    vname, kw, row = args; kw = dict(kw); cm = kw.pop('cost_mult', 1.0); l26 = kw.pop('lots2026', False)
    try:
        c = data.load_cycle(row['und'], row['expiry'], row['d1'], row['d0']); units = ref.LOT[row['und']] if (l26 or not row['lot1'] == row['lot1']) else int(row['lot1'])
        lp = V.build(c, row['und'], units=units, **kw).run(); r = V.result(lp, c, row['und'], cm); r.update(variant=vname, und=row['und'], expiry=row['expiry'], d1=row['d1'], d0=row['d0'], units=units, ok=True)
    except Exception as e: r = dict(variant=vname, und=row['und'], expiry=row['expiry'], ok=False, err=repr(e)[:150])
    return r


def label(d0, d1):
    if d0 <= '2025-11-17': return 'IS'
    if d1 <= '2025-11-17': return 'EMBARGO'
    if d0 < '2026-06-22': return 'OOS_clean_before_live_window'
    if d0 <= '2026-10-22': return 'OOS_exposed_live_window'
    return 'OOS_after_live_window'


def summ(df):
    if not len(df): return {}
    d = df.sort_values('d0'); wk = d.assign(wk=pd.to_datetime(d.d0).dt.strftime('%G-W%V')).groupby('wk').net.sum() / CAP; sd = wk.std(ddof=1); eq = np.cumsum(d.net.values) + CAP; pk = np.maximum.accumulate(np.concatenate([[CAP], eq]))[1:]; dd = ((eq - pk) / pk).min()
    win = d[d.net > 0]; los = d[d.net <= 0]; top5 = d.net.nlargest(5).sum()
    return dict(cycles=len(d), weeks=len(wk), gross=d.gross.sum(), net=d.net.sum(), costs=d.costs.sum(), slippage=d.slippage.sum(), net_pct_of_capital=100 * d.net.sum() / CAP, weekly_sharpe=(wk.mean() / sd * np.sqrt(52)) if sd and sd > 0 else np.nan, max_dd_pct_cycle_level=100 * dd, win_rate=100 * len(win) / len(d),
                profit_factor=(win.net.sum() / abs(los.net.sum())) if len(los) and los.net.sum() != 0 else np.nan, worst_cycle=d.net.min(), best_cycle=d.net.max(), top5_cycles_net=top5, net_ex_top5=d.net.sum() - top5, cycle_stop_share=100 * d.cycle_stop.mean(), leg_stops_per_cycle=d.leg_stops.mean(), orders_per_cycle=d.n_orders.mean(), no_market_per_cycle=d.no_market.mean())


if __name__ == '__main__':
    jobs = [(vn, kw, row) for vn, kw in VARIANTS.items() for row in REG.to_dict('records')]
    with Pool(4) as p: R = p.map(one, jobs, chunksize=8)
    D = pd.DataFrame(R); bad = D[~D.ok.astype(bool)]; print('runs', len(D), 'failed', len(bad)); D = D[D.ok.astype(bool)].merge(REG[['und', 'expiry', 'expiry_structure', 'eligibility', 'vol_regime', 'trend_regime']], on=['und', 'expiry'])
    D['split'] = [label(a, b) for a, b in zip(D.d0, D.d1)]; D.to_csv(f'{ref.OUT}/v1_backtest_cycles.csv', index=False)
    rows = []
    for vn, g in D.groupby('variant'):
        for nm, sel in (('IS', g.split == 'IS'), ('OOS (all)', g.split.str.startswith('OOS')), ('OOS clean before live window', g.split == 'OOS_clean_before_live_window'), ('OOS live window (rules read from it)', g.split == 'OOS_exposed_live_window'), ('OOS after live window', g.split == 'OOS_after_live_window'),
                        ('IS NIFTY', (g.split == 'IS') & (g.und == 'NIFTY')), ('IS SENSEX', (g.split == 'IS') & (g.und == 'SENSEX')), ('OOS NIFTY', g.split.str.startswith('OOS') & (g.und == 'NIFTY')), ('OOS SENSEX', g.split.str.startswith('OOS') & (g.und == 'SENSEX')),
                        ('IS strict only', (g.split == 'IS') & (g.eligibility == 'FULLY_FEASIBLE')), ('OOS strict only', g.split.str.startswith('OOS') & (g.eligibility == 'FULLY_FEASIBLE'))):
            s = summ(g[sel]); 
            if s: rows.append(dict(variant=vn, group=nm, **s))
        for st, gg in g.groupby('expiry_structure'): rows.append(dict(variant=vn, group='structure: ' + st, **summ(gg)))
    S = pd.DataFrame(rows); S.to_csv(f'{ref.OUT}/v1_backtest_summary.csv', index=False); pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30)
    print(S[(S.variant == 'V0_base') & ~S.group.str.startswith('structure')][['group', 'cycles', 'gross', 'net', 'costs', 'weekly_sharpe', 'max_dd_pct_cycle_level', 'win_rate', 'cycle_stop_share', 'leg_stops_per_cycle']].round(2).to_string(index=False))
