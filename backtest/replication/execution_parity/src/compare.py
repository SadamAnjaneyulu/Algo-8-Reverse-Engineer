"""Behavioural comparison engine: one-to-one event agreement with tolerance + phase-preserving circular-shift null, and contract-level inventory-path comparison.
Event identity and lot allocation are kept separate; inventory is per contract (ownership-free)."""
import numpy as np, pandas as pd
import ref  # sets sys.path for lot_lifecycle/src
from matching import match
NM = 375


def _prep(df, minute_col):
    d = df.copy(); d['sec'] = d[minute_col].astype(int) * 60; d['lots'] = d['lots'].astype(int); return d


def agree(sim, act, tol_min, strike='any', group=('und', 'expiry', 'cp'), minute='j'):
    """sim/act columns: und, expiry, cp, strike, lots, <minute>. returns dict(P, R, matched, n_sim, n_act)"""
    s = _prep(sim, minute); a = _prep(act, minute)
    if len(s) == 0 or len(a) == 0: return dict(matched=0, n_sim=int(s.lots.sum()) if len(s) else 0, n_act=int(a.lots.sum()) if len(a) else 0, P=np.nan, R=0.0 if len(a) else np.nan)
    m = match(s, a, tol_min * 60, strike, group); return dict(matched=m['matched'], n_sim=m['sim_lots'], n_act=m['act_lots'], P=m['precision'], R=m['recall'])


def shifted(sim, rng, minute='j', lo=0, hi=NM - 1, by_day=True):
    """circular shift of every simulated event minute inside the 375-minute session [0, 374] (375 = 25 x 15, so wrapping preserves the 15-minute clock phase exactly) by a random multiple of 15 min (30..120), one shift per (cycle, day); no event dropped"""
    s = sim.copy(); W = hi - lo + 1
    for key, idx in s.groupby(['und', 'expiry', 'day']).groups.items():
        sh = int(rng.integers(2, 9)) * 15 * int(rng.choice([-1, 1])); s.loc[idx, minute] = lo + np.mod(s.loc[idx, minute].values - lo + sh, W)
    return s


def agree_with_null(sim, act, tol_min, strike='any', group=('und', 'expiry', 'cp'), ndraw=100, seed=11, minute='j'):
    o = agree(sim, act, tol_min, strike, group, minute); rng = np.random.default_rng(seed); Ps = []; Rs = []
    for _ in range(ndraw):
        n = agree(shifted(sim, rng, minute), act, tol_min, strike, group, minute); Ps.append(n['P']); Rs.append(n['R'])
    nP = float(np.nanmean(Ps)) if len(Ps) and not np.all(np.isnan(Ps)) else np.nan; nR = float(np.nanmean(Rs)) if len(Rs) and not np.all(np.isnan(Rs)) else np.nan
    o.update(null_P=nP, null_R=nR, lift_P=(o['P'] / nP if nP and nP == nP and o['P'] == o['P'] else np.nan), lift_R=(o['R'] / nR if nR and nR == nR and o['R'] == o['R'] else np.nan)); return o


def classify(o, lift_floor=1.5):
    """pre-registered rule (EXECUTION_PARITY_METHODOLOGY section 6). o: dict with P, R, lift_P, lift_R"""
    P, R = o['P'], o['R']
    if o.get('n_act', 1) == 0: return 'NOT TESTABLE'                       # nothing original to compare with
    if R == R and R < 0.20: return 'MISMATCH'                              # pre-registered: recall < 0.20 is MISMATCH even if the component produced no events (P undefined)
    if P != P or R != R: return 'NOT TESTABLE'
    if P >= 0.80 and R >= 0.80 and (o.get('lift_P', np.nan) >= lift_floor) and (o.get('lift_R', np.nan) >= lift_floor): return 'MATCH'
    if P >= 0.50 and R >= 0.20: return 'PARTIAL MATCH'
    return 'MISMATCH'


def path_from_events(ev, cycle_contracts=None):
    """contract-level net lots at the END of every minute (index day*NM + minute) from an event table with columns d (0/1), j, right, strike, signed lots 'sl'"""
    keys = sorted(set(zip(ev.right if 'right' in ev else ev.cp, ev.strike))) if cycle_contracts is None else cycle_contracts; ki = {k: i for i, k in enumerate(keys)}; M = np.zeros((len(keys), 2 * NM))
    for r in ev.itertuples():
        cp = r.right if hasattr(r, 'right') else r.cp; t = int(r.d) * NM + int(np.clip(r.j, 0, NM - 1)); M[ki[(cp, int(r.strike))], t:] += r.sl
    return keys, M


def inventory_compare(keys_a, Ma, keys_s, Ms):
    """align on the union of contracts; active = either path non-zero. returns dict of exact share, MAE, normalised MAE, mean |actual|, plus per-minute-bin MAE (6 bins of the 2-day timeline)"""
    ks = sorted(set(keys_a) | set(keys_s)); ia = {k: i for i, k in enumerate(keys_a)}; is_ = {k: i for i, k in enumerate(keys_s)}; T = Ma.shape[1]
    A = np.zeros((len(ks), T)); S = np.zeros((len(ks), T))
    for i, k in enumerate(ks):
        if k in ia: A[i] = Ma[ia[k]]
        if k in is_: S[i] = Ms[is_[k]]
    act = (A != 0) | (S != 0); n = int(act.sum())
    if n == 0: return dict(active=0, exact=np.nan, mae=np.nan, nmae=np.nan, mean_abs_actual=np.nan)
    d = np.abs(A - S)[act]; ma = np.abs(A)[act].mean()
    return dict(active=n, exact=float((d == 0).mean()), mae=float(d.mean()), nmae=float(d.mean() / ma) if ma > 0 else np.nan, mean_abs_actual=float(ma), A=A, S=S, keys=ks)
