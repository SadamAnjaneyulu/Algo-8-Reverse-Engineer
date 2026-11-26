"""Metrics, splits, overfitting checks and figures for the reconstructed-Algo-8 backtest (PREREGISTRATION.md). Reads results/runs.pkl; writes results/*.csv, results/summary.json, figures/."""
import sys, os, json, math, pickle, warnings
R = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
for p in (R, f'{R}/backtest'): sys.path.insert(0, p)
warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from bt import metrics as M
RES = f'{R}/backtest/recon_bt/results'; FIG = f'{R}/backtest/recon_bt/figures'; os.makedirs(FIG, exist_ok=True); CAP = 20_000_000; rng = np.random.default_rng(20261126)
runs = pickle.load(open(f'{RES}/runs.pkl', 'rb')); LEVELS = ['NONE', 'S125', 'S200']
def split_of(d0): return 'DEV' if '2026-06-22' <= d0 <= '2026-10-22' else ('POST' if d0 >= '2026-10-23' else 'PRE')
def user_split(d1, d0): return 'EMBARGO' if (d1 <= '2025-11-17' < d0) else ('USER_IS' if d0 <= '2025-11-17' else 'USER_OOS')
D = {}
for lv in LEVELS:
    df = pd.DataFrame([{k: v for k, v in r.items()} for (n, u, e), r in runs.items() if n == lv]).sort_values(['d0', 'und']).reset_index(drop=True)
    df['split'] = df.d0.map(split_of); df['usplit'] = [user_split(a, b) for a, b in zip(df.d1, df.d0)]; df['peak_margin'] = np.nan; df['year'] = df.d0.str.slice(0, 4); df['quarter'] = pd.PeriodIndex(pd.to_datetime(df.d0), freq='Q').astype(str); D[lv] = df
N = len(D['S200']); assert all(len(D[l]) == N for l in LEVELS) and N == 275
def summ(df, label):
    if not len(df): return dict(label=label, cycles=0)
    s = M.summarize(df, label); r = df.net.values; q = np.sort(r); k = max(int(math.ceil(0.05 * len(q))), 1); s['cvar5_cycle'] = q[:k].mean(); s['stop_rate_pct'] = 100 * df.stopped.mean(); s['median_cycle'] = float(np.median(r)); s['avg_orders_per_cycle'] = df.n_orders.mean(); return s
SC = {'ALL': lambda d: d, 'NIFTY': lambda d: d[d.und == 'NIFTY'], 'SENSEX': lambda d: d[d.und == 'SENSEX']}
SPL = {'ALL_PERIODS': lambda d: d, 'PRE': lambda d: d[d.split == 'PRE'], 'DEV': lambda d: d[d.split == 'DEV'], 'POST': lambda d: d[d.split == 'POST'], 'USER_IS': lambda d: d[d.usplit == 'USER_IS'], 'USER_OOS': lambda d: d[d.usplit == 'USER_OOS'], 'OOS_ALL(PRE+POST)': lambda d: d[d.split != 'DEV']}
rows = []
for lv in LEVELS:
    for sc, f in SC.items():
        for sp, g in SPL.items():
            s = summ(g(f(D[lv])), f'{lv}|{sc}|{sp}'); s.update(level=lv, scope=sc, split=sp); rows.append(s)
T = pd.DataFrame(rows); keep = ['level', 'scope', 'split', 'cycles', 'net_pnl', 'gross_pnl', 'costs', 'slippage', 'win_rate_pct', 'sharpe', 'sortino', 'max_dd_rs', 'max_dd_pct', 'profit_factor', 'avg_win', 'avg_loss', 'expectancy', 'median_cycle', 'worst_cycle', 'best_cycle', 'cvar5_cycle', 'top5_share_of_gross_wins_pct', 'ann_return_pct', 'vol_ann_pct', 'longest_dd_days', 'stop_rate_pct', 'avg_orders_per_cycle']
T[keep].to_csv(f'{RES}/summary_table.csv', index=False)
# ---- bootstrap (week blocks of 4)
def wk(df): return df.assign(wk=pd.to_datetime(df.d0).dt.strftime('%G-W%V')).groupby('wk').net.sum()
def block_boot_sharpe(w, B=4000, blk=4):
    x = w.values / CAP; n = len(x)
    if n < 12: return (float('nan'), float('nan'))
    out = []
    for _ in range(B):
        idx = np.concatenate([np.arange(s, s + blk) % n for s in rng.integers(0, n, int(math.ceil(n / blk)))])[:n]; y = x[idx]; sd = y.std(ddof=1); out.append(y.mean() / sd * math.sqrt(52) if sd > 0 else np.nan)
    return tuple(np.nanpercentile(out, [2.5, 97.5]))
ci = {}
for lv in LEVELS:
    for sc in SC:
        for sp in ('PRE', 'DEV', 'POST', 'ALL_PERIODS', 'OOS_ALL(PRE+POST)'):
            g = SPL[sp](SC[sc](D[lv])); lo, hi = block_boot_sharpe(wk(g)) if len(g) else (np.nan, np.nan); ci[(lv, sc, sp)] = (lo, hi)
