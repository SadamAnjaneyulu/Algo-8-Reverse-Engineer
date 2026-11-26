"""D0 chunk 5 (plan reports/D0_FREE_RUN_PLAN.md): free-running D0 simulator from the real carried book, all parts refit on each split's training cycles.
Splits: OOF (cid parity halves), forward A (per version, earliest two thirds by expiry -> rest), forward B (V1 -> V2, V2 tests use V1 waves of the same underlying).
Simulator per minute: cycle stop (cumulative MTM at the minute close <= -1.20 lakh -> liquidate all), body buy-backs K3 (theta, tp), body sells (timetable waves, D-1 breakout pair,
D0 solo ladder M1, counter-sell r x simulated other-right buy-backs), opening wings at 09:15, hedge controller (buy gap S-L at the 2.5%-of-ATM wing; release excess outermost first
from h_ wings and v_ lump), 15:14 clearance (buy back all shorts, sell all longs).
Outputs bl_d0_fr_orders.pkl.gz ({split: {cid: orders DataFrame[cls, cp, j, strike, lots]}}), bl_d0_fr_params.json"""
import sys, warnings, json, itertools; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
def ns_of(path, stop):
    src = open(path).read(); ns = {'__name__': 'ns'}; exec(src[:src.index(stop)], ns); return ns
NT = ns_of('bl_d0s_tt.py', 'WALL = waves(D0C)'); NB = ns_of('bl_d0b_mach.py', 'rows = []; chosen = {}; PER = {}'); NS = ns_of('bl_d0s_solo.py', "fams = {'M1 spot ladder'")
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); O = load_orders(); OPT = pd.read_pickle(f'{OUT}/bl_d0_opt.pkl.gz'); SPT = pd.read_pickle(f'{OUT}/bl_d0_spot.pkl.gz'); BK = pd.read_pickle(f'{OUT}/bl_d0b_book.pkl.gz')
D0C = NT['D0C']; L_STOP = 1.20e5
# ---------------- fitted parts
def fit(train, test, vmap):
    W = NT['waves'](train); Wt = []
    for v_test, v_src in vmap.items():
        w = W[W.version == v_src].copy(); w['version'] = v_test; Wt.append(w)
    W = pd.concat(Wt, ignore_index=True) if Wt else W
    grid = [dict(theta=t, price='high', tp=p, tp_gate=0) if p else dict(theta=t, price='high') for t in NB['TH_'] for p in (None, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4)]
    k3 = max(grid, key=lambda P: NB['f1'](P, train))
    best = max(itertools.product(NS['CFG1'], NS['CFG3']), key=lambda c: NS['f1p'](NS['sc'](lambda i, c=c: {cp: NS['F1c'][c[0]][i][cp] + NS['F3c'][c[1]][i][cp] for cp in ('CE', 'PE')}, train)))
    ow = []
    for i in train:
        r = CY.iloc[i]; z = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 1) & (O.module == 'num') & (O.role == 'open_long') & (O.tod < 33480)]; ow.append(int(z.lots.sum()))
    return dict(W=W, k3=k3, m1=best[0], r=best[1], ow=int(np.median(ow)))
