"""Plan reports/UNRESOLVED_THREE_PLAN.md, M2 statistics, G1 tables, G2 tail model, G3 break-even and expected benefit of the long legs.
Inputs outputs/unres/*.csv, repo daily NIFTY / SENSEX files (data_validation/reference), outputs/bt3_results/ablate_diffs.csv. Outputs outputs/unres/{margin_stats,gap_tables,evt_fit,ev_table}.csv and unres_gap_summary.json."""
import sys, os, json, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from scipy.optimize import minimize
OUT = os.path.join(os.path.dirname(os.path.abspath('.')), 'outputs'); UN = f'{OUT}/unres'; REF = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(OUT)))), 'data_validation', 'reference'); B = 2000; CAP = 2e7
C = pd.read_csv(f'{UN}/real_margin_cycles.csv'); G = pd.read_csv(f'{UN}/gap_stress.csv'); rng = np.random.default_rng(20261124)
# ---------------- M2: real vs simulated margin on the same cycles
r = C[C.book == 'real'].set_index(['und', 'expiry']); s = C[C.book == 'sim_full'].set_index(['und', 'expiry']).loc[r.index]; wk = pd.to_datetime(pd.Series(r.index.get_level_values(1))).dt.strftime('%G-%V').values
def boot(f, n=B):
    w = np.unique(wk); out = []
    for _ in range(n):
        pick = np.concatenate([np.where(wk == k)[0] for k in rng.choice(w, len(w))]); out.append(f(pick))
    return np.nanquantile(out, [.025, .975])
rp, sp = r.peak_nse.values, s.peak_nse.values
M = pd.DataFrame([dict(stat='real peak margin, median (₹ crore)', value=np.median(rp) / 1e7, lo=boot(lambda i: np.median(rp[i]) / 1e7)[0], hi=boot(lambda i: np.median(rp[i]) / 1e7)[1]),
                  dict(stat='real cycles with peak margin > ₹2 crore', value=(rp > CAP).mean(), lo=boot(lambda i: (rp[i] > CAP).mean())[0], hi=boot(lambda i: (rp[i] > CAP).mean())[1]),
                  dict(stat='simulator, same cycles: peak margin median (₹ crore)', value=np.median(sp) / 1e7, lo=np.nan, hi=np.nan),
                  dict(stat='simulator, same cycles: share of cycles > ₹2 crore', value=(sp > CAP).mean(), lo=np.nan, hi=np.nan),
                  dict(stat='Spearman real vs simulator peak margin', value=pd.Series(rp).corr(pd.Series(sp), method='spearman'), lo=boot(lambda i: pd.Series(rp[i]).corr(pd.Series(sp[i]), method='spearman'))[0], hi=boot(lambda i: pd.Series(rp[i]).corr(pd.Series(sp[i]), method='spearman'))[1]),
                  dict(stat='ratio of medians real / simulator', value=np.median(rp) / np.median(sp), lo=np.nan, hi=np.nan),
                  dict(stat='real overnight (D-1 close) margin, median (₹ crore)', value=r.margin_d1_close.median() / 1e7, lo=np.nan, hi=np.nan), dict(stat='real: peak short units, median', value=r.peak_short_units.median(), lo=np.nan, hi=np.nan)])
M.to_csv(f'{UN}/margin_stats.csv', index=False)
# ---------------- G1: stress tables
T = G.groupby(['book', 'gap', 'vm']).loss.agg(books='size', mean='mean', median='median', p95=lambda x: x.quantile(.95), worst='max', best='min', share_over_2cr=lambda x: (x > CAP).mean()).reset_index(); T.to_csv(f'{UN}/gap_tables.csv', index=False)
# ---------------- G2: gaps from the repo's daily files, GPD fit
def gaps(f):
    d = pd.read_csv(f'{REF}/{f}', parse_dates=['date_ist']).sort_values('date_ist'); d = d[(d.open > 0) & (d.close > 0)]; return pd.Series(np.log(d.open.values[1:] / d.close.values[:-1]), index=d.date_ist.values[1:])
