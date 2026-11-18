"""After FROZEN_CONFIG.json is committed: out-of-sample run, stress tests, tables, charts. Usage: python3 -m bt.final_run oos | stress | tables"""
import json, os, sys
import numpy as np, pandas as pd
from . import experiment as X, metrics as M, config as C
BASE = dict(slip_pct=0.005, slip_min=0.10, delay_min=0, cost_mult=1.0)
SCEN = {'base': {}, 'slippage_x3': dict(slip_pct=0.015, slip_min=0.30), 'slippage_x6': dict(slip_pct=0.03, slip_min=0.60), 'costs_x2': dict(cost_mult=2.0), 'delay_1min': dict(delay_min=1), 'delay_3min': dict(delay_min=3),
        'reduced_liquidity': dict(slip_pct=0.015, slip_min=0.30, delay_min=3)}
FROZEN = json.load(open('FROZEN_CONFIG.json')) if os.path.exists('FROZEN_CONFIG.json') else None
R = 'results'


def names_for(v): return sorted({'HOLD', FROZEN['frozen'][v]['config']})


def oos_cycles(): u = X.usable(); return u[u.split == 'OOS'].reset_index(drop=True)


def all_cycles(): return X.usable()


def table(name, v, params=BASE, tag='', cyc=None, lots=3):
    return X.account_all(name, v, params, cyc=all_cycles() if cyc is None else cyc, tag=tag, lots=lots)


def subsets(d):
    out = {'IS': d[d.split == 'IS'], 'OOS': d[d.split == 'OOS'], 'OOS_exposed': d[d.subset == 'OOS_EXPOSED'], 'OOS_clean_before': d[d.subset == 'OOS_CLEAN_BEFORE'], 'OOS_clean_after': d[d.subset == 'OOS_CLEAN_AFTER'], 'OOS_clean_all': d[d.subset.isin(['OOS_CLEAN_BEFORE', 'OOS_CLEAN_AFTER'])]}
    return out


def run_oos():
    for v in X.VARIANTS:
        X.run_engine(names_for(v), v, cyc=oos_cycles(), check=True)
    print('oos engine runs done')


def build_tables():
    rows = []; led = []
    for v in X.VARIANTS:
        for n in names_for(v):
            d = table(n, v)
            for part, sub in subsets(d).items():
                for scope, dd in (('NIFTY', sub[sub.und == 'NIFTY']), ('SENSEX', sub[sub.und == 'SENSEX']), ('COMBINED', sub)):
                    if len(dd): s = M.summarize(dd, f'{v}|{n}|{part}|{scope}'); s.update(variant=v, config=n, part=part, scope=scope, parity_all=bool(dd.parity.all())); rows.append(s)
            for r in d.itertuples():
                for k, tr in enumerate(r.trades): led.append(dict(variant=v, config=n, und=r.und, expiry=r.expiry, split=r.split, subset=r.subset, ts_epoch=tr[0], leg=tr[1], side=tr[2], qty=tr[3], ref_price=tr[4], exec_price=round(tr[5], 4), kind=tr[6]))
                for lid, q, val in r.settle: led.append(dict(variant=v, config=n, und=r.und, expiry=r.expiry, split=r.split, subset=r.subset, ts_epoch=0, leg=lid, side=0, qty=q, ref_price=val, exec_price=val, kind='SETTLEMENT'))
    pd.DataFrame(rows).to_csv(f'{R}/performance_summary.csv', index=False); pd.DataFrame(led).to_csv(f'{R}/trade_ledger.csv', index=False)
    return pd.DataFrame(rows)


def run_stress():
    out = []
    for v in X.VARIANTS:
        for n in names_for(v):
            for sc, p in SCEN.items():
                d = table(n, v, dict(BASE, **p))
                for part in ('IS', 'OOS'):
                    for scope in ('NIFTY', 'SENSEX', 'COMBINED'):
                        dd = subsets(d)[part]; dd = dd if scope == 'COMBINED' else dd[dd.und == scope]
                        if len(dd): s = M.summarize(dd); out.append(dict(variant=v, config=n, scenario=sc, part=part, scope=scope, net_pnl=s['net_pnl'], sharpe=s['sharpe'], max_dd_pct=s['max_dd_pct'], win_rate_pct=s['win_rate_pct'], profit_factor=s['profit_factor'], cycles=s['cycles']))
    # engine-level stresses: sizing and missing observations
    for v in X.VARIANTS:
        for n in names_for(v):
            for tag, kw in (('_L1', dict(lots=1)), ('_L6', dict(lots=6)), ('_M20s1', dict(drop=0.2, dseed=1)), ('_M20s2', dict(drop=0.2, dseed=2)), ('_M20s3', dict(drop=0.2, dseed=3))):
                X.run_engine([n], v, cyc=all_cycles(), check=True, tag=tag, **kw)
                d = table(n, v, BASE, tag=tag)
                for part in ('IS', 'OOS'):
                    for scope in ('NIFTY', 'SENSEX', 'COMBINED'):
                        dd = subsets(d)[part]; dd = dd if scope == 'COMBINED' else dd[dd.und == scope]
                        if len(dd): s = M.summarize(dd); out.append(dict(variant=v, config=n, scenario={'_L1': 'size_1_lot', '_L6': 'size_6_lots'}.get(tag, 'missing_20pct_bars_seed' + tag[-1]), part=part, scope=scope, net_pnl=s['net_pnl'], sharpe=s['sharpe'], max_dd_pct=s['max_dd_pct'], win_rate_pct=s['win_rate_pct'], profit_factor=s['profit_factor'], cycles=s['cycles'], parity_all=bool(dd.parity.all())))
    pd.DataFrame(out).to_csv(f'{R}/stress_tests.csv', index=False)


if __name__ == '__main__':
    {'oos': run_oos, 'tables': build_tables, 'stress': run_stress}[sys.argv[1]]()
