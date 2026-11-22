"""D0 scheduler structure, step 4 (post-hoc, plan reports/D0_SCHED_RULE_PLAN.md addendum): timers that may SKIP slots.
A gapped timer = (phase, period P, first, last): its members are all clock times congruent to phase (mod P) within +-TOL s between first and last; it needs >= 3 members and a fill ratio (members / expected slots) >= FILL.
Same integer program as bl_d0r_ilp, cost = MU + LAM x (skipped slots) per timer (LAM = 0.3, plan addendum A: prefer the largest period that explains the members). Null: clock times shifted independently by +-150 s. Outputs bl_d0r_gap.csv, bl_summary_d0r3.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy.optimize import milp, LinearConstraint, Bounds
from scipy.sparse import lil_matrix
import bl_d0r_ilp as I
PER = [300 * k for k in range(1, 19)]
def cands(t, tol=2.0, fill=0.6, minlen=3):
    t = np.asarray(t, float); n = len(t); out = {}
    for i in range(n):
        for P in PER:
            ph = t[i]; d = (t - ph) % P; m = np.where((np.minimum(d, P - d) <= tol))[0]
            m = [j for j in m if t[j] >= ph - tol]
            if len(m) < minlen: continue
            first, last = t[m[0]], t[m[-1]]; slots = int(round((last - first) / P)) + 1
            for L in range(minlen, len(m) + 1):
                mm = m[:L]; sl = int(round((t[mm[-1]] - t[mm[0]]) / P)) + 1
                if len(mm) / sl >= fill: out[(tuple(mm), P)] = 1
    return [(P, list(ix)) for (ix, P) in out]
def solve(t, mu=1.5, tol=2.0, fill=0.6, lam=0.3):
    t = np.asarray(t, float); n = len(t); C = cands(t, tol, fill)
    if not C: return [], np.ones(n, bool)
    A = lil_matrix((n, len(C)))
    for k, (P, ix) in enumerate(C):
        for j in ix: A[j, k] = 1
    skips = [int(round((np.max(t[ix]) - np.min(t[ix])) / P)) + 1 - len(ix) for P, ix in C]
    res = milp(np.array([mu + lam * sk - len(ix) for (P, ix), sk in zip(C, skips)], float), constraints=LinearConstraint(A.tocsr(), -np.inf, 1), integrality=np.ones(len(C)), bounds=Bounds(0, 1), options=dict(time_limit=60))
    ch = [C[k] for k in np.where(res.x > .5)[0]]; alive = np.ones(n, bool)
    for P, ix in ch: alive[ix] = False
    return ch, alive
if __name__ == '__main__':
    W1 = pd.read_csv(f'{OUT}/bl_d0q_d1waves.csv'); WA = pd.read_csv(f'{OUT}/bl_d0q_waves.csv'); rng = np.random.default_rng(13); rows = []; R = {}
    for day in ('D-1', 'D0'):
        for u, v in (('NIFTY', 'V1'), ('NIFTY', 'V2'), ('SENSEX', 'V1'), ('SENSEX', 'V2')):
            W = WA if day == 'D0' else W1; t = np.sort(W[(W.und == u) & (W.version == v)].t.values)
            if len(t) < 12: continue
            c1, a1 = I.solve(t); c2, a2 = solve(t); nl = []; nt = []
            for _ in range(8):
                tn = t + rng.uniform(-150, 150, len(t)); cc, aa = solve(tn); nl.append((~aa).mean()); nt.append(len(cc))
            rows.append(dict(day=day, group=f'{u} {v}', waves=len(t), strict_timers=len(c1), strict_covered=(~a1).mean(), gapped_timers=len(c2), gapped_covered=(~a2).mean(), null_covered_mean=np.mean(nl), null_covered_max=np.max(nl), null_timers=np.mean(nt)))
            print(rows[-1])
            if (u, v, day) in (('NIFTY', 'V1', 'D0'),):
                D = I.describe(t, c2); print(D.to_string(index=False)); print('residual:', ' '.join(I.hm(x)[:8] for x in t[a2])); R['nifty_v1_d0_gapped_residual'] = [I.hm(x) for x in t[a2]]
    G = pd.DataFrame(rows); G.to_csv(f'{OUT}/bl_d0r_gap.csv', index=False); R['rows'] = G.round(4).to_dict('records'); rec('d0r3', R)
    # ---- forward test for gapped timers: fit on clock times before 12:00, predict every slot of each timer for up to 6 slots after its last member, score the clock times from 12:00 on
    rows = []; rng = np.random.default_rng(29)
    for day in ('D-1', 'D0'):
        for u, v in (('NIFTY', 'V1'), ('NIFTY', 'V2'), ('SENSEX', 'V1'), ('SENSEX', 'V2')):
            W = WA if day == 'D0' else W1; t = np.sort(W[(W.und == u) & (W.version == v)].t.values); te = t[t < 43200.0]; tg = t[t >= 43200.0]
            if len(te) < 12 or len(tg) < 5: continue
            ch, _ = solve(te)
            if not ch: continue
            tms = [dict(P=P, last=float(np.max(te[ix])), phase=float(np.min(te[ix]))) for P, ix in ch]
            def preds(tms_): return np.concatenate([tm['last'] + tm['P'] * np.arange(1, 7) for tm in tms_])
            def score(pr):
                pr = pr[(pr >= 43200.0) & (pr <= 53400.0)]
                rec = np.mean([np.min(np.abs(pr - x)) <= 2 for x in tg]) if len(pr) else 0.0; prec = np.mean([np.min(np.abs(tg - p)) <= 2 for p in pr]) if len(pr) else np.nan
                return rec, prec
            rec_, prec_ = score(preds(tms)); nr = []; npc = []
            for _ in range(400):
                tm2 = [dict(tm, last=tm['last'] + rng.uniform(4, tm['P'] - 4)) for tm in tms]; a, b = score(preds(tm2)); nr.append(a); npc.append(b)
            rows.append(dict(day=day, group=f'{u} {v}', timers=len(tms), targets=len(tg), recall=rec_, recall_null_mean=np.mean(nr), recall_null_p95=np.percentile(nr, 95), precision=prec_, precision_null_mean=np.nanmean(npc), above_p95=bool(rec_ > np.percentile(nr, 95))))
    F = pd.DataFrame(rows); F.to_csv(f'{OUT}/bl_d0r_gap_fwd.csv', index=False); print(F.round(3).to_string(index=False)); R['forward'] = F.round(4).to_dict('records'); rec('d0r3', R)
