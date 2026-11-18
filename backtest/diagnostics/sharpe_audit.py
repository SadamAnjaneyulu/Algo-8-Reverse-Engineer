"""Sharpe audit: reproduces the reported figures, then recomputes Sharpe on explicitly defined portfolio-level series."""
import json, math
from common import *
rng = np.random.default_rng(20261119)


def weekly_series(d, col='net', fill_calendar=False):
    w = d.groupby('wk')[col].sum()
    if fill_calendar:                                         # idle ISO weeks inside the sample become zero-P&L weeks
        a, b = pd.Timestamp(d.d1.min()), pd.Timestamp(d.d0.max()); allw = pd.Series(0.0, index=sorted({x.strftime('%G-W%V') for x in pd.date_range(a, b, freq='D')})); w = (allw + w).fillna(allw)
        w = allw.copy(); w.update(d.groupby('wk')[col].sum())
    return w


def sharpe(r, k):
    r = np.asarray(r, float); return float(r.mean() / r.std(ddof=1) * math.sqrt(k)) if len(r) > 2 and r.std(ddof=1) > 0 else float('nan')


def boot_ci(r, k, n=10000, block=1):
    r = np.asarray(r, float); L = len(r); out = []
    for _ in range(n):
        if block == 1: s = r[rng.integers(0, L, L)]
        else:
            nb = int(math.ceil(L / block)); st = rng.integers(0, L - block + 1, nb); s = np.concatenate([r[i:i + block] for i in st])[:L]
        out.append(sharpe(s, k))
    return tuple(np.nanpercentile(out, [2.5, 97.5]))


def lo_se(sr_period, n): return math.sqrt((1 + 0.5 * sr_period ** 2) / n)          # Lo (2002) i.i.d. standard error of a per-period Sharpe


def daily_pnl(d):
    """business-day P&L from the minute-level equity path (idle days are zero)"""
    inc = []
    for r in d.itertuples():
        prev = 0.0
        for t, v in r.path: inc.append((pd.Timestamp(t + 19800, unit='s').normalize(), v - prev)); prev = v
    s = pd.Series(dict()) if not inc else pd.DataFrame(inc, columns=['day', 'inc']).groupby('day').inc.sum()
    a, b = pd.Timestamp(d.d1.min()), pd.Timestamp(d.d0.max()); idx = pd.bdate_range(a, b); return s.reindex(idx).fillna(0.0)


rows = []; detail = {}
for variant, name in (('HOLD_SETTLE', 'HOLD'), ('HOLD_SETTLE', 'cut_t20000_f10000_re_cd1800band'), ('FLATTEN_1525', 'HOLD')):
    d = cycles(name, variant)
    for p in ('IS', 'OOS', 'OOS_exposed', 'OOS_clean'):
        for und in ('COMBINED', 'NIFTY', 'SENSEX'):
            x = part(d, p, und)
            if len(x) < 4: continue
            w = weekly_series(x); wz = weekly_series(x, fill_calendar=True); wg = weekly_series(x, 'gross'); dd = daily_pnl(x)
            rep = M.summarize(x)['sharpe']                                                                      # the figure originally reported
            k = 52; lo, hi = boot_ci(w.values / CAP, k, 4000, block=4)
            rows.append(dict(variant=variant, config=name, period=p, scope=und, cycles=len(x), weeks_traded=len(w), weeks_in_calendar_span=len(wz), reported_sharpe=rep, weekly_traded_only=sharpe(w / CAP, k), weekly_idle_weeks_as_zero=sharpe(wz / CAP, k),
                             daily_bdays_idle_zero=sharpe(dd / CAP, 252), gross_weekly_traded_only=sharpe(wg / CAP, k), weekly_sharpe_ci95_lo=lo, weekly_sharpe_ci95_hi=hi, lo_se_annual=lo_se(sharpe(w / CAP, 1), len(w)) * math.sqrt(k),
                             denominator_check_Rs10M=sharpe(w / 1e7, k), mean_week_rs=w.mean(), sd_week_rs=w.std(ddof=1), t_stat_mean=w.mean() / (w.std(ddof=1) / math.sqrt(len(w)))))
T = pd.DataFrame(rows); T.to_csv(f'{RES}/sharpe_audit.csv', index=False)
# difference test: IS vs OOS vs clean weekly P&L (Welch + bootstrap of the Sharpe difference)
d = cycles('HOLD', 'HOLD_SETTLE'); wi = weekly_series(part(d, 'IS')) / CAP; wo = weekly_series(part(d, 'OOS')) / CAP; wc = weekly_series(part(d, 'OOS_clean')) / CAP
diff = []
for _ in range(10000): diff.append(sharpe(wi.values[rng.integers(0, len(wi), len(wi))], 52) - sharpe(wo.values[rng.integers(0, len(wo), len(wo))], 52))
dc = [sharpe(wo.values[rng.integers(0, len(wo), len(wo))], 52) - sharpe(wc.values[rng.integers(0, len(wc), len(wc))], 52) for _ in range(10000)]
out = dict(IS_minus_OOS_sharpe_diff=float(sharpe(wi, 52) - sharpe(wo, 52)), IS_minus_OOS_ci95=[float(x) for x in np.percentile(diff, [2.5, 97.5])], P_IS_le_OOS=float(np.mean(np.array(diff) <= 0)),
           weeks=dict(IS=len(wi), OOS=len(wo), clean=len(wc)), mean_weekly_rs=dict(IS=float(wi.mean() * CAP), OOS=float(wo.mean() * CAP), clean=float(wc.mean() * CAP)), sd_weekly_rs=dict(IS=float(wi.std() * CAP), OOS=float(wo.std() * CAP), clean=float(wc.std() * CAP)))
# decomposition of the IS -> OOS fall: mean vs volatility
out['decomposition'] = dict(sharpe_IS=sharpe(wi, 52), sharpe_OOS=sharpe(wo, 52), sharpe_OOS_with_IS_mean=float(wi.mean() / wo.std(ddof=1) * math.sqrt(52)), sharpe_OOS_with_IS_sd=float(wo.mean() / wi.std(ddof=1) * math.sqrt(52)))
json.dump(out, open(f'{RES}/sharpe_comparison.json', 'w'), indent=1)
pd.set_option('display.width', 250); print(T[(T.config == 'HOLD') & (T.variant == 'HOLD_SETTLE')][['period', 'scope', 'cycles', 'weeks_traded', 'reported_sharpe', 'weekly_traded_only', 'weekly_idle_weeks_as_zero', 'daily_bdays_idle_zero', 'weekly_sharpe_ci95_lo', 'weekly_sharpe_ci95_hi', 'lo_se_annual', 'denominator_check_Rs10M']].round(2).to_string(index=False)); print(json.dumps(out, indent=1))
