"""One cycle of the reconstructed Algo 8, free-running (D-1 engine B1 -> simulated carry -> D0 engine forward configuration), with a cumulative hard stop, then accounting.
Real orders are never an input. Conventions: backtest/recon_bt/PREREGISTRATION.md."""
import sys, os, json, math, datetime, warnings
R = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
for p in (R, f'{R}/d1_strategy', f'{R}/d0_strategy', f'{R}/backtest'): sys.path.insert(0, p)
warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from bt import gitdata, account as ACC
from d1_algo import config_for, D1Engine, ReplayFeed, PaperBroker, run_replay
from d0_algo import D0Config, D0Engine, D0Market
from algo8_integrated.handoff import d1_state_to_d0_opening, HandoffError
STEP = {'NIFTY': 50.0, 'SENSEX': 100.0}; FREEZE = {'NIFTY': 27, 'SENSEX': 50}; REF_UNIT = {'NIFTY': 65, 'SENSEX': 20}; OPEN_S = 33300
FROZEN = json.load(open(f'{R}/backtest/replication/deep_dive/outputs/phase1/8/frozen_d0_params.json')); WAVES = pd.DataFrame(FROZEN['waves'])
_S = None
def src():
    global _S
    if _S is None: _S = gitdata.Src()
    return _S
MIN = [f'{h:02d}:{m:02d}' for h in range(9, 16) for m in range(60) if '09:15' <= f'{h:02d}:{m:02d}' <= '15:29']; MI = {m: i for i, m in enumerate(MIN)}
def load_session(und, expiry, day):
    """one session's index bars and full option chain bars on the 375-minute grid (same construction as the 2026 research caches: forward-filled along time, no back-fill)"""
    S = src(); x = S.csv(f'normalized/{und.lower()}/underlying/spot/{day}.csv'); h = x.datetime.str.slice(11, 16).map(MI); x = x[h.notna()].assign(j=h[h.notna()].astype(int))
    sp = pd.DataFrame({'j': range(375)}).merge(x[['j', 'open', 'high', 'low', 'close']], on='j', how='left').ffill().bfill()
    x = S.csv(f'normalized/{und.lower()}/options/exp{expiry}_{day}.csv'); h = x.datetime.str.slice(11, 16).map(MI); x = x[h.notna()].assign(j=h[h.notna()].astype(int))
    K = np.array(sorted(x.strike.unique()), float); ki = {k: i for i, k in enumerate(K)}; o = {'K': K}
    for cp in ('CE', 'PE'):
        z = x[x.right == cp]
        for col in ('open', 'high', 'low', 'close'):
            a = np.full((len(K), 375), np.nan); a[z.strike.map(ki).values, z.j.values] = z[col].values; o[(cp, col)] = pd.DataFrame(a).T.ffill().T.values
    return sp, o
def d0_config(und, d1, L):
    ver = 'V2' if d1 >= '2026-09-16' else 'V1'; W = WAVES[(WAVES.und == und) & (WAVES.version == ver)]
    return D0Config(waves=[(float(t), int(l)) for t, l in zip(W.t, W.lots)], buyback_theta=FROZEN['theta'], buyback_tp=FROZEN['take_profit'], ladder_step=FROZEN['ladder']['step'], ladder_gate_min=FROZEN['ladder']['gate_min'], ladder_mult=FROZEN['ladder']['multi_lot'],
                    counter_ratio=FROZEN['counter_ratio'], opening_wing_lots=FROZEN['opening_wings_lots'], cycle_stop_rupees=(L if L else 1e18), risk_mode='enforce')
class _Fill:
    def __init__(s, side, price, lots): s.side, s.price, s.lots = side, price, lots
