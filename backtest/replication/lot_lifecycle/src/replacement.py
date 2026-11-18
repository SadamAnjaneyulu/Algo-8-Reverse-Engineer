"""Phase 4: strict buy-back -> sale pair analysis (D0, cycles with known carry-in). For every body buy-back ORDER the first body opening-sale order (any right) within 300 s is the candidate. Each (buy-back, candidate) pair gets: same right?, same contract?, strike distance (steps), lot ratio, delay, whether the candidate sits in a scheduled window, whether exposure on that right was restored.
Chance baseline (v2, after review D5): each buy-back time is shifted CIRCULARLY inside the 09:16-15:29 window by a random multiple of 15 min (30..120 min), so clock phase relative to scheduled sale windows is preserved and no draw is dropped; pairing is ONE-TO-ONE (an opening-sale order is consumed by at most one buy-back, chronologically) in observed and null alike; only buy-backs inside the window enter either side. 200 draws, cycle-level bootstrap CIs. Excess = observed / null per pair-type cell. Classification (documented thresholds; procedure, not a rule of the algorithm):
 STRONGLY_SUPPORTED: same right AND lots equal AND delay<=60 s AND not in a scheduled window AND cell excess >= 2 AND no other equal-quality candidate within the window
 POSSIBLE: same right AND (cell excess >= 1.2 OR in scheduled window with equal lots)
 POSSIBLE_CROSS_RIGHT: OPPOSITE right, delay<=60 s, not scheduled, cell excess >= 2 (the cells show opposite-right sales after a buy-back exceed chance more than same-right ones)
 COINCIDENTAL: cell excess < 1.2 OR candidate in a scheduled window with different lots OR opposite right
 UNRESOLVED: no candidate, or several equal-quality candidates, or buy-back is a final-liquidation (>=15:10)
 CONFIRMED: impossible by construction (no parent/allocation id in the export) and never assigned."""
