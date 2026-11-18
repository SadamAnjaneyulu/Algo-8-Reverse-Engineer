"""One-to-one event matching with a time WINDOW (remediation of defect C). Replaces the legacy fixed bins (j//2, j//10).
Method: within each group (cycle, right[, strike]) an optimal one-to-one assignment (Hungarian algorithm, scipy) minimises the total |time difference| subject to |dt| <= tolerance; unit lots are matched individually so a lot can never match twice; unmatched simulated and actual lots are returned, not forced.
Timestamps: actual fills are whole seconds; simulated decisions are minute-resolution (bar open at second 0 of the minute) -> tolerances below one minute test coincidence with the minute's first seconds only; report several."""
import numpy as np, pandas as pd
from scipy.optimize import linear_sum_assignment


def match(sim, act, tol_s, strike='any', group=('und', 'expiry', 'cp')):
    """sim, act: DataFrames with columns group + ['sec', 'lots'] (+ 'strike'); lots are expanded to unit rows. returns dict(matched, sim_unmatched, act_unmatched, pairs DataFrame)"""
    keys = list(group) + (['strike'] if strike == 'same' else [])
    sim = sim.reset_index(drop=True); act = act.reset_index(drop=True)                     # duplicate index labels would corrupt the repeat below
    S = sim.loc[sim.index.repeat(sim.lots.astype(int))].reset_index(drop=True); A = act.loc[act.index.repeat(act.lots.astype(int))].reset_index(drop=True); pairs = []; ms = set(); ma = set()
    sg = {k: g for k, g in S.groupby(keys)}; ag = {k: g for k, g in A.groupby(keys)}
    for k, g in sg.items():
        h = ag.get(k)
        if h is None: continue
        cost = np.abs(g.sec.values[:, None] - h.sec.values[None, :]).astype(float); big = 1e9; c = np.where(cost <= tol_s, cost, big)
        r, cidx = linear_sum_assignment(c)
        for i, j in zip(r, cidx):
            if c[i, j] < big: pairs.append((g.index[i], h.index[j], cost[i, j])); ms.add(g.index[i]); ma.add(h.index[j])
    P = pd.DataFrame(pairs, columns=['sim_idx', 'act_idx', 'abs_dt_s'])
    return dict(matched=len(P), sim_lots=len(S), act_lots=len(A), precision=len(P) / len(S) if len(S) else np.nan, recall=len(P) / len(A) if len(A) else np.nan, sim_unmatched=len(S) - len(ms), act_unmatched=len(A) - len(ma), pairs=P)


def match_binned_legacy(sim, act, bin_s, strike='any', group=('und', 'expiry', 'cp')):
    """legacy fixed-bin count matching (kept only to reproduce the old verdicts)"""
    keys = list(group) + (['strike'] if strike == 'same' else []) + ['b']
    s = sim.assign(b=(sim.sec // bin_s).astype(int)).groupby(keys).lots.sum(); a = act.assign(b=(act.sec // bin_s).astype(int)).groupby(keys).lots.sum(); m = pd.concat([s, a], axis=1).fillna(0); m.columns = ['s', 'a']; mt = np.minimum(m.s, m.a).sum()
    return dict(matched=mt, sim_lots=m.s.sum(), act_lots=m.a.sum(), precision=mt / m.s.sum() if m.s.sum() else np.nan, recall=mt / m.a.sum() if m.a.sum() else np.nan)
