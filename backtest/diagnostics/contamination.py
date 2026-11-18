"""Contamination / representativeness: exposed vs clean OOS, bootstrap CIs, distribution comparisons. Nothing here is used to tune anything."""
import json, math
from scipy import stats
from common import *
rng = np.random.default_rng(11)
d = cycles('HOLD', 'HOLD_SETTLE'); fz = cycles('cut_t20000_f10000_re_cd1800band', 'HOLD_SETTLE'); F = pd.read_csv(f'{RES}/regime_features_cycles.csv')
rows = []
for lab, t in (('HOLD', d), ('FROZEN', fz)):
    for p in ('IS', 'OOS', 'OOS_exposed', 'OOS_clean', 'OOS_clean_before', 'OOS_clean_after'):
        x = part(t, p); r = x.net.values; bs = [r[rng.integers(0, len(r), len(r))].mean() for _ in range(10000)]
        rows.append(dict(config=lab, part=p, cycles=len(r), net=r.sum(), mean=r.mean(), mean_ci95_lo=np.percentile(bs, 2.5), mean_ci95_hi=np.percentile(bs, 97.5), sharpe=M.summarize(x)['sharpe'], p_mean_le_0=float(np.mean(np.array(bs) <= 0)), win_rate=(r > 0).mean()))
C_ = pd.DataFrame(rows); C_.to_csv(f'{RES}/contamination_tables.csv', index=False); pd.set_option('display.width', 250); print(C_.round(3).to_string(index=False))
# permutation: exposed mean vs clean mean (HOLD)
a = part(d, 'OOS_exposed').net.values; b = part(d, 'OOS_clean').net.values; obs = a.mean() - b.mean(); allv = np.r_[a, b]; sims = []
for _ in range(20000): rng.shuffle(allv); sims.append(allv[:len(a)].mean() - allv[len(a):].mean())
print('exposed-minus-clean mean/cycle', obs, 'perm p(two-sided)', float((np.abs(sims) >= abs(obs)).mean()))
# representativeness: exposed vs IS vs clean, KS tests on market descriptors, per index
rep = []
for u in ('NIFTY', 'SENSEX'):
    for ft in ('abs_move_pct', 'prem_pct_spot', 'rv5_pct', 'd0_range_pct', 'premium_over_absmove'):
        i = F[(F.und == u) & (F.split == 'IS')][ft].dropna(); e = F[(F.und == u) & (F.subset == 'OOS_EXPOSED')][ft].dropna(); c = F[(F.und == u) & (F.subset.isin(['OOS_CLEAN_BEFORE', 'OOS_CLEAN_AFTER']))][ft].dropna()
        rep.append(dict(und=u, feature=ft, IS_mean=i.mean(), exposed_mean=e.mean(), clean_mean=c.mean(), ks_p_exposed_vs_IS=stats.ks_2samp(e, i).pvalue, ks_p_clean_vs_IS=stats.ks_2samp(c, i).pvalue, ks_p_exposed_vs_clean=stats.ks_2samp(e, c).pvalue))
Rp = pd.DataFrame(rep); Rp.to_csv(f'{RES}/representativeness.csv', index=False); print(Rp.round(3).to_string(index=False))
# time-sliced OOS net (quarterly by D0) to show where P&L sits
d['q'] = pd.to_datetime(d.d0).dt.to_period('Q').astype(str); q = d[d.split == 'OOS'].groupby(['q', 'und']).net.agg(['count', 'sum']).unstack().fillna(0); q.to_csv(f'{RES}/oos_quarterly_net.csv'); print(q.round(0))
