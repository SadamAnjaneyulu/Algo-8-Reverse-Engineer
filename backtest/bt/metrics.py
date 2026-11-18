"""Performance metrics. Return frequency: one return per expiry cycle (about one per week), annualised with sqrt(52). Capital is the stated Rs 2 crore held constant (unlevered, no compounding, risk-free rate 0)."""
import math
from datetime import date
import numpy as np, pandas as pd
from . import config as C
K = 52


def equity_curve(df):
    """(times, cumulative net P&L) built from every cycle's intra-cycle path; cycles are additive"""
    inc = []
    for r in df.itertuples():
        prev = 0.0
        for t, v in r.path: inc.append((t, v - prev)); prev = v
    inc.sort(); t = np.array([x[0] for x in inc]); v = np.cumsum([x[1] for x in inc]); return t, v


def drawdown(t, v, cap=C.CAPITAL_RS):
    eq = cap + v; peak = np.maximum.accumulate(np.concatenate([[cap], eq]))[1:]; dd = eq - peak; ddp = dd / peak
    i = int(np.argmin(dd)) if len(dd) else 0; pk = int(np.argmax(eq[:i + 1])) if len(dd) else 0
    # duration: longest stretch below a prior peak, in calendar days
    longest = cur = 0.0; start = None
    for k in range(len(eq)):
        if eq[k] >= peak[k] - 1e-9: start = t[k]; cur = 0.0
        else: cur = (t[k] - (start if start is not None else t[0])) / 86400.0
        longest = max(longest, cur)
    return dict(max_dd_rs=float(dd.min()) if len(dd) else 0.0, max_dd_pct=float(ddp.min()) if len(dd) else 0.0, longest_dd_days=float(longest))


def weekly(df, col='net'):
    d = df.copy(); d['wk'] = pd.to_datetime(d.d0).dt.strftime('%G-W%V'); return d.groupby('wk')[col].sum()


def summarize(df, label='', cap=C.CAPITAL_RS):
    if not len(df): return dict(label=label, cycles=0)
    r = weekly(df).values / cap; n = len(r); mean = r.mean(); sd = r.std(ddof=1) if n > 1 else float('nan'); dn = r[r < 0]; dsd = math.sqrt((dn ** 2).sum() / n) if n else float('nan')
    t, v = equity_curve(df); dd = drawdown(t, v); span_y = max((pd.Timestamp(df.d0.max()) - pd.Timestamp(df.d1.min())).days / 365.25, 1e-9); tot = df.net.sum(); ann = tot / cap / span_y
    win = df[df.net > 0]; los = df[df.net <= 0]; pf = win.net.sum() / abs(los.net.sum()) if len(los) and los.net.sum() != 0 else float('inf')
    return dict(label=label, cycles=len(df), weeks=n, gross_pnl=df.gross.sum(), net_pnl=tot, costs=df.costs.sum(), slippage=df.slippage.sum(), cum_return_pct=100 * tot / cap, ann_return_pct=100 * ann, avg_pnl_per_cycle=df.net.mean(),
                vol_ann_pct=100 * sd * math.sqrt(K), sharpe=(mean / sd * math.sqrt(K)) if sd and sd == sd and sd > 0 else float('nan'), sortino=(mean / dsd * math.sqrt(K)) if dsd and dsd > 0 else float('nan'), downside_dev_ann_pct=100 * dsd * math.sqrt(K),
                max_dd_rs=dd['max_dd_rs'], max_dd_pct=100 * dd['max_dd_pct'], longest_dd_days=dd['longest_dd_days'], calmar=(ann / abs(dd['max_dd_pct'])) if dd['max_dd_pct'] < 0 else float('nan'),
                win_rate_pct=100 * len(win) / len(df), avg_win=win.net.mean() if len(win) else 0.0, avg_loss=los.net.mean() if len(los) else 0.0, profit_factor=pf, expectancy=df.net.mean(), total_orders=int(df.n_orders.sum()),
                avg_margin_proxy=df.peak_margin.mean(), peak_margin_proxy=df.peak_margin.max(), peak_margin_util_pct=100 * df.peak_margin.max() / cap, best_cycle=df.net.max(), worst_cycle=df.net.min(),
                top5_share_of_gross_wins_pct=(100 * win.net.nlargest(5).sum() / win.net.sum()) if len(win) and win.net.sum() > 0 else float('nan'))
