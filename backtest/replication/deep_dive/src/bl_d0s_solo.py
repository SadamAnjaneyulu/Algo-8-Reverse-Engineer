"""D0 chunk 1, addendum 1c (plan reports/D0_SELLS_PLAN.md): competing machines for D0 solo sells, grid-fitted on one cycle half (cid parity), scored on the other.
M1 spot ladder (X steps, fresh-extreme gate, lots 1 or steps crossed), M2 premium ladder (last-sold contract's minute low delta below the reference; roll to the strike
whose premium is nearest the last real sale premium), M3 counter-sell r x real buy-back lots on the other right, M4 union M1/M2 + M3. Resets at real pair sales; activity before the real stop.
Lot F1 at +-1 minute on solo lots (minute only; histogram matcher: exact minute first, then the minute before, then after).
Outputs bl_d0s_solo.csv, bl_d0s_solo_grid.csv, bl_summary_d0s3.json"""
import sys, warnings, itertools; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
src = open('bl_d0s_tt.py').read(); exec(src[:src.index('WALL = waves(D0C)')])
SO = S[S.lab == 'solo']; NJ = 376
def hist(js, w=None):
    a = np.zeros(NJ, int); np.add.at(a, np.clip(np.asarray(js, int), 0, NJ - 1), 1 if w is None else np.asarray(w, int)); return a
def mt(a, p):
    a = a.copy(); p = p.copy(); m = np.minimum(a, p); n = int(m.sum()); a -= m; p -= m
    for j in range(NJ):
        if a[j] == 0: continue
        for jj in (j - 1, j + 1):
            if 0 <= jj < NJ and a[j] and p[jj]: x = min(a[j], p[jj]); a[j] -= x; p[jj] -= x; n += x
    return n
REALH = {(i, cp): hist(SO[(SO.cid == i) & (SO.cp == cp)].j, SO[(SO.cid == i) & (SO.cp == cp)].lots) for i in D0C for cp in ('CE', 'PE')}
PAIRJ = {(i, cp): sorted(S[(S.cid == i) & (S.cp == cp) & (S.pid >= 0)].j.unique().tolist()) for i in D0C for cp in ('CE', 'PE')}
PAIRP = {}
for i in D0C:
    for cp in ('CE', 'PE'):
        g = S[(S.cid == i) & (S.cp == cp) & (S.pid >= 0)].sort_values('tod'); PAIRP[(i, cp)] = list(zip(g.j, g.strike, g.px))
