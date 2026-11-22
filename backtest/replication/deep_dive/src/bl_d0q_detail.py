"""D0 scheduled pairs, full detail for one cycle (usage: python bl_d0q_detail.py [cid]; default 4) + a leave-one-cycle-out recurrence test for all cycles.
Per pair of the cycle: pair time, CE / PE order times, strike, lots per right, fill prices, spot at the previous minute close, ATM strike of that close, on the cycle's own D-1 clock (+-3 s of a D-1 scheduled pair),
recurs in OTHER cycles of the group (waves learned without this cycle, +-3 s), and a null (the same waves shifted +137 s).
Pooled test (all cycles): share of pairs that recur in the other cycles, by whether they are on the D-1 clock.
Outputs bl_d0q_detail<cid>.csv, bl_d0q_loo.csv, bl_summary_d0q3.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
src = open('bl_d0s_tt.py').read(); exec(src[:src.index('WALL = waves(D0C)')])
cid_ = int(sys.argv[1]) if len(sys.argv) > 1 else 4; P1 = pd.read_csv(f'{OUT}/bl_react_pairs.csv'); P1 = P1[P1.sched]; CYi = {(r.und, r.expiry): i for i, r in enumerate(CY.itertuples())}; P1['cid'] = [CYi.get((u, e)) for u, e in zip(P1.und, P1.expiry)]
hm = lambda t: f'{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{int(t % 60):02d}'; R = {}
WALL = waves(D0C); wl = {g: WALL[(WALL.und == g[0]) & (WALL.version == g[1])].t.values for g in sorted({GRP(i) for i in D0C})}
PS['sched_all'] = [len(wl[GRP(i)]) > 0 and np.min(np.abs(wl[GRP(i)] - t)) <= 3 for i, t in zip(PS.cid, PS.t0)]; SP_ = PS[PS.sched_all].copy()
# leave-one-cycle-out recurrence
rows = []
for i in D0C:
    g = GRP(i); tr = [c for c in D0C if GRP(c) == g and c != i]
    if len(tr) < 2: continue
    W = waves(tr); W = W[(W.und == g[0]) & (W.version == g[1])].t.values
    a = P1[P1.cid == i].te.values; mine = SP_[SP_.cid == i]
    for x in mine.itertuples():
        rows.append(dict(cid=i, group=f'{g[0]} {g[1]}', t=x.t0, on_D1_clock=bool(len(a) and np.min(np.abs(a - x.t0)) <= 3), recurs_in_other_cycles=bool(len(W) and np.min(np.abs(W - x.t0)) <= 3), null_shift137=bool(len(W) and np.min(np.abs(W + 137 - x.t0)) <= 3), lots=int(x.lots)))
L = pd.DataFrame(rows); L.to_csv(f'{OUT}/bl_d0q_loo.csv', index=False)
tab = L.groupby(['group', 'on_D1_clock']).agg(pairs=('t', 'size'), recur=('recurs_in_other_cycles', 'mean'), null=('null_shift137', 'mean')).reset_index(); print(tab.round(3).to_string(index=False))
R['loo_pooled'] = dict(pairs=int(len(L)), recur=float(L.recurs_in_other_cycles.mean()), null=float(L.null_shift137.mean()), recur_on_D1_clock=float(L[L.on_D1_clock].recurs_in_other_cycles.mean()), recur_extra=float(L[~L.on_D1_clock].recurs_in_other_cycles.mean()), null_extra=float(L[~L.on_D1_clock].null_shift137.mean()),
                       n_on_D1_clock=int(L.on_D1_clock.sum()), n_extra=int((~L.on_D1_clock).sum()))
R['loo_by_group_extra'] = {f'{g}': dict(pairs=int(len(d)), recur=float(d.recurs_in_other_cycles.mean())) for g, d in L[~L.on_D1_clock].groupby('group')}; print(R['loo_pooled'])
# one cycle in detail
i = cid_; r = CY.iloc[i]; sp = SP[(r.und, r.expiry)]; K = M[i]['K']; c = sp.close.values; mine = SP_[SP_.cid == i].sort_values('t0'); a = P1[P1.cid == i].te.values; det = []
for x in mine.itertuples():
    o = S[(S.cid == i) & (S.pid == x.pid)].sort_values('cp'); ce = o[o.cp == 'CE'].iloc[0]; pe = o[o.cp == 'PE'].iloc[0]; j = int((x.t0 - 33300) // 60); c0 = c[j - 1] if j > 0 else c[0]; atm = float(K[np.argmin(np.abs(K - c0))])
    lo = L[(L.cid == i) & (np.abs(L.t - x.t0) < 1e-6)]
    det.append(dict(time=hm(x.t0), CE_order=hm(ce.tod), PE_order=hm(pe.tod), strike=int(ce.strike), lots_CE=int(ce.lots), lots_PE=int(pe.lots), px_CE=round(float(ce.px), 1), px_PE=round(float(pe.px), 1), spot_prev_min_close=round(float(c0), 1), ATM_of_prev_close=int(atm), strike_is_that_ATM=bool(atm == ce.strike),
                    on_D1_clock=bool(np.min(np.abs(a - x.t0)) <= 3) if len(a) else False, recurs_in_other_cycles=bool(lo.recurs_in_other_cycles.iloc[0]) if len(lo) else None, seconds=float(x.t0)))
DT = pd.DataFrame(det); DT.to_csv(f'{OUT}/bl_d0q_detail{i}.csv', index=False)
tot = S[S.cid == i]; R['cycle'] = dict(cid=i, und=r.und, expiry=r.expiry, pairs=len(DT), lots_in_scheduled_pairs=int(DT.lots_CE.sum() + DT.lots_PE.sum()), total_D0_body_sell_lots=int(tot.lots.sum()), pairs_with_1_lot=int(((DT.lots_CE == 1) & (DT.lots_PE == 1)).sum()), pairs_with_more_lots=int(((DT.lots_CE > 1) | (DT.lots_PE > 1)).sum()),
                                       on_D1_clock=int(DT.on_D1_clock.sum()), extra=int((~DT.on_D1_clock).sum()), recur_in_other_cycles=int(DT.recurs_in_other_cycles.fillna(False).sum()), recur_extra=int(DT[~DT.on_D1_clock].recurs_in_other_cycles.fillna(False).sum()), strike_is_ATM=int(DT.strike_is_that_ATM.sum()),
                                       same_second_groups={k: int(v) for k, v in DT.groupby('time').size().loc[lambda s: s > 1].items()}, ce_to_pe_gap_s_median=float(np.median([abs(S[(S.cid == i) & (S.pid == p) & (S.cp == 'CE')].tod.iloc[0] - S[(S.cid == i) & (S.pid == p) & (S.cp == 'PE')].tod.iloc[0]) for p in mine.pid])))
rec('d0q3', R); print(R['cycle']); print(DT.drop(columns='seconds').head(12).to_string(index=False))
