"""Pre-paper-trading battery (reports/PREPAPER_PLAN.md): B2 tables, B3 Deflated Sharpe / PBO (CSCV) / random-timetable null, B4 path & tail, headline metrics, gates G1-G8.
Inputs outputs/prepaper/var_*.csv, exec_cycles.csv, capacity.csv. Output outputs/prepaper/{param_table,headline,path,worst_cycles,gates}.csv and pp_summary.json."""
import sys, os, json, glob, itertools, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from scipy.stats import norm
OUT = os.path.join(os.path.dirname(os.path.abspath('.')), 'outputs'); PP = f'{OUT}/prepaper'; CAP = 2e7; rng = np.random.default_rng(20261124)
V = pd.concat([pd.read_csv(f) for f in glob.glob(f'{PP}/var_*.csv')]); V = V[V.ok]; V['wk'] = pd.to_datetime(V.d0).dt.strftime('%G-%V')
E = pd.read_csv(f'{PP}/exec_cycles.csv'); E['wk'] = pd.to_datetime(E.d0).dt.strftime('%G-%V'); full = V[V.variant == 'full']; base = full.net.mean()
assert abs(E.net.mean() - base) < 1, 'exec and full runs differ'
# ---------------- B2 parameter table
rows = []
for name, g in V.groupby('variant'):
    if name == 'full' or name.startswith('null'): continue
    par, lvl = name.rsplit(' ', 1); m = g.net.mean(); rows.append(dict(parameter=par, level=lvl, mean_net=m, change_vs_full=m - base, change_pct=(m - base) / base, oos_mean_net=g[g.split == 'OOS'].net.mean()))
PT = pd.DataFrame(rows); PT.to_csv(f'{PP}/param_table.csv', index=False)
core = PT[PT.level.isin(['-20%', '+20%', '-5min', '+5min'])]; g3_fail = core[(core.mean_net <= 0) | (core.change_pct < -0.5)]
# ---------------- B3c null
nulls = V[V.variant.str.startswith('null')].groupby('variant').net.mean(); null_pct = float((nulls < base).mean()); null_p95 = float(np.quantile(nulls, .95))
# ---------------- weekly matrix for DSR and PBO (full + B2 variants)
cand = ['full'] + sorted(v for v in V.variant.unique() if v != 'full' and not v.startswith('null'))
W = V[V.variant.isin(cand)].pivot_table(index='wk', columns='variant', values='net', aggfunc='sum').sort_index().fillna(0.0)[cand]
sr = W.mean() / W.std(ddof=1); r = W['full'].values; T_ = len(r); SR = sr['full']; g3 = pd.Series(r).skew(); g4 = pd.Series(r).kurt() + 3
def dsr(N):
    em = 0.5772156649; sr0 = np.sqrt(sr.drop('full').var(ddof=1)) * ((1 - em) * norm.ppf(1 - 1 / N) + em * norm.ppf(1 - 1 / (N * np.e)))
    return float(norm.cdf((SR - sr0) * np.sqrt(T_ - 1) / np.sqrt(1 - g3 * SR + (g4 - 1) / 4 * SR ** 2))), float(sr0)
