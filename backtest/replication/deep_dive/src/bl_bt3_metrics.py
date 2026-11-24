"""Metrics for the combined backtest (plan reports/BACKTEST3Y_PLAN.md): total trades (orders), win rate (cycles), profit factor, Sharpe (weekly aggregate, x sqrt 52), return on Rs 2 crore, max drawdown, trades per day; Rs and points x lots.
usage as module: metrics(cycles_df, col) ; as script: python bl_bt3_metrics.py <split> (prints both timetable runs and the pre-registered version selection for IS)."""
import sys, os, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
OUT = os.path.join(os.path.dirname(os.path.abspath('.')), 'outputs'); RES = f'{OUT}/bt3_results'; CAP = 2e7
def weekly(df, col):
    d = df.copy(); d['wk'] = pd.to_datetime(d.d0).dt.strftime('%G-%V'); return d.groupby('wk')[col].sum().sort_index()
def boot_ci(x, nb=2000, seed=1, block=None):
    rng = np.random.default_rng(seed); x = np.asarray(x, float)
    if block is None: m = [rng.choice(x, len(x)).mean() for _ in range(nb)]
    else:
        g = np.unique(block); idx = {b: np.where(block == b)[0] for b in g}; m = []
        for _ in range(nb): ii = np.concatenate([idx[b] for b in rng.choice(g, len(g))]); m.append(x[ii].mean())
    return float(np.quantile(m, .025)), float(np.quantile(m, .975))
def metrics(df, col='net'):
    x = df[col].values; pos = x[x > 0].sum(); neg = -x[x < 0].sum(); w = weekly(df, col); cum = w.cumsum(); dd = (cum - cum.cummax()).min(); yrs = max((pd.to_datetime(df.d0).max() - pd.to_datetime(df.d0).min()).days / 365.25, 1e-9)
    lo, hi = boot_ci(x); blo, bhi = boot_ci(x, block=pd.to_datetime(df.d0).dt.strftime('%Y-%m').values)
    return dict(cycles=len(df), orders=int(df.orders.sum()), trades_per_day=float(df.orders.sum() / (2 * len(df))), win_rate=float((x > 0).mean()), profit_factor=float(pos / neg) if neg > 0 else np.inf, mean_rs=float(x.mean()), median_rs=float(np.median(x)), t_stat=float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))) if len(x) > 2 else np.nan,
                ci_cycle_lo=lo, ci_cycle_hi=hi, ci_month_lo=blo, ci_month_hi=bhi, total_rs=float(x.sum()), return_pct_on_2cr=float(100 * x.sum() / CAP), annualised_return_pct=float(100 * x.sum() / CAP / yrs), sharpe_weekly=float(w.mean() / w.std(ddof=1) * np.sqrt(52)) if len(w) > 2 and w.std() > 0 else np.nan, max_drawdown_rs=float(dd), max_drawdown_pct=float(100 * dd / CAP), points_lots_mean=float((df[col] / df.unit).mean()))
def table(split, runs=('A/V1', 'B/V2')):
    rows = []
    for run in runs:
        C = pd.read_csv(f'{RES}/{split}_{run.replace("/", "-")}_cycles.csv'); C = C[C.ok]
        for col in ('gross', 'net'):
            for u in ('ALL', 'NIFTY', 'SENSEX'):
                d = C if u == 'ALL' else C[C.und == u]
                if len(d) > 2: rows.append(dict(split=split, run=run, basis=col, index=u, **metrics(d, col)))
    return pd.DataFrame(rows)
if __name__ == '__main__':
    split = sys.argv[1] if len(sys.argv) > 1 else 'IS'; T = table(split); pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30)
    show = ['run', 'basis', 'index', 'cycles', 'orders', 'trades_per_day', 'win_rate', 'profit_factor', 'mean_rs', 'median_rs', 't_stat', 'ci_cycle_lo', 'ci_cycle_hi', 'total_rs', 'return_pct_on_2cr', 'sharpe_weekly', 'max_drawdown_pct']
    print(T[show].round(2).to_string(index=False)); T.to_csv(f'{RES}/{split}_metrics.csv', index=False)
    if split == 'IS':
        net = {r: pd.read_csv(f'{RES}/IS_{r.replace("/", "-")}_cycles.csv').net.mean() for r in ('A/V1', 'B/V2')}; sel = max(net, key=net.get); print('IS mean net per cycle:', {k: round(v) for k, v in net.items()}, '=> selected timetable version for the OOS point line:', sel); open(f'{RES}/IS_version_selection.txt', 'w').write(f'{sel}\n{net}\n')
