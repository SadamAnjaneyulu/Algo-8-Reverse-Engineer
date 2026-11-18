"""Return distribution + recomputation of the user's starting figures (HOLD_SETTLE baseline, base costs)."""
import json, math
from scipy import stats
from common import *
d = cycles('HOLD', 'HOLD_SETTLE'); d['expiry'] = pd.to_datetime(d.expiry)
fz = json.load(open(os.path.join(BT, 'FROZEN_CONFIG.json')))
print('frozen keys', list(fz)[:12])
rows = []; 
def dist(x, label):
    r = x.net.values; n = len(r); top = lambda k, asc=False: float(np.sort(r)[::-1][:k].sum()) if not asc else float(np.sort(r)[:k].sum())
    tot = r.sum(); w = x.groupby('wk').net.sum()
    eq = np.cumsum(x.sort_values('d0').net.values); peak = np.maximum.accumulate(np.r_[0, eq])[1:]; dd = eq - peak
    # longest consecutive losing-cycle run (chronological, per index and combined by expiry date)
    s = (x.sort_values(['d0', 'und']).net.values < 0).astype(int); run = best = 0
    for v in s: run = run + 1 if v else 0; best = max(best, run)
    # drawdown duration in cycles
    dur = mx = 0
    for v in dd: dur = dur + 1 if v < 0 else 0; mx = max(mx, dur)
    return dict(sample=label, cycles=n, total_net=tot, mean=r.mean(), median=float(np.median(r)), std=r.std(ddof=1), pct_pos=(r > 0).mean(), pct_neg=(r < 0).mean(), pct_zero=(r == 0).mean(),
                best=r.max(), worst=r.min(), skew=float(stats.skew(r)), excess_kurt=float(stats.kurtosis(r)), top1=top(1), top5=top(5), top10=top(10), bot5=top(5, True), bot10=top(10, True),
                top5_share_of_total=top(5) / tot if tot else float('nan'), top10_share_of_total=top(10) / tot if tot else float('nan'), total_ex_top5=tot - top(5), total_ex_top10=tot - top(10),
                mean_win=r[r > 0].mean(), mean_loss=r[r < 0].mean(), payoff_ratio=-r[r > 0].mean() / r[r < 0].mean(), max_consec_losing_cycles=best, max_dd_rs_cycle_path=float(dd.min()), longest_dd_cycles=mx,
                median_to_mean=float(np.median(r) / r.mean()) if r.mean() else float('nan'), t_mean=float(r.mean() / (r.std(ddof=1) / math.sqrt(n))))
for p in ('IS', 'OOS', 'OOS_exposed', 'OOS_clean', 'OOS_clean_before', 'OOS_clean_after'):
    for u in ('COMBINED', 'NIFTY', 'SENSEX'):
        x = part(d, p, u)
        if len(x) > 3: rows.append(dict(dist(x, f'{p}|{u}'), part=p, scope=u))
D = pd.DataFrame(rows); D.to_csv(f'{RES}/return_distribution.csv', index=False)
# ranked cycle table (all cycles, ranked by net, with subset tag)
rk = d[['und', 'expiry', 'split', 'subset', 'gross', 'net', 'slippage', 'costs']].sort_values('net', ascending=False).reset_index(drop=True); rk.index += 1; rk.index.name = 'rank_all'
rk.to_csv(f'{RES}/ranked_cycles_all.csv')
for p in ('IS', 'OOS', 'OOS_clean'):
    x = part(d, p)[['und', 'expiry', 'subset', 'gross', 'net']].sort_values('net', ascending=False).reset_index(drop=True); x.index += 1; x.to_csv(f'{RES}/ranked_cycles_{p}.csv')
# leave-k-out on OOS (remove the k best cycles) -- diagnostic only
o = part(d, 'OOS').sort_values('net', ascending=False); lk = []
for k in range(0, 11): 
    y = o.iloc[k:]; w = y.groupby('wk').net.sum(); lk.append(dict(removed_best=k, oos_net=y.net.sum(), sharpe_weekly=w.mean() / w.std(ddof=1) * math.sqrt(52) / (1) if len(w) > 2 else None))
pd.DataFrame(lk).to_csv(f'{RES}/oos_leave_best_out.csv', index=False)
# permutation test for mean/cycle (sign-flip) - tests H0: symmetric around 0
rng = np.random.default_rng(7); pt = []
for p in ('IS', 'OOS', 'OOS_clean', 'OOS_exposed'):
    r = part(d, p).net.values; obs = r.mean(); sims = np.array([(r * rng.choice([-1, 1], len(r))).mean() for _ in range(20000)]); pt.append(dict(part=p, mean=obs, p_signflip_1sided=float((sims >= obs).mean())))
pd.DataFrame(pt).to_csv(f'{RES}/signflip_tests.csv', index=False)
# monthly stats (calendar month of D0, combined)
d['month'] = pd.to_datetime(d.d0).dt.strftime('%Y-%m'); mo = d.groupby(['split', 'month']).net.sum().reset_index(); mo.to_csv(f'{RES}/monthly_net.csv', index=False)
ms = []
for p in ('IS', 'OOS'):
    m = mo[mo.split == p].net; ms.append(dict(part=p, months=len(m), mean=m.mean(), median=m.median(), std=m.std(ddof=1), pct_pos=(m > 0).mean(), best=m.max(), worst=m.min(), sharpe_monthly_ann=m.mean() / m.std(ddof=1) * math.sqrt(12) / 1.0))
ms = pd.DataFrame(ms); ms.to_csv(f'{RES}/monthly_stats.csv', index=False)
# the user's starting figures: recompute from artifacts
def tot(p): return float(part(d, p).net.sum())
start = dict(IS_net=tot('IS'), OOS_net=tot('OOS'), clean_OOS_net=tot('OOS_clean'), exposed_net=tot('OOS_exposed'), exposed_cycles=int(len(part(d, 'OOS_exposed'))), uninspected_cycles=int(len(part(d, 'OOS_clean'))),
             sharpe_IS=M.summarize(part(d, 'IS'))['sharpe'], sharpe_OOS=M.summarize(part(d, 'OOS'))['sharpe'], sharpe_clean=M.summarize(part(d, 'OOS_clean'))['sharpe'],
             oos_ex_best5=float(part(d, 'OOS').net.nlargest(5).pipe(lambda s: part(d, 'OOS').net.sum() - s.sum())),
             exposed_share_of_oos=tot('OOS_exposed') / tot('OOS'))
d2 = cycles('cut_t20000_f10000_re_cd1800band', 'HOLD_SETTLE'); start['frozen_full_OOS'] = float(part(d2, 'OOS').net.sum()); start['frozen_clean_OOS'] = float(part(d2, 'OOS_clean').net.sum())
d3 = cycles('HOLD', 'FLATTEN_1525'); start['flatten_full_OOS'] = float(part(d3, 'OOS').net.sum()); start['flatten_clean_OOS'] = float(part(d3, 'OOS_clean').net.sum()); start['flatten_IS'] = float(part(d3, 'IS').net.sum())
json.dump(start, open(f'{RES}/starting_figures_recomputed.json', 'w'), indent=1)
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
print(json.dumps(start, indent=1)); print(D[D.scope == 'COMBINED'].set_index('sample').T.round(3).to_string()); print(pd.DataFrame(lk).round(1)); print(pd.DataFrame(pt)); print(ms.round(2))
print(D[D.scope != 'COMBINED'][['sample', 'cycles', 'total_net', 'mean', 'median', 'pct_pos', 'top5', 'top5_share_of_total', 'skew']].round(3).to_string())