JSTOP = {i: int(min((STOP[i] - 33300) // 60, 375)) for i in D0C}
def m1(i, X, G, mult):
    d = M[i]; h, l, c, st = d['h'], d['l'], d['c'], X * d['step']; out = {}
    for cp in ('CE', 'PE'):
        evs = PAIRJ[(i, cp)]; ptr = 0; refp = None; a = np.zeros(NJ, int)
        for j in range(1, min(375, JSTOP[i])):
            while ptr < len(evs) and evs[ptr] < j: refp = c[max(evs[ptr] - 1, 0)]; ptr += 1
            if refp is None: continue
            if G and not ((l[j] < l[max(j - G, 0):j].min()) if cp == 'CE' else (h[j] > h[max(j - G, 0):j].max())): continue
            dv = (refp - l[j]) if cp == 'CE' else (h[j] - refp)
            if dv > st: n = int(dv // st); a[j] += min(n, 10) if mult else 1; refp = refp - n * st if cp == 'CE' else refp + n * st
        out[cp] = a
    return out
def m2(i, dl, mult):
    d = M[i]; op = d['op']; ki = d['ki']; K = d['K']; out = {}
    for cp in ('CE', 'PE'):
        ev = PAIRP[(i, cp)]; ptr = 0; kref = None; pref = None; p0 = None; a = np.zeros(NJ, int); lo_ = op[(cp, 'low')]; cl = op[(cp, 'close')]
        for j in range(1, min(375, JSTOP[i])):
            while ptr < len(ev) and ev[ptr][0] < j: _, kref, pref = ev[ptr]; p0 = pref; ptr += 1
            if kref is None or int(kref) not in ki: continue
            x = lo_[ki[int(kref)], j]
            if not (x == x) or x <= 0: continue
            if x <= pref * (1 - dl):
                n = max(1, int(np.floor(np.log(x / pref) / np.log(1 - dl)))); a[j] += min(n, 10) if mult else 1
                col = cl[:, j]; ok = np.isfinite(col)
                if ok.any(): kk = K[ok][np.argmin(np.abs(col[ok] - p0))]; kref = kk; pref = float(cl[ki[int(kk)], j])
        out[cp] = a
    return out
def m3(i, r):
    out = {}
    for cp in ('CE', 'PE'):
        o = 'PE' if cp == 'CE' else 'CE'; b = B[(B.cid == i) & (B.cp == o) & (B.tod < STOP[i])].sort_values('tod'); a = np.zeros(NJ, int); acc = 0.0
        for j, n in zip(b.j, b.lots): acc += r * n; k = int(acc); acc -= k; a[min(j, NJ - 1)] += k
        out[cp] = a
    return out
CFG1 = list(itertools.product((0.05, 0.1, 0.2, 0.3, 0.5), (0, 15, 30, 60), (False, True))); CFG2 = list(itertools.product((0.02, 0.03, 0.05, 0.08, 0.12), (False, True))); CFG3 = (0.25, 0.5, 1.0, 2.0)
F1c = {c: {i: m1(i, *c) for i in D0C} for c in CFG1}; F2c = {c: {i: m2(i, *c) for i in D0C} for c in CFG2}; F3c = {c: {i: m3(i, c) for i in D0C} for c in CFG3}
def sc(get, cids):
    tp = ns = nr = 0; per = []
    for i in cids:
        x = [0, 0, 0]
        for cp in ('CE', 'PE'): p = get(i)[cp]; a = REALH[(i, cp)]; x[0] += mt(a, p); x[1] += int(p.sum()); x[2] += int(a.sum())
        per.append(tuple(x))
    return per
f1p = lambda per: 2 * sum(x[0] for x in per) / max(sum(x[1] + x[2] for x in per), 1)
fams = {'M1 spot ladder': [(c, (lambda c: lambda i: F1c[c][i])(c)) for c in CFG1], 'M2 premium ladder': [(c, (lambda c: lambda i: F2c[c][i])(c)) for c in CFG2], 'M3 counter-sell on real buy-backs': [(c, (lambda c: lambda i: F3c[c][i])(c)) for c in CFG3]}
un = []
for nm, F in (('M1', F1c), ('M2', F2c)):
    for c, c3 in itertools.product(F, CFG3): un.append(((nm, c, c3), (lambda F, c, c3: lambda i: {cp: F[c][i][cp] + F3c[c3][i][cp] for cp in ('CE', 'PE')})(F, c, c3)))
fams['M4 union ladder + counter-sell'] = un; fams['D-1 ladder unchanged (X 0.2, gate 60, 1 lot)'] = [((0.2, 60, False), lambda i: F1c[(0.2, 60, False)][i])]
rows = []; grid = []
for nm, cands in fams.items():
    per_te = []; chosen = []
    for half in (0, 1):
        tr = [i for i in D0C if i % 2 != half]; te = [i for i in D0C if i % 2 == half]; best = None
        for c, g in cands:
            v = f1p(sc(g, tr)); grid.append(dict(family=nm, half=half, cfg=str(c), F1_train=v))
            if best is None or v > best[0]: best = (v, c, g)
        chosen.append(str(best[1])); per_te += sc(best[2], te)
    f, lo, hi = boot([x for x in per_te]); a = np.array(per_te)
    rows.append(dict(machine=nm, F1=f, ci_lo=lo, ci_hi=hi, precision=a[:, 0].sum() / max(a[:, 1].sum(), 1), recall=a[:, 0].sum() / max(a[:, 2].sum(), 1), sim_lots=int(a[:, 1].sum()), real_lots=int(a[:, 2].sum()), chosen=' | '.join(chosen)))
# placebo for the chosen M4: cycle-permuted market for the ladder part (buy-backs real)
T = pd.DataFrame(rows)

# placebos (acceptance rule): chosen M1 config on cycle-permuted spot; M3 r = 0.5 with buy-back times shifted +-10 min
Mreal = dict(M)
def perm_m1(c):
    per = []
    for n, i in enumerate(D0C):
        M[i] = Mreal[D0C[(n + 1) % len(D0C)]]; g = m1(i, *c); M[i] = Mreal[i]; per += sc(lambda _i: g, [i])
    return per
pl = []
for c in ((0.05, 60, True), (0.1, 60, True)):
    pp = perm_m1(c); f, lo, hi = boot(pp); a = np.array(pp); pl.append(dict(machine=f'placebo M1 {c} on cycle-permuted spot (all cycles)', F1=f, ci_lo=lo, ci_hi=hi, precision=a[:, 0].sum() / max(a[:, 1].sum(), 1), recall=a[:, 0].sum() / max(a[:, 2].sum(), 1), sim_lots=int(a[:, 1].sum()), real_lots=int(a[:, 2].sum()), chosen='placebo'))
    pp = sc(lambda i, c=c: F1c[c][i], D0C); f, lo, hi = boot(pp); a = np.array(pp); pl.append(dict(machine=f'M1 {c} real spot (all cycles, same config, for the placebo comparison)', F1=f, ci_lo=lo, ci_hi=hi, precision=a[:, 0].sum() / max(a[:, 1].sum(), 1), recall=a[:, 0].sum() / max(a[:, 2].sum(), 1), sim_lots=int(a[:, 1].sum()), real_lots=int(a[:, 2].sum()), chosen='reference'))
Breal = B.copy()
for shv in (600, -600):
    B = Breal.assign(tod=Breal.tod + shv, j=((Breal.tod + shv - 33300) // 60).astype(int).clip(0, 375)); pp = sc(lambda i: m3(i, 0.5), D0C); f, lo, hi = boot(pp); a = np.array(pp)
    pl.append(dict(machine=f'placebo M3 r 0.5, buy-backs shifted {shv:+d} s', F1=f, ci_lo=lo, ci_hi=hi, precision=a[:, 0].sum() / max(a[:, 1].sum(), 1), recall=a[:, 0].sum() / max(a[:, 2].sum(), 1), sim_lots=int(a[:, 1].sum()), real_lots=int(a[:, 2].sum()), chosen='placebo'))
B = Breal; pp = sc(lambda i: m3(i, 0.5), D0C); f, lo, hi = boot(pp); a = np.array(pp)
pl.append(dict(machine='M3 r 0.5 real buy-back times (all cycles, reference)', F1=f, ci_lo=lo, ci_hi=hi, precision=a[:, 0].sum() / max(a[:, 1].sum(), 1), recall=a[:, 0].sum() / max(a[:, 2].sum(), 1), sim_lots=int(a[:, 1].sum()), real_lots=int(a[:, 2].sum()), chosen='reference'))
# post-hoc: grid-boundary check (finer steps, longer gates), out-of-fold the same way
ext = list(itertools.product((0.02, 0.03, 0.05), (60, 90, 120), (True,))); Fx = {c: {i: m1(i, *c) for i in D0C} for c in ext}; per_te = []; ch = []
for half in (0, 1):
    tr = [i for i in D0C if i % 2 != half]; te = [i for i in D0C if i % 2 == half]; best = max(ext, key=lambda c: f1p(sc(lambda i: Fx[c][i], tr))); ch.append(str(best)); per_te += sc(lambda i: Fx[best][i], te)
f, lo, hi = boot(per_te); a = np.array(per_te); pl.append(dict(machine='post-hoc: M1 extended grid (X 0.02-0.05, gate 60-120)', F1=f, ci_lo=lo, ci_hi=hi, precision=a[:, 0].sum() / max(a[:, 1].sum(), 1), recall=a[:, 0].sum() / max(a[:, 2].sum(), 1), sim_lots=int(a[:, 1].sum()), real_lots=int(a[:, 2].sum()), chosen=' | '.join(ch)))
T = pd.concat([T, pd.DataFrame(pl)], ignore_index=True)
T.to_csv(f'{OUT}/bl_d0s_solo.csv', index=False); pd.DataFrame(grid).to_csv(f'{OUT}/bl_d0s_solo_grid.csv', index=False); print(T.round(3).to_string(index=False))
# descriptive (quoted in addendum 1c): solo bursts (gap <= 30 s, same right) vs other-right buy-backs within 90 s of the burst
bu = []
for (i, cp), g in SO[SO.cid.isin(D0C)].groupby(['cid', 'cp']):
    g = g.sort_values('tod'); gid = (g.tod.diff().fillna(1e9) > 30).cumsum()
    for _, x in g.groupby(gid):
        t0, t1 = x.tod.min(), x.tod.max(); o = 'PE' if cp == 'CE' else 'CE'; b = B[(B.cid == i) & (B.cp == o) & (B.tod >= t0 - 90) & (B.tod <= t1 + 90)]
        bu.append(dict(lots=x.lots.sum(), prem=(x.lots * x.px).sum(), ob_lots=b.lots.sum(), ob_prem=(b.lots * b.px).sum(), ob_dt=(b.tod.min() - t0) if len(b) else np.nan))
BU = pd.DataFrame(bu); xb = BU[BU.ob_lots > 0]
DESC = dict(bursts=len(BU), share_bursts_with_other_bb=float((BU.ob_lots > 0).mean()), lots_share=float(xb.lots.sum() / BU.lots.sum()), dt_q=xb.ob_dt.quantile([.1, .25, .5, .75, .9]).tolist(), lots_ratio_q=(xb.lots / xb.ob_lots).quantile([.1, .25, .5, .75, .9]).tolist(), prem_ratio_q=(xb.prem / xb.ob_prem).quantile([.1, .25, .5, .75, .9]).tolist())
print(DESC)
R = {r.machine: dict(F1=round(r.F1, 4), precision=round(r.precision, 4), recall=round(r.recall, 4), chosen=r.chosen) for r in T.itertuples()}; R['burst_coupling'] = DESC; rec('d0s3', R)
