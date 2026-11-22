"""Free-running D-1 simulator (plan reports/D1_FREE_RUN_PLAN.md). sim_cycle(i, P, mode) -> (orders DataFrame, book snapshots).
Orders: cid, cls, cp, j (minute index, 09:15 = 0), strike, lots (one row per order, lots column), step.
Modes: 'free' = everything from market data; 'tf_hedge' = body sells / buy-backs / body-stream longs are the REAL orders, the hedge wings and lump are simulated on that book."""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
import bl_ohlc, bl_sd_build
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); OH = bl_ohlc.load(); OP = bl_sd_build.load_opt(); W = pd.read_csv(f'{OUT}/bl_react_wave_clock.csv'); O_ = load_orders(); LATE = pd.read_pickle(f'{OUT}/bl_auc_all_panel.pkl.gz')[['cid', 'j', 'cp', 'bk15', 'pl15_itm']]
LATE = LATE[(LATE.j >= 345) & (LATE.j <= 374) & ((LATE.bk15 == 1) | (LATE.pl15_itm == 1))]
SDL = pd.read_pickle(f'{OUT}/bl_sd_orders.pkl.gz'); SDL['t2'] = np.where(SDL.deep, 'deep', np.where((SDL.typ == 'solo') & (SDL.te >= 54000), 'late', SDL.typ)); SDL['sd'] = np.where(SDL.typ == 'reactive', np.sign(SDL.off_atm).astype(int), np.where(SDL.cp == 'CE', -1, 1))
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
    plan = {}; add = lambda j, cp, k, n, t, sd=0: plan.setdefault(j, []).append([cp, k, n, t, sd]); ev = {'CE': [], 'PE': []}; wv = W[W.version == r.version]
    for w in wv.itertuples():
        j = int((33360 + w.sec_after_0916 - 33300) // 60); k = atm(c[cj(j - 1)])
        for cp in ('CE', 'PE'): add(j, cp, k, 1, 'scheduled'); ev[cp].append(j)
    for j, s, dep in react_fires(i, d, P.get('rep_max', 0), P.get('rep_gap', 2)):
        k = atm(c[cj(j - 1)]) + s * step; n = min(1 + int(dep // P['tp']), 3)
        for cp in ('CE', 'PE'): add(j, cp, k, n, 'reactive', s); ev[cp].append(j)
        ex = int(np.clip(round(P['a'] + P['b'] * dep), 0, 7))
        if ex: add(j, 'PE' if s > 0 else 'CE', k, ex, 'extra', s)
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
        sdl = SDL[SDL.cid == i]; lab_ = {(round(x.te, 3), x.cp, int(x.strike)): (x.t2, x.sd) for x in sdl.itertuples()}
        for q in real[(real.module == 'num') & real.role.isin(['open_short', 'cover_short'])].itertuples():
            ty_, sd0 = lab_.get((round(q.te, 3), q.cp, int(q.strike)), ('solo', 0)); rb.setdefault(q.j, []).append((q.role, q.cp, int(q.strike), int(q.lots), q.px_avg, ty_, sd0))
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
            fired = {'CE': False, 'PE': False}; nbb = {'CE': 0, 'PE': 0}; stopped = set(); pf = P.get('bb_price', 'close'); vel = P.get('bb_vel'); th2 = P.get('bb_cluster')
            def pnow(cp, k):
                if pf == 'high': return px(cp, k, j, 'high')
                if pf == 'close_now': return px(cp, k, j, 'close')
                if pf == 'typical': return (px(cp, k, j, 'high') + px(cp, k, j, 'low') + px(cp, k, j, 'close')) / 3
                if pf == 'open_now': return px(cp, k, j, 'open')
                return px(cp, k, j - 1)
            mlb = P.get('ml_bb')
            if mlb:                                                                # learned buy-back policy (plan D1_ML_PLAN.md)
                feats = []; refs = []; rsum = {}
                for (cp, k), lots in shorts.items():
                    pc0 = px(cp, k, j - 1)
                    for lt in lots: rsum.setdefault(cp, [0.0, 0.0]); rsum[cp][0] += pc0 if pc0 == pc0 else 0.0; rsum[cp][1] += lt[1] if lt[1] == lt[1] else 0.0
                for (cp, k), lots in shorts.items():
                    if not lots: continue
                    sgn = 1 if cp == 'CE' else -1; pc0 = px(cp, k, j - 1); ph0 = px(cp, k, j, 'high'); b4 = px(cp, k, j - 4); jc = cj(j - 1); lo30 = max(jc - 30, 0)
                    dn = float((c[jc] > h[lo30:jc].max()) if cp == 'CE' else (c[jc] < l[lo30:jc].min())) if jc > lo30 else 0.0
                    rr = rsum[cp][0] / rsum[cp][1] if rsum[cp][1] > 0 else np.nan
                    for n_, lt in enumerate(lots):
                        ej, ep = lt[0], lt[1]
                        if j <= ej or not (ep > 0): continue
                        tc = {'scheduled': 0, 'reactive': 1, 'extra': 2, 'solo': 2, 'counter': 2, 'late': 3, 'deep': 4}.get(lt[2], 2) if len(lt) > 2 else 0
                        adv = sgn * (c[jc] - lt[4]) / step if len(lt) > 4 and lt[4] == lt[4] else 0.0
                        feats.append([pc0 / ep, ph0 / ep, j - ej, tc, adv, (ph0 / b4) if b4 > 0 else np.nan, dn, rr, len(lots), j]); refs.append((cp, k, n_))
                if feats:
                    pr_ = mlb['model'].predict_proba(np.array(feats, float))[:, 1]; drop = {}
                    for (cp, k, n_), p_ in zip(refs, pr_):
                        if p_ >= mlb['tau']: drop.setdefault((cp, k), set()).add(n_)
                    for (cp, k), idx in drop.items():
                        keep = []
                        for n_, lt in enumerate(shorts[(cp, k)]):
                            if n_ in idx: rec_('body_buyback', cp, j, k, 1); bodyorders.append(('cover', cp, k, 1)); fired[cp] = True; nbb[cp] += 1
                            else: keep.append(lt)
                        shorts[(cp, k)] = keep
            for (cp, k), lots in (list(shorts.items()) if not mlb else []):
                keep = []; pn = pnow(cp, k); vtrig = False
                if vel and lots:
                    base = px(cp, k, j - 1 - vel[0]); hh = px(cp, k, j, 'high'); vtrig = base == base and base > 0 and hh == hh and hh / base >= vel[1]
                lots_sorted = sorted(lots, key=lambda t: t[1])                       # cheapest entry first (highest ratio)
                mN = P.get('bb_mkt'); mkt_ok = True
                if mN:
                    jc = cj(j - 1); lo_ = max(jc - mN, 0); mkt_ok = (c[jc] > h[lo_:jc].max()) if cp == 'CE' else (c[jc] < l[lo_:jc].min()) if jc > lo_ else False
                lo_t = P.get('bb_lo'); b_ok = False
                if lo_t:
                    jc = cj(j - 1); mN2 = P.get('bb_lo_mkt'); vv = P.get('bb_lo_vel')
                    if mN2: lo2 = max(jc - mN2, 0); b_ok = ((c[jc] > h[lo2:jc].max()) if cp == 'CE' else (c[jc] < l[lo2:jc].min())) if jc > lo2 else False
                    if vv and not b_ok:
                        base_ = px(cp, k, j - 4); hh_ = px(cp, k, j, 'high'); b_ok = base_ == base_ and base_ > 0 and hh_ / base_ >= vv
                    pc_ = px(cp, k, j - 1)
                nB = 0
                for n_, lt in enumerate(lots_sorted):
                    ej, ep = lt[0], lt[1]
                    rr_ = pn / ep if (pn == pn and ep > 0) else 0.0
                    hit = j > ej and rr_ >= P['theta'] and (mkt_ok or rr_ >= P.get('bb_hi', 99))
                    if not hit and lo_t and b_ok and j > ej and ep > 0 and pc_ > ep and rr_ >= lo_t and (P.get('bb_lo_qty', 'one') == 'all' or nB == 0): hit = True; nB += 1
                    if not hit and vtrig and n_ == 0 and j > ej: hit = True
                    if hit: rec_('body_buyback', cp, j, k, 1); bodyorders.append(('cover', cp, k, 1)); fired[cp] = True; nbb[cp] += 1; stopped.add((cp, k))
                    else: keep.append(lt)
                shorts[(cp, k)] = keep
            if th2:
                for (cp, k), lots in list(shorts.items()):
                    if not fired[cp]: continue
                    pn = pnow(cp, k); keep = []
                    for lt in lots:
                        ej, ep = lt[0], lt[1]
                        if j > ej and pn == pn and ep > 0 and pn / ep >= th2: rec_('body_buyback', cp, j, k, 1); bodyorders.append(('cover', cp, k, 1)); nbb[cp] += 1
                        else: keep.append(lt)
                    shorts[(cp, k)] = keep
            # rebalancing-event parts (plan BUYBACK_EVENTS_PLAN.md): straddle partner, reactive continuation exit, solo reversal exit
            if P.get('ev_partner'):
                for (cp, k) in list(stopped):
                    oth = 'PE' if cp == 'CE' else 'CE'; lots = shorts.get((oth, k), []); keep = []
                    for lt in lots:
                        if j > lt[0]: rec_('body_buyback', oth, j, k, 1); bodyorders.append(('cover', oth, k, 1)); nbb[oth] += 1
                        else: keep.append(lt)
                    if lots: shorts[(oth, k)] = keep
            dR, dS = P.get('ev_react'), P.get('ev_solo')
            if dR or dS:
                for (cp, k), lots in list(shorts.items()):
                    sgn = 1 if cp == 'CE' else -1; keep = []
                    for lt in lots:
                        ej, ep, t_, sd_, s0 = lt; hit = False
                        if j > ej and s0 == s0:
                            mv = (c[cj(j - 1)] - s0) / step
                            if dR and t_ in ('reactive', 'extra') and j - ej <= 10 and sd_ == sgn and sd_ * mv >= dR: hit = True
                            if dS and t_ == 'solo' and sgn * mv >= dS: hit = True
                        if hit: rec_('body_buyback', cp, j, k, 1); bodyorders.append(('cover', cp, k, 1)); fired[cp] = True; nbb[cp] += 1
                        else: keep.append(lt)
                    shorts[(cp, k)] = keep
            # sells
            sells = [list(x) for x in plan.get(j, [])] if mode == 'free' else [[cp_, k_, n_, ty_, p_, sd0, 'real'] for role_, cp_, k_, n_, p_, ty_, sd0 in rb.get(j, []) if role_ == 'open_short']
            mls = P.get('ml_sell') if mode == 'free' else None
            if mls:                                                                # learned solo-sell policy (plan D1_ML_PLAN.md)
                sells = [x for x in sells if x[3] != 'extra']; arr = mls['mkt'][i]; rows_ = []
                for ci_, cp in enumerate(('CE', 'PE')):
                    num = den = 0.0; nl = 0
                    for (c2, k2), lots in shorts.items():
                        if c2 != cp: continue
                        pk = px(cp, k2, j - 1)
                        for lt in lots:
                            if pk == pk and lt[1] == lt[1]: num += pk; den += lt[1]; nl += 1
                    bk_ = (num / den if den > 0 else np.nan, nl)
                    rows_.append([int(cp == 'CE')] + list(arr[min(j, 389), ci_]) + [bk_[0], np.nan, bk_[1], np.nan])
                rows_[0][-3] = rows_[1][-4]; rows_[0][-1] = rows_[1][-2]; rows_[1][-3] = rows_[0][-4]; rows_[1][-1] = rows_[0][-2]
                pp = mls['model'].predict_proba(np.array(rows_, float)); cls_ = mls['model'].classes_
                for ci_, cp in enumerate(('CE', 'PE')):
                    cum = [pp[ci_][cls_ >= kk].sum() for kk in range(1, int(cls_.max()) + 1)]; nS = int(sum(1 for q in cum if q >= mls['t']))
                    if nS: sells.append([cp, None, nS, 'late' if j >= 345 else 'solo'])
            for cp in (lad.get(j, []) if (mode == 'free' and not mls) else []):
                nS = 1
                if P.get('solo_b') is not None:                                   # solo lots per ladder fire grow with the depth beyond the 60-min extreme (plan D1_LOTS_PLAN.md)
                    dep_ = ((l[max(j - 60, 0):j].min() - l[j]) if cp == 'CE' else (h[j] - h[max(j - 60, 0):j].max())) / step
                    nS = int(np.clip(round(P.get('solo_a', 1.0) + P['solo_b'] * max(dep_, 0.0)), 1, 8))
                sells.append([cp, None, nS, 'solo'])
            for cp in (late_fires.get(j, []) if (mode == 'free' and not mls) else []): sells.append([cp, None, int(P.get('late_n', 1)), 'late'])
            if mode == 'free' and P.get('ev_counter'):
                for cp in ('CE', 'PE'):
                    if fired[cp]: sells.append(['PE' if cp == 'CE' else 'CE', None, 1 if P['ev_counter'] == 'one' else max(nbb[cp], 1), 'solo'])
            for sl_ in sells:
                cp, k, n, t = sl_[:4]
                if k is None:
                    a0 = atm(c[cj(j - 1)])
                    if t == 'late': k = a0 - step if cp == 'CE' else a0 + step
                    elif last_px[cp] is None: k = a0
                    else:
                        cand = K[np.abs(K - a0) <= 4 * step]; pr = np.array([px(cp, kk, j - 1) for kk in cand]); k = float(cand[np.argmin(np.abs(np.nan_to_num(pr, nan=1e9) - last_px[cp]))])
                isreal = len(sl_) > 6 and sl_[6] == 'real'; ep = sl_[4] if isreal else px(cp, k, j, 'open'); ep = ep if ep == ep and ep > 0 else px(cp, k, j - 1); sd_ = sl_[5] if isreal else (sl_[4] if len(sl_) > 4 else 0)
                for _ in range(n): shorts.setdefault((cp, k), []).append((j, ep, t, sd_, c[cj(j - 1)])); rec_('body_sell', cp, j, k, 1, t)
                last_px[cp] = ep; bodyorders.append(('sell', cp, k, n))
        else:
            for role, cp, k, n, p_, _t, _s in rb.get(j, []):
                if role == 'open_short':
                    for _ in range(n): shorts.setdefault((cp, k), []).append((j, p_, 'real', 0, np.nan))
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
