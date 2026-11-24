"""3-year backtest, simulator (plan reports/BACKTEST3Y_PLAN.md): D-1 (d1_strategy batch rules) -> carried book -> D0 (the M0 simulator of bl_d0_fr / bl_d0v_sizing) on full-chain minute arrays.
sim_d0 = bl_d0v_sizing.sim2 (mode M0, s = 1) with explicit inputs (no globals) and a fill record. Identity check against sim2 in check_identity().
Fills: (day 0 = D-1, 1 = D0, minute j, cp, strike, side +1 buy / -1 sell, lots, price, class, n_orders). Orders are counted as the real system sends them (body orders one lot each; hedge, wing, lump, stop orders one per record).
Accounting layer (bt/account.py cost model, flagged unverified there): slippage max(0.10, 0.5%) against the order, dated statutory costs, Rs 20 brokerage per order."""
import sys, os, json, warnings; sys.path.insert(0, '.'); sys.path.insert(0, '/home/user/Algo-8-Reverse-Engineer/d1_strategy'); sys.path.insert(0, '/home/user/Algo-8-Reverse-Engineer/backtest'); warnings.filterwarnings('ignore')
from bl_common import *
import bl_d0_fr as F
import algo8_d1 as A
from bt import account as ACC
import datetime as dt
BT3 = f'{OUT}/bt3'; NT = F.NT; L_STOP = F.L_STOP
FROZEN = json.load(open(f'{OUT}/bl_bt3_frozen.json')); W_ALL = pd.read_csv(f'{OUT}/bl_bt3_frozen_waves.csv')
P_FROZEN = dict(W=W_ALL, k3=FROZEN['k3'], m1=tuple(FROZEN['m1']), r=FROZEN['counter_r'], ow=FROZEN['opening_longs'])
BODY_SELL = ('scheduled_straddle', 'breakout_straddle', 'breakout_extra', 'ladder_solo')
def load(und, expiry): return pd.read_pickle(f"{os.environ.get('BT3_DIR', BT3)}/{und}_{expiry}.pkl.gz")   # BT3_DIR=outputs/bt3x: session to 15:39 after the closing auction
def versions_for(d1, d0, run):
    """run 'A/V1' or 'B/V2' for dates before the live window; observed versions inside and after it."""
    if d1 >= '2026-06-22': return ('B' if d1 >= '2026-09-16' else 'A', 'V2' if d0 >= '2026-09-16' else 'V1')
    return ('A', 'V1') if run == 'A/V1' else ('B', 'V2')
def d1_config(und, d1, vd1, variant=None):
    cfg = A.config_for(und, d1); nifty = und == 'NIFTY'; v = variant or {}
    cfg.timetable = list(A.SCHEDULE_B if vd1 == 'B' else A.SCHEDULE_A); cfg.opening_wing_offset_steps = 20.0 if (not nifty and vd1 == 'B') else 39.8
    if v.get('d1_no_sched'): cfg.timetable = []
    if v.get('d1_no_brk'): cfg.breakout_start_min = 10 ** 6
    if v.get('d1_no_lad'): cfg.ladder_step = 1e6
    if v.get('d1_no_stop'): cfg.stop_ratio = 1e9
    if v.get('d1_no_wings'): cfg.wing_premium_frac = 0.0; cfg.opening_wing_lots_per_right = 0; cfg.lump_ratio = 0.0
    if v.get('d1_no_lump'): cfg.lump_ratio = 0.0
    if v.get('shift_waves'): cfg.timetable = [t + 2220 for t in cfg.timetable]                                                 # +37 minutes
    for k_, val_ in (v.get('d1_set') or {}).items(): setattr(cfg, k_, val_)                                                  # parameter sensitivity (PREPAPER_PLAN B2)
    if v.get('shift_s'): cfg.timetable = [min(max(t + v['shift_s'], 1), 22000) for t in cfg.timetable]                         # timing shift in seconds
    if v.get('random_tt') is not None:                                                                                         # random-timetable null (PREPAPER_PLAN B3c)
        rg = np.random.default_rng(int(v['random_tt']) * 7919 + (1 if nifty else 2) + (10 if vd1 == 'B' else 0)); tt = cfg.timetable
        if tt: cfg.timetable = sorted(int(x) for x in rg.uniform(1, max(tt), len(tt)))
    return cfg