# ---------------- simulator
def sim(i, P):
    r = CY.iloc[i]; op = OPT[(r.und, r.expiry)]; K = op['K']; ki = {int(k): x for x, k in enumerate(K)}; sp = SPT[(r.und, r.expiry)]; h, l, c = sp.high.values, sp.low.values, sp.close.values; st = ref.STEP[r.und]; u = float(r.unit)
    def px(cp, k, j, f='close'):
        x = ki.get(int(k)); v = op[(cp, f)][x, min(max(j, 0), 374)] if x is not None else np.nan; return float(v) if v == v else np.nan
    atm = lambda x: float(K[np.argmin(np.abs(K - x))])
    # carried book (real D-1 orders): body short lots with entries, other positions by module
    lots = [[L['cp'], L['strike'], L['entry']] for L in BK[i]['at_open']]
    z1 = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 0)]; sg = np.where(z1.side.str.lower() == 'buy', 1, -1); cash = float((-sg * z1.px_avg * z1.lots * u).sum())
    oth = {}
    for q, s_ in zip(z1.itertuples(), sg):
        if q.module == 'num' and q.role in ('open_short', 'cover_short'): continue
        k = (q.module, q.cp, int(q.strike)); oth[k] = oth.get(k, 0) + s_ * q.lots
    longs = {k: v for k, v in oth.items() if v > 0}; oshort = {k: -v for k, v in oth.items() if v < 0}
    W = P['W']; W = W[(W.und == r.und) & (W.version == r.version)]; wv = {}
    for x in W.itertuples(): wv.setdefault(int((x.t - 33300) // 60), []).append(int(x.lots))
    fires = {}
    for j, s in NT['fires'](dict(h=h, l=l, c=c, step=st)): fires.setdefault(j, []).append(s)
    X_, G_, mult = P['m1']; stp = X_ * st; refp = {'CE': None, 'PE': None}; acc = {'CE': 0.0, 'PE': 0.0}; out = []; stopped = False
    rec_ = lambda cls, cp, j, k, n: out.append((cls, cp, j, int(k), int(n)))
    def mtm(j):
        v = cash
        for cp, k, e in lots:
            p = px(cp, k, j)
            if p == p: v -= p * u
        for (m, cp, k), n in longs.items():
            p = px(cp, k, j)
            if p == p: v += n * p * u
        for (m, cp, k), n in oshort.items():
            p = px(cp, k, j)
            if p == p: v -= n * p * u
        return v
    for j in range(0, 375):
        if stopped: break
        if mtm(j) <= -L_STOP:                                                  # cycle stop: liquidate everything
            agg = {}
            for cp, k, e in lots: agg[(cp, k)] = agg.get((cp, k), 0) + 1
            for (m, cp, k), n in list(longs.items()) + list(oshort.items()): agg[(cp, k)] = agg.get((cp, k), 0) + n
            for (cp, k), n in agg.items(): rec_('stop', cp, j, k, n)
            stopped = True; break
        jp = max(j - 1, 0); c0 = c[jp] if j > 0 else sp.open.values[0]
        if j == 359:                                                           # 15:14 clearance
            agg = {}
            for cp, k, e in lots: agg[(cp, k)] = agg.get((cp, k), 0) + 1
            for (cp, k), n in agg.items(): rec_('body_buyback', cp, j, k, n)
            for (m, cp, k), n in longs.items(): rec_('body_long' if m == 'num' else 'wing_sell', cp, j, k, n)
            lots = []; longs = {}; break
        nbb = {'CE': 0, 'PE': 0}; keep = []
        if j >= 1:
            for L in lots:
                cp, k, e = L; ph = px(cp, k, j, 'high'); pl = px(cp, k, j, 'low')
                if e > 0 and ((ph == ph and ph >= P['k3']['theta'] * e) or (P['k3'].get('tp') and pl == pl and pl <= P['k3']['tp'] * e)):
                    rec_('body_buyback', cp, j, k, 1); nbb[cp] += 1; p = px(cp, k, j); cash -= (p if p == p else e) * u
                else: keep.append(L)
            lots = keep
        sells = []
        for n in wv.get(j, []):
            k = atm(c0); sells += [('CE', k, n, 'pair'), ('PE', k, n, 'pair')]
        if 75 <= j <= 360:
            for s in fires.get(j, []): k = atm(c0) + s * st; sells += [('CE', k, 1, 'pair'), ('PE', k, 1, 'pair')]
        for cp in ('CE', 'PE'):
            if refp[cp] is None or j < 1: continue
            if G_ and not ((l[j] < l[max(j - G_, 0):j].min()) if cp == 'CE' else (h[j] > h[max(j - G_, 0):j].max())): continue
            dv = (refp[cp] - l[j]) if cp == 'CE' else (h[j] - refp[cp])
            if dv > stp: n = int(dv // stp); sells.append((cp, atm(c0), min(n, 10) if mult else 1, 'solo')); refp[cp] = refp[cp] - n * stp if cp == 'CE' else refp[cp] + n * stp
        if any(t == 'pair' for *_, t in sells): refp = {'CE': c0, 'PE': c0}          # reset after this minute's ladder check (as M1)
        for cp in ('CE', 'PE'):
            o = 'PE' if cp == 'CE' else 'CE'; acc[cp] += P['r'] * nbb[o]; n = int(acc[cp]); acc[cp] -= n
            if n: sells.append((cp, atm(c0), n, 'solo'))
        for cp, k, n, t in sells:
            if int(k) not in ki: continue
            e = px(cp, k, jp); e = e if e == e else px(cp, k, j)
            rec_('body_sell', cp, j, k, n); lots += [[cp, k, e]] * n; cash += (e if e == e else 0) * n * u
        if j == 0 and P['ow']:
            for cp, nn in (('CE', P['ow'] // 2), ('PE', P['ow'] - P['ow'] // 2)):
                k = atm(c0 + (1 if cp == 'CE' else -1) * 17 * st); rec_('body_long', cp, j, k, nn); longs[('num', cp, int(k))] = longs.get(('num', cp, int(k)), 0) + nn; p = px(cp, k, j); cash -= (p if p == p else 0) * nn * u
        for cp in ('CE', 'PE'):                                                # hedge controller
            S_ = sum(1 for L in lots if L[0] == cp) + sum(n for (m, c2, k), n in oshort.items() if c2 == cp); L_ = sum(n for (m, c2, k), n in longs.items() if c2 == cp); g = S_ - L_
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
    return pd.DataFrame(out, columns=['cls', 'cp', 'j', 'strike', 'lots'])
if __name__ == '__main__':
    VER = {i: CY.iloc[i].version for i in D0C}; exp = {i: CY.iloc[i].expiry for i in D0C}
    A_tr, A_te = [], []
    for v in ('V1', 'V2'):
        cv = sorted([i for i in D0C if VER[i] == v], key=lambda i: exp[i]); n = int(np.ceil(len(cv) * 2 / 3)); A_tr += cv[:n]; A_te += cv[n:]
    SPL = {'OOF half 0 test': ([i for i in D0C if i % 2 == 1], [i for i in D0C if i % 2 == 0], {'V1': 'V1', 'V2': 'V2'}), 'OOF half 1 test': ([i for i in D0C if i % 2 == 0], [i for i in D0C if i % 2 == 1], {'V1': 'V1', 'V2': 'V2'}),
           'forward A (same version, later cycles)': (A_tr, A_te, {'V1': 'V1', 'V2': 'V2'}), 'forward B (train V1, test V2)': ([i for i in D0C if VER[i] == 'V1'], [i for i in D0C if VER[i] == 'V2'], {'V2': 'V1', 'V1': 'V1'})}
    RES = {}; PAR = {}
    for nm, (tr, te, vm) in SPL.items():
        P = fit(tr, te, vm); PAR[nm] = dict(train=tr, test=te, k3=P['k3'], m1=list(P['m1']), r=P['r'], ow=P['ow'], waves=int(len(P['W'])))
        RES[nm] = {i: sim(i, P) for i in te}; print(nm, PAR[nm]['k3'], P['m1'], P['r'], P['ow'], {k: int(sum(d[d.cls == k].lots.sum() for d in RES[nm].values())) for k in ('body_sell', 'body_buyback', 'wing_buy', 'wing_sell', 'body_long', 'stop')})
    pd.to_pickle(RES, f'{OUT}/bl_d0_fr_orders.pkl.gz'); json.dump(PAR, open(f'{OUT}/bl_d0_fr_params.json', 'w'), indent=1, default=str)
