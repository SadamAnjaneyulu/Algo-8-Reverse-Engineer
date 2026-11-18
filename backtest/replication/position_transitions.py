"""Position-level transition dataset from the REAL ledger: state before every 15-minute slot, per contract, with the action taken during the slot (RETAINED / ADDED / REDUCED / CLOSED / OPENED) and decision-time features.
Features use information available at the snapshot (previous completed minute): contract price, spot, ratio to cheapest/average open entry, strike offset, Black-Scholes IV/delta (r=0; IV solved from the option price -- a *derived* measure), cycle MTM at LTP, time to expiry.
Outcome: subsequent P&L of the contract's lots to the next snapshot and to the end. ASSOCIATION ONLY."""
import math
from collections import defaultdict
from scipy.stats import norm
from common import *
from data import *
E = pd.read_csv(f'{RES}/live_decision_events.csv'); E = E[E.tp.isin(['num', 'h_'])].copy(); E['sgn'] = np.where(E.side == 'Buy', 1, -1)
LOT = {'NIFTY': 65, 'SENSEX': 20}


def bs(S, K, T, sigma, cp):
    if T <= 0 or sigma <= 0: return (max(S - K, 0) if cp == 'CE' else max(K - S, 0)), 0.0
    d1 = (math.log(S / K) + 0.5 * sigma * sigma * T) / (sigma * math.sqrt(T)); d2 = d1 - sigma * math.sqrt(T)
    p = S * norm.cdf(d1) - K * norm.cdf(d2) if cp == 'CE' else K * norm.cdf(-d2) - S * norm.cdf(-d1); delta = norm.cdf(d1) if cp == 'CE' else norm.cdf(d1) - 1; return p, delta


def iv(p, S, K, T, cp):
    intr_ = max(S - K, 0) if cp == 'CE' else max(K - S, 0)
    if T <= 0 or p <= intr_ + 0.01: return np.nan
    lo, hi = 0.01, 3.0
    for _ in range(40):
        mid = 0.5 * (lo + hi); v = bs(S, K, T, mid, cp)[0]
        if v > p: hi = mid
        else: lo = mid
    return 0.5 * (lo + hi)


rows = []
for (u, e), g in E.groupby(['und', 'expiry']):
    m = g.iloc[0]; c = load_cycle(u, e, m.d1, m.d0); step = 50 if u == 'NIFTY' else 100; ki = {int(k): i for i, k in enumerate(c['strikes'])}; lot = LOT[u]
    g = g.sort_values(['day', 'row']); lots = defaultdict(list); cash = 0.0; ev = list(g.itertuples()); ptr = 0; totmin = 750
    exp_ts = pd.Timestamp(m.d0) + pd.Timedelta(hours=15, minutes=30)
    snaps = [(di, 1 + 15 * k) for di in (0, 1) for k in range(25)]
    prev_state = None
    for di, sm in snaps:
        gm = di * 375 + sm
        # apply all events with global minute < gm
        while ptr < len(ev) and ((0 if ev[ptr].day == 'D-1' else 1) * 375 + ev[ptr].minute) < gm:
            r = ev[ptr]; key = (r.tp, r.cp, int(r.strike)); q = r.lots
            if (r.tp == 'num' and r.side == 'Sell') or (r.tp == 'h_' and r.side == 'Buy'): lots[key].append([r.px, q]); cash += -r.sgn * q * lot * r.px
            else:
                cash += -r.sgn * q * lot * r.px
                while q > 1e-9 and lots[key]:
                    x = lots[key][0]; t = min(q, x[1]); x[1] -= t; q -= t
                    if x[1] <= 1e-9: lots[key].pop(0)
            ptr += 1
        pm = sm - 1; S = c[(di, 'spot')][max(pm, 0)]; ts = pd.Timestamp(m.d1 if di == 0 else m.d0) + pd.Timedelta(hours=9, minutes=15 + pm)
        T = max((exp_ts - ts).total_seconds() / (365 * 86400), 1e-9)
        state = {}; mark = 0.0
        for key, L in lots.items():
            q = sum(x[1] for x in L)
            if q <= 1e-9: continue
            role, cp, K = key; i = ki.get(K); p = c[(di, cp, 'close')][i, max(pm, 0)] if i is not None else np.nan
            ent = [x[0] for x in L for _ in range(1)]; cheapest = min(ent); avg = sum(x[0] * x[1] for x in L) / q
            sg = 1 if role == 'h_' else -1; mark += sg * q * lot * p
            state[key] = dict(q=q, p=p, cheapest=cheapest, avg=avg, ratio_cheapest=p / cheapest, ratio_avg=p / avg, off=(K - S) / step, upnl=sg * -(avg - p) * -1 * q * lot * (-1) if False else (avg - p) * q * lot * (1 if role == 'num' else -1) * (1 if role == 'num' else 1))
        cyc_mtm = cash + mark
        if prev_state is not None:
            ps, pdi, psm, pS, pmtm, pT = prev_state
            keys = set(ps) | set(state)
            rt_open = defaultdict(int)
            for key in keys:
                q0 = ps.get(key, {}).get('q', 0); q1 = state.get(key, {}).get('q', 0)
                if q1 > q0 + 1e-9 and q0 == 0: a = 'OPENED'
                elif q1 > q0 + 1e-9: a = 'ADDED'
                elif q1 < q0 - 1e-9 and q1 <= 1e-9: a = 'CLOSED'
                elif q1 < q0 - 1e-9: a = 'REDUCED'
                else: a = 'RETAINED'
                if key[0] == 'num' and a in ('OPENED', 'ADDED'): rt_open[key[1]] += 1
                f = ps.get(key)
                if f is None: continue                                    # decisions about EXISTING positions only
                role, cp, K = key; Sx = pS; Tx = pT; ivv = iv(f['p'], Sx, K, Tx, cp); dl = bs(Sx, K, Tx, ivv, cp)[1] if ivv == ivv else np.nan
                rows.append(dict(und=u, expiry=e, day='D-1' if pdi == 0 else 'D0', slot=(psm - 1) // 15, role=role, cp=cp, strike=K, action=a, q0=q0, q1=q1, price=f['p'], cheapest_entry=f['cheapest'], avg_entry=f['avg'], ratio_cheapest=f['ratio_cheapest'], ratio_avg=f['ratio_avg'], strike_off_steps=f['off'], iv=ivv, delta=dl,
                                 cycle_mtm=pmtm, hours_to_exp=pT * 365 * 24, spot=pS, spot_move_steps=(S - pS) / step if True else np.nan, d_price=(state.get(key, {}).get('p', np.nan) - f['p']) if key in state else np.nan, lots_total_book=sum(v['q'] for k2, v in ps.items() if k2[0] == 'num')))
        prev_state = (state, di, sm, S, cyc_mtm, T)
T_ = pd.DataFrame(rows); T_.to_csv(f'{RES}/position_transitions.csv', index=False); print(len(T_), T_.groupby(['role', 'action']).size().unstack().fillna(0).astype(int))
