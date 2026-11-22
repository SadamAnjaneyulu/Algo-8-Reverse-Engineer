"""D0 scheduler structure, step 2 (plan reports/D0_SCHED_RULE_PLAN.md): minimum-description timer decomposition by integer programming.
Candidate timers: for every wave i and every period P in PERIODS (multiples of 5 min), the chain i, i+P, i+2P, ... (each member within +-TOL s of a wave, nearest unused), and all its prefixes with >= MINLEN members.
Choose chains to maximise (waves covered) - MU x (timers used), each wave covered at most once (duplicated seconds are separate waves). Solver: scipy milp (HiGHS).
Null: the same procedure on wave times shifted independently by uniform +-SH s (keeps density, destroys exact spacing)."""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from scipy.optimize import milp, LinearConstraint, Bounds
from scipy.sparse import lil_matrix
hm = lambda t: f'{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{int(t % 60):02d}'
PERIODS = [300 * k for k in range(1, 19)]          # 5 .. 90 min
def candidates(t, tol=2.0, minlen=3, periods=PERIODS):
    t = np.asarray(t, float); n = len(t); order = np.argsort(t); out = {}
    for i in range(n):
        for P in periods:
            idx = [i]; cur = t[i]
            while True:
                nxt = cur + P; c = [j for j in range(n) if abs(t[j] - nxt) <= tol and j not in idx and t[j] > cur + P - tol - 1]
                if not c: break
                j = min(c, key=lambda j: abs(t[j] - nxt)); idx.append(j); cur = t[j]
            for L in range(minlen, len(idx) + 1): out[(tuple(idx[:L]), P)] = 1
    return [(P, list(ix)) for (ix, P) in out]
def solve(t, tol=2.0, minlen=3, mu=1.5, periods=PERIODS, time_limit=60):
    t = np.asarray(t, float); n = len(t); C = candidates(t, tol, minlen, periods)
    if not C: return [], np.ones(n, bool)
    A = lil_matrix((n, len(C)))
    for k, (P, ix) in enumerate(C):
        for j in ix: A[j, k] = 1
    cost = np.array([mu - len(ix) for P, ix in C], float)           # minimise  mu*x - covered
    res = milp(cost, constraints=LinearConstraint(A.tocsr(), -np.inf, 1), integrality=np.ones(len(C)), bounds=Bounds(0, 1), options=dict(time_limit=time_limit))
    chosen = [C[k] for k in np.where(res.x > .5)[0]]; alive = np.ones(n, bool)
    for P, ix in chosen: alive[ix] = False
    return chosen, alive
def describe(t, chains):
    t = np.asarray(t, float); out = []
    for P, ix in chains:
        tt = np.sort(t[ix]); out.append(dict(period_min=P // 60, count=len(ix), first=hm(tt[0]), last=hm(tt[-1]), second_offset=int(round(np.median(tt % 60))) % 60, spread_s=round(float((tt - np.arange(len(tt)) * P).max() - (tt - np.arange(len(tt)) * P).min()), 1)))
    return pd.DataFrame(out).sort_values(['first']).reset_index(drop=True)
if __name__ == '__main__':
    from bl_common import *
    W1 = pd.read_csv(f'{OUT}/bl_d0q_d1waves.csv'); WA = pd.read_csv(f'{OUT}/bl_d0q_waves.csv'); rng = np.random.default_rng(11)
    for u, v, d in (('NIFTY', 'V1', 'D-1'), ('NIFTY', 'V1', 'D0'), ('SENSEX', 'V2', 'D0')):
        W = WA if d == 'D0' else W1; t = W[(W.und == u) & (W.version == v)].t.values
        ch, alive = solve(t); D = describe(t, ch); cov = []; nt = []
        for _ in range(8):
            tn = t + rng.uniform(-150, 150, len(t)); c2, a2 = solve(tn); cov.append((~a2).mean()); nt.append(len(c2))
        print(f'\n== {d} {u} {v}: {len(t)} waves -> {len(ch)} timers cover {int((~alive).sum())} ({(~alive).mean():.0%}) | null: coverage {100 * np.mean(cov):.0f}% (max {100 * np.max(cov):.0f}%), timers {np.mean(nt):.1f}'); print(D.to_string(index=False)); print('   residual:', ' '.join(hm(x)[:8] for x in np.sort(t)[alive]))