GN = gaps('yahoo_daily_NSEI.csv'); GS = gaps('yahoo_daily_BSESN.csv')
def gpd_fit(x, u, bounds=((-0.5, 1.0), (1e-6, None))):
    e = x[x > u] - u
    def nll(p):
        xi, b = p
        if b <= 0: return 1e12
        z = 1 + xi * e / b
        if (z <= 0).any(): return 1e12
        return len(e) * np.log(b) + (1 + 1 / xi) * np.log(z).sum() if abs(xi) > 1e-6 else len(e) * np.log(b) + e.sum() / b
    best = min((minimize(nll, [x0, e.mean()], bounds=bounds, method='L-BFGS-B') for x0 in (0.1, 0.0, 0.3)), key=lambda r_: r_.fun); return best.x[0], best.x[1], len(e)
def tail_prob(x, xi, b, u, nu, n): return (nu / n) * (1 + xi * (x - u) / b) ** (-1 / xi) if abs(xi) > 1e-6 else (nu / n) * np.exp(-(x - u) / b)
XS = [0.03, 0.05, 0.07, 0.10]; rows = []; fits = {}
for nm, g in (('NIFTY', GN), ('SENSEX', GS)):
    a = g.abs().values; n = len(a); u = np.quantile(a, .95); xi, b, nu = gpd_fit(a, u); fits[nm] = (xi, b, u, nu, n)
    bs = []
    for _ in range(B):
        xb = rng.choice(a, n); ub = np.quantile(xb, .95); xib, bb, nub = gpd_fit(xb, ub); bs.append([xib] + [tail_prob(x, xib, bb, ub, nub, n) for x in XS])
    bs = np.array(bs)
    rows.append(dict(index=nm, nights=n, max_abs_gap=a.max(), q99=np.quantile(a, .99), threshold_u=u, exceedances=nu, shape=xi, scale=b, shape_lo=np.nanquantile(bs[:, 0], .025), shape_hi=np.nanquantile(bs[:, 0], .975),
                     **{f'P(|gap|>={int(100 * x)}%)': tail_prob(x, xi, b, u, nu, n) for x in XS}, **{f'P{int(100 * x)}_lo': np.nanquantile(bs[:, 1 + k], .025) for k, x in enumerate(XS)}, **{f'P{int(100 * x)}_hi': np.nanquantile(bs[:, 1 + k], .975) for k, x in enumerate(XS)},
                     **{f'P(|gap|>={int(100 * x)}%) shape0': tail_prob(x, 0.0, a[a > u].mean() - u, u, nu, n) for x in XS}, **{f'P(|gap|>={int(100 * x)}%) shape0.3': tail_prob(x, 0.3, b, u, nu, n) for x in XS}))
E = pd.DataFrame(rows); E.to_csv(f'{UN}/evt_fit.csv', index=False)
# ---------------- G3: expected benefit of the long legs (curve pinned to 0 at no gap; volatility shock grows with the gap)
cost = float(pd.read_csv(f'{OUT}/bt3_results/ablate_diffs.csv').set_index('variant').loc['d1_no_wings', 'net_k_diff']); grid = sorted(set(G.gap)); VM = [1.0, 1.5, 2.0]
RULES = {'no vol shock': lambda g: 1.0, 'base: 1 + 10|gap| (cap 2)': lambda g: min(1 + 10 * abs(g), 2.0), 'high: 1 + 20|gap| (cap 2)': lambda g: min(1 + 20 * abs(g), 2.0)}
def D_curve(book_full, book_no, rule):
    L = {vm: (G[(G.book == book_no) & (G.vm == vm)].groupby('gap').loss.mean() - G[(G.book == book_full) & (G.vm == vm)].groupby('gap').loss.mean()) for vm in VM}
    ys = {g: float(np.interp(rule(g), VM, [L[vm].loc[g] for vm in VM])) for g in grid}; xs = [-0.25] + [g for g in grid if g < 0] + [0.0] + [g for g in grid if g > 0] + [0.25]
    yv = [ys[[g for g in grid if g < 0][0]]] + [ys[g] for g in grid if g < 0] + [0.0] + [ys[g] for g in grid if g > 0] + [ys[[g for g in grid if g > 0][-1]]]
    return lambda g: np.interp(np.asarray(g, float), xs, yv)
