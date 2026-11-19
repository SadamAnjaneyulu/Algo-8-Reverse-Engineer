"""Build the cycle eligibility register for the historical replay (criteria: config/eligibility_criteria.yaml, fixed before this ran).
Data: expected-expiry coverage tables (independent calendar) + per-cycle full-chain minute caches (backtest/replication/cache, built from the pinned dataset commit)."""
import os, sys, pickle, math
import numpy as np, pandas as pd, yaml
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); REPO = os.path.dirname(ROOT)
CRIT = yaml.safe_load(open(f'{ROOT}/config/eligibility_criteria.yaml'))
VAL = f'{REPO}/data_validation/reports/tables'; CACHE = f'{REPO}/backtest/replication/cache'
MIN = [f'{h:02d}:{m:02d}' for h in range(9, 16) for m in range(60) if '09:15' <= f'{h:02d}:{m:02d}' <= '15:29']; MI = {m: i for i, m in enumerate(MIN)}
STEP = {'NIFTY': 50, 'SENSEX': 100}; FW = CRIT['policy']['fill_window_minutes']
D1W = [MI[h] for h in CRIT['windows']['d1_scheduled']]
D0W = [MI['09:30'] + 15 * k for k in range(23)]
special_d1 = {tuple(x) for x in CRIT['special_sessions_and_outages']['special_d1']}; outage = {(x[0], x[2], x[1]) for x in CRIT['special_sessions_and_outages']['outage']}


def wing_dist(und, d0):
    return 2000 if und == 'NIFTY' else (4000 if d0 < '2026-09-16' else 2000)


def executable(c, day, cp, strikes_ix, k, i):
    """first executable bar (volume>0) for (cp, strike k) in minutes i..i+FW-1 -> (minute, open) or None"""
    r = strikes_ix.get(k)
    if r is None: return None
    vol, op = c[(day, cp, 'volume')], c[(day, cp, 'open')]
    for j in range(i, min(i + FW, len(MIN))):
        if np.isfinite(vol[r, j]) and vol[r, j] > 0 and np.isfinite(op[r, j]): return j, op[r, j]
    return None


def atm(c, day, und, i):
    S = c[(day, 'spot')]
    if i - 1 < 0 or not np.isfinite(S[i - 1]): return None
    return STEP[und] * math.floor(S[i - 1] / STEP[und] + 0.5)


def straddle_exec(c, day, und, six, i):
    K = atm(c, day, und, i)
    if K is None: return False
    return executable(c, day, 'CE', six, K, i) is not None and executable(c, day, 'PE', six, K, i) is not None


def period(und, d0):
    if d0 < '2024-06-01': return 'P1_dev_2023-11_to_2024-05'
    if d0 < '2025-06-01': return 'P2_validation_2024-06_to_2025-05'
    if d0 < '2026-06-22': return 'P3_primary_2025-06_to_2026-06-21'
    if d0 <= '2026-10-22': return 'P4_live_window_2026-06-22_to_10-22'
    return 'P5_after_live_window'


def tier(d0):
    if d0 <= '2025-11-17': return 'T3_in_sample_of_prior_programmes'
    if d0 < '2026-06-22': return 'T2_previously_scored_by_related_strategies'
    if d0 <= '2026-10-22': return 'T4_live_window_reverse_engineering'
    return 'T1_never_evaluated'


rows = []
for und in ('NIFTY', 'SENSEX'):
    t = pd.read_csv(f'{VAL}/{und.lower()}_expiry_coverage.csv')
    for r in t.itertuples():
        d0, d1, st = r.d0_expected, r.d1_expected, r.status
        row = dict(und=und, expiry=r.expected_expiry, d1=d1, d0=d0, validation_status=st, period=period(und, d0), tier=tier(d0), notes=r.notes if isinstance(r.notes, str) else '')
        reasons = []; cls = None
        sp = (und, r.expected_expiry) in special_d1; out = [k for k in outage if k[0] == und and k[1] in (d1, d0)]
        row.update(special_d1=sp, outage_sessions=';'.join(f'{k[2]}:{k[1]}' for k in out))
        fn = f'{CACHE}/{und}_{r.expected_expiry}.pkl'
        if st == 'Missing': cls = 'UNUSABLE'; reasons.append('validation status Missing')
        if sp: cls = 'UNUSABLE'; reasons.append('D-1 is a special (Muhurat) session')
        if cls is None and os.path.exists(fn):
            c = pickle.load(open(fn, 'rb')); six = {int(k): i for i, k in enumerate(c['strikes'])}
            o_ok = straddle_exec(c, 0, und, six, MI['09:16']); K = atm(c, 0, und, MI['09:16']); W = wing_dist(und, d0)
            wce = K is not None and executable(c, 0, 'CE', six, K + W, MI['09:16'])
            wpe = K is not None and executable(c, 0, 'PE', six, K - W, MI['09:16'])
            # wing window is 09:16-09:20 (5 bars): extend the check
            def wing_ok(cp, k):
                if k is None: return False
                r_ = six.get(int(k)); v = c[(0, cp, 'volume')]
                return r_ is not None and any(np.isfinite(v[r_, j]) and v[r_, j] > 0 for j in range(MI['09:16'], MI['09:20'] + 1))
            wce = wing_ok('CE', None if K is None else K + W); wpe = wing_ok('PE', None if K is None else K - W)
            n1 = sum(straddle_exec(c, 0, und, six, i) for i in D1W); n0 = sum(straddle_exec(c, 1, und, six, i) for i in D0W)
            row.update(open_atm_exec=bool(o_ok), wing_ce_exact=bool(wce), wing_pe_exact=bool(wpe), d1_windows_exec=n1, d0_windows_exec=n0, spot_missing_d1=int(np.isnan(c[(0, 'spot')]).sum()), spot_missing_d0=int(np.isnan(c[(1, 'spot')]).sum()), lot_d1=None)
            if st == 'Partial' or out: cls = 'PARTIAL'; reasons.append('status Partial' if st == 'Partial' else 'outage session')
            elif not o_ok: cls = 'PARTIAL'; reasons.append('opening ATM leg not executable')
            elif n1 < 15: cls = 'PARTIAL'; reasons.append(f'only {n1}/17 D-1 windows executable')
            elif not (wce and wpe): cls = 'FEASIBLE_WITH_DECLARED_SUBSTITUTION'; reasons.append('seed wing not exact')
            else: cls = 'FULLY_FEASIBLE'
        elif cls is None:
            cls = 'PARTIAL' if st == 'Partial' else 'UNUSABLE'; reasons.append(f'status {st}; no full-chain cache')
        row.update(eligibility=cls, reasons='; '.join(reasons)); rows.append(row)
R = pd.DataFrame(rows); os.makedirs(f'{ROOT}/experiments/results', exist_ok=True); R.to_csv(f'{ROOT}/experiments/results/cycle_eligibility_register.csv', index=False)
pd.set_option('display.width', 220)
print(R.groupby(['und', 'eligibility']).size().unstack(fill_value=0)); print(R.groupby(['period', 'und', 'eligibility']).size().unstack(fill_value=0)); print(R.groupby(['tier', 'eligibility']).size().unstack(fill_value=0))
