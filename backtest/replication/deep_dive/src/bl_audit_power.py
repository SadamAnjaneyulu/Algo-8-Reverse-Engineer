"""Independent simulation-based power / size analysis of the pre-registered forward test (reports/POWER_ANALYSIS.md). Does NOT change the frozen rule or score.

Data-generating model. Synthetic forward cycles are resampled WHOLE from the 18 development cycles (their real feature paths, window of 25 minutes x 2 sides). Labels are drawn from
  logit p = a + lam * (b_ext5 z_ext5 + b_mv1 z_mv1) + b_clock z_clock_true
with the frozen coefficients b and z standardised as in the frozen model; a is set so the event rate equals the development rate (48 / 900 rows = 2.67 events per cycle); lam is calibrated
by bisection so that the POPULATION paired delta AUC of the frozen score over the clock baseline equals each target. Cycle counts, unequal event counts per cycle and the clustering are therefore realistic.
Frozen score and baseline are evaluated on identical rows with the same statistic as the protocol (stratified AUC within (cycle, side) blocks, paired). Two clock-table scenarios:
  'exact'   the frozen development table is the clock (regime-A like);  'burnin'  the table is estimated from 10 synthetic burn-in cycles (regime B), noisy, and used by BOTH score and baseline.
Inference per look: percentile cluster bootstrap and linearised cluster-robust t interval, each at the level the design requires. Designs: fixed-N (5% two-sided), Pocock K=2 (30/60, nominal 2.94%),
Pocock K=3 (30/60/90, nominal 2.21%), and the v1-harness behaviour (K=2 looks at 95%) to show the size inflation. Futility at look 1: stop if the primary point estimate <= 0.
Output outputs/audit/power_*.csv, power_summary.json
"""
import sys, os, json, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from scipy.stats import rankdata, t as tdist
import bl_validation as V
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'outputs'); AU = f'{OUT}/audit'; NJ = 25
R_REPS = int(os.environ.get('R_REPS', 600)); BOOT = int(os.environ.get('BOOT', 300)); SEED = int(os.environ.get('SEED', 20261124))
M = json.load(open(f'{OUT}/fwd/frozen_model.json')); MU, SD, BETA, ICPT = np.array(M['mean']), np.array(M['std']), np.array(M['coef']), M['intercept']
D = pd.read_csv(f'{OUT}/trig/event_table.csv.gz'); D = D[(D.era == 'after') & (D.outlier == 0)].copy(); D['cyc'] = D.und + '|' + D.expiry; CY = sorted(D.cyc.unique()); NC = len(CY)
def cube(col): return np.stack([np.stack([D[(D.cyc == c) & (D.side == s)].sort_values('j')[col].values for s in ('CE', 'PE')]) for c in CY]).astype(float)
Z1 = (np.nan_to_num(cube('FUT_ext5'), nan=M['medians']['FUT_ext5']) - MU[0]) / SD[0]; Z2 = (np.nan_to_num(cube('FUT_mv1'), nan=M['medians']['FUT_mv1']) - MU[1]) / SD[1]
TAB = np.array([[M['clock_table'][f'{j}|{s}'] for j in range(360, 385)] for s in ('CE', 'PE')]); ZC_TRUE = (TAB - MU[2]) / SD[2]            # (2, 25)
RATE = D.y.sum() / len(D)
def rates(lam, a):
    eta = a + lam * (BETA[0] * Z1 + BETA[1] * Z2) + BETA[2] * ZC_TRUE[None]; return 1 / (1 + np.exp(-eta))
def solve_a(lam):
    lo, hi = -12.0, 4.0
    for _ in range(50):
        mid = (lo + hi) / 2
        if rates(lam, mid).mean() > RATE: hi = mid
        else: lo = mid
    return (lo + hi) / 2
def comp_fast(Sc, Bl, Y):
    """per-cycle (a_k, d_k): a_k = U_score - U_base summed over the cycle's valid blocks, d_k = sum n1 n0. Arrays (m, 2, NJ)."""
    m = Y.shape[0]; n1 = Y.sum(2); valid = (n1 > 0) & (n1 < NJ)
    def U(Z): return (rankdata(Z.reshape(m * 2, NJ), axis=1).reshape(m, 2, NJ) * Y).sum(2) - n1 * (n1 + 1) / 2
    a = ((U(Sc) - U(Bl)) * valid).sum(1); d = (n1 * (NJ - n1) * valid).sum(1); return a, d
def draw_cycles(rng, m, lam, a):
    idx = rng.integers(0, NC, m); p = rates(lam, a)[idx]; return idx, (rng.random(p.shape) < p).astype(int)
def score_arrays(idx, zc_hat):
    zc = np.broadcast_to(zc_hat[None], (len(idx), 2, NJ)); Sc = ICPT + BETA[0] * Z1[idx] + BETA[1] * Z2[idx] + BETA[2] * zc; return Sc, np.array(zc)
def table_hat(rng, lam, a, nb=10):
    idx, Y = draw_cycles(rng, nb, lam, a); freq = (Y > 0).mean(0); return (freq - MU[2]) / SD[2]