# ---------------- D-1: run the batch rules, replay the orders into fills, a carried book and cash
def run_d1(cyc, cfg, unit, causal=True, flip_ladder=False):
    K = cyc['opt1']['K']; chain = A.OptionChain(strikes=K, bars={(cp, f): cyc['opt1'][(cp, f)] for cp in ('CE', 'PE') for f in ('open', 'high', 'low', 'close')}); s = cyc['spot1']
    orig_lad = A.ladder_fires
    if flip_ladder: A.ladder_fires = lambda *a, **k: {j_: ['PE' if r_ == 'CE' else 'CE' for r_ in rs_] for j_, rs_ in orig_lad(*a, **k).items()}
    try: res = A.D1Strategy(cfg).run(s.open.values.astype(float), s.high.values.astype(float), s.low.values.astype(float), s.close.values.astype(float), chain, max_minute=390)
    finally: A.ladder_fires = orig_lad
    ki = {int(k): i for i, k in enumerate(K)}
    def px(cp, k, j, f='close'):
        i = ki.get(int(k)); a_ = chain.bars[(cp, f)]; v = a_[i, min(max(j, 0), a_.shape[1] - 1)] if i is not None else np.nan; return float(v) if v == v else np.nan
    def pc(cp, k, j):
        p = px(cp, k, j); return p if p == p and p > 0 else (px(cp, k, j - 1) if px(cp, k, j - 1) == px(cp, k, j - 1) else 0.05)
    shorts = {}; longs = {}; fills = []; cash = 0.0
    for o in res.orders:
        j, cp, k, n = o.minute, o.right, int(o.strike), o.lots
        if o.role in BODY_SELL:
            ep = px(cp, k, j, 'open'); ep = ep if ep == ep and ep > 0 else pc(cp, k, j - 1)                               # the price D1Strategy books internally (stop level reference)
            fp = ep if (not causal or o.role == 'scheduled_straddle') else pc(cp, k, j)                                    # causal: a signal that uses the minute's own extreme is filled at that minute's close
            shorts.setdefault((cp, k), []).extend([(ep, fp)] * n); fills.append((0, j, cp, k, -1, n, fp, 'body_sell', n)); cash += fp * n * unit
        elif o.role == 'stop_buyback':
            lst = sorted(shorts.get((cp, k), [])); e = lst.pop(0) if lst else (np.nan, np.nan); shorts[(cp, k)] = lst
            if causal and e[0] == e[0]:
                hi = px(cp, k, j, 'high'); op_ = px(cp, k, j, 'open'); lvl = cfg.stop_ratio * e[0]; p = min(hi, max(lvl, op_ if op_ == op_ else 0.0)) if hi == hi else pc(cp, k, j)      # stop-order semantics: the level, or the gap open
            else: p = pc(cp, k, j)
            fills.append((0, j, cp, k, 1, 1, p, 'body_buyback', 1)); cash -= p * unit
        elif o.role in ('protective_wing_buy', 'opening_wing_buy', 'overnight_lump'):
            mod = 'h_' if o.role == 'protective_wing_buy' else ('num' if o.role == 'opening_wing_buy' else 'v_'); longs[(mod, cp, k)] = longs.get((mod, cp, k), 0) + n; p = pc(cp, k, j)
            fills.append((0, j, cp, k, 1, n, p, {'h_': 'wing_buy', 'num': 'body_long', 'v_': 'lump'}[mod], 1 if mod != 'num' else n)); cash -= p * n * unit
        elif o.role == 'protective_wing_sell':
            left = n
            for key in [kk for kk in longs if kk[0] == 'h_' and kk[1] == cp and kk[2] == k]:
                x = min(left, longs[key]); longs[key] -= x; left -= x
            p = pc(cp, k, j); fills.append((0, j, cp, k, -1, n, p, 'wing_sell', 1)); cash += p * n * unit
    lots = [[cp, k, e[1]] for (cp, k), lst in shorts.items() for e in lst]; longs = {k: v for k, v in longs.items() if v > 0}
    return dict(fills=fills, lots=lots, longs=longs, cash=cash, n_orders=len(res.orders))
