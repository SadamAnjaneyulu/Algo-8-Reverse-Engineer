"""Combined D-1 selling reconstruction: every real D-1 body sell lot (CE/PE) vs the three decoded sell rules run together.
Scheduled: version timetable (33 waves, fixed seconds), each wave 1 CE + 1 PE at the strike nearest the previous minute's close.
Reactive: first intrabar break of the previous two clock-aligned 30-min candles' true high/low, per side per candle, 10:30-15:15; 1 CE + 1 PE at ATM +/- 1 step.
Solo (the stated rule): every minute, if the previous minute's close is a fresh LOW of the last N closes -> sell 1 CE; fresh HIGH -> sell 1 PE (ATM); N = 15 (also 5, 30).
Matching: one-to-one by lot, same cycle and right, within +-tol minutes (tol 0/1/2); strike agreement reported for matched lots.
Outputs bl_all_sells_type.csv, bl_all_sells_combined.csv, bl_all_sells_cycles.csv, bl_summary_all1.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
exec(open('bl_dq_final.py').read().split("rows = []\nfor nm, fn")[0])
R = {}; O = load_orders(); W = pd.read_csv(f'{OUT}/bl_react_wave_clock.csv'); CYv = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); ch = Chain()
def actual(d):
    u, e = d['und'], d['expiry']; s = O[(O.und == u) & (O.expiry == e) & (O.dayno == 0) & (O.module == 'num') & (O.role == 'open_short')].sort_values('te'); g = Pr[(Pr.und == u) & (Pr.expiry == e)]
    rows = []; used = set()
    for o in s.itertuples():
        typ = 'solo'
        cand = g[(g.strike == o.strike) & ((g.te - o.te).abs() <= 3)]
        for p in cand.itertuples():
            key = (p.Index, o.cp)
            if key not in used: used.add(key); typ = 'scheduled' if p.sched else 'reactive'; break
        for _ in range(int(o.lots)): rows.append(dict(j=int((o.te - 33300) // 60), cp=o.cp, strike=int(o.strike), typ=typ))
    return pd.DataFrame(rows)
def preds(d, solo_N=15, solo_on=True):
    K = np.array(ch.cyc(d['und'], d['expiry'])['strikes'], float); near = lambda x: K[np.argmin(np.abs(K - x))]; c = d['c']; step = d['step']; out = []
    ver = CYv[(CYv.und == d['und']) & (CYv.expiry == d['expiry'])].version.iloc[0]
    for w in W[W.version == ver].itertuples():
        j = int((33360 + w.sec_after_0916 - 33300) // 60); k = near(c[max(j - 1, 0)])
        for cp in ('CE', 'PE'): out.append(dict(j=j, cp=cp, strike=int(k), typ='scheduled'))
    for j, s in machv(d):
        k = near(c[max(j - 1, 0)]) + s * step
        for cp in ('CE', 'PE'): out.append(dict(j=j, cp=cp, strike=int(k), typ='reactive'))
    if solo_on:
        for j in range(solo_N + 1, 375):
            prev = c[j - 1]; w_ = c[j - 1 - solo_N:j - 1]
            if prev < w_.min(): out.append(dict(j=j, cp='CE', strike=int(near(prev)), typ='solo'))
            elif prev > w_.max(): out.append(dict(j=j, cp='PE', strike=int(near(prev)), typ='solo'))
    return pd.DataFrame(out)
def match(A, Pd, tol, need_strike=False):
    """one-to-one greedy by time distance within cycle & right; returns list of (a_idx, p_idx)"""
    pairs = []
    for cp in ('CE', 'PE'):
        a = A[A.cp == cp]; p = Pd[Pd.cp == cp]; used = set()
        cand = []
        for ia, ra in a.iterrows():
            near_p = p[(p.j - ra.j).abs() <= tol]
            if need_strike: near_p = near_p[near_p.strike == ra.strike]
            for ip, rp in near_p.iterrows(): cand.append((abs(rp.j - ra.j), ia, ip))
        ua = set()
        for dist, ia, ip in sorted(cand):
            if ia in ua or ip in used: continue
            ua.add(ia); used.add(ip); pairs.append((ia, ip))
    return pairs
ACT = {d['cid']: actual(d) for d in CYC}; PRD = {d['cid']: preds(d) for d in CYC}
rows = []; comb = []
for tol in (0, 1, 2):
    for typ in ('scheduled', 'reactive', 'solo'):
        na = npred = nm = nm_str = 0
        for d in CYC:
            A = ACT[d['cid']]; Pd = PRD[d['cid']]; A_ = A[A.typ == typ]; P_ = Pd[Pd.typ == typ]; m = match(A_, P_, tol); na += len(A_); npred += len(P_); nm += len(m); nm_str += sum(int(A_.loc[a].strike == P_.loc[p].strike) for a, p in m)
        rows.append(dict(tolerance_min=tol, sell_type=typ, actual_lots=na, predicted_lots=npred, matched=nm, precision=nm / max(npred, 1), recall=nm / max(na, 1), F1=2 * nm / max(na + npred, 1), strike_exact_of_matched=nm_str / max(nm, 1)))
    for nm_, filt in (('all three rules vs all D-1 sells', None), ('scheduled + reactive only vs all D-1 sells', ('scheduled', 'reactive'))):
        na = npred = nm = nm_str = 0
        for d in CYC:
            A = ACT[d['cid']]; Pd = PRD[d['cid']]; P_ = Pd if filt is None else Pd[Pd.typ.isin(filt)]; m = match(A, P_, tol); na += len(A); npred += len(P_); nm += len(m); nm_str += sum(int(A.loc[a].strike == P_.loc[p].strike) for a, p in m)
        comb.append(dict(tolerance_min=tol, model=nm_, actual_lots=na, predicted_lots=npred, matched=nm, precision=nm / npred, recall=nm / na, F1=2 * nm / (na + npred), strike_exact_of_matched=nm_str / max(nm, 1)))
T = pd.DataFrame(rows); C = pd.DataFrame(comb); T.round(4).to_csv(f'{OUT}/bl_all_sells_type.csv', index=False); C.round(4).to_csv(f'{OUT}/bl_all_sells_combined.csv', index=False)
print(T.round(3).to_string(index=False)); print(C.round(3).to_string(index=False))
# solo look-back variants and per-cycle totals
sv = []
for N in (5, 10, 15, 20, 30, 60):
    na = npred = nm = 0
    for d in CYC:
        A = ACT[d['cid']]; A_ = A[A.typ == 'solo']; P_ = preds(d, N); P_ = P_[P_.typ == 'solo']; m = match(A_, P_, 1); na += len(A_); npred += len(P_); nm += len(m)
    sv.append(dict(solo_lookback_min=N, actual=na, predicted=npred, matched=nm, precision=nm / npred, recall=nm / na, F1=2 * nm / (na + npred)))
SV = pd.DataFrame(sv); SV.round(4).to_csv(f'{OUT}/bl_all_sells_solo_N.csv', index=False); print(SV.round(3).to_string(index=False))
cy = []
for d in CYC:
    A = ACT[d['cid']]; Pd = PRD[d['cid']]; cy.append(dict(und=d['und'], expiry=d['expiry'], **{f'actual_{t}': int((A.typ == t).sum()) for t in ('scheduled', 'reactive', 'solo')}, **{f'pred_{t}': int((Pd.typ == t).sum()) for t in ('scheduled', 'reactive', 'solo')}))
CC = pd.DataFrame(cy); CC.to_csv(f'{OUT}/bl_all_sells_cycles.csv', index=False); print(CC.describe().round(1).T[['mean', 'std', 'min', 'max']])
R['by_type'] = T.round(4).to_dict('records'); R['combined'] = C.round(4).to_dict('records'); R['solo_N'] = SV.round(4).to_dict('records'); R['actual_share'] = {t: float(sum((ACT[i].typ == t).sum() for i in ACT) / sum(len(ACT[i]) for i in ACT)) for t in ('scheduled', 'reactive', 'solo')}
from scipy.stats import spearmanr
for t in ('scheduled', 'reactive', 'solo'): R[f'cycle_corr_{t}'] = [float(v) for v in spearmanr(CC[f'actual_{t}'], CC[f'pred_{t}'])]
print(R['actual_share']); rec('all1', R)
