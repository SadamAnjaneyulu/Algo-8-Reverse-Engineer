"""Execution, cost, settlement, margin-proxy and equity accounting applied to the fills the engine produced. The engine itself has no costs, no slippage and no settlement.
All amounts are in rupees. Gross = engine reference prices + settlement; Net = delayed / slipped execution prices - statutory costs."""
import bisect
from datetime import date
import numpy as np
from . import config as C
from .scen import epoch, lot_of, iid, end_hm

# ----- cost model (rates by date). Status: STT 0.1%->0.15% from 2026-04-01 and exercise 0.125%->0.15%: CONFIRMED by 2026 budget reports; 0.0625% before 2024-10-01: widely cited, date of change from memory (UNVERIFIED);
# exchange charges, brokerage, stamp duty, SEBI fee, GST: standard published schedules quoted from memory (UNVERIFIED); Algo 8's actual broker terms are unknown.
BROKERAGE = 20.0; GST = 0.18; SEBI = 0.000001; STAMP_BUY = 0.00003
TXN = {'NIFTY': 0.00035, 'SENSEX': 0.000325}


def stt_sell(d):
    d = date.fromisoformat(d) if isinstance(d, str) else d
    return 0.000625 if d < date(2024, 10, 1) else (0.001 if d < date(2026, 4, 1) else 0.0015)


def stt_exercise(d):
    d = date.fromisoformat(d) if isinstance(d, str) else d
    return 0.00125 if d < date(2026, 4, 1) else 0.0015


def order_costs(und, day, side, value, mult=1.0):
    b = BROKERAGE; t = TXN[und] * value; s = SEBI * value; g = GST * (b + t + s); stamp = STAMP_BUY * value if side > 0 else 0.0; stt = stt_sell(day) * value if side < 0 else 0.0
    return mult * (b + t + s + g + stamp + stt)


class Px:
    """per-leg price access built from the cycle's real bars (D-1 and D0)"""
    def __init__(self, c):
        self.leg_of = {iid(c, lid): lid for lid in c['legs']}; self.start = {}; self.open = {}; self.close = {}
        for lid in c['legs']:
            st, op, cl = [], [], []
            for day, fr in ((c['d1'], c['frames'][lid][0]), (c['d0'], c['frames'][lid][1])):
                for r in fr.itertuples():
                    if '09:15' <= r.hm <= '15:29': st.append(epoch(day, r.hm)); op.append(float(r.open)); cl.append(float(r.close))
            o = np.argsort(st); self.start[lid] = np.array(st)[o]; self.open[lid] = np.array(op)[o]; self.close[lid] = np.array(cl)[o]

    def mark(self, lid, t):
        """close of the latest bar that has completed by time t (bar start + 60 <= t); None before the first bar"""
        i = bisect.bisect_right(self.start[lid], t - 60) - 1
        return None if i < 0 else float(self.close[lid][i])

    def bar_open(self, lid, t):
        i = bisect.bisect_left(self.start[lid], t)
        return float(self.open[lid][i]) if i < len(self.start[lid]) and self.start[lid][i] == t else self.mark(lid, t)


def intrinsic(cp, K, S): return max(S - K, 0.0) if cp == 'CE' else max(K - S, 0.0)


def max_loss(c, inv):
    """worst-case loss at expiry of the open positions, premiums ignored (conservative margin PROXY: not exchange SPAN)"""
    pts = [0.0] + [c['legs'][l]['strike'] for l in c['legs']]; pts.append(max(pts) * 2)
    pay = [sum(q * intrinsic(c['legs'][l]['cp'], c['legs'][l]['strike'], S) for l, q in inv.items()) for S in pts]
    return max(-min(pay), 0.0)