T['sharpe_ci_lo'] = [ci[(r.level, r.scope, r.split)][0] if (r.level, r.scope, r.split) in ci else np.nan for r in T.itertuples()]; T['sharpe_ci_hi'] = [ci[(r.level, r.scope, r.split)][1] if (r.level, r.scope, r.split) in ci else np.nan for r in T.itertuples()]
T[keep + ['sharpe_ci_lo', 'sharpe_ci_hi']].to_csv(f'{RES}/summary_table.csv', index=False)
# ---- stress, scaling, concentration (net only)
st = []
for lv in LEVELS:
    for sc in SC:
        for sp in ('PRE', 'DEV', 'POST', 'ALL_PERIODS'):
            g = SPL[sp](SC[sc](D[lv]))
            if not len(g): continue
            top5 = g.net.nlargest(5).sum(); st.append(dict(level=lv, scope=sc, split=sp, cycles=len(g), net=g.net.sum(), net_without_top5=g.net.sum() - top5, net_slip3x=(g.gross - 3 * g.slippage - g.costs).sum(), net_cost3x=(g.gross - g.slippage - 3 * g.costs).sum(), net_slip3x_cost3x=(g.gross - 3 * g.slippage - 3 * g.costs).sum(), net_scaled_2026_lots=g.net_scaled_2026lots.sum(), positive_quarters_pct=100 * (g.groupby('quarter').net.sum() > 0).mean(), positive_years_pct=100 * (g.groupby('year').net.sum() > 0).mean()))
S2 = pd.DataFrame(st); S2.to_csv(f'{RES}/stress_concentration.csv', index=False)
# ---- per year / quarter
Y = D['S200'].groupby(['und', 'year']).agg(cycles=('net', 'size'), net=('net', 'sum'), win=('net', lambda x: 100 * (x > 0).mean())).reset_index(); Y.to_csv(f'{RES}/by_year_S200.csv', index=False)
Qr = D['S200'].groupby('quarter').net.sum().reset_index(); Qr.to_csv(f'{RES}/by_quarter_S200.csv', index=False)
# ---- paired stop comparison S200 - S125 (and vs NONE)
def paired(a, b, sp, B=4000):
    x = D[a].set_index(['und', 'expiry']); y = D[b].set_index(['und', 'expiry']); d = (x.net - y.net).rename('d').to_frame().join(x[['d0', 'split']]); d = d[d.split == sp] if sp != 'ALL' else d
    w = d.assign(wk=pd.to_datetime(d.d0).dt.strftime('%G-W%V')).groupby('wk').d.sum().values; n = len(w); bs = [w[rng.integers(0, n, n)].mean() for _ in range(B)] if n > 3 else [np.nan]
    return dict(a=a, b=b, split=sp, cycles=len(d), mean_diff_per_cycle=d.d.mean(), total_diff=d.d.sum(), ci_lo_per_week=float(np.percentile(bs, 2.5)), ci_hi_per_week=float(np.percentile(bs, 97.5)), cycles_changed=int((d.d != 0).sum()), cycles_better=int((d.d > 0).sum()), cycles_worse=int((d.d < 0).sum()), diff_without_top5=d.d.sum() - d.d.nlargest(5).sum(), top5_share_pct=100 * d.d.nlargest(5).sum() / d.d.sum() if d.d.sum() > 0 else float('nan'))
P = pd.DataFrame([paired(a, b, sp) for a, b in (('S200', 'S125'), ('S200', 'NONE'), ('S125', 'NONE')) for sp in ('PRE', 'DEV', 'POST', 'ALL')]); P.to_csv(f'{RES}/stop_paired.csv', index=False)
# ---- grades
def grade(lv):
    pre = SPL['PRE'](D[lv]); g = {}
    lo, hi = ci[(lv, 'ALL', 'PRE')]; sh = T[(T.level == lv) & (T.scope == 'ALL') & (T.split == 'PRE')].sharpe.iloc[0]
    g['R1 PRE Sharpe > 0 and 95% block-bootstrap lower bound > 0'] = (sh, lo, bool(sh > 0 and lo > 0))
    n_, s_ = SC['NIFTY'](pre).net.sum(), SC['SENSEX'](pre).net.sum(); g['R2 PRE net > 0 for NIFTY and SENSEX'] = ((n_, s_), None, bool(n_ > 0 and s_ > 0))
    pq = 100 * (pre.groupby('quarter').net.sum() > 0).mean(); g['R3 >= 60% of PRE quarters positive'] = (pq, 60, bool(pq >= 60))
    t5 = pre.net.sum() - pre.net.nlargest(5).sum(); g['R4 PRE net > 0 without the 5 best cycles'] = (t5, 0, bool(t5 > 0))
    c3 = (pre.gross - pre.slippage - 3 * pre.costs).sum(); g['R5 PRE net > 0 at 3x costs'] = (c3, 0, bool(c3 > 0))
    post = SPL['POST'](D[lv]); g['R6 POST net > 0'] = (post.net.sum(), len(post), bool(len(post) >= 1 and post.net.sum() > 0))
    shd = T[(T.level == lv) & (T.scope == 'ALL') & (T.split == 'DEV')].sharpe.iloc[0]; g['R7 DEV->PRE Sharpe ratio (reported)'] = (sh / shd if shd else np.nan, None, None)
    return g
