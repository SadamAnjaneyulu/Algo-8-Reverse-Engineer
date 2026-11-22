"""D0 scheduler structure, step 1 (exploratory; plan reports/D0_SCHED_RULE_PLAN.md): decompose a group's clock times into arithmetic progressions ('timers': start, period, count, second offset).
Method: periods P = whole minutes 3..60; a chain = t, t+P, t+2P, ... each within +-TOL s of a wave time; greedy: take the longest chain (>= MINLEN) over all (start, P), remove its waves, repeat.
Null: the same greedy run on the wave times with every wave moved by an independent uniform shift of +-SH s (keeps the density, destroys exact spacing). Outputs printed; library functions reused by bl_d0r_*.py"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
hm = lambda t: f'{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{int(t % 60):02d}'
def greedy(times, tol=2.0, minlen=4, pmin=3, pmax=60):
    t = np.sort(np.asarray(times, float)); alive = np.ones(len(t), bool); chains = []
    while True:
        best = None
        for i in np.where(alive)[0]:
            for P in range(pmin * 60, pmax * 60 + 1, 60):
                idx = [i]; cur = t[i]
                while True:
                    nxt = cur + P; c = np.where(alive & (np.abs(t - nxt) <= tol) & (t > idx_t(t, idx)))[0]
                    if not len(c): break
                    j = c[np.argmin(np.abs(t[c] - nxt))]; idx.append(j); cur = t[j]
                if len(idx) >= minlen and (best is None or len(idx) > len(best[1]) or (len(idx) == len(best[1]) and P < best[0])): best = (P, idx)
        if best is None: break
        P, idx = best; chains.append((P, idx)); alive[idx] = False
    return chains, alive
def idx_t(t, idx): return t[idx[-1]]
def describe(t, chains):
    t = np.sort(np.asarray(t, float)); out = []
    for P, idx in chains: out.append(dict(period_min=P // 60, count=len(idx), first=hm(t[idx[0]]), last=hm(t[idx[-1]]), second_offsets=sorted({int(round(t[k] % 60)) % 60 for k in idx})))
    return pd.DataFrame(out)
if __name__ == '__main__':
    from bl_common import *
    W1 = pd.read_csv(f'{OUT}/bl_d0q_d1waves.csv'); WA = pd.read_csv(f'{OUT}/bl_d0q_waves.csv'); rng = np.random.default_rng(3)
    for nm, t in (('D-1 NIFTY V1', W1[(W1.und == 'NIFTY') & (W1.version == 'V1')].t.values), ('D0 NIFTY V1', WA[(WA.und == 'NIFTY') & (WA.version == 'V1')].t.values)):
        ch, alive = greedy(t); D = describe(t, ch); print(f'\n== {nm}: {len(t)} waves -> {len(ch)} chains covering {int((~alive).sum())} waves ({(~alive).mean():.0%}); residual {int(alive.sum())}'); print(D.to_string(index=False))
        cov = []
        for _ in range(20):
            tn = t + rng.uniform(-150, 150, len(t)); c2, a2 = greedy(tn); cov.append((~a2).mean())
        print('   null coverage (waves shifted +-150 s): mean %.0f%%, max %.0f%%' % (100 * np.mean(cov), 100 * np.max(cov)))
        print('   residual times:', ' '.join(hm(x) for x in np.sort(t)[alive]))
