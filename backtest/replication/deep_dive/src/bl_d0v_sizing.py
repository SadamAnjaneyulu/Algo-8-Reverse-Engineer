"""D0 sizing treatments in the free-run simulator (plan reports/D0_SIZING_PLAN.md).
sim2 = copy of bl_d0_fr.sim with (a) lot counts of solo-sell events and buy-back events replaced by M0 (unchanged) / A (empirical draw) / B (fixed median), (b) a global scale s,
(c) cash settled at the stop and at the 15:14 clearance so the cycle profit and loss is complete, (d) peak short lots per right.
Integrity check first: M0, s = 1 must reproduce bl_d0_fr_orders.pkl.gz exactly.
Usage: OMP_NUM_THREADS=1 python bl_d0v_sizing.py [check|run]"""
import sys, os, json, warnings, itertools; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
import bl_d0_fr as F
from multiprocessing import Pool
CY, O, OPT, SPT, BK, NT = F.CY, F.O, F.OPT, F.SPT, F.BK, F.NT; D0C = F.D0C; L_STOP = F.L_STOP
PAR = json.load(open(f'{OUT}/bl_d0_fr_params.json')); RES0 = pd.read_pickle(f'{OUT}/bl_d0_fr_orders.pkl.gz')
VM = {'OOF half 0 test': {'V1': 'V1', 'V2': 'V2'}, 'OOF half 1 test': {'V1': 'V1', 'V2': 'V2'}, 'forward A (same version, later cycles)': {'V1': 'V1', 'V2': 'V2'}, 'forward B (train V1, test V2)': {'V2': 'V1', 'V1': 'V1'}}
def srnd(x, rng): f = np.floor(x); return int(f + (rng.random() < x - f))
def make_P(nm):
    p = PAR[nm]; tr = p['train']; W = NT['waves'](tr); Wt = []
    for v_test, v_src in VM[nm].items():
        w = W[W.version == v_src].copy(); w['version'] = v_test; Wt.append(w)
    W = pd.concat(Wt, ignore_index=True) if Wt else W
    PN = pd.read_pickle(f'{OUT}/bl_d0f_panel.pkl.gz'); X = pd.read_pickle(f'{OUT}/bl_d0y_lots.pkl.gz'); X = X[~X.type.astype(str).str.startswith(('1', '2'))]
    solo = PN[(PN.cid.isin(tr)) & (PN.y_lots > 0)].y_lots.astype(int).values; bb = X[X.cid.isin(tr)].groupby(['cid', 'j', 'cp']).size().values
    return dict(W=W, k3=p['k3'], m1=tuple(p['m1']), r=p['r'], ow=p['ow'], solo=solo, bb=bb, solo_med=int(np.median(solo)), bb_med=int(np.median(bb)))