class _Book: pass
def epoch(day, sec): return datetime.date.fromisoformat(day).toordinal() * 86400 + sec
def run_cycle(task):
    """task: dict(und, expiry, d1, d0, lot, L (None = no stop), cost_mult). Returns the cycle's accounting row, fills and equity path."""
    und, expiry, d1, d0, lot, L = task['und'], task['expiry'], task['d1'], task['d0'], int(task['lot']), task.get('L'); cm = task.get('cost_mult', 1.0)
    sp1, o1 = load_session(und, expiry, d1); sp0, o0 = load_session(und, expiry, d0)
    # ---- D-1
    feed = ReplayFeed(sp1.open.values, sp1.high.values, sp1.low.values, sp1.close.values, o1['K'], {k: v for k, v in o1.items() if isinstance(k, tuple)})
    cfg = config_for(und, d1, order_split='one_lot_v2', lot_units=lot, cycle_stop_rupees=L); br = PaperBroker(feed); e1 = D1Engine(cfg, feed, br); run_replay(e1, feed); fills = []
    for f in br.all_fills: fills.append(dict(day=d1, t=float(f.ts), cp=f.right, k=int(f.strike), sg=1 if f.side == 'BUY' else -1, n=int(f.lots), p=float(f.price), orders=1, src='D1'))
    d1_stopped = bool(e1.stopped); d0_stopped = False; handoff = None; ev0 = []; stop_minute = None
    if d1_stopped: stop_minute = int((e1.stop_time - OPEN_S) // 60)
    if not d1_stopped:
        mk = D0Market(K=o0['K'], step=STEP[und], unit=float(lot), spot_open=sp0.open.values, spot_high=sp0.high.values, spot_low=sp0.low.values, spot_close=sp0.close.values, opt={k: v for k, v in o0.items() if isinstance(k, tuple)})
        b = _Book(); from d1_algo.models import Lot
        b.shorts = {}
        for (cp, k), lots in e1.book.shorts.items():
            for l in lots: b.shorts.setdefault((cp, k), []).append(l)
        b.wings = {k: v for k, v in e1.book.wings.items() if v > 0}; b.lump = {k: v for k, v in e1.book.lump.items() if v > 0}
        try:
            op = d1_state_to_d0_opening(b, [_Fill('SELL' if f['sg'] < 0 else 'BUY', f['p'], f['n']) for f in fills], float(lot), chain=mk.K)
            e0 = D0Engine(d0_config(und, d1, L), mk, op); e0.run(); d0_stopped = bool(e0.stopped); ev0 = e0.events
            if d0_stopped: stop_minute = int(min(e.j for e in ev0 if e.cls == 'stop'))
            rej = len(e0.rejected)
        except HandoffError as ex: handoff = str(ex); rej = 0
    # ---- D0 events -> fills at reference prices
    fz = FREEZE[und]
    for e in ev0:
        t = OPEN_S + 60 * e.j
        if e.cls == 'stop':
            agg = {}                                                       # one order per contract and component kind (the engine lists one part per lot; the real stop module sends per-contract orders)
            for kind, n in e.parts: agg[kind] = agg.get(kind, 0) + n
            for kind, n in agg.items(): fills.append(dict(day=d0, t=float(t), cp=e.cp, k=int(e.strike), sg=-1 if kind == 'long' else 1, n=int(n), p=float(e.px), orders=math.ceil(n / fz), src='D0'))
        else: fills.append(dict(day=d0, t=float(t), cp=e.cp, k=int(e.strike), sg=1 if e.side == 'buy' else -1, n=int(e.lots), p=float(e.px), orders=math.ceil(e.lots / fz), src='D0'))
    # ---- accounting
    ch = {d1: (o1, sp1), d0: (o0, sp0)}; gross = 0.0; slip = 0.0; costs = 0.0; n_orders = 0; pos = {}; sl = []
    for f in sorted(fills, key=lambda x: (epoch(x['day'], x['t']))):
        p = f['p']
        if not (p == p) or p <= 0: p = 0.05
        s = max(0.10, 0.005 * p); pe = max(p + f['sg'] * s, 0.05); v_ref = p * f['n'] * lot; v_exe = pe * f['n'] * lot
        gross += -f['sg'] * v_ref; slip += f['sg'] * (pe - p) * f['n'] * lot
        # costs per order chunk (brokerage per order; statutory on value)
        costs += ACC.order_costs(und, f['day'], f['sg'], v_exe, cm) + (f['orders'] - 1) * ACC.BROKERAGE * cm * (1 + ACC.GST); n_orders += f['orders']
        key = (f['cp'], f['k']); pos[key] = pos.get(key, 0) + f['sg'] * f['n']
    # residual positions: cash-settle at intrinsic of the last D0 spot close (reported)
    resid = {k: v for k, v in pos.items() if v != 0}; resid_d1 = {}
    settle = 0.0
    for (cp, k), q in list(pos.items()):
        if q == 0: continue
        s0 = float(sp0.close.values[-1]); iv = max(s0 - k, 0.0) if cp == 'CE' else max(k - s0, 0.0); settle += q * iv * lot
    net_before_settle = gross - slip; net = net_before_settle + settle - costs; gross_total = gross + settle
    # ---- equity path (net, minute closes)
    F = sorted(fills, key=lambda x: epoch(x['day'], x['t'])); fi = 0; cash = 0.0; cc = 0.0; pos = {}; path = []; ki = {d: {int(k): i for i, k in enumerate(ch[d][0]['K'])} for d in ch}; last_j = {d1: 374, d0: 374}
    if d1_stopped: last_j = {d1: 374, d0: -1}
    if d0_stopped: last_j[d0] = min(374, stop_minute + 1)
    for day in (d1, d0):
        for j in range(0, last_j[day] + 1):
            tend = epoch(day, OPEN_S + 60 * (j + 1))
            while fi < len(F) and epoch(F[fi]['day'], F[fi]['t']) < tend:
                f = F[fi]; p = f['p'] if f['p'] == f['p'] and f['p'] > 0 else 0.05; pe = max(p + f['sg'] * max(0.10, 0.005 * p), 0.05); cash += -f['sg'] * pe * f['n'] * lot
                cc += ACC.order_costs(und, f['day'], f['sg'], pe * f['n'] * lot, cm) + (f['orders'] - 1) * ACC.BROKERAGE * cm * (1 + ACC.GST); key = (f['cp'], f['k']); pos[key] = pos.get(key, 0) + f['sg'] * f['n']; fi += 1
            mtm = 0.0
            for (cp, k), q in pos.items():
                if q == 0: continue
                o = ch[day][0]; x = ki[day].get(k); pr = o[(cp, 'close')][x, min(j, 374)] if x is not None else np.nan
                if pr == pr: mtm += q * pr * lot
            path.append((tend, cash + mtm - cc))
    path.append((epoch(d0, 16 * 3600), net))
    spans = {'NIFTY': 'N', 'SENSEX': 'S'}
    return dict(und=und, expiry=expiry, d1=d1, d0=d0, lot=lot, L=L, gross=gross_total, slippage=slip, costs=costs, net=net, n_orders=n_orders, n_fills=len(fills), d1_stopped=d1_stopped, d0_stopped=d0_stopped, stopped=d1_stopped or d0_stopped, stop_minute=stop_minute, handoff_error=handoff,
                residual_d0_contracts=len(resid), residual_d1_contracts=len(resid_d1), settle=settle, min_path=min(v for _, v in path), max_path=max(v for _, v in path), net_scaled_2026lots=net * REF_UNIT[und] / lot, path=path, rejected=rej if (not d1_stopped and handoff is None) else 0)