from ledger import *
L = pd.read_csv(f'{OUT}/lots.csv.gz'); F = load_fills(); C = pd.read_csv(f'{OUT}/cycles.csv'); C = C[C.carry_in_known]; rng = np.random.default_rng(8)
body = L[(L.role == 'body') & (L.side == 'SHORT') & (~L.entry_unrecorded)]
op = body.groupby('entry_tag').agg(und=('index', 'first'), expiry=('expiry', 'first'), day=('entry_day', 'first'), sec=('entry_sec', 'first'), cp=('cp', 'first'), strike=('strike', 'first'), lots=('lot_id', 'size')).reset_index()
cb = L[(L.role == 'body') & (L.side == 'SHORT') & (L.close_module == 'num')].groupby('close_tag').agg(und=('index', 'first'), expiry=('expiry', 'first'), day=('close_day', 'first'), sec=('close_sec', 'first'), cp=('cp', 'first'), strike=('strike', 'first'), lots=('lot_id', 'size')).reset_index()
d0 = C.set_index(['und', 'expiry']).d0.to_dict(); op = op[[d0.get((u, e)) == d for u, e, d in zip(op.und, op.expiry, op.day)]]; cb = cb[[d0.get((u, e)) == d for u, e, d in zip(cb.und, cb.expiry, cb.day)]]
def sched(sec):
    mm = (sec // 60) % 60; ss = sec % 60; off = ((mm - 1) % 15) * 60 + ss; off0 = (mm % 15) * 60 + ss
    return ((off < 180) | (off >= 898)) & (sec >= 9 * 3600 + 16 * 60 - 2) | ((off0 < 180) & (sec >= 13 * 3600 + 30 * 60) & (sec <= 15 * 3600 + 3 * 60))
op = op.assign(sched=sched(op.sec.values)); step = {'NIFTY': 50, 'SENSEX': 100}
LO, HI = 9 * 3600 + 16 * 60, 15 * 3600 + 29 * 60 + 59; W = HI - LO + 1
cb_all = len(cb); cb = cb[(cb.sec >= LO) & (cb.sec <= HI)]; print('buy-back orders', cb_all, 'inside 09:16-15:29:', len(cb))
COLS = ['und', 'expiry', 'b_tag', 'b_sec', 'b_cp', 'b_lots', 'has_candidate', 's_tag', 'delay', 'same_right', 'same_contract', 'strike_dist', 'lots_equal', 'lot_ratio', 'sched', 'n_equal_quality', 'late']
def pairs(cb, op, shift=False):
    """one-to-one: buy-backs processed chronologically (after optional circular shift); each takes the earliest still-unassigned opening-sale order at or after its time within 300 s"""
    out = []
    for (u, e), g in cb.groupby(['und', 'expiry']):
        o = op[(op.und == u) & (op.expiry == e)].sort_values('sec'); sa = o.sec.values; ocp = o.cp.values; ost = o.strike.values; ol = o.lots.values; osc = o.sched.values; otag = o.entry_tag.values; used = np.zeros(len(sa), bool)
        t0 = g.sec.values.astype(float); t = LO + np.mod(t0 - LO + rng.integers(2, 9, len(g)) * 900 * rng.choice([-1, 1]), W) if shift else t0; order = np.argsort(t, kind='stable')
        for k in order:
            tk = t[k]; i = np.searchsorted(sa, tk, side='left'); r_cp, r_st, r_l, r_tag = g.cp.values[k], g.strike.values[k], g.lots.values[k], g.close_tag.values[k]; late = bool(g.sec.values[k] >= 15 * 3600 + 10 * 60)
            cand = [j for j in range(i, min(i + 12, len(sa))) if sa[j] <= tk + 300 and not used[j]]
            if not cand: out.append((u, e, r_tag, tk, r_cp, r_l, False) + (None,) * 9 + (late,)); continue
            j = cand[0]; used[j] = True; d = sa[j] - tk; same_r = ocp[j] == r_cp; same_c = same_r and ost[j] == r_st; sd = abs(ost[j] - r_st) / step[u]
            eq = sum(1 for q in cand if ocp[q] == r_cp and ol[q] == r_l and sa[q] - tk <= 60)
            out.append((u, e, r_tag, tk, r_cp, r_l, True, otag[j], d, bool(same_r), bool(same_c), sd, bool(ol[j] == r_l), ol[j] / r_l, bool(osc[j]), eq, late))
    return pd.DataFrame(out, columns=COLS)
def cell(p):
    p = p[p.has_candidate].copy()
    for c_ in ('same_right', 'same_contract', 'lots_equal', 'sched'): p[c_] = p[c_].astype(bool)
    p['delay'] = p.delay.astype(float); p['strike_dist'] = p.strike_dist.astype(float); p['type'] = np.where(p.same_contract, 'same_contract', np.where(p.same_right & (p.strike_dist <= 1), 'same_right_<=1step', np.where(p.same_right, 'same_right_far', 'opposite_right'))); p['dbin'] = pd.cut(p.delay, [-1, 30, 60, 120, 300], labels=['0-30', '30-60', '60-120', '120-300']); p['sch'] = np.where(p.sched, 'sched', 'unsched'); return p
OB = pairs(cb, op); O = cell(OB); NDRAW = 200; null = []; null_cyc = []
for k in range(NDRAW):
    NB = pairs(cb, op, shift=True); N = cell(NB); null.append(N.groupby(['type', 'dbin', 'sch'], observed=True).size())
    null_cyc.append(N.assign(hit=N.same_right & (N.delay <= 60)).groupby(['und', 'expiry']).hit.sum())
NM = pd.concat(null, axis=1).fillna(0); Nm = NM.mean(axis=1).rename('null'); Ob = O.groupby(['type', 'dbin', 'sch'], observed=True).size().rename('obs'); T = pd.concat([Ob, Nm, NM.quantile(.025, axis=1).rename('null_p2.5'), NM.quantile(.975, axis=1).rename('null_p97.5')], axis=1).fillna(0); T['excess_ratio'] = T.obs / T.null.replace(0, np.nan); T['excess_pairs'] = T.obs - T.null; T.to_csv(f'{OUT}/replacement_cells.csv')
pd.set_option('display.width', 250); print('buy-back orders (in-window)', len(OB), 'with candidate <=300 s', int(OB.has_candidate.sum())); print(T[T.obs >= 20].round(2).to_string())
# aggregate rate with cycle bootstrap: P(same-right opening sale within 60 s after a buy-back), observed vs null mean
NC = pd.concat(null_cyc, axis=1).fillna(0).mean(axis=1); OC = O.assign(hit=O.same_right & (O.delay <= 60)).groupby(['und', 'expiry']).hit.sum(); NB_ = OB.groupby(['und', 'expiry']).size(); idx = NB_.index; OC = OC.reindex(idx).fillna(0); NC = NC.reindex(idx).fillna(0); bs = []
for _ in range(2000):
    s_ = rng.integers(0, len(idx), len(idx)); bs.append(OC.values[s_].sum() / max(NC.values[s_].sum(), 1e-9))
print('P(same-right sale <=60 s after buy-back): observed', round(OC.sum() / NB_.sum(), 3), ' null', round(NC.sum() / NB_.sum(), 3), ' ratio', round(OC.sum() / NC.sum(), 2), ' cycle-bootstrap 95% CI', np.round(np.percentile(bs, [2.5, 97.5]), 2))
pd.DataFrame([dict(obs_rate=OC.sum() / NB_.sum(), null_rate=NC.sum() / NB_.sum(), ratio=OC.sum() / NC.sum(), ci_lo=np.percentile(bs, 2.5), ci_hi=np.percentile(bs, 97.5), buybacks=int(NB_.sum()), cycles=len(idx), draws=NDRAW)]).to_csv(f'{OUT}/replacement_headline.csv', index=False)
# classification, with a threshold sensitivity grid (the thresholds are author-chosen, NOT derived)
def klass(r, ex, emin, dmax):
    if not r.has_candidate or r.late: return 'UNRESOLVED'
    key = ('same_contract' if r.same_contract else ('same_right_<=1step' if (r.same_right and r.strike_dist <= 1) else ('same_right_far' if r.same_right else 'opposite_right')), pd.cut([r.delay], [-1, 30, 60, 120, 300], labels=['0-30', '30-60', '60-120', '120-300'])[0], 'sched' if r.sched else 'unsched'); e = ex.get(key, np.nan)
    if not r.same_right: return 'POSSIBLE_CROSS_RIGHT' if (e >= emin and r.delay <= dmax and not r.sched) else 'COINCIDENTAL'
    if r.n_equal_quality > 1: return 'UNRESOLVED'
    if r.lots_equal and r.delay <= dmax and (not r.sched) and e >= emin: return 'STRONGLY_SUPPORTED'
    if (e >= 1.2) or (r.sched and r.lots_equal): return 'POSSIBLE'
    return 'COINCIDENTAL'
ex = T.excess_ratio.to_dict(); grid = []
for emin in (1.5, 2, 3):
    for dmax in (30, 60, 120):
        cl = pd.Series([klass(r, ex, emin, dmax) for r in OB.itertuples()]); grid.append(dict(excess_min=emin, delay_max=dmax, **cl.value_counts().to_dict()))
G = pd.DataFrame(grid).fillna(0); G.to_csv(f'{OUT}/replacement_threshold_grid.csv', index=False); print(G.to_string(index=False))
OB['classification'] = [klass(r, ex, 2, 60) for r in OB.itertuples()]; OB.to_csv(f'{OUT}/replacement_pairs.csv.gz', index=False)
cnt = OB.classification.value_counts(); print('primary thresholds (2, 60 s):', cnt.to_dict(), (cnt / len(OB)).round(3).to_dict()); print('lots in each class:', OB.groupby('classification').b_lots.sum().to_dict())
