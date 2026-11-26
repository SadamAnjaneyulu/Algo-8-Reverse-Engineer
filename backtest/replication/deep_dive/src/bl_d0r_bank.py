"""D0 scheduler structure, step 3 (plan reports/D0_SCHED_RULE_PLAN.md): robustness of T1 to the timer-cost setting, timer FAMILIES (period, second-offset class) across groups and days,
credibility pruning (a timer counts as credible if it has >= 4 members or its family appears in >= 2 group-days), coverage of the clock times by the credible timers only.
Outputs bl_d0r_robust.csv, bl_d0r_families.csv, bl_d0r_prune.csv, bl_summary_d0r2.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
import bl_d0r_ilp as I
src = open('bl_d0r_val.py').read(); exec(src[:src.index('rows = []; TM = []')])
# ---------------- robustness of T1 to mu (and tolerance)
def timers_mu(t, mu, tol=2.0):
    ch, alive = I.solve(t, mu=mu, tol=tol); out = []
    for P, ix in ch: tt = np.sort(t[ix]); out.append(dict(P=P, t0=float(tt[0]), n=len(ix), last=float(tt[-1]), sec=float(np.median(tt % 60)), phase=float(np.median((tt - np.arange(len(tt)) * P)))))
    return out, alive
rb = []
for mu, tol in ((1.5, 2.0), (2.5, 2.0), (3.5, 2.0), (1.5, 3.0), (1.5, 1.0)):
    TOL = tol
    for day in ('D-1', 'D0'):
        for u, v in GR:
            t = times(day, u, v)
            if len(t) < 12: continue
            te = t[t < 43200.0]; tg = t[t >= 43200.0]; tms, _ = timers_mu(te, mu, tol)
            if not tms: rb.append(dict(mu=mu, tol=tol, day=day, group=f'{u} {v}', timers=0, real=0.0, null_mean=np.nan, null_p95=np.nan, above=False)); continue
            pr = np.concatenate([predict(x, k_more=6) for x in tms]); pr = pr[pr >= 43200.0]; real = cover(tg, pr); nl = null_cover(tg, tms, lambda s: predict(s, k_more=6), draws=300)
            rb.append(dict(mu=mu, tol=tol, day=day, group=f'{u} {v}', timers=len(tms), real=real, null_mean=nl.mean(), null_p95=np.percentile(nl, 95), above=bool(real > np.percentile(nl, 95))))
TOL = 2.0; RB = pd.DataFrame(rb); RB.to_csv(f'{OUT}/bl_d0r_robust.csv', index=False); print(RB.round(3).to_string(index=False)); print('T1 above null p95:', RB.above.sum(), 'of', len(RB))
# ---------------- families
TM = pd.read_csv(f'{OUT}/bl_d0r_timers.csv'); TM['gd'] = TM.day + ' ' + TM.und + ' ' + TM.version
def off_class(s):
    s = s % 60; d0 = min(s, 60 - s)
    if d0 <= 2.6: return ':00'
    for lo, hi, lab in ((3.5, 7.5, ':04-06'), (8.5, 11.0, ':09-10'), (26.5, 28.9, ':27-28'), (29.5, 32.0, ':30-31')):
        if lo <= s <= hi: return lab
    return f':{int(round(s)):02d}'
TM['offset'] = [off_class(s) for s in TM.sec]; TM['family'] = [f'every {p} min @ {o}' for p, o in zip(TM.period_min, TM.offset)]
fam = TM.groupby('family').agg(period_min=('period_min', 'first'), offset=('offset', 'first'), timers=('n', 'size'), group_days=('gd', 'nunique'), members=('n', 'sum'), groups=('gd', lambda s: ', '.join(sorted(set(s))))).reset_index().sort_values(['group_days', 'timers'], ascending=False)
fam.to_csv(f'{OUT}/bl_d0r_families.csv', index=False); print(fam[['family', 'timers', 'group_days', 'members']].to_string(index=False))
FAMN = fam.set_index('family').group_days; TM['credible'] = [(n >= 4) or (FAMN[f] >= 2) for n, f in zip(TM.n, TM.family)]; TM.to_csv(f'{OUT}/bl_d0r_timers.csv', index=False)
# ---------------- coverage by credible timers only
pr_ = []
for day in ('D-1', 'D0'):
    for u, v in GR:
        t = times(day, u, v)
        if len(t) < 6: continue
        tms, alive = I.solve(t); allc = sum(len(ix) for _, ix in tms)
        sub = TM[(TM.day == day) & (TM.und == u) & (TM.version == v)]
        # recompute membership for the credible timers: match by (P, first member)
        ok = 0; ncred = 0
        for (P, ix), (_, row) in zip(sorted(tms, key=lambda x: np.sort(t[x[1]])[0]), sub.sort_values('phase_s').iterrows()): pass
        cov_cred = 0
        by_key = {(int(r.P), r.first): r.credible for r in sub.itertuples()}
        for P, ix in tms:
            tt = np.sort(t[ix]); key = (int(P), I.hm(tt[0]))
            if by_key.get(key, False): cov_cred += len(ix); ncred += 1
        pr_.append(dict(day=day, group=f'{u} {v}', waves=len(t), timers=len(tms), covered_all=allc / len(t), credible_timers=ncred, covered_credible=cov_cred / len(t)))
PR = pd.DataFrame(pr_); PR.to_csv(f'{OUT}/bl_d0r_prune.csv', index=False); print(PR.round(3).to_string(index=False))
R = dict(robust_above=int(RB.above.sum()), robust_runs=len(RB), families=len(fam), families_in_2plus=int((fam.group_days >= 2).sum()), credible_timers=int(TM.credible.sum()), timers=len(TM)); rec('d0r2', R); print(R)
