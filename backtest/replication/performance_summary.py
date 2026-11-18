import math, json
from common import *
D = pd.read_csv(f'{RES}/performance_cycles.csv'); D['wk'] = pd.to_datetime(D.d0).dt.strftime('%G-W%V'); D['d0'] = pd.to_datetime(D.d0); D['d1'] = pd.to_datetime(D.d1)
LIVE = pd.read_csv(f'{RES}/live_cycle_pnl.csv', parse_dates=['expiry']); B = pd.read_csv(f'{RES}/../../results/performance_summary.csv') if os.path.exists(f'{RES}/../../results/performance_summary.csv') else None


def summ(x, col='net'):
    w = x.groupby('wk')[col].sum() / CAP; n = len(w); sd = w.std(ddof=1) if n > 1 else np.nan; sh = w.mean() / sd * math.sqrt(52) if sd and sd > 0 else np.nan
    y = x.sort_values(['d0', 'und']); eq = np.cumsum(y[col].values); pk = np.maximum.accumulate(np.r_[0, eq])[1:]; dd = (eq - pk).min() if len(eq) else 0
    span = max((x.d0.max() - x.d1.min()).days / 365.25, 1e-9); tot = x[col].sum(); win = x[x[col] > 0][col].sum(); los = -x[x[col] <= 0][col].sum()
    return dict(cycles=len(x), weeks=n, net_pnl=tot, ret_pct=100 * tot / CAP, cagr_pct=100 * ((1 + tot / CAP) ** (1 / span) - 1), vol_ann_pct=100 * sd * math.sqrt(52), sharpe=sh, max_dd_rs_cycle_path=dd, max_dd_pct=100 * dd / CAP, win_rate=100 * (x[col] > 0).mean(), profit_factor=win / los if los else np.nan, worst_cycle=x[col].min(), best_cycle=x[col].max(),
                orders_per_cycle=x.n_orders.mean(), costs=x.costs.sum(), slippage=x.slippage.sum(), stop_cycles=int(x.stopped.sum()))
parts = {'IS': lambda d: d[d.split == 'IS'], 'OOS': lambda d: d[d.split == 'OOS'], 'OOS exposed (live window)': lambda d: d[d.subset == 'OOS_EXPOSED'], 'OOS clean': lambda d: d[d.subset.isin(['OOS_CLEAN_BEFORE', 'OOS_CLEAN_AFTER'])], 'OOS clean-before': lambda d: d[d.subset == 'OOS_CLEAN_BEFORE'],
         'Screenshot window 2025-03-03..2026-05-27': lambda d: d[(d.d0 >= '2025-03-03') & (d.d0 <= '2026-05-27')], 'ALL': lambda d: d}
rows = []
for v in ('R1', 'R2'):
    for p, f in parts.items():
        for col in ('net', 'gross'):
            x = f(D[D.variant == v]); rows.append(dict(variant=v, part=p, basis=col, **summ(x, col)))
S = pd.DataFrame(rows); S.to_csv(f'{RES}/performance_summary_replication.csv', index=False); pd.set_option('display.width', 280); pd.set_option('display.max_columns', 30)
print(S[S.basis == 'net'][['variant', 'part', 'cycles', 'weeks', 'net_pnl', 'ret_pct', 'cagr_pct', 'sharpe', 'vol_ann_pct', 'max_dd_pct', 'win_rate', 'profit_factor', 'orders_per_cycle', 'stop_cycles']].round(2).to_string(index=False))
print(S[S.basis == 'gross'][['variant', 'part', 'net_pnl', 'sharpe']].round(2).to_string(index=False))
# live reference: 35 cycles
for col in ('gross', 'net_cost_model'):
    w = LIVE.groupby(LIVE.expiry.dt.strftime('%G-W%V'))[col].sum() / CAP; print('LIVE', col, 'sharpe', round(w.mean() / w.std(ddof=1) * math.sqrt(52), 2), 'total', round(LIVE[col].sum()))