N_counted = len(glob.glob(f'{PP}/var_*.csv')) + len(glob.glob(f'{OUT}/bt3_results/ablate_*_cycles.csv')) + 4
D_c, sr0_c = dsr(N_counted); D_1000, sr0_1000 = dsr(1000)
S_ = 16; blocks = np.array_split(np.arange(T_), S_); M = W.values; lam = []
for comb in itertools.combinations(range(S_), S_ // 2):
    isx = np.concatenate([blocks[i] for i in comb]); oos = np.concatenate([blocks[i] for i in range(S_) if i not in comb])
    a = M[isx]; b = M[oos]; s_is = a.mean(0) / a.std(0, ddof=1); s_oos = b.mean(0) / b.std(0, ddof=1); n_star = int(np.argmax(s_is)); w = (np.sum(s_oos < s_oos[n_star]) + 1) / (M.shape[1] + 1); lam.append(np.log(w / (1 - w)))
lam = np.array(lam); PBO = float((lam <= 0).mean()); np.savetxt(f'{PP}/pbo_logits.txt', lam)
# ---------------- B4 path and tail (weekly, both sizings)
def weekly(col): return E.groupby('wk')[col].sum().sort_index()
def path_stats(w):
    eq = w.cumsum(); dd = eq - eq.cummax(); mdd = float(-dd.min()); under = (dd < 0).astype(int); runs = under.groupby((under != under.shift()).cumsum()).cumsum(); longest = int(runs.max())
    x = w.values; n = len(x); res = []
    for _ in range(10000):
        idx = []; i = rng.integers(n)
        while len(idx) < 52:
            idx.append(i % n); i = rng.integers(n) if rng.random() < 0.25 else i + 1                       # stationary bootstrap, mean block 4 weeks
        y = x[idx]; e = np.cumsum(y); res.append((y.sum(), float(-(e - np.maximum.accumulate(np.concatenate([[0], e]))[1:]).min())))
    res = np.array(res)
    return dict(weeks=n, mean_week=float(x.mean()), sd_week=float(x.std(ddof=1)), sharpe_annual=float(x.mean() / x.std(ddof=1) * np.sqrt(52)), total=float(x.sum()), max_drawdown=mdd, longest_underwater_weeks=longest,
                one_year_pnl_median=float(np.median(res[:, 0])), one_year_pnl_p5=float(np.quantile(res[:, 0], .05)), one_year_mdd_p95=float(np.quantile(res[:, 1], .95)), p_loss_10=float((res[:, 0] < -0.1 * CAP).mean()), p_loss_20=float((res[:, 0] < -0.2 * CAP).mean()), p_loss_30=float((res[:, 0] < -0.3 * CAP).mean()), p_negative_year=float((res[:, 0] < 0).mean()))
PS = {k: path_stats(weekly(c)) for k, c in (('constant lot', 'net'), ('margin-capped', 'net_capped'))}; pd.DataFrame(PS).T.to_csv(f'{PP}/path.csv')
years = (pd.to_datetime(E.d0).max() - pd.to_datetime(E.d0).min()).days / 365.25; cyc_per_year = len(E) / years; funding = CAP * 0.065 / cyc_per_year
def headline(x, lab):
    w = x[x > 0].sum(); l = -x[x < 0].sum(); return dict(set=lab, cycles=len(x), mean_net=float(x.mean()), win_rate=float((x > 0).mean()), profit_factor=float(w / l) if l > 0 else np.inf, total=float(x.sum()), return_on_2cr_per_year=float(x.sum() / years / CAP))
H = pd.DataFrame([headline(E.net, 'all, constant lot'), headline(E[E.split == 'IS'].net, 'IS'), headline(E[E.split == 'OOS'].net, 'OOS'), headline(E[E.split == 'LIVE_FITTED'].net, 'live window'), headline(E.net_capped, 'all, margin-capped'), headline(E.net - funding, 'all, after funding cost (6.5%)')]); H.to_csv(f'{PP}/headline.csv', index=False)
TQ = pd.read_csv(f'{OUT}/unres/cycle_night_gaps.csv')[['und', 'expiry', 'gap_min_0916']]; WC = E.nsmallest(10, 'net')[['und', 'expiry', 'split', 'net', 'gross', 'iv_shock_2.0']].merge(full[['und', 'expiry', 'stop_j']], on=['und', 'expiry']).merge(TQ, on=['und', 'expiry']); WC.to_csv(f'{PP}/worst_cycles.csv', index=False)
cap = pd.read_csv(f'{PP}/capacity.csv'); c10 = float(cap[(cap['size'] == 1.0) & (cap.threshold == 0.10)].share_of_fill_units_at_or_below.iloc[0])
oos = E[E.split == 'OOS'].net.mean(); be = float(E.net_m0.mean() / (E.net_m0.mean() - E.net.mean()))
G = [dict(gate='G1 Costs', value=f"mean net ₹{base:,.0f} (all) / ₹{oos:,.0f} (OOS) / ₹{E['net_cost1.5_slip2'].mean():,.0f} (costs ×1.5, slippage ×2)", passed=bool(base > 0 and oos > 0 and E['net_cost1.5_slip2'].mean() > 0)),
     dict(gate='G2 Execution', value=f"mean net with 1-minute delay ₹{E.net_delay1.mean():,.0f}", passed=bool(E.net_delay1.mean() > 0)),
     dict(gate='G3 Parameter stability', value='no ±20% / ±5-min change flips or halves the mean' if not len(g3_fail) else '; '.join(f"{r.parameter} {r.level}: ₹{r.mean_net:,.0f} ({100 * r.change_pct:+.0f}%)" for r in g3_fail.itertuples()), passed=bool(len(g3_fail) == 0)),
     dict(gate='G4 Overfitting', value=f"PBO {PBO:.2f}; Deflated Sharpe {D_c:.2f} at N = {N_counted} ({D_1000:.2f} at N = 1,000)", passed=bool(PBO < 0.5 and D_c >= 0.95)),
     dict(gate='G5 Noise floor', value=f"real timetable ₹{base:,.0f} vs random-timetable null: 95th pct ₹{null_p95:,.0f}; real above {100 * null_pct:.0f}% of 20 null runs", passed=bool(base > null_p95)),
     dict(gate='G6 Path / tail', value=f"1-year 95th-pct max drawdown ₹{PS['constant lot']['one_year_mdd_p95'] / 1e5:,.1f} lakh; P(1-year loss > 10%) {100 * PS['constant lot']['p_loss_10']:.1f}%", passed=bool(PS['constant lot']['one_year_mdd_p95'] < 0.2 * CAP and PS['constant lot']['p_loss_10'] < 0.10)),
     dict(gate='G7 Capacity', value=f"{100 * c10:.1f}% of fill volume at ≤ 10% of minute volume", passed=bool(c10 >= 0.90)),
     dict(gate='G8 Margin-capped book', value=f"mean net ₹{E.net_capped.mean():,.0f}; {100 * (E.peak_margin_capped > CAP).mean():.1f}% of cycles still above ₹2 crore", passed=bool(E.net_capped.mean() > 0 and (E.peak_margin_capped > CAP).mean() <= 0.05))]
GT = pd.DataFrame(G); GT.to_csv(f'{PP}/gates.csv', index=False)
summ = dict(base=float(base), oos=float(oos), breakeven_mult=be, funding_per_cycle=float(funding), cycles_per_year=float(cyc_per_year), PBO=PBO, DSR_counted=D_c, DSR_1000=D_1000, N_counted=N_counted, SR_week=float(SR), sr0_counted=sr0_c, null_pct=null_pct, null_p95=null_p95, null_mean=float(nulls.mean()), null_min=float(nulls.min()), null_max=float(nulls.max()),
            g3_failures=int(len(g3_fail)), gates_passed=int(GT.passed.sum()), verdict='GO' if GT.passed.all() else 'NO-GO', path=PS, capacity_10=c10, iv_shock={k: dict(mean=float(E[k].mean()), p95=float(E[k].quantile(.95)), worst=float(E[k].max())) for k in ('iv_shock_1.5', 'iv_shock_2.0')})
json.dump(summ, open(f'{PP}/pp_summary.json', 'w'), indent=1, default=float)
pd.set_option('display.width', 250); pd.set_option('display.max_colwidth', 140); print(GT.to_string()); print(H.round(3).to_string()); print(PT.sort_values(['parameter', 'level']).round(3).to_string()); print(json.dumps({k: v for k, v in summ.items() if k != 'path'}, indent=0, default=float)[:1500]); print(pd.DataFrame(PS).round(0).to_string()); print(WC.round(0).to_string())
# ---------------- eras (cost and market-structure regimes; descriptive)
ER = []
for lab, lo, hi in (('Nov 2023 – Sep 2024 (STT 0.0625%, NSE fee 0.0495%)', '2000-01-01', '2024-10-01'), ('Oct 2024 – Mar 2026 (STT 0.1%)', '2024-10-01', '2026-04-01'), ('Apr – 2 Aug 2026 (STT 0.15%)', '2026-04-01', '2026-08-03'), ('from 3 Aug 2026 (STT 0.15% + closing auction)', '2026-08-03', '2100-01-01')):
    g = E[(E.d0 >= lo) & (E.d0 < hi)]
    if len(g): x = g.net; ER.append(dict(era=lab, cycles=len(g), mean_net=float(x.mean()), mean_gross=float(g.gross.mean()), costs_share_of_gross=float((g.gross - g.net).sum() / g.gross.sum()) if g.gross.sum() > 0 else np.nan, win_rate=float((x > 0).mean()), after_funding=float(x.mean() - funding)))
ER = pd.DataFrame(ER); ER.to_csv(f'{PP}/eras.csv', index=False); print(ER.round(3).to_string())
wk = E.groupby('wk').net.sum().sort_index(); y = wk.values; x = np.arange(len(y), dtype=float); X = np.column_stack([np.ones_like(x), x]); b = np.linalg.lstsq(X, y, rcond=None)[0]; u = y - X @ b
XtXi = np.linalg.inv(X.T @ X); Sg = (X * u[:, None]).T @ (X * u[:, None])
for L in range(1, 5): w_ = 1 - L / 5; G_ = (X[L:] * u[L:, None]).T @ (X[:-L] * u[:-L, None]); Sg += w_ * (G_ + G_.T)                                     # Newey-West, 4 lags
se = np.sqrt(np.diag(XtXi @ Sg @ XtXi)); t_ = b[1] / se[1]; json.dump(dict(slope_per_week=float(b[1]), slope_t=float(t_), slope_p=float(2 * (1 - norm.cdf(abs(t_))))), open(f'{PP}/trend.json', 'w'), indent=1); print('weekly trend (Rs per week per week)', round(b[1]), 't', round(t_, 2))
