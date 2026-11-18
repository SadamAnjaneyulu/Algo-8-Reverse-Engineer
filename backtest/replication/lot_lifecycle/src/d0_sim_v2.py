"""D0 replay simulator v2 (remediation of review defects A, B, E; see SIMULATOR_DEFECT_REMEDIATION.md). Derived from d0_reconstruction/d0_sim.py v1.1 (preserved). Differences: (A) passive lump/stop/manual/body-long lots are CLOSED at a cycle stop (the ledger shows the stop module closing lump lots); (B) replacement sales carry NO wing by default and `replacement_wings='one_per_lot'` gives the opposite bound -- the ledger supports neither as a rule (41 % paired, 0.47 per lot); (E) the opening book can be supplied from the independent lot engine (`start=`).
 (separate module; not part of the production engine). Starts every D0 from the ACTUAL overnight book (ledger orders of D-1) and applies the frozen rule set D0-v1 minute by minute.
Time convention (identical to the R1 fix): index j = minute since 09:15; a decision at minute j may use data up to the close of minute j-1 (at j = 0 the last D-1 bar); fills are at the OPEN of minute j.
Components (rules_d0_v1.json): S1 scheduled ladder at grid-A slots while the book is active; S2 Clock-B tick (act iff short lots >= threshold; buy back 1 lot of the largest short contract; replace 1 lot at ATM next minute); S3 optional 1.6x price stop (variant);
S4 15:14 flatten; S5 wings (price ratio); cycle stop on LTP MTM. Lump-hedge, platform risk actor and manual orders are passive (held to expiry)."""
import json
from collections import deque, defaultdict
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'd0_reconstruction'))
from d0common import *
from data import load_cycle, NM
import rules as R1                                    # replication/rules.py (nearest_strike, wing_strike_index, leg_stop_hit)
RULES = json.load(open(os.path.join(RES, 'rules_d0_v1.json')))
LAD = RULES['S1_scheduled_ladder_slot0_is_0916']; TH = RULES['S2_clockB_act_threshold_total_short_lots']; WR = RULES['S5_wing_ratio_sched_off']; WR_REP = RULES['S5_wing_ratio_replacement']; WL_REP = RULES['S5_wing_lots_per_lot_replacement']


def start_book(ev_d1):
    """actual D-1 orders -> body shorts, wings, passive lots, cash (rupees at fill prices)"""
    body = defaultdict(deque); wing = defaultdict(deque); passive = defaultdict(float); cash = 0.0
    ROUTE = {('num', 'Sell'): 'body', ('num', 'Buy'): 'body', ('h_', 'Buy'): 'wing', ('h_', 'Sell'): 'wing'}
    for r in ev_d1.itertuples():
        cash += -(1 if r.side == 'Buy' else -1) * r.lots * LOT[r.und] * r.px; k = (r.cp, r.strike); q = r.lots
        if r.module == 'num':
            if r.side == 'Sell':
                bl = passive.get(('body_long',) + k, 0.0)            # v1.1 fix: a body Sell first closes any body LONG lots (same routing as build_events.py)
                t = min(q, bl)
                if t > 0: passive[('body_long',) + k] = bl - t; q -= t
                if q > 1e-9: body[k].append([q, r.px])
                q = 0
            else:
                L = body[k]
                while q > 1e-9 and L: t = min(q, L[0][0]); L[0][0] -= t; q -= t; (L.popleft() if L[0][0] <= 1e-9 else None)
                if q > 1e-9: passive[('body_long',) + k] += q
        elif r.module == 'h_':
            if r.side == 'Buy': wing[k].append([q, r.px])
            else:
                L = wing[k]
                while q > 1e-9 and L: t = min(q, L[0][0]); L[0][0] -= t; q -= t; (L.popleft() if L[0][0] <= 1e-9 else None)
                if q > 1e-9: passive[('wing_short',) + k] += q
        else: passive[(r.module, ) + k] += (r.lots if r.side == 'Buy' else -r.lots)               # lump / stop / manual: signed net, passive
    return body, wing, passive, cash