def pop_delta(lam, a, rng, m=6000):
    idx, Y = draw_cycles(rng, m, lam, a); Sc, Bl = score_arrays(idx, ZC_TRUE); aa, dd = comp_fast(Sc, Bl, Y); return float(aa.sum() / dd.sum())
def calibrate(target, rng):
    """lam such that the population delta AUC (exact clock) equals target"""
    lo, hi = 0.0, 4.0
    for _ in range(22):
        mid = (lo + hi) / 2; a = solve_a(mid); v = pop_delta(mid, a, np.random.default_rng(99))
        if v < target: lo = mid
        else: hi = mid
    lam = (lo + hi) / 2; return lam, solve_a(lam), pop_delta(lam, solve_a(lam), np.random.default_rng(100))
def ci_level(a, d, level, method, rng):
    m = len(a); Dsum = d.sum()
    if Dsum <= 0: return np.nan, np.nan
    est = a.sum() / Dsum
    if method == 'lin':
        r = a - est * d; se = np.sqrt(m / (m - 1.0) * (r ** 2).sum()) / Dsum; crit = tdist.ppf(1 - (1 - level) / 2, m - 1); return est, est - crit * se
    W = rng.multinomial(m, np.ones(m) / m, size=BOOT).astype(float); x = (W @ a) / np.where(W @ d > 0, W @ d, np.nan); return est, float(np.nanquantile(x, (1 - level) / 2))
DESIGNS = {'fixed': None, 'pocock2': dict(looks=[30, 60], level=1 - 0.0294), 'pocock3': dict(looks=[30, 60, 90], level=1 - 0.0221), 'v1_bug_95': dict(looks=[30, 60], level=0.95)}
FIXED_N = [10, 20, 30, 40, 60, 80, 100, 150, 200]
def simulate(lam, a, scenario, rng):
    """one replication -> dict of results for every design and method"""
    mmax = 200; idx, Y = draw_cycles(rng, mmax, lam, a); zc_hat = ZC_TRUE if scenario == 'exact' else table_hat(rng, lam, a); Sc, Bl = score_arrays(idx, zc_hat); aa, dd = comp_fast(Sc, Bl, Y); out = {}
    for meth in ('lin', 'boot'):
        for N in FIXED_N:
            est, lo = ci_level(aa[:N], dd[:N], 0.95, meth, rng); out[('fixed', meth, N)] = bool(lo > 0)
        for name in ('pocock2', 'pocock3', 'v1_bug_95'):
            cfg = DESIGNS[name]; rej = False
            for i, L in enumerate(cfg['looks']):
                est, lo = ci_level(aa[:L], dd[:L], cfg['level'], meth, rng)
                if lo > 0: rej = True; break
                if i == 0 and est <= 0: break           # futility at the first look
            out[(name, meth, cfg['looks'][-1])] = rej
    out['eff_cycles_30'] = float(dd[:30].sum() ** 2 / (dd[:30] ** 2).sum()) if (dd[:30] ** 2).sum() > 0 else 0.0; out['events_30'] = float(Y[:30].sum()); out['cycles_with_pairs_30'] = int((dd[:30] > 0).sum()); return out
if __name__ == '__main__':
    rng0 = np.random.default_rng(SEED); targets = {'+0.098': 0.098, '+0.075': 0.075, '+0.050': 0.050, '+0.025': 0.025, '0.000': 0.0}; cal = {}
    for k, v in targets.items(): lam, a, pv = calibrate(v, rng0); cal[k] = dict(lam=lam, a=a, pop_delta=pv)
    lam0 = 0.0; a0 = solve_a(0.0); cal['no_info_lam0'] = dict(lam=0.0, a=a0, pop_delta=pop_delta(0.0, a0, np.random.default_rng(101))); print('calibration', json.dumps(cal, default=lambda z: round(float(z), 4)))
    rows = []; extra = {}
    for scen in ('exact', 'burnin'):
        for k, c in cal.items():
            rng = np.random.default_rng(SEED + hash((scen, k)) % 10 ** 6); res = [simulate(c['lam'], c['a'], scen, rng) for _ in range(R_REPS)]
            for key in res[0]:
                if isinstance(key, tuple): p = float(np.mean([r[key] for r in res])); rows.append(dict(scenario=scen, effect=k, pop_delta=c['pop_delta'], design=key[0], method=key[1], N_or_maxN=key[2], rejection_rate=p, se=float(np.sqrt(p * (1 - p) / R_REPS))))
            extra[f'{scen}|{k}'] = dict(eff_cycles_30=float(np.mean([r['eff_cycles_30'] for r in res])), events_30=float(np.mean([r['events_30'] for r in res])), cycles_with_pairs_30=float(np.mean([r['cycles_with_pairs_30'] for r in res])))
            print(scen, k, 'done', flush=True)
    P = pd.DataFrame(rows); P.to_csv(f'{AU}/power_sim.csv', index=False); json.dump(dict(calibration=cal, reps=R_REPS, boot=BOOT, per_scenario=extra, rate=float(RATE), dev_cycles=NC), open(f'{AU}/power_summary.json', 'w'), indent=1, default=float); print('written', len(P))