DOC = np.array([6.95, 5.69, 6.11, 12.24, 7.87, 6.77, 8.70, 5.94, 5.66, 6.65, 5.96, 12.20, 6.66, 6.18, 5.84, 5.92, 8.30, 7.61, 5.56, 12.98, 5.74]) / 100        # published falls 2000-2022 (the 2024 event lies inside the 3-year sample and is excluded here)
N_DOC = int(23.7 * 252); gN = GN.values; aN = np.abs(gN); xi0, b0, u0, nu0, n0 = fits['NIFTY']; ev = []; tail_grid = np.linspace(u0, 0.25, 3000)
def ev_gpd_from(Dc, g_s, xi, b, u, nu, n):
    a = np.abs(g_s); body = g_s[a <= u]; sf = tail_prob(tail_grid, xi, b, u, nu, n); pm = np.maximum(-np.diff(sf), 0); mid = 0.5 * (tail_grid[1:] + tail_grid[:-1]); Ds = 0.5 * (Dc(mid) + Dc(-mid)); return float(np.sum(Dc(body)) / n + np.sum(pm * Ds))
for book_f, book_n, lab in (('sim_full', 'sim_d1_no_wings', 'simulated books'), ('real', 'real_no_longs', 'real books')):
    for rn, rule in RULES.items():
        Dc = D_curve(book_f, book_n, rule); emp = float(np.mean(Dc(gN))); gp = ev_gpd_from(Dc, gN, xi0, b0, u0, nu0, n0)
        bsE = []; bsG = []
        for _ in range(300):
            gb = rng.choice(gN, len(gN)); ab = np.abs(gb); ub = np.quantile(ab, .95); xib, bb, nub = gpd_fit(ab, ub); bsE.append(float(np.mean(Dc(gb)))); bsG.append(ev_gpd_from(Dc, gb, xib, bb, ub, nub, len(gb)))
        docs = {phi: float(np.sum(Dc(-phi * DOC))) / N_DOC for phi in (1.0, 0.5)}
        ev.append(dict(books=lab, vol_shock=rn, net_cost_of_longs_in_sample=cost, ev_in_sample_nights=emp, ev_in_sample_lo=np.quantile(bsE, .025), ev_in_sample_hi=np.quantile(bsE, .975), ev_gpd=gp, ev_gpd_lo=np.nanquantile(bsG, .025), ev_gpd_hi=np.nanquantile(bsG, .975),
                       ev_gpd_extra_beyond_sample=gp - emp, ev_documented_extra_phi1=docs[1.0], ev_documented_extra_phi05=docs[0.5], **{f'D({int(100 * x)}%)_down': float(Dc(-x)) for x in (0.01, 0.02, 0.03, 0.05, 0.07, 0.10, 0.13)}, **{f'breakeven_prob_{int(100 * x)}%': cost / float(0.5 * (Dc(x) + Dc(-x))) for x in (0.03, 0.05, 0.07, 0.10, 0.13)}))
EV = pd.DataFrame(ev); EV.to_csv(f'{UN}/ev_table.csv', index=False)
doc_p = len(DOC) / N_DOC; json.dump(dict(doc_events=len(DOC), doc_nights=N_DOC, doc_prob_per_night=doc_p, max_gap_daily_nifty=float(GN.abs().max()), max_gap_daily_sensex=float(GS.abs().max()), real_peak_median_cr=float(np.median(rp) / 1e7), real_over_2cr=float((rp > CAP).mean()),
               spearman=float(pd.Series(rp).corr(pd.Series(sp), method='spearman')), cost=cost), open(f'{UN}/unres_gap_summary.json', 'w'), indent=1)
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
print(M.round(3).to_string()); print(E.T.round(5).to_string()); pd.set_option('display.float_format', lambda v: f'{v:,.4f}' if abs(v) < 1 else f'{v:,.0f}'); print(EV.T.to_string())
print(T[(T.vm == 1.5) & (T.gap.isin([-0.15, -0.10, -0.05, -0.03, 0.03, 0.05, 0.10, 0.15]))][['book', 'gap', 'books', 'mean', 'p95', 'worst', 'best', 'share_over_2cr']].round(-3).to_string())
print(T[(T.vm == 2.0) & (T.gap.isin([-0.13, 0.13, -0.15, 0.15]))][['book', 'gap', 'mean', 'p95', 'worst', 'share_over_2cr']].round(-3).to_string())
