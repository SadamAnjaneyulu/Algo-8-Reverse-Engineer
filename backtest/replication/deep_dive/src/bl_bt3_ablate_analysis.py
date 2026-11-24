"""Analysis of the ablation / placebo runs (plan reports/ALPHA_SOURCE_PLAN.md). Constant lot size (NIFTY 65, SENSEX 20). Paired difference to the full strategy with a week-cluster bootstrap; risk measures per variant.
Outputs outputs/bt3_results/ablate_summary.csv, ablate_diffs.csv"""
import sys, os, glob, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
OUT = os.path.join(os.path.dirname(os.path.abspath('.')), 'outputs'); RES = f'{OUT}/bt3_results'; REFU = {'NIFTY': 65.0, 'SENSEX': 20.0}; rng = np.random.default_rng(7)
ORDER = ['full', 'd1_no_timetable', 'd1_no_breakout', 'd1_no_ladder', 'd1_no_stops', 'd1_no_wings', 'd1_no_lump', 'd0_no_new_sells', 'd0_no_waves', 'd0_no_breakout', 'd0_no_ladder', 'd0_no_counter', 'd0_no_stop_tp', 'd0_no_hedge', 'no_cycle_stop', 'd0_only', 'P1_flip_ladder_direction', 'P2_shift_waves_37min']
T = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv')[['und', 'expiry', 'split3']]
def load(name):
    d = pd.read_csv(f'{RES}/ablate_{name}_cycles.csv'); d = d[d.ok].merge(T, on=['und', 'expiry'], suffixes=('', '_t')); k = d.und.map(REFU) / d.unit; d['net_k'] = d.net * k; d['gross_k'] = d.gross * k; d['wk'] = pd.to_datetime(d.d0).dt.strftime('%G-%V'); d['stopped'] = d.stop_j.notna(); return d.sort_values(['und', 'expiry']).reset_index(drop=True)
D = {n: load(n) for n in ORDER}; base = D['full']; assert all(len(D[n]) == len(base) and (D[n].expiry.values == base.expiry.values).all() for n in ORDER)
def wk_stats(d, col):
    w = d.groupby('wk')[col].mean(); cum = w.cumsum(); return float(w.mean() / w.std(ddof=1) * np.sqrt(52)) if w.std() > 0 else np.nan, float((cum - cum.cummax()).min())
rows = []
for n in ORDER:
    d = D[n]; sh, dd = wk_stats(d, 'net_k'); x = d.net_k.values; rows.append(dict(variant=n, cycles=len(d), net_mean=x.mean(), gross_mean=d.gross_k.mean(), net_sd=x.std(ddof=1), net_p5=np.quantile(x, .05), net_worst=x.min(), win_rate=(x > 0).mean(), weekly_sharpe=sh, max_dd_weekly_mean=dd, orders=d.orders.mean(), stop_share=d.stopped.mean(), peak_short_lots=((d.peak_CE + d.peak_PE) / 2).mean()))
SUM = pd.DataFrame(rows); SUM.round(2).to_csv(f'{RES}/ablate_summary.csv', index=False)
def paired(n, col, mask=None):
    a = D[n][col].values - base[col].values; wk = base.wk.values
    if mask is not None: a = a[mask]; wk = wk[mask]
    u = np.unique(wk); idx = {w: np.where(wk == w)[0] for w in u}; b = []
    for _ in range(2000): ch = rng.choice(u, len(u)); b.append(a[np.concatenate([idx[w] for w in ch])].mean())
    return float(a.mean()), float(np.quantile(b, .025)), float(np.quantile(b, .975))
dr = []
for n in ORDER[1:]:
    row = dict(variant=n)
    for col in ('net_k', 'gross_k'): m, lo, hi = paired(n, col); row[f'{col}_diff'] = m; row[f'{col}_lo'] = lo; row[f'{col}_hi'] = hi
    for sp in ('IS', 'OOS', 'LIVE_FITTED'): row[f'net_diff_{sp}'] = float((D[n].net_k.values - base.net_k.values)[(base.split3 == sp).values].mean())
    row['sign_consistent_across_splits'] = bool(np.all(np.sign([row['net_diff_IS'], row['net_diff_OOS'], row['net_diff_LIVE_FITTED']]) == np.sign(row['net_k_diff'])))
    row['d_sd'] = float(D[n].net_k.std(ddof=1) - base.net_k.std(ddof=1)); row['d_worst'] = float(D[n].net_k.min() - base.net_k.min()); row['d_p5'] = float(np.quantile(D[n].net_k, .05) - np.quantile(base.net_k, .05)); dr.append(row)
DF = pd.DataFrame(dr); DF['verdict'] = np.where(DF.net_k_lo > 0, 'removing it RAISES net (it hurts the mean)', np.where(DF.net_k_hi < 0, 'removing it LOWERS net (it carries the edge)', 'not distinguishable from zero')); DF.round(1).to_csv(f'{RES}/ablate_diffs.csv', index=False)
pd.set_option('display.width', 280); pd.set_option('display.max_columns', 40); print(SUM[['variant', 'net_mean', 'gross_mean', 'net_sd', 'net_p5', 'net_worst', 'win_rate', 'weekly_sharpe', 'orders', 'stop_share']].round(1).to_string(index=False)); print(DF[['variant', 'net_k_diff', 'net_k_lo', 'net_k_hi', 'gross_k_diff', 'net_diff_IS', 'net_diff_OOS', 'net_diff_LIVE_FITTED', 'sign_consistent_across_splits', 'd_sd', 'd_worst', 'verdict']].round(0).to_string(index=False))
