"""Free-running D-1 simulator (plan reports/D1_FREE_RUN_PLAN.md). sim_cycle(i, P, mode) -> (orders DataFrame, book snapshots).
Orders: cid, cls, cp, j (minute index, 09:15 = 0), strike, lots (one row per order, lots column), step.
Modes: 'free' = everything from market data; 'tf_hedge' = body sells / buy-backs / body-stream longs are the REAL orders, the hedge wings and lump are simulated on that book."""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
import bl_ohlc, bl_sd_build
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); OH = bl_ohlc.load(); OP = bl_sd_build.load_opt(); W = pd.read_csv(f'{OUT}/bl_react_wave_clock.csv'); O_ = load_orders(); LATE = pd.read_pickle(f'{OUT}/bl_auc_all_panel.pkl.gz')[['cid', 'j', 'cp', 'bk15', 'pl15_itm']]
LATE = LATE[(LATE.j >= 345) & (LATE.j <= 374) & ((LATE.bk15 == 1) | (LATE.pl15_itm == 1))]
REAL = O_[O_.dayno == 0].copy(); REAL['j'] = ((REAL.te - 33300) // 60).astype(int)
JMAX = 390
def regime(d1): return 'r1' if d1 <= '2026-08-05' else ('r2' if d1 <= '2026-08-19' else 'r3')
def prep(i):
    r = CY.iloc[i]; o = OH[(r.und, r.expiry)]; op = OP[(r.und, r.expiry)]; K = op['K']
    return dict(r=r, h=o.high.values, l=o.low.values, c=o.close.values, op=op, K=K, step=ref.STEP[r.und], ki={int(k): x for x, k in enumerate(K)})
def react_fires(i, d, rep_max=0, rep_gap=2):
    """First intrabar break per side per 30-min candle (decoded). Optional repeats (rep_max > 0): after the first entry of a candle-side, each new running extreme
    of the current candle beyond the channel, at least rep_gap minutes after the previous fire of that side, fires again (at most rep_max repeats)."""
    h, l, step = d['h'], d['l'], d['step']; out = []; done = {}; ext = {}
    for j in range(75, 361):
        clock = 33300 + 60 * j; b0 = (clock // 1800) * 1800; a = int(np.ceil((b0 - 3600 - 33300) / 60)); e = int(np.ceil((b0 - 33300) / 60))
        if e - max(a, 0) < 2: continue
        H, L = h[max(a, 0):e].max(), l[max(a, 0):e].min()
        for s, fl, dep, x in ((1, h[j] > H, (h[j] - H) / step, h[j]), (-1, l[j] < L, (L - l[j]) / step, -l[j])):
            if not fl: continue
            key = (b0, s)
            if key not in done: out.append((j, s, dep)); done[key] = [j, 0]; ext[key] = x
            elif rep_max and done[key][1] < rep_max and x > ext[key] and j - done[key][0] >= rep_gap: out.append((j, s, dep)); done[key] = [j, done[key][1] + 1]; ext[key] = x
            elif x > ext[key]: ext[key] = x
    return out
def sim_cycle(i, P, mode='free', late=False):
    d = prep(i); r = d['r']; h, l, c, op, K, step, ki = d['h'], d['l'], d['c'], d['op'], d['K'], d['step'], d['ki']; und = r.und
    cj = lambda j: min(max(j, 0), 374); atm = lambda x: float(K[np.argmin(np.abs(K - x))])
    def px(cp, k, j, f='close'):
        x = ki.get(int(k)); return float(op[(cp, f)][x, cj(j)]) if x is not None else np.nan
    # ---- body sell plan (free mode): minute -> list of (cp, strike, lots, typ)
    plan = {}; add = lambda j, cp, k, n, t: plan.setdefault(j, []).append([cp, k, n, t]); ev = {'CE': [], 'PE': []}; wv = W[W.version == r.version]
    for w in wv.itertuples():
        j = int((33360 + w.sec_after_0916 - 33300) // 60); k = atm(c[cj(j - 1)])
        for cp in ('CE', 'PE'): add(j, cp, k, 1, 'scheduled'); ev[cp].append(j)
    for j, s, dep in react_fires(i, d, P.get('rep_max', 0), P.get('rep_gap', 2)):
        k = atm(c[cj(j - 1)]) + s * step; n = min(1 + int(dep // P['tp']), 3)
        for cp in ('CE', 'PE'): add(j, cp, k, n, 'reactive'); ev[cp].append(j)
        ex = int(np.clip(round(P['a'] + P['b'] * dep), 0, 7))
        if ex: add(j, 'PE' if s > 0 else 'CE', k, ex, 'extra')
    # solo ladder (spot ladder X = 0.2 step, fresh 60-min extreme gate), reference reset at scheduled/reactive events
    X = 0.2; st = step * X; lad = {}
    for cp in ('CE', 'PE'):
        evs = sorted(set(ev[cp])); ptr = 0; refp = None
        for j in range(1, 375):
            while ptr < len(evs) and evs[ptr] < j: refp = c[max(evs[ptr] - 1, 0)]; ptr += 1
            if refp is None: continue
            if not ((l[j] < l[max(j - 60, 0):j].min()) if cp == 'CE' else (h[j] > h[max(j - 60, 0):j].max())): continue
            if cp == 'CE' and l[j] < refp - st: lad.setdefault(j, []).append(cp); refp = refp - st * max(1, int((refp - l[j]) // st))
            elif cp == 'PE' and h[j] > refp + st: lad.setdefault(j, []).append(cp); refp = refp + st * max(1, int((h[j] - refp) // st))
    late_fires = {}
    if late:
        for x in LATE[LATE.cid == i].itertuples(): late_fires.setdefault(x.j, []).append(x.cp)
    real = REAL[(REAL.und == r.und) & (REAL.expiry == r.expiry)]
    rb = {}; rl = {}
    if mode in ('tf_hedge', 'tf_bb'):
        for q in real[(real.module == 'num') & real.role.isin(['open_short', 'cover_short'])].itertuples(): rb.setdefault(q.j, []).append((q.role, q.cp, int(q.strike), int(q.lots), q.px_avg))
        for q in real[(real.module == 'num') & real.role.isin(['open_long', 'close_long'])].itertuples(): rl.setdefault(q.j, []).append((q.role, q.cp, int(q.strike), int(q.lots)))
    shorts = {}; wings = {}; lump = {}; orders = []; last_px = {'CE': None, 'PE': None}; snaps = []; Pl = P['lump_t'][regime(r.d1)]
    rec_ = lambda cls, cp, j, k, n, typ='': orders.append(dict(cid=i, cls=cls, cp=cp, j=j, strike=int(k), lots=int(n), step=step, typ=typ))
    for j in range(1, JMAX):
        # opening wings (free mode): all at j = 1
        if mode in ('free', 'tf_bb') and j == 1:
            off = P['open_off'][(und, r.version)]
            for cp in ('CE', 'PE'):
                kk = atm(c[0]) + (1 if cp == 'CE' else -1) * off * step; kk = float(K[np.argmin(np.abs(K - kk))])
                for _ in range(3): wings[(cp, kk)] = wings.get((cp, kk), 0) + 1; rec_('opening_wings', cp, j, kk, 1)
        bodyorders = []
        if mode in ('free', 'tf_bb'):
            # buy-backs first. Default (P['bb_price'] = 'close', no velocity / cluster): previous completed close >= theta x own entry price.
            # Options: bb_price 'high' (current minute high, intrabar stop); bb_vel (n, b): own premium high[j] / close[j-1-n] >= b also stops the highest-ratio lot;
            # bb_cluster th2: when any stop fires on a right in this minute, lots on that right with ratio >= th2 are bought back too.
            fired = {'CE': False, 'PE': False}; pf = P.get('bb_price', 'close'); vel = P.get('bb_vel'); th2 = P.get('bb_cluster')
            def pnow(cp, k): return px(cp, k, j, 'high') if pf == 'high' else px(cp, k, j - 1)
            for (cp, k), lots in list(shorts.items()):
                keep = []; pn = pnow(cp, k); vtrig = False
                if vel and lots:
                    base = px(cp, k, j - 1 - vel[0]); hh = px(cp, k, j, 'high'); vtrig = base == base and base > 0 and hh == hh and hh / base >= vel[1]
                lots_sorted = sorted(lots, key=lambda t: t[1])                       # cheapest entry first (highest ratio)
                for n_, (ej, ep) in enumerate(lots_sorted):
                    hit = j > ej and pn == pn and ep > 0 and pn / ep >= P['theta']
                    if not hit and vtrig and n_ == 0 and j > ej: hit = True
                    if hit: rec_('body_buyback', cp, j, k, 1); bodyorders.append(('cover', cp, k, 1)); fired[cp] = True
                    else: keep.append((ej, ep))
                shorts[(cp, k)] = keep
            if th2:
                for (cp, k), lots in list(shorts.items()):
                    if not fired[cp]: continue
                    pn = pnow(cp, k); keep = []
                    for (ej, ep) in lots:
                        if j > ej and pn == pn and ep > 0 and pn / ep >= th2: rec_('body_buyback', cp, j, k, 1); bodyorders.append(('cover', cp, k, 1))
                        else: keep.append((ej, ep))
                    shorts[(cp, k)] = keep
            # sells
            sells = [list(x) for x in plan.get(j, [])] if mode == 'free' else [[cp_, k_, n_, 'real', p_] for role_, cp_, k_, n_, p_ in rb.get(j, []) if role_ == 'open_short']
            for cp in (lad.get(j, []) if mode == 'free' else []): sells.append([cp, None, 1, 'solo'])
            for cp in (late_fires.get(j, []) if mode == 'free' else []): sells.append([cp, None, 1, 'late'])
            for sl_ in sells:
                cp, k, n, t = sl_[:4]
                if k is None:
                    a0 = atm(c[cj(j - 1)])
                    if t == 'late': k = a0 - step if cp == 'CE' else a0 + step
                    elif last_px[cp] is None: k = a0
                    else:
                        cand = K[np.abs(K - a0) <= 4 * step]; pr = np.array([px(cp, kk, j - 1) for kk in cand]); k = float(cand[np.argmin(np.abs(np.nan_to_num(pr, nan=1e9) - last_px[cp]))])
                ep = sl_[4] if t == 'real' else px(cp, k, j, 'open'); ep = ep if ep == ep and ep > 0 else px(cp, k, j - 1)
                for _ in range(n): shorts.setdefault((cp, k), []).append((j, ep)); rec_('body_sell', cp, j, k, 1, t)
                last_px[cp] = ep; bodyorders.append(('sell', cp, k, n))
        else:
            for role, cp, k, n, p_ in rb.get(j, []):
                if role == 'open_short':
                    for _ in range(n): shorts.setdefault((cp, k), []).append((j, p_))
                else:
                    for _ in range(n):
                        if shorts.get((cp, k)): shorts[(cp, k)].pop(0)
                bodyorders.append((role, cp, k, n))
            for role, cp, k, n in rl.get(j, []): wings[(cp, float(k))] = wings.get((cp, float(k)), 0) + (n if role == 'open_long' else -n)
        # hedge controller (all body orders of the minute, then wing orders)
        if bodyorders or j == 1:
            for cp in ('CE', 'PE'):
                S = sum(len(v) for (c2, _), v in shorts.items() if c2 == cp); Lw = sum(v for (c2, _), v in wings.items() if c2 == cp and v > 0); gap = S - Lw
                if gap > 0:
                    a0 = atm(c[cj(j - 1)]); sg = 1 if cp == 'CE' else -1; tgt = P['k'] * px(cp, a0, j - 1); cand = K[sg * (K - c[cj(j - 1)]) > 0]
                    pr = np.array([px(cp, kk, j - 1) for kk in cand]); ok = pr > 0
                    if ok.any() and tgt == tgt and tgt > 0:
                        kk = float(cand[ok][np.argmin(np.abs(np.log(pr[ok] / tgt)))]); wings[(cp, kk)] = wings.get((cp, kk), 0) + gap; rec_('wing_buy', cp, j, kk, gap)
                elif gap < 0:
                    ex = -gap; sg = 1 if cp == 'CE' else -1; held = sorted([(kk, v) for (c2, kk), v in wings.items() if c2 == cp and v > 0], key=lambda t: -sg * (t[0] - c[cj(j - 1)]))
                    for kk, v in held:
                        if ex <= 0: break
                        n = min(v, ex); wings[(cp, kk)] -= n; ex -= n; rec_('wing_sell', cp, j, kk, n)
        # overnight lump
        if j == Pl:
            Sce = sum(len(v) for (c2, _), v in shorts.items() if c2 == 'CE'); Spe = sum(len(v) for (c2, _), v in shorts.items() if c2 == 'PE'); cp = 'CE' if Sce > Spe else 'PE'; Sh = max(Sce, Spe)
            n = int(round(P['lump_ratio'][und] * Sh))
            if n > 0:
                S0 = c[cj(j - 1)]; a = np.argmin(np.abs(K - S0)); sig = (op[('CE', 'close')][a, cj(j - 1)] + op[('PE', 'close')][a, cj(j - 1)]) / (0.7979 * S0); sg = 1 if cp == 'CE' else -1
                kk = float(K[np.argmin(np.abs(K - S0 * (1 + sg * P['lump_z'] * sig)))]); lump[(cp, kk)] = n; rec_('lump', cp, j, kk, n)
        if j % 60 == 0 or j == 374:
            snaps.append(dict(cid=i, j=j, **{f'S_{cp}': sum(len(v) for (c2, _), v in shorts.items() if c2 == cp) for cp in ('CE', 'PE')}, **{f'L_{cp}': sum(v for (c2, _), v in wings.items() if c2 == cp and v > 0) + sum(v for (c2, _), v in lump.items() if c2 == cp) for cp in ('CE', 'PE')}))
    net = {}
    for (cp, k), v in shorts.items(): net[(cp, int(k))] = net.get((cp, int(k)), 0) - len(v)
    for (cp, k), v in wings.items(): net[(cp, int(k))] = net.get((cp, int(k)), 0) + v
    for (cp, k), v in lump.items(): net[(cp, int(k))] = net.get((cp, int(k)), 0) + v
    return pd.DataFrame(orders), pd.DataFrame(snaps), {k: v for k, v in net.items() if v != 0}
