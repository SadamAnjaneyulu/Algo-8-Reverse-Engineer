"""Supplement to bl_audit_power.py (same data-generating model, same calibration).
(1) 'crossfit' clock baseline: the clock used by BOTH score and baseline for confirmatory cycle k is the frequency table of the 10 burn-in cycles plus the OTHER confirmatory cycles seen so far
    (leave-own-cycle-out), instead of the 10 burn-in cycles alone. This changes only the baseline's estimation noise, not the frozen score's features or coefficients.
(2) large-N sweep (exact clock, linearised interval, fixed N, 5% two-sided) to size the small effects.
Output outputs/audit/power_crossfit.csv, power_large_n.csv"""
import sys, os, json, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
os.environ.setdefault('R_REPS', '600'); import bl_audit_power as P
R = int(os.environ['R_REPS']); AU = P.AU; cal = json.load(open(f'{AU}/power_summary.json'))['calibration']
def crossfit_clock(Y, Yb, L):
    cb = (Yb > 0).sum(0); cf = (Y[:L] > 0).sum(0); own = (Y[:L] > 0).astype(int); freq = (cb[None] + cf[None] - own) / (Yb.shape[0] + L - 1); return (freq - P.MU[2]) / P.SD[2]    # (L, 2, NJ)
def one(lam, a, rng, designs):
    idx, Y = P.draw_cycles(rng, 90, lam, a); _, Yb = P.draw_cycles(rng, 10, lam, a); out = {}
    for name, (looks, level) in designs.items():
        for meth in ('lin', 'boot'):
            rej = False
            for i, L in enumerate(looks):
                zc = crossfit_clock(Y, Yb, L); Sc = P.ICPT + P.BETA[0] * P.Z1[idx[:L]] + P.BETA[1] * P.Z2[idx[:L]] + P.BETA[2] * zc; aa, dd = P.comp_fast(Sc, zc, Y[:L]); est, lo = P.ci_level(aa, dd, level, meth, rng)
                if lo > 0: rej = True; break
                if len(looks) > 1 and i == 0 and est <= 0: break
            out[(name, meth)] = rej
    return out
if __name__ == '__main__':
    designs = {'fixed30': ([30], 0.95), 'fixed60': ([60], 0.95), 'fixed90': ([90], 0.95), 'pocock2': ([30, 60], 1 - 0.0294), 'pocock3': ([30, 60, 90], 1 - 0.0221)}; rows = []
    for k, c in cal.items():
        rng = np.random.default_rng(P.SEED + 7 + abs(hash(k)) % 10 ** 5); res = [one(c['lam'], c['a'], rng, designs) for _ in range(R)]
        for key in res[0]: p = float(np.mean([r[key] for r in res])); rows.append(dict(scenario='crossfit', effect=k, pop_delta=c['pop_delta'], design=key[0], method=key[1], rejection_rate=p, se=float(np.sqrt(p * (1 - p) / R))))
        print('crossfit', k, 'done', flush=True)
    pd.DataFrame(rows).to_csv(f'{AU}/power_crossfit.csv', index=False)
    # large-N sweep for the small effects (exact clock, linearised, fixed N)
    Ns = [100, 150, 200, 300, 400, 600]; rows = []
    for k in ('+0.050', '+0.025'):
        c = cal[k]; rng = np.random.default_rng(P.SEED + 99); hit = {N: 0 for N in Ns}; Rr = max(R // 2, 300)
        for _ in range(Rr):
            idx, Y = P.draw_cycles(rng, max(Ns), c['lam'], c['a']); Sc, Bl = P.score_arrays(idx, P.ZC_TRUE); aa, dd = P.comp_fast(Sc, Bl, Y)
            for N in Ns:
                est, lo = P.ci_level(aa[:N], dd[:N], 0.95, 'lin', rng); hit[N] += bool(lo > 0)
        rows += [dict(effect=k, N=N, power=hit[N] / Rr) for N in Ns]; print('largeN', k, {N: round(hit[N] / Rr, 3) for N in Ns}, flush=True)
    pd.DataFrame(rows).to_csv(f'{AU}/power_large_n.csv', index=False)
