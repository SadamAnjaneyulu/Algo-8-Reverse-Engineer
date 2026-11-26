"""Body-sell mismatch ledger and failure categories (pre-registered in reports/BODY_SELL_MISMATCH_PLAN.md). Step 1 of diagnose -> fix -> verify: builds the ledger and the breakdown; changes no engine code, fits nothing.
Unit: the accepted F run (outputs/scoring/d1_F_v2_onelot), one-to-one matching, cumulative 60 s. Classification functions are pure (tested in tests/test_bodysell_ledger.py)."""
import sys, os, json, warnings; sys.path.insert(0, '.'); sys.path.insert(0, '../..'); sys.path.insert(0, '../../..'); sys.path.insert(0, '../../../../d1_strategy'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd

W_NEAR, W_FAR = 60, 300                                                           # fixed in the plan, not varied
OPEN_S = 9 * 3600 + 15 * 60
MISS_CATS = {'M1': 'supply/count: a same-type simulated sell within 60 s was matched elsewhere', 'M2': 'possible wrong side: an unmatched opposite-type simulated sell within 60 s', 'M3': 'timing offset: an unmatched same-type simulated sell within 61-300 s', 'M4': 'trigger never fires: no simulated sell of that type within 300 s'}
EXTRA_CATS = {'X1': 'real supply exhausted: a same-type real sell within 60 s was matched elsewhere', 'X2': 'possible wrong side: an unmatched opposite-type real sell within 60 s', 'X3': 'timing offset: an unmatched same-type real sell within 61-300 s', 'X4': 'no real decision within 300 s'}
OPP = {'CE': 'PE', 'PE': 'CE'}

def _times(df, col): return df[col].values.astype(int)

def prepare(real, sim, pairs):
    """real: DataFrame cyc, cp, side, strike, lots, t, cls, row (prepared order); sim: cyc, cp, side, strike, lots, sec(or t), cls, role, seq; pairs: ri, si, tier, dt, dstrike, dlots (positional). Adds matched flags and partner indices."""
    r = real.reset_index(drop=True).copy(); s = sim.reset_index(drop=True).copy()
    if 'sec' not in s: s['sec'] = np.floor(s['t'].astype(float)).astype(int) if 't' in s else pd.Series(dtype=int)
    r['t'] = r.t.astype(int); r['m'] = False; s['m'] = False; r['partner'] = -1; s['partner'] = -1
    r.loc[pairs.ri.values, 'm'] = True; s.loc[pairs.si.values, 'm'] = True; r.loc[pairs.ri.values, 'partner'] = pairs.si.values; s.loc[pairs.si.values, 'partner'] = pairs.ri.values
    for c in ('tier', 'dt', 'dstrike', 'dlots'): r[c] = np.nan
    for c in ('tier', 'dt', 'dstrike', 'dlots'): r.loc[pairs.ri.values, c] = pairs[c].values
    return r, s

def _pool(df, tcol):
    """sell-side orders of one cycle indexed by (cp): sorted times, matched flags, original indices"""
    out = {}
    for (cyc, cp), g in df[df.side == 'sell'].groupby(['cyc', 'cp']):
        g = g.sort_values(tcol); out[(cyc, cp)] = (g[tcol].values.astype(int), g.m.values.astype(bool), g.index.values)
    return out

def _nearest(pool, cyc, cp, t, only_unmatched=False, exclude=None):
    """(distance, matched, index) of the nearest sell of this type to time t; None if none"""
    p = pool.get((cyc, cp))
    if p is None: return None
    ts, ms, ix = p; mask = np.ones(len(ts), bool)
    if only_unmatched: mask &= ~ms
    if exclude is not None: mask &= ix != exclude
    if not mask.any(): return None
    d = np.abs(ts - t); d = np.where(mask, d, 10 ** 9); k = int(np.argmin(d)); return int(d[k]), bool(ms[k]), int(ix[k])

def classify_missing(R, pool_sim_other, pool_real_same, cyc, cp, t, own_index):
    """category of a missing real body sell by the fixed cascade M1 > M2 > M3 > M4"""
    same = _nearest(pool_sim_other, cyc, cp, t); opp = _nearest(pool_sim_other, cyc, OPP[cp], t, only_unmatched=True); samefar = _nearest(pool_sim_other, cyc, cp, t, only_unmatched=True)
    if same is not None and same[0] <= W_NEAR: return 'M1', same
    if opp is not None and opp[0] <= W_NEAR: return 'M2', opp
    if samefar is not None and W_NEAR < samefar[0] <= W_FAR: return 'M3', samefar
    return 'M4', same

def classify_extra(pool_real, cyc, cp, t):
    same = _nearest(pool_real, cyc, cp, t); opp = _nearest(pool_real, cyc, OPP[cp], t, only_unmatched=True); samefar = _nearest(pool_real, cyc, cp, t, only_unmatched=True)
    if same is not None and same[0] <= W_NEAR: return 'X1', same
    if opp is not None and opp[0] <= W_NEAR: return 'X2', opp
    if samefar is not None and W_NEAR < samefar[0] <= W_FAR: return 'X3', samefar
    return 'X4', same

def inferred_module(r_all_sells_pool, cyc, cp, t, timetable_secs):
    """module of a real sell, inferred (the log has no module label inside the body module): scheduled clock > pair > solo"""
    if any(abs(t - (OPEN_S + 60 + s)) <= 1 for s in timetable_secs): return 'scheduled_clock'
    o = _nearest(r_all_sells_pool, cyc, OPP[cp], t)
    if o is not None and o[0] <= 2: return 'pair'
    return 'solo'

def books_before(df, tcol, ordcols, cyc_col='cyc'):
    """per order: short lots S and long lots L per option type, netted per contract, immediately BEFORE the order (log/sim order). Returns DataFrame aligned to df.index."""
    out = pd.DataFrame(index=df.index, columns=['S_CE', 'L_CE', 'S_PE', 'L_PE'], dtype=float)
    for cyc, g in df.groupby(cyc_col):
        g = g.sort_values(ordcols); net = {}
        for ix, cp, k, side, n in zip(g.index, g.cp, g.strike, g.side, g.lots):
            S = {'CE': 0, 'PE': 0}; L = {'CE': 0, 'PE': 0}
            for (c, _), v in net.items():
                if v < 0: S[c] += -v
                elif v > 0: L[c] += v
            out.loc[ix, ['S_CE', 'L_CE', 'S_PE', 'L_PE']] = [S['CE'], L['CE'], S['PE'], L['PE']]
            net[(cp, float(k))] = net.get((cp, float(k)), 0) + (n if side == 'buy' else -n)
    return out

def book_at_second(df, tcol, cyc, sec, strictly_before=True):
    """book of a DataFrame of orders (any side) of one cycle before second sec (orders with time < sec)"""
    g = df[(df.cyc == cyc) & ((df[tcol] < sec) if strictly_before else (df[tcol] <= sec))]; net = {}
    for cp, k, side, n in zip(g.cp, g.strike, g.side, g.lots): net[(cp, float(k))] = net.get((cp, float(k)), 0) + (n if side == 'buy' else -n)
    S = {'CE': 0, 'PE': 0}; L = {'CE': 0, 'PE': 0}
    for (c, _), v in net.items():
        if v < 0: S[c] += -v
        elif v > 0: L[c] += v
    return S, L

def build_ledgers(real, sim, pairs, timetables):
    """real/sim/pairs as in prepare(); timetables: {cyc: list of scheduled seconds}. Returns (ledger_real, ledger_sim) for body sells only."""
    r, s = prepare(real, sim, pairs); pool_sim = _pool(s, 'sec'); pool_real = _pool(r, 't')
    LR = r[(r.cls == 'body_sell') & (r.side == 'sell')].copy(); LS = s[(s.cls == 'body_sell') & (s.side == 'sell')].copy()
    rc, rn, rd, rpart, rcls = [], [], [], [], []
    for ix, row in LR.iterrows():
        mod = inferred_module(pool_real, row.cyc, row.cp, int(row.t), timetables.get(row.cyc, []))
        if row.m: rc.append('matched'); rn.append(None); rd.append(None)
        else:
            c, nb = classify_missing(r, pool_sim, pool_real, row.cyc, row.cp, int(row.t), ix); rc.append(c); rn.append(nb[0] if nb else None); rd.append(None if nb is None else s.at[nb[2], 'role'] if c in ('M1', 'M3', 'M2') else None)
        rpart.append(mod)
    LR['category'] = rc; LR['nearest_sim_dist'] = rn; LR['nearest_sim_role'] = rd; LR['inferred_module'] = rpart; LR['late'] = (LR.t >= OPEN_S + 345 * 60)
    xc, xn = [], []
    for ix, row in LS.iterrows():
        if row.m: xc.append('matched'); xn.append(None)
        else: c, nb = classify_extra(pool_real, row.cyc, row.cp, int(row.sec)); xc.append(c); xn.append(nb[0] if nb else None)
    LS['category'] = xc; LS['nearest_real_dist'] = xn; LS['late'] = (LS.sec >= OPEN_S + 345 * 60)
    return LR, LS, r, s
