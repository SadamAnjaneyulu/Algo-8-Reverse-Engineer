"""Phase 4: strict buy-back -> sale pair analysis (D0, cycles with known carry-in). For every body buy-back ORDER the first body opening-sale order (any right) within 300 s is the candidate. Each (buy-back, candidate) pair gets: same right?, same contract?, strike distance (steps), lot ratio, delay, whether the candidate sits in a scheduled window, whether exposure on that right was restored.
Chance baseline: the same pairing with every buy-back time shifted by +/-20..120 min inside the session (100 draws). Excess = observed / null per pair-type cell. Classification (documented thresholds; procedure, not a rule of the algorithm):
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
def pairs(cb, op, shift=None):
    """vectorised per cycle: first opening sale at or after the buy-back time within 300 s"""
    out = []
    for (u, e), g in cb.groupby(['und', 'expiry']):
        o = op[(op.und == u) & (op.expiry == e)].sort_values('sec'); sa = o.sec.values; ocp = o.cp.values; ost = o.strike.values; ol = o.lots.values; osc = o.sched.values; otag = o.entry_tag.values
        bs = g.sec.values.astype(float); t = bs + (shift(len(g)) if shift else 0.0)
        for k in range(len(g)):
            tk = t[k]
            if shift and not (9 * 3600 + 16 * 60 <= tk <= 15 * 3600 + 29 * 60): continue
            i = np.searchsorted(sa, tk, side='left'); j = i
            while j < len(sa) and sa[j] <= tk + 300 and j < i + 8: j += 1
            r_cp, r_st, r_l, r_tag = g.cp.values[k], g.strike.values[k], g.lots.values[k], g.close_tag.values[k]
            if j == i: out.append((u, e, r_tag, tk, r_cp, r_l, False) + (None,) * 9); continue
            d = sa[i] - tk; same_r = ocp[i] == r_cp; same_c = same_r and ost[i] == r_st; sd = abs(ost[i] - r_st) / step[u]
            eq = int(((ocp[i:j] == r_cp) & (ol[i:j] == r_l) & (sa[i:j] - tk <= 60)).sum())
            out.append((u, e, r_tag, tk, r_cp, r_l, True, otag[i], d, bool(same_r), bool(same_c), sd, bool(ol[i] == r_l), ol[i] / r_l, bool(osc[i]), eq, bool(g.sec.values[k] >= 15 * 3600 + 10 * 60)))
    return pd.DataFrame(out, columns=['und', 'expiry', 'b_tag', 'b_sec', 'b_cp', 'b_lots', 'has_candidate', 's_tag', 'delay', 'same_right', 'same_contract', 'strike_dist', 'lots_equal', 'lot_ratio', 'sched', 'n_equal_quality', 'late'])
def cell(p):
    p = p[p.has_candidate].copy()
    for c_ in ('same_right', 'same_contract', 'lots_equal', 'sched'): p[c_] = p[c_].astype(bool)
    p['delay'] = p.delay.astype(float); p['strike_dist'] = p.strike_dist.astype(float); p['type'] = np.where(p.same_contract, 'same_contract', np.where(p.same_right & (p.strike_dist <= 1), 'same_right_<=1step', np.where(p.same_right, 'same_right_far', 'opposite_right'))); p['dbin'] = pd.cut(p.delay, [-1, 30, 60, 120, 300], labels=['0-30', '30-60', '60-120', '120-300']); p['sch'] = np.where(p.sched, 'sched', 'unsched'); return p
O = cell(pairs(cb, op)); OB = pairs(cb, op); null = []
for k in range(40):
    sg = rng.choice([-1, 1]); N = cell(pairs(cb, op, shift=lambda n: sg * rng.uniform(1200, 7200, n)))
    null.append(N.groupby(['type', 'dbin', 'sch'], observed=True).size())
Nm = pd.concat(null, axis=1).fillna(0).mean(axis=1).rename('null'); Ob = O.groupby(['type', 'dbin', 'sch'], observed=True).size().rename('obs'); T = pd.concat([Ob, Nm], axis=1).fillna(0); T['excess_ratio'] = T.obs / T.null.replace(0, np.nan); T['excess_pairs'] = T.obs - T.null; T.to_csv(f'{OUT}/replacement_cells.csv')
pd.set_option('display.width', 250); print('buy-back orders', len(OB), 'with candidate <=300 s', int(OB.has_candidate.sum())); print(T[T.obs >= 20].round(2).to_string())
# classification
ex = T.excess_ratio.to_dict()
def klass(r):
    if not r.has_candidate or r.late: return 'UNRESOLVED'
    key = ('same_contract' if r.same_contract else ('same_right_<=1step' if (r.same_right and r.strike_dist <= 1) else ('same_right_far' if r.same_right else 'opposite_right')), pd.cut([r.delay], [-1, 30, 60, 120, 300], labels=['0-30', '30-60', '60-120', '120-300'])[0], 'sched' if r.sched else 'unsched'); e = ex.get(key, np.nan)
    if not r.same_right: return 'POSSIBLE_CROSS_RIGHT' if (e >= 2 and r.delay <= 60 and not r.sched) else 'COINCIDENTAL'
    if r.n_equal_quality > 1: return 'UNRESOLVED'
    if r.lots_equal and r.delay <= 60 and (not r.sched) and e >= 2: return 'STRONGLY_SUPPORTED'
    if (e >= 1.2) or (r.sched and r.lots_equal): return 'POSSIBLE'
    return 'COINCIDENTAL'
OB['classification'] = [klass(r) if r.has_candidate else 'UNRESOLVED' for r in OB.itertuples()]; OB.to_csv(f'{OUT}/replacement_pairs.csv.gz', index=False)
cnt = OB.classification.value_counts(); print(cnt.to_dict(), (cnt / len(OB)).round(3).to_dict())
print('lots in each class:', OB.groupby('classification').b_lots.sum().to_dict())
obs60 = ((O.same_right) & (O.delay <= 60)).sum() / len(OB); nul60 = np.mean([n[[(t_ != 'opposite_right') and (d_ in ('0-30', '30-60')) for (t_, d_, s_) in n.index]].sum() for n in null]) / len(OB); print('P(same-right opening sale within 60 s of a buy-back): observed', round(obs60, 3), ' time-shift null', round(nul60, 3))