def account(c, fills, variant, p):
    """fills: engine fills [(fid, instrument, ts, side, qty, price_paise)]. p: dict(slip_pct, slip_min, delay_min, cost_mult). Returns per-cycle result with equity path."""
    px = Px(c); und = c['und']; d = p.get('delay_min', 0) * 60; sp, sm, cm = p.get('slip_pct', 0.005), p.get('slip_min', 0.10), p.get('cost_mult', 1.0)
    E = epoch(c['d0'], end_hm(variant)); lot = lot_of(c)
    trades = []                                                  # (ts, lid, side, qty, ref_price(engine), exec_price, kind)
    inv = {l: 0 for l in c['legs']}
    for fid, ins, ts, side, qty, pr in sorted(fills, key=lambda f: (f[2], f[0])):
        lid = px.leg_of[ins]; ref = pr / 100.0
        if fid.startswith('S'):
            e = px.bar_open(lid, ts + d); e = ref if e is None else e
        else:
            e = px.mark(lid, ts + d); e = ref if e is None else e
        slip = max(sm, sp * e); trades.append((ts, lid, side, qty, ref, e + side * slip, 'SEED' if fid.startswith('S') else 'ENGINE')); inv[lid] += side * qty
    settle = []; S_off = c['official_close']; end_trades = []
    if variant == 'FLATTEN_1525':
        for lid, q in inv.items():
            if q:
                ref = px.mark(lid, E); e = px.mark(lid, E + d); ref = ref if ref is not None else 0.05; e = e if e is not None else ref; side = -1 if q > 0 else 1; slip = max(sm, sp * e)
                tr = (E, lid, side, abs(q), ref, e + side * slip, 'FLATTEN'); trades.append(tr); end_trades.append(tr); inv[lid] = 0
    else:
        for lid, q in inv.items():
            if q: settle.append((lid, q, intrinsic(c['legs'][lid]['cp'], c['legs'][lid]['strike'], S_off)))
    # ----- cash flows
    gross = sum(-t[2] * t[3] * t[4] for t in trades) + sum(q * v for _, q, v in settle)
    net_px = sum(-t[2] * t[3] * t[5] for t in trades) + sum(q * v for _, q, v in settle)
    costs = sum(order_costs(und, c['d1'] if t[6] == 'SEED' else c['d0'], t[2], t[3] * t[5], cm) if t[6] != 'ENGINE' or True else 0 for t in trades)
    exercise_stt = sum(cm * stt_exercise(c['d0']) * v * q for _, q, v in settle if q > 0 and v > 0)
    costs += exercise_stt; net = net_px - costs
    # per-leg gross attribution (reference prices)
    leg_pnl = {l: 0.0 for l in c['legs']}
    for t in trades: leg_pnl[t[1]] += -t[2] * t[3] * t[4]
    for lid, q, v in settle: leg_pnl[lid] += q * v
    # ----- equity path (net): minute grid of the real bars
    T = sorted({int(x) for l in c['legs'] for x in px.start[l] + 60 if x + 60 <= E + 3600} | {t[0] for t in trades}); T = [t for t in T if t >= min(tr[0] for tr in trades)]
    path = []; cash = 0.0; ti = 0; tr_sorted = sorted(trades, key=lambda t: t[0]); pos = {l: 0 for l in c['legs']}; cost_cum = 0.0
    for t in T:
        while ti < len(tr_sorted) and tr_sorted[ti][0] <= t:
            tr = tr_sorted[ti]; cash += -tr[2] * tr[3] * tr[5]; cost_cum += order_costs(und, c['d1'] if tr[6] == 'SEED' else c['d0'], tr[2], tr[3] * tr[5], cm); pos[tr[1]] += tr[2] * tr[3]; ti += 1
        mtm = sum(q * (px.mark(l, t) or 0.0) for l, q in pos.items()); path.append((t, cash + mtm - cost_cum))
    path.append((E + 1, net))                                    # final settled value
    # ----- margin proxy path (at fill events)
    mpos = {l: 0 for l in c['legs']}; peak_margin = 0.0; marg = []
    for tr in tr_sorted:
        mpos[tr[1]] += tr[2] * tr[3]; m = max_loss(c, mpos); peak_margin = max(peak_margin, m); marg.append((tr[0], m))
    n_orders = len(trades); lots_total = sum(t[3] for t in trades) / lot
    return dict(gross=gross, net=net, slippage=gross - net_px, costs=costs, net_before_costs=net_px, n_orders=n_orders, n_engine_orders=sum(1 for t in trades if t[6] == 'ENGINE'), lots_traded=lots_total, peak_margin=peak_margin,
                leg_pnl=leg_pnl, path=path, trades=trades, settle=settle, official_close=S_off, official_close_src=c['official_close_src'], min_path=min(v for _, v in path), max_path=max(v for _, v in path))