def sim2(i, P, mode='M0', s=1.0, rng=None, order='ratio'):
    """All decisions (triggers, event sizes, which lots) run at the real-size book. The account is a thinned copy: every lot carries a keep flag (probability s, drawn when the lot is created; a scheduled pair is kept as a pair);
    cash, hedge, peak and the cycle stop (level x s) use kept lots only. s = 1 keeps everything and is identical to bl_d0_fr.sim in M0."""
    r = CY.iloc[i]; op = OPT[(r.und, r.expiry)]; K = op['K']; ki = {int(k): x for x, k in enumerate(K)}; sp = SPT[(r.und, r.expiry)]; h, l, c = sp.high.values, sp.low.values, sp.close.values; st = ref.STEP[r.und]; u = float(r.unit)
    def px(cp, k, j, f='close'):
        x = ki.get(int(k)); v = op[(cp, f)][x, min(max(j, 0), 374)] if x is not None else np.nan; return float(v) if v == v else np.nan
    atm = lambda x: float(K[np.argmin(np.abs(K - x))])
    keepf = (lambda: True) if s >= 1 else (lambda: bool(rng.random() < s))
    lots = [[L['cp'], L['strike'], L['entry'], keepf()] for L in BK[i]['at_open']]                  # lot = [cp, strike, entry, kept by the account]
    z1 = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 0)]; sg = np.where(z1.side.str.lower() == 'buy', 1, -1); cash = float((-sg * z1.px_avg * z1.lots * u).sum())
    oth = {}
    for q, s_ in zip(z1.itertuples(), sg):
        if q.module == 'num' and q.role in ('open_short', 'cover_short'): continue
        k = (q.module, q.cp, int(q.strike)); oth[k] = oth.get(k, 0) + s_ * q.lots
    longs = {k: v for k, v in oth.items() if v > 0}; oshort = {k: -v for k, v in oth.items() if v < 0}
    if s < 1:
        longs = {k: int(rng.binomial(v, s)) for k, v in longs.items()}; longs = {k: v for k, v in longs.items() if v > 0}; oshort = {k: int(rng.binomial(v, s)) for k, v in oshort.items()}; oshort = {k: v for k, v in oshort.items() if v > 0}; cash *= s
    LS = L_STOP * s
    W = P['W']; W = W[(W.und == r.und) & (W.version == r.version)]; wv = {}
    for x in W.itertuples(): wv.setdefault(int((x.t - 33300) // 60), []).append(int(x.lots))
    fires = {}
    for j, s_ in NT['fires'](dict(h=h, l=l, c=c, step=st)): fires.setdefault(j, []).append(s_)
    X_, G_, mult = P['m1']; stp = X_ * st; refp = {'CE': None, 'PE': None}; acc = {'CE': 0.0, 'PE': 0.0}; out = []; stopped = False; peak = {'CE': 0, 'PE': 0}; stop_j = None
    rec_ = lambda cls, cp, j, k, n: out.append((cls, cp, j, int(k), int(n)))
    def mtm(j):
        v = cash
        for cp, k, e, kp in lots:
            if not kp: continue
            p = px(cp, k, j)
            if p == p: v -= p * u
        for (m, cp, k), n in longs.items():
            p = px(cp, k, j)
            if p == p: v += n * p * u
        for (m, cp, k), n in oshort.items():
            p = px(cp, k, j)
            if p == p: v -= n * p * u
        return v
    def settle(j):
        nonlocal cash
        for cp, k, e, kp in lots:
            if kp: p = px(cp, k, j); cash -= (p if p == p else (e if e == e else 0)) * u
        for (m, cp, k), n in longs.items(): p = px(cp, k, j); cash += n * (p if p == p else 0) * u
        for (m, cp, k), n in oshort.items(): p = px(cp, k, j); cash -= n * (p if p == p else 0) * u
    for j in range(0, 375):
        if stopped: break
        if mtm(j) <= -LS:
            agg = {}
            for cp, k, e, kp in lots:
                if kp: agg[(cp, k)] = agg.get((cp, k), 0) + 1
            for (m, cp, k), n in list(longs.items()) + list(oshort.items()): agg[(cp, k)] = agg.get((cp, k), 0) + n
            for (cp, k), n in agg.items(): rec_('stop', cp, j, k, n)
            settle(j); lots = []; longs = {}; oshort = {}; stopped = True; stop_j = j; break
        jp = max(j - 1, 0); c0 = c[jp] if j > 0 else sp.open.values[0]
        if j == 359:
            agg = {}
            for cp, k, e, kp in lots:
                if kp: agg[(cp, k)] = agg.get((cp, k), 0) + 1
            for (cp, k), n in agg.items(): rec_('body_buyback', cp, j, k, n)
            for (m, cp, k), n in longs.items(): rec_('body_long' if m == 'num' else 'wing_sell', cp, j, k, n)
            settle(j); lots = []; longs = {}; oshort = {}; break
        nbb = {'CE': 0, 'PE': 0}
        if j >= 1:
            th = P['k3']['theta']; tpv = P['k3'].get('tp')
            if mode == 'M0':
                take = set()
                for n_, (cp, k, e, kp) in enumerate(lots):
                    ph = px(cp, k, j, 'high'); pl = px(cp, k, j, 'low')
                    if e > 0 and ((ph == ph and ph >= th * e) or (tpv and pl == pl and pl <= tpv * e)): take.add(n_)
            else:
                take = set()
                for cp in ('CE', 'PE'):
                    idx = [n_ for n_, L in enumerate(lots) if L[0] == cp]; cross = []; rest = []; rat = {}
                    for n_ in idx:
                        _, k, e, _kp = lots[n_]; ph = px(cp, k, j, 'high'); pl = px(cp, k, j, 'low'); rat[n_] = (ph / e) if (ph == ph and e == e and e > 0) else 0.0
                        (cross if (e > 0 and ((ph == ph and ph >= th * e) or (tpv and pl == pl and pl <= tpv * e))) else rest).append(n_)
                    if not cross: continue
                    m = int(rng.choice(P['bb'])) if mode == 'A' else P['bb_med']
                    ordl = (sorted(cross, key=lambda n_: -rat[n_]) + sorted(rest, key=lambda n_: -rat[n_])) if order == 'ratio' else cross + rest
                    take.update(ordl[:min(m, len(ordl))])
            keep = []
            for n_, L in enumerate(lots):
                if n_ in take:
                    cp, k, e, kp = L; nbb[cp] += 1
                    if kp: rec_('body_buyback', cp, j, k, 1); p = px(cp, k, j); cash -= (p if p == p else e) * u
                else: keep.append(L)
            lots = keep
        sells = []                                                                  # (cp, strike, units, kind); a unit is one lot, pair units are kept jointly
        for n in wv.get(j, []): sells.append(('PAIR', atm(c0), n, 'pair'))
        if 75 <= j <= 360:
            for s_ in fires.get(j, []): sells.append(('PAIR', atm(c0) + s_ * st, 1, 'pair'))
        solo_ev = []
        for cp in ('CE', 'PE'):
            if refp[cp] is None or j < 1: continue
            if G_ and not ((l[j] < l[max(j - G_, 0):j].min()) if cp == 'CE' else (h[j] > h[max(j - G_, 0):j].max())): continue
            dv = (refp[cp] - l[j]) if cp == 'CE' else (h[j] - refp[cp])
            if dv > stp: n = int(dv // stp); solo_ev.append((cp, min(n, 10) if mult else 1)); refp[cp] = refp[cp] - n * stp if cp == 'CE' else refp[cp] + n * stp
        if any(t == 'pair' for *_, t in sells): refp = {'CE': c0, 'PE': c0}
        for cp in ('CE', 'PE'):
            o = 'PE' if cp == 'CE' else 'CE'; acc[cp] += P['r'] * nbb[o]; n = int(acc[cp]); acc[cp] -= n
            if n: solo_ev.append((cp, n))
        for cp, n in solo_ev:
            if mode == 'A': n = int(rng.choice(P['solo']))
            elif mode == 'B': n = P['solo_med']
            if n: sells.append((cp, atm(c0), n, 'solo'))
        for cp, k, n, t in sells:
            if int(k) not in ki: continue
            e = px('CE' if cp == 'PAIR' else cp, k, jp); e = e if e == e else px('CE' if cp == 'PAIR' else cp, k, j)
            if cp == 'PAIR':
                for _ in range(n):
                    kp = keepf()
                    for r_ in ('CE', 'PE'):
                        e_ = px(r_, k, jp); e_ = e_ if e_ == e_ else px(r_, k, j)
                        lots.append([r_, k, e_, kp])
                        if kp: rec_('body_sell', r_, j, k, 1); cash += (e_ if e_ == e_ else 0) * u
            else:
                for _ in range(n):
                    kp = keepf(); lots.append([cp, k, e, kp])
                    if kp: rec_('body_sell', cp, j, k, 1); cash += (e if e == e else 0) * u
        if j == 0 and P['ow']:
            ow = P['ow'] if s >= 1 else srnd(P['ow'] * s, rng)
            for cp, nn in (('CE', ow // 2), ('PE', ow - ow // 2)):
                if nn == 0: continue
                k = atm(c0 + (1 if cp == 'CE' else -1) * 17 * st); rec_('body_long', cp, j, k, nn); longs[('num', cp, int(k))] = longs.get(('num', cp, int(k)), 0) + nn; p = px(cp, k, j); cash -= (p if p == p else 0) * nn * u
        for cp in ('CE', 'PE'):
            S_ = sum(1 for L in lots if L[0] == cp and L[3]) + sum(n for (m, c2, k), n in oshort.items() if c2 == cp); L_ = sum(n for (m, c2, k), n in longs.items() if c2 == cp); g = S_ - L_; peak[cp] = max(peak[cp], S_)
            if g > 0:
                a = px(cp, atm(c0), jp); pr = op[(cp, 'close')][:, jp]; otm = (K - c0) * (1 if cp == 'CE' else -1) > 0; ok = otm & np.isfinite(pr)
                if a == a and ok.any():
                    k = K[ok][np.argmin(np.abs(pr[ok] - 0.025 * a))]; rec_('wing_buy', cp, j, k, g); longs[('h_', cp, int(k))] = longs.get(('h_', cp, int(k)), 0) + g; p = px(cp, k, j); cash -= (p if p == p else 0) * g * u
            elif g < 0:
                need = -g; cand = sorted([(m, c2, k) for (m, c2, k), n in longs.items() if c2 == cp and m in ('h_', 'v_') and n > 0], key=lambda x: -((x[2] - c0) * (1 if cp == 'CE' else -1)))
                for key in cand:
                    if need <= 0: break
                    x = min(need, longs[key]); longs[key] -= x; need -= x; rec_('wing_sell', cp, j, key[2], x); p = px(cp, key[2], j); cash += (p if p == p else 0) * x * u
                    if longs[key] == 0: del longs[key]
    return pd.DataFrame(out, columns=['cls', 'cp', 'j', 'strike', 'lots']), dict(pnl=cash, peak_CE=peak['CE'], peak_PE=peak['PE'], stop_j=stop_j)
# ------------- real comparators
TL = pd.read_pickle(f'{OUT}/bl_d0u_timeline.pkl.gz')
def real_info(i):
    r = CY.iloc[i]; z = O[(O.und == r.und) & (O.expiry == r.expiry)]; u = float(r.unit); sg = np.where(z.side.str.lower() == 'buy', 1, -1); cash = float((-sg * z.px_avg * z.lots * u).sum()); op = OPT[(r.und, r.expiry)]; ki = {int(k): x for x, k in enumerate(op['K'])}
    net = {}
    for cp, k, q in zip(z.cp, z.strike, sg * z.lots): net[(cp, int(k))] = net.get((cp, int(k)), 0) + q
    resid = 0.0
    for (cp, k), q in net.items():
        x = ki.get(k)
        if q != 0 and x is not None:
            p = op[(cp, 'close')][x, 374]; resid += q * (p if p == p else 0) * u
    d0 = z[z.dayno == 1]; st = d0[d0.module == 's_']
    return dict(pnl=cash + resid, cash=cash, resid=resid, peak_CE=float(TL[(i, 'CE')]['S'][:360].max()) if (i, 'CE') in TL else np.nan, peak_PE=float(TL[(i, 'PE')]['S'][:360].max()) if (i, 'PE') in TL else np.nan,
                stop_j=int(((st.tod - 33300) // 60).min()) if len(st) else None)

def null_pnl(i):
    """null comparator: the carried book is held to the 15:14 clearance, nothing is traded on D0 (no stop, no new sells, no hedge)"""
    r = CY.iloc[i]; op = OPT[(r.und, r.expiry)]; ki = {int(k): x for x, k in enumerate(op['K'])}; u = float(r.unit)
    px = lambda cp, k, j: (lambda v: float(v) if v == v else np.nan)(op[(cp, 'close')][ki[int(k)], j]) if int(k) in ki else np.nan
    z1 = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 0)]; sg = np.where(z1.side.str.lower() == 'buy', 1, -1); cash = float((-sg * z1.px_avg * z1.lots * u).sum()); oth = {}
    for q, s_ in zip(z1.itertuples(), sg):
        if q.module == 'num' and q.role in ('open_short', 'cover_short'): continue
        oth[(q.cp, int(q.strike))] = oth.get((q.cp, int(q.strike)), 0) + s_ * q.lots
    for L in BK[i]['at_open']: p = px(L['cp'], L['strike'], 359); cash -= (p if p == p else (L['entry'] if L['entry'] == L['entry'] else 0)) * u
    for (cp, k), n in oth.items(): p = px(cp, k, 359); cash += n * (p if p == p else 0) * u
    return cash
CLS = {('num', 'open_short'): 'body_sell', ('num', 'cover_short'): 'body_buyback', ('h_', 'open_long'): 'wing_buy', ('h_', 'close_long'): 'wing_sell', ('v_', 'close_long'): 'wing_sell', ('num', 'open_long'): 'body_long', ('num', 'close_long'): 'body_long'}
NMOD = ['body_sell', 'body_buyback', 'wing_buy', 'wing_sell', 'body_long', 'stop']; REAL = {}
for i in D0C:
    r = CY.iloc[i]; z = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 1)].copy(); z['cls'] = ['stop' if m == 's_' else CLS.get((m, ro), 'not_modelled') for m, ro in zip(z.module, z.role)]; z['j'] = ((z.tod - 33300) // 60).clip(0, 389).astype(int); REAL[i] = z
def match(rj, rk, sj, sk, tol=1):
    bucket = {}
    for n, j in enumerate(sj): bucket.setdefault(int(j), []).append(n)
    used = np.zeros(len(sj), bool); done = np.zeros(len(rj), bool); dk = []
    for ps in range(tol + 1):
        for a in range(len(rj)):
            if done[a]: continue
            best = None
            for jj in ({rj[a]} if ps == 0 else {rj[a] - ps, rj[a] + ps}):
                for n in bucket.get(int(jj), []):
                    if used[n]: continue
                    d = abs(sk[n] - rk[a])
                    if best is None or d < best[0]: best = (d, n)
            if best: used[best[1]] = True; done[a] = True; dk.append(best[0])
    return np.array(dk)
expand = lambda df: (np.repeat(df.j.values, df.lots.values).astype(int), np.repeat(df.strike.values, df.lots.values).astype(float))
def f1_cycle(i, s_df):
    """per class: (real lots, sim lots, matched) for one cycle"""
    out = {}
    for c in NMOD:
        a = b = tp = 0
        for cp in ('CE', 'PE'):
            rj, rk = expand(REAL[i][(REAL[i].cls == c) & (REAL[i].cp == cp)]); sj, sk = expand(s_df[(s_df.cls == c) & (s_df.cp == cp)]); a += len(rj); b += len(sj)
            if len(rj) and len(sj): tp += len(match(rj, rk, sj, sk))
        out[c] = (a, b, tp)
    return out
# ------------- tasks
G = {}
def task(a):
    nm, i, mode, s, rep, order = a; rng = np.random.default_rng(1000 * rep + 7 * i + 3); o, info = sim2(i, G[nm], mode, s, rng, order); f = f1_cycle(i, o) if s >= 1 else None
    tot = {c: int(o[o.cls == c].lots.sum()) for c in NMOD}
    return dict(split=nm, cid=i, mode=mode, s=s, rep=rep, order=order, f1=f, lots=tot, **info), (o if (mode == 'M0' and s >= 1 and rep == 0) else None)
def check():
    for nm in PAR: G[nm] = make_P(nm)
    bad = 0; n = 0
    for nm in PAR:
        for i in PAR[nm]['test']:
            o, _ = sim2(i, G[nm], 'M0', 1.0, np.random.default_rng(0)); ref_ = RES0[nm][i]; n += 1
            agg = lambda d: d.groupby(['cls', 'cp', 'j', 'strike']).lots.sum().sort_index()
            if not agg(o).equals(agg(ref_)): bad += 1; print('MISMATCH', nm, i, int(o.lots.sum()), int(ref_.lots.sum()))
    print('integrity check: cycles compared', n, 'mismatches', bad); return bad
if __name__ == '__main__':
    mode_ = sys.argv[1] if len(sys.argv) > 1 else 'check'
    if mode_ == 'check': sys.exit(1 if check() else 0)
    if check(): sys.exit('integrity check failed: M0 s=1 does not reproduce the stored simulation')
    REPS = 10; jobs = []
    for nm in PAR:
        te = PAR[nm]['test']
        for i in te:
            jobs += [(nm, i, 'M0', 1.0, 0, 'ratio'), (nm, i, 'B', 1.0, 0, 'ratio'), (nm, i, 'B', 1.0, 0, 'fifo')]
            for rep in range(REPS): jobs += [(nm, i, 'A', 1.0, rep, 'ratio')] + ([(nm, i, 'A', 1.0, rep, 'fifo')] if rep < 5 else [])
    for nm in ('OOF half 0 test', 'OOF half 1 test'):
        for i in PAR[nm]['test']:
            for s in (0.5, 0.25, 0.1):
                for mode in ('M0', 'A', 'B'):
                    for rep in range(REPS): jobs.append((nm, i, mode, s, rep, 'ratio'))
    print('jobs', len(jobs), flush=True); import time; t0 = time.time(); R = []; ORD = {}
    with Pool(4) as pool:
        for n_, (d, o) in enumerate(pool.imap_unordered(task, jobs, chunksize=8)):
            R.append(d)
            if o is not None: ORD[(d['split'], d['cid'])] = o
            if n_ % 500 == 0: print(n_, round(time.time() - t0), flush=True)
    pd.to_pickle(R, f'{OUT}/bl_d0v_runs.pkl.gz'); pd.to_pickle(ORD, f'{OUT}/bl_d0v_m0_orders.pkl.gz'); print('done', len(R), round(time.time() - t0))