# ---------------- D0: M0 simulator with explicit inputs
def sim_d0(cyc, ver, P, book, unit, causal=True):
    und = cyc['und']; op = cyc['opt0']; K = op['K']; ki = {int(k): x for x, k in enumerate(K)}; sp = cyc['spot0']; h, l, c = sp.high.values.astype(float), sp.low.values.astype(float), sp.close.values.astype(float); st = ref.STEP[und]; u = float(unit)
    def px(cp, k, j, f='close'):
        x = ki.get(int(k)); a_ = op[(cp, f)]; v = a_[x, min(max(j, 0), a_.shape[1] - 1)] if x is not None else np.nan; return float(v) if v == v else np.nan
    atm = lambda x: float(K[np.argmin(np.abs(K - x))])
    lots = [list(L) for L in book['lots']]; longs = dict(book['longs']); oshort = dict(book.get('oshort', {})); cash = float(book['cash']); fills = []
    W = P['W']; W = W[(W.und == und) & (W.version == ver)]; wv = {}
    for x in W.itertuples(): wv.setdefault(int((x.t - 33300) // 60), []).append(int(x.lots))
    fires = {}
    for j, s_ in NT['fires'](dict(h=h, l=l, c=c, step=st)): fires.setdefault(j, []).append(s_)
    X_, G_, mult = P['m1']; stp = X_ * st; refp = {'CE': None, 'PE': None}; acc = {'CE': 0.0, 'PE': 0.0}; stopped = False; peak = {'CE': 0, 'PE': 0}; stop_j = None
    def fl(cls, cp, j, k, n, price, side, norders):
        nonlocal cash
        fills.append((1, j, cp, int(k), side, int(n), float(price), cls, int(norders))); cash += -side * price * n * u
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
        if mtm(j) <= -(1e18 if P.get('no_cycle_stop') else P.get('L_STOP', L_STOP)):                                   # L_STOP override: parameter sensitivity (PREPAPER_PLAN B2)
            agg = {}
            for cp, k, e in lots: agg.setdefault((cp, k), []).append(e)
            for (cp, k), es in agg.items():
                p = px(cp, k, j); p = p if p == p else float(np.mean(es)); fl('stop', cp, j, k, len(es), p, 1, 1)
            for (m, cp, k), n in longs.items():
                p = px(cp, k, j); fl('stop', cp, j, k, n, p if p == p else 0.0, -1, 1)
            for (m, cp, k), n in oshort.items():
                p = px(cp, k, j); fl('stop', cp, j, k, n, p if p == p else 0.0, 1, 1)
            lots = []; longs = {}; oshort = {}; stopped = True; stop_j = j; break
        jp = max(j - 1, 0); c0 = c[jp] if j > 0 else sp.open.values[0]
        if j == 359:
            agg = {}
            for cp, k, e in lots: agg.setdefault((cp, k), []).append(e)
            for (cp, k), es in agg.items():
                p = px(cp, k, j); p = p if p == p else float(np.mean(es)); fl('body_buyback', cp, j, k, len(es), p, 1, len(es))
            for (m, cp, k), n in longs.items():
                p = px(cp, k, j); fl('body_long' if m == 'num' else 'wing_sell', cp, j, k, n, p if p == p else 0.0, -1, 1)
            for (m, cp, k), n in oshort.items():
                p = px(cp, k, j); cash -= n * (p if p == p else 0.0) * u                       # as bl_d0v_sizing.sim2: settled in cash, not an order
            lots = []; longs = {}; oshort = {}; break
        nbb = {'CE': 0, 'PE': 0}; keep = []
        if j >= 1:
            th = P['k3']['theta']; tpv = P['k3'].get('tp')
            for L in lots:
                cp, k, e = L; ph = px(cp, k, j, 'high'); pl = px(cp, k, j, 'low'); st_hit = ph == ph and ph >= th * e; tp_hit = bool(tpv) and pl == pl and pl <= tpv * e
                if e > 0 and (st_hit or tp_hit):
                    nbb[cp] += 1; p = px(cp, k, j); p = p if p == p else e
                    if causal:
                        oj = px(cp, k, j, 'open'); oj = oj if oj == oj else p
                        p = min(ph, max(th * e, oj)) if st_hit else max(pl, min(tpv * e, oj))                                  # stop / take-profit order semantics
                    fl('body_buyback', cp, j, k, 1, p, 1, 1)
                else: keep.append(L)
            lots = keep
        sells = []
        for n in wv.get(j, []): k = atm(c0); sells += [('CE', k, n, 0), ('PE', k, n, 0)]                                       # 0 = timer (clock) order
        if 75 <= j <= 360 and not P.get('no_fires'):
            for s_ in fires.get(j, []): k = atm(c0) + s_ * st; sells += [('CE', k, 1, 1), ('PE', k, 1, 1)]                    # 1 = reactive (uses the minute's own extreme)
        pair = len(sells) > 0
        for cp in ('CE', 'PE'):
            if refp[cp] is None or j < 1: continue
            if G_ and not ((l[j] < l[max(j - G_, 0):j].min()) if cp == 'CE' else (h[j] > h[max(j - G_, 0):j].max())): continue
            dv = (refp[cp] - l[j]) if cp == 'CE' else (h[j] - refp[cp])
            if dv > stp: n = int(dv // stp); sells.append((('PE' if cp == 'CE' else 'CE') if P.get('flip_ladder') else cp, atm(c0), min(n, 10) if mult else 1, 1)); refp[cp] = refp[cp] - n * stp if cp == 'CE' else refp[cp] + n * stp
        if pair: refp = {'CE': c0, 'PE': c0}
        for cp in ('CE', 'PE'):
            o = 'PE' if cp == 'CE' else 'CE'; acc[cp] += P['r'] * nbb[o]; n = int(acc[cp]); acc[cp] -= n
            if n: sells.append((cp, atm(c0), n, 1))
        if P.get('hold'): sells = []                                                                                    # diagnostic variant: no new sells on D0 (the carried D-1 book is only managed and closed)
        for cp, k, n, kind in sells:
            if int(k) not in ki: continue
            e = px(cp, k, jp); e = e if e == e else px(cp, k, j); e = e if e == e else 0.0
            if causal and kind == 1:
                ec = px(cp, k, j); e = ec if ec == ec else e                                                                    # reactive sale: filled at the close of the trigger minute
            fl('body_sell', cp, j, k, n, e, -1, n); lots += [[cp, k, e]] * n
        if j == 0 and P['ow']:
            for cp, nn in (('CE', P['ow'] // 2), ('PE', P['ow'] - P['ow'] // 2)):
                if nn == 0: continue
                k = atm(c0 + (1 if cp == 'CE' else -1) * 17 * st); p = px(cp, k, j); fl('body_long', cp, j, k, nn, p if p == p else 0.0, 1, nn); longs[('num', cp, int(k))] = longs.get(('num', cp, int(k)), 0) + nn
        for cp in ('CE', 'PE'):
            S_ = sum(1 for L in lots if L[0] == cp) + sum(n for (m, c2, k), n in oshort.items() if c2 == cp); L_ = sum(n for (m, c2, k), n in longs.items() if c2 == cp); g = S_ - L_; peak[cp] = max(peak[cp], S_)
            if P.get('no_hedge'): continue
            if g > 0:
                a = px(cp, atm(c0), jp); pr = op[(cp, 'close')][:, jp]; otm = (K - c0) * (1 if cp == 'CE' else -1) > 0; ok = otm & np.isfinite(pr)
                if a == a and ok.any():
                    k = K[ok][np.argmin(np.abs(pr[ok] - 0.025 * a))]; p = px(cp, k, j); fl('wing_buy', cp, j, k, g, p if p == p else 0.0, 1, 1); longs[('h_', cp, int(k))] = longs.get(('h_', cp, int(k)), 0) + g
            elif g < 0:
                need = -g; cand = sorted([(m, c2, k) for (m, c2, k), n in longs.items() if c2 == cp and m in ('h_', 'v_') and n > 0], key=lambda x: -((x[2] - c0) * (1 if cp == 'CE' else -1)))
                for key in cand:
                    if need <= 0: break
                    x = min(need, longs[key]); longs[key] -= x; need -= x; p = px(cp, key[2], j); fl('wing_sell', cp, j, key[2], x, p if p == p else 0.0, -1, 1)
                    if longs[key] == 0: del longs[key]
    return fills, dict(gross=cash, peak_CE=peak['CE'], peak_PE=peak['PE'], stop_j=stop_j)
# ---------------- one cycle, both days
def run_cycle(row, run, P=None, causal=True, variant=None):
    P = P or P_FROZEN; cyc = load(row['und'], row['expiry']); unit = float(row['unit']); vd1, vd0 = versions_for(row['d1'], row['d0'], run)
    cfg = d1_config(row['und'], row['d1'], vd1, variant); r1 = run_d1(cyc, cfg, unit, causal, bool((variant or {}).get('flip_ladder')))
    fills0, info = sim_d0(cyc, vd0, P, dict(lots=r1['lots'], longs=r1['longs'], cash=r1['cash']), unit, causal)
    f = pd.DataFrame(r1['fills'] + fills0, columns=['day', 'j', 'cp', 'strike', 'side', 'lots', 'price', 'cls', 'n_orders']); f.insert(0, 'expiry', row['expiry']); f.insert(0, 'und', row['und'])
    return f, dict(und=row['und'], expiry=row['expiry'], d1=row['d1'], d0=row['d0'], split3=row.get('split3'), run=run, vd1=vd1, vd0=vd0, unit=unit, gross=info['gross'], peak_CE=info['peak_CE'], peak_PE=info['peak_PE'], stop_j=info['stop_j'], carried_short_lots=len(r1['lots']), carried_long_lots=int(sum(r1['longs'].values())), d1_orders=r1['n_orders'])
# ---------------- accounting: slippage, dated statutory costs, brokerage per order
def account(f, und, d1, d0, unit, slip_mult=1.0, cost_mult=1.0):
    gross = net_px = costs = slip = 0.0; orders = 0
    for q in f.itertuples():
        day = dt.date.fromisoformat(d1 if q.day == 0 else d0); n_o = max(q.n_orders, 1); lots_per = q.lots / n_o; s = max(0.10 * slip_mult, 0.005 * slip_mult * q.price); e = q.price + q.side * s
        gross += -q.side * q.price * q.lots * unit; net_px += -q.side * e * q.lots * unit; slip += s * q.lots * unit; costs += n_o * ACC.order_costs(und, day, q.side, e * lots_per * unit, cost_mult); orders += n_o
    return dict(gross=gross, net=net_px - costs, costs=costs, slippage=slip, orders=orders)
ACC = ACC
# ---------------- stress re-pricing from the saved fills (needs the bars): delay of d minutes, or fills at the real in-bar position
def reprice(f, cyc, mode, d=0):
    """returns a copy of the fills with prices re-read from the minute bars. mode 'delay': price = close of minute j + d; 'barpos': sells at 0.30 and buys at 0.62 of the minute's low-high range (D0_QTY A4)."""
    g = f.copy(); out = []
    for q in g.itertuples():
        op = cyc['opt1'] if q.day == 0 else cyc['opt0']; K = op['K']; i = int(np.searchsorted(K, q.strike))
        if i >= len(K) or K[i] != q.strike: out.append(q.price); continue
        j = int(min(max(q.j, 0), 374))
        if mode == 'delay': v = op[(q.cp, 'close')][i, min(j + d, 374)]
        else: lo, hi = op[(q.cp, 'low')][i, j], op[(q.cp, 'high')][i, j]; v = lo + (0.30 if q.side < 0 else 0.62) * (hi - lo)
        out.append(float(v) if v == v and v > 0 else q.price)
    g['price'] = out; return g
