"""D0 scheduler structure, validation T1-T4 (plan reports/D0_SCHED_RULE_PLAN.md). Timers from bl_d0r_ilp.solve (periods = multiples of 5 min, chains >= 3, mu = 1.5, tol = 2 s).
T1 forward extrapolation: fit timers on clock times before 12:00, extend each up to 6 members, share of the clock times from 12:00 on within +-2 s of a prediction; null = same timers with random phase shifts (>= 4 s up to the period), 500 draws.
T2 D-1 timers (extended over the whole day) vs D0 times of the same group, and D0 timers vs D-1 times; T3 NIFTY V1 D0 timers vs NIFTY V2 / SENSEX V2 D0 times; T4 timer tables.
Outputs bl_d0r_timers.csv, bl_d0r_t1.csv, bl_d0r_t23.csv, bl_summary_d0r1.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from bl_d0r_ilp import solve, describe, hm
W1 = pd.read_csv(f'{OUT}/bl_d0q_d1waves.csv'); WA = pd.read_csv(f'{OUT}/bl_d0q_waves.csv'); rng = np.random.default_rng(101); R = {}
GR = [('NIFTY', 'V1'), ('NIFTY', 'V2'), ('SENSEX', 'V1'), ('SENSEX', 'V2')]; TOL = 2.0
def times(day, u, v): W = WA if day == 'D0' else W1; return np.sort(W[(W.und == u) & (W.version == v)].t.values)
def timers_of(t):
    ch, alive = solve(t); out = []
    for P, ix in ch: tt = np.sort(t[ix]); out.append(dict(P=P, t0=float(tt[0]), n=len(ix), last=float(tt[-1]), sec=float(np.median(tt % 60)), phase=float(np.median((tt - np.arange(len(tt)) * P))) ))
    return out, alive
def predict(tm, upto=None, back=False, k_more=None, lo=33000.0, hi=56000.0):
    """fire times of a timer extended: forward from its last member (k_more members) or over the whole day (back=True, both directions)"""
    P = tm['P']; ph = tm['phase']
    if back: n0 = int(np.ceil((lo - ph) / P)); n1 = int(np.floor((hi - ph) / P)); return ph + P * np.arange(n0, n1 + 1)
    return tm['last'] + P * np.arange(1, k_more + 1)
def cover(target, preds):
    if len(preds) == 0 or len(target) == 0: return 0.0
    return float(np.mean([np.min(np.abs(preds - x)) <= TOL for x in target]))
def null_cover(target, tms, mk, draws=500):
    out = []
    for _ in range(draws):
        pr = []
        for tm in tms:
            s = dict(tm); s['phase'] = tm['phase'] + rng.uniform(4, tm['P'] - 4); s['last'] = tm['last'] + (s['phase'] - tm['phase']); pr.append(mk(s))
        out.append(cover(target, np.concatenate(pr) if pr else np.array([])))
    return np.array(out)
rows = []; TM = []
for day in ('D-1', 'D0'):
    for u, v in GR:
        t = times(day, u, v)
        if len(t) < 12: continue
        tms, alive = timers_of(t); R[f'{day} {u} {v}'] = dict(waves=len(t), timers=len(tms), covered=float((~alive).mean()))
        for k, tm in enumerate(tms): TM.append(dict(day=day, und=u, version=v, **{x: tm[x] for x in ('P', 'n', 'sec')}, period_min=tm['P'] // 60, first=hm(tm['t0']), last_member=hm(tm['last']), phase_s=tm['phase']))
        # T1 forward extrapolation
        SPL = 12 * 3600.0; te = t[t < SPL]
        if len(te) >= 12:
            tm1, _ = timers_of(te); tg = t[t >= SPL]; pr = np.concatenate([predict(x, k_more=6) for x in tm1]) if tm1 else np.array([]); pr = pr[pr >= SPL]
            real = cover(tg, pr); nl = null_cover(tg, tm1, lambda s: predict(s, k_more=6))
            rows.append(dict(test='T1 morning timers -> afternoon times', day=day, group=f'{u} {v}', targets=len(tg), timers_fit=len(tm1), real_share=real, null_mean=nl.mean(), null_p95=np.percentile(nl, 95), ratio=real / max(nl.mean(), 1e-9)))
TMd = pd.DataFrame(TM); TMd.to_csv(f'{OUT}/bl_d0r_timers.csv', index=False)
# T2 D-1 timers -> D0 and reverse, same group
for u, v in GR:
    for a, b in (('D-1', 'D0'), ('D0', 'D-1')):
        ta, tb = times(a, u, v), times(b, u, v)
        if len(ta) < 12 or len(tb) < 12: continue
        tms, _ = timers_of(ta); pr = np.concatenate([predict(x, back=True) for x in tms]); real = cover(tb, pr); nl = null_cover(tb, tms, lambda s: predict(s, back=True))
        rows.append(dict(test=f'T2 {a} timers -> {b} times', day=b, group=f'{u} {v}', targets=len(tb), timers_fit=len(tms), real_share=real, null_mean=nl.mean(), null_p95=np.percentile(nl, 95), ratio=real / max(nl.mean(), 1e-9)))
# T3 across groups (D0)
src = times('D0', 'NIFTY', 'V1'); tms, _ = timers_of(src); pr = np.concatenate([predict(x, back=True) for x in tms])
for u, v in (('NIFTY', 'V2'), ('SENSEX', 'V2'), ('SENSEX', 'V1')):
    tb = times('D0', u, v); real = cover(tb, pr); nl = null_cover(tb, tms, lambda s: predict(s, back=True))
    rows.append(dict(test='T3 NIFTY V1 D0 timers -> other group D0 times', day='D0', group=f'{u} {v}', targets=len(tb), timers_fit=len(tms), real_share=real, null_mean=nl.mean(), null_p95=np.percentile(nl, 95), ratio=real / max(nl.mean(), 1e-9)))
T = pd.DataFrame(rows); T['above_null_p95'] = T.real_share > T.null_p95; T.to_csv(f'{OUT}/bl_d0r_t1.csv', index=False); print(T.round(3).to_string(index=False)); print(TMd.round(1).to_string(index=False))
R['tests'] = T.round(4).to_dict('records'); rec('d0r1', R)