def simulate_d0(c, und, ev_d1, start=None, replacement_wings='none', passive_at_stop='close_all', price_stop=False, cycle_stop=True, stop_rs=RULES['cycle_stop_rs'], no_replacement=False, no_scheduled=False, no_clockb=False):
    lot = LOT[und]; step = 50 if und == 'NIFTY' else 100; strikes = c['strikes']; ki = {int(k): i for i, k in enumerate(strikes)}
    px = {}
    for r in ('CE', 'PE'):
        a = np.concatenate([c[(0, r, 'close')], c[(1, r, 'close')]], axis=1).copy()
        for j in range(1, a.shape[1]): m = np.isnan(a[:, j]); a[m, j] = a[m, j - 1]
        px[r] = a[:, NM:]; px[r + '_prev0'] = a[:, NM - 1]
    op = {r: c[(1, r, 'open')] for r in ('CE', 'PE')}; spot1 = c[(1, 'spot')]; spot0_last = c[(0, 'spot')][NM - 1]
    import copy as _copy
    body, wing, passive, cash = (_copy.deepcopy(start) if start is not None else start_book(ev_d1));          # D7: never mutate the caller's start tuple
    cash0 = cash; log = []; pend = []; stopped = False; kclock = 0
    def prev(r, si, j): return px[r + '_prev0'][si] if j == 0 else px[r][si, j - 1]
    def mk(cp, k, j, fb):
        i = ki.get(k); p = prev(cp, i, j) if i is not None else np.nan
        return p if p == p else fb
    def S_prev(j): return spot0_last if j == 0 else spot1[j - 1]
    def fill(r, si, j):
        o = op[r][si, j]; return o if o == o else prev(r, si, j)
    def trade(j, r, si, side, q, role, cls):
        nonlocal cash; p = fill(r, si, j); cash += -side * q * lot * p; log.append(dict(j=j, cp=r, strike=int(strikes[si]), side=side, lots=q, role=role, cls=cls, ref_px=p)); return p
    def trade_k(j, r, k, side, q, role, cls):
        """trade by strike; contracts absent from the downloaded chain are filled at the last actual order price of that lot (documented limitation)"""
        nonlocal cash
        i = ki.get(k)
        if i is not None: return trade(j, r, i, side, q, role, cls)
        L = wing.get((r, k)) or body.get((r, k)); p = L[0][1] if L else 0.0; cash += -side * q * lot * p; log.append(dict(j=j, cp=r, strike=int(k), side=side, lots=q, role=role, cls=cls, ref_px=p, missing_contract=True)); return p
    def total_short(): return sum(x[0] for L in body.values() for x in L)
    def mtm(j):
        v = cash
        for (cp, k), L in body.items(): v += -sum(x[0] for x in L) * lot * mk(cp, k, j, L[0][1] if L else 0)
        for (cp, k), L in wing.items(): v += sum(x[0] for x in L) * lot * mk(cp, k, j, L[0][1] if L else 0)
        for key, q in passive.items():
            if key[0] in ('body_long', 'v_', 's_', 'm_', 'wing_short'):
                cp, k = key[1], key[2]; v += (q if key[0] != 'wing_short' else -q) * lot * mk(cp, k, j, 0.0)
        return v
    def sell_body(j, r, lots, cls, wing_per_lot, wratio):
        S = S_prev(j)
        if S != S: return
        si = R1.nearest_strike(strikes, S, step)
        if not (fill(r, si, j) == fill(r, si, j)): return
        bp = prev(r, si, j); trade(j, r, si, -1, lots, 'body', cls); body[(r, int(strikes[si]))].append([lots, fill(r, si, j)])
        nw = (int(lots) if replacement_wings == 'one_per_lot' else 0) if cls == 'REPLACEMENT_SALE' else int(np.floor(lots * wing_per_lot + 1e-9))
        if nw > 0 and bp == bp:
            wi = R1.wing_strike_index(strikes, r, si, bp, lambda i: prev(r, i, j), ratio=wratio)
            if wi is not None and fill(r, wi, j) == fill(r, wi, j): trade(j, r, wi, 1, nw, 'wing', 'HEDGE_ADD'); wing[(r, int(strikes[wi]))].append([nw, fill(r, wi, j)])
    def buy_body(j, r, k, lots, cls):
        L = body[(r, k)]; q = min(lots, sum(x[0] for x in L))
        if q <= 1e-9: return 0
        trade_k(j, r, k, 1, q, 'body', cls); rem = q
        while rem > 1e-9 and L: t = min(rem, L[0][0]); L[0][0] -= t; rem -= t; (L.popleft() if L[0][0] <= 1e-9 else None)
        return q
    def release_wings(j, r, lots):
        """HDG-06: wings are released alongside body buy-backs of the same right (1 wing lot per body lot, farthest-first)"""
        keys = sorted([k for (cp, k), L in wing.items() if cp == r and sum(x[0] for x in L) > 1e-9], key=lambda k: -abs(k - S_prev(j) if S_prev(j) == S_prev(j) else 0)); rem = lots
        for k in keys:
            L = wing[(r, k)]; q = min(rem, sum(x[0] for x in L)); trade_k(j, r, k, -1, q, 'wing', 'HEDGE_REDUCE'); x_ = q
            while x_ > 1e-9 and L: t = min(x_, L[0][0]); L[0][0] -= t; x_ -= t; (L.popleft() if L[0][0] <= 1e-9 else None)
            rem -= q
            if rem <= 1e-9: break
    v0 = mtm(0)                                             # value of the actual carry-in book at the D-1 close (common baseline for sim and actual D0 increments)
    for j in range(NM):
        mm = (555 + j) % 60; hh = (555 + j) // 60
        # pending replacements from the previous minute
        for (jj, r, lots) in [p for p in pend if p[0] == j]:
            if not stopped and not no_replacement: sell_body(j, r, lots, 'REPLACEMENT_SALE', WL_REP, WR_REP)
        pend = [p for p in pend if p[0] != j]
        # stops
        if cycle_stop and not stopped and (total_short() > 0) and mtm(j) <= -stop_rs:
            for (cp, k), L in list(body.items()):
                q = sum(x[0] for x in L)
                if q > 1e-9: buy_body(j, cp, k, q, 'STOP_LIQUIDATION')
            for (cp, k), L in list(wing.items()):
                q = sum(x[0] for x in L)
                if q > 1e-9: trade_k(j, cp, k, -1, q, 'wing', 'STOP_LIQUIDATION'); L.clear()
            for key, q in (list(passive.items()) if passive_at_stop == 'close_all' else []):                  # (A) ASSUMPTION (not evidence): close every passive lot at the stop; passive_at_stop='keep' is the legacy bound (the ledger shows the stop module closing only ~12 % of carried lump lots)
                if key[0] in ('body_long', 'v_', 's_', 'm_', 'wing_short') and abs(q) > 1e-9:
                    cp_, k_ = key[1], key[2]; side_ = 1 if (key[0] == 'wing_short' or q < 0) else -1; trade_k(j, cp_, k_, side_, abs(q), 'passive', 'STOP_LIQUIDATION_PASSIVE'); passive[key] = 0.0
            stopped = True
        if stopped: continue
        if price_stop:
            for (cp, k), L in list(body.items()):
                for x in list(L):
                    pr = mk(cp, k, j, x[1])
                    if R1.leg_stop_hit(pr, x[1], RULES['S3_price_stop_mult']) and x in L:
                        trade_k(j, cp, k, 1, x[0], 'body', 'PRICE_STOP_BUYBACK'); L.remove(x); release_wings(j, cp, x[0])
        # S4 flatten
        if j == RULES['S4_final_flatten_minute_0915_eq_0']:
            for (cp, k), L in list(body.items()):
                q = sum(x[0] for x in L)
                if q > 1e-9: buy_body(j, cp, k, q, 'FINAL_LIQUIDATION')
            for (cp, k), L in list(wing.items()):
                q = sum(x[0] for x in L)
                if q > 1e-9: trade_k(j, cp, k, -1, q, 'wing', 'FINAL_LIQUIDATION'); L.clear()
            continue
        if j > RULES['S4_final_flatten_minute_0915_eq_0']: continue
        # S2 Clock-B tick
        if mm % 15 == 14 and (hh * 60 + mm) >= 9 * 60 + 29 and not no_clockb:
            if total_short() >= TH:
                cand = [((cp, k), sum(x[0] for x in L)) for (cp, k), L in body.items() if sum(x[0] for x in L) > 1e-9]
                S = S_prev(j); (cp, k), q = sorted(cand, key=lambda z: (-z[1], abs(z[0][1] - S)))[0]
                if buy_body(j, cp, k, 1, 'CLOCKB_BUYBACK'): release_wings(j, cp, 1); pend.append((j + 1, cp, 1))
        # S1 scheduled slot (grid A: minute-of-hour 1,16,31,46 from 09:16)
        if mm % 15 == 1 and j >= 1 and not no_scheduled and total_short() > 0:
            k_ = (j - 1) // 15
            if k_ < len(LAD):
                for r in ('CE', 'PE'):
                    n = LAD[k_][r]
                    for _ in range(n): sell_body(j, r, 1, 'SCHEDULED_SALE', 1.0, WR)
    # settlement of anything left (D0 close)
    S0 = YAHOO[und].close.get(pd.Timestamp(c['d0']), np.nan); sett = 0.0
    for (cp, k), L in body.items(): q = sum(x[0] for x in L); sett += -q * lot * (max(S0 - k, 0) if cp == 'CE' else max(k - S0, 0))
    for (cp, k), L in wing.items(): q = sum(x[0] for x in L); sett += q * lot * (max(S0 - k, 0) if cp == 'CE' else max(k - S0, 0))
    for key, q in passive.items():
        if key[0] in ('body_long', 'v_', 's_', 'm_', 'wing_short'):
            cp, k = key[1], key[2]; v = max(S0 - k, 0) if cp == 'CE' else max(k - S0, 0); sett += (q if key[0] != 'wing_short' else -q) * lot * v
    return dict(gross=cash + sett, v0=v0, cash_start=cash0, sett=sett, orders=pd.DataFrame(log), stopped=stopped, passive_open_at_end={k: v for k, v in passive.items() if abs(v) > 1e-9})