G = {lv: grade(lv) for lv in LEVELS}
Pp = P.set_index(['a', 'b', 'split']); r = {}
def sd(sp): return Pp.loc[('S200', 'S125', sp)]
a_ = bool(sd('PRE').ci_lo_per_week > 0); b_ = bool(all(sd(s).mean_diff_per_cycle > 0 for s in ('DEV', 'PRE', 'POST'))); c_ = bool(sd('PRE').diff_without_top5 > 0)
w200 = D['S200'].net.min(); w125 = D['S125'].net.min(); dd200 = T[(T.level == 'S200') & (T.scope == 'ALL') & (T.split == 'ALL_PERIODS')].max_dd_rs.iloc[0]; dd125 = T[(T.level == 'S125') & (T.scope == 'ALL') & (T.split == 'ALL_PERIODS')].max_dd_rs.iloc[0]
d_ = bool(w200 >= 1.25 * w125 and dd200 >= 1.25 * dd125)      # (losses are negative numbers: no more than 25% worse)
STOPVERDICT = dict(a_paired_ci_lower_gt0_in_PRE=a_, b_positive_mean_in_DEV_PRE_POST=b_, c_positive_after_removing_top5_in_PRE=c_, d_worst_cycle_and_maxdd_not_more_than_25pct_worse=d_, worst_cycle=dict(S200=w200, S125=w125), maxdd_rs=dict(S200=dd200, S125=dd125), S200_better_supported=bool(a_ and b_ and c_ and d_))
json.dump(dict(grades={lv: {k: [None if (isinstance(x, float) and x != x) else (list(x) if isinstance(x, tuple) else x) for x in v] for k, v in g.items()} for lv, g in G.items()}, stop_verdict=STOPVERDICT, n_cycles=N), open(f'{RES}/summary.json', 'w'), indent=1, default=float)
# per-cycle ledger
led = D['S200'][['und', 'expiry', 'd1', 'd0', 'split', 'usplit', 'lot', 'gross', 'slippage', 'costs', 'net', 'n_orders', 'stopped', 'stop_minute', 'min_path', 'max_path', 'handoff_error', 'residual_d0_contracts', 'settle']].copy()
for lv in ('NONE', 'S125'): led[f'net_{lv}'] = D[lv].net.values; led[f'stopped_{lv}'] = D[lv].stopped.values
led.rename(columns={'net': 'net_S200', 'stopped': 'stopped_S200'}).to_csv(f'{RES}/cycle_ledger.csv', index=False)
# ---- figures
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
def curve(df):
    t, v = M.equity_curve(df); return pd.to_datetime(t, unit='s') if False else pd.to_datetime([pd.Timestamp.fromordinal(int(x // 86400)) + pd.Timedelta(seconds=float(x % 86400)) for x in t]), v
fig, ax = plt.subplots(3, 1, figsize=(11, 10), sharex=True)
for a, (sc, f) in zip(ax, SC.items()):
    for lv, col in (('NONE', '#999999'), ('S125', '#d95f02'), ('S200', '#1b9e77')):
        x, v = curve(f(D[lv])); a.plot(x, v / 1e5, label=lv, color=col, lw=1.2)
    a.axvspan(pd.Timestamp('2026-06-22'), pd.Timestamp('2026-10-22'), color='#bbbbee', alpha=0.35, label='DEV window'); a.axvline(pd.Timestamp('2025-11-17'), color='k', ls=':', lw=1); a.set_ylabel('cumulative net P&L (Rs lakh)'); a.set_title(sc); a.grid(alpha=.3)
ax[0].legend(); plt.tight_layout(); plt.savefig(f'{FIG}/equity_curves.png', dpi=130); plt.close()
fig, ax = plt.subplots(1, 1, figsize=(11, 4))
for lv, col in (('S125', '#d95f02'), ('S200', '#1b9e77')):
    x, v = curve(D[lv]); eq = CAP + v; pk = np.maximum.accumulate(eq); ax.plot(x, (eq - pk) / 1e5, label=lv, color=col, lw=1)
ax.set_ylabel('drawdown (Rs lakh)'); ax.legend(); ax.grid(alpha=.3); plt.tight_layout(); plt.savefig(f'{FIG}/drawdown.png', dpi=130); plt.close()
print(T[T.split.isin(['ALL_PERIODS', 'PRE', 'DEV', 'POST'])][['level', 'scope', 'split', 'cycles', 'net_pnl', 'win_rate_pct', 'sharpe', 'max_dd_rs', 'max_dd_pct', 'profit_factor']].round(2).to_string(index=False)); print(json.dumps(STOPVERDICT, default=float, indent=1)); print({lv: {k: v[2] for k, v in G[lv].items()} for lv in LEVELS})
