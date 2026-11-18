"""Ladder-level Python reference simulator of the reconstructed Algo 8 decisions on full-chain minute data. Variants:
  R1 = D-1 ladder + wings + leg stop + cycle stop + carry + D0 management (leg stop, cycle stop) + 15:14 flatten. No new D0 sales. No lump hedge (unknown).
  R2 = R1 + D0 sales at the per-slot MEDIAN lots observed in the live window (HYPOTHESIS-level, fitted to that window)."""
from common import *
from data import *
from bt import account as A
import rules as R
SLIP_PCT, SLIP_MIN = 0.005, 0.10


def d0_median_ladder():
    E = pd.read_csv(f'{RES}/live_decision_events.csv'); b = E[(E.tp == 'num') & (E.side == 'Sell') & (E.day == 'D0')].copy(); b['k'] = (b.minute - 1) // 15; b['off'] = (b.minute - 1) % 15
    cyc = b[['und', 'expiry']].drop_duplicates(); out = []
    for k in range(25):
        x = b[(b.k == k) & (b.off < 3)].groupby(['und', 'expiry', 'cp']).lots.sum().unstack('cp').reindex(columns=['CE', 'PE']).fillna(0).reset_index(); f = cyc.merge(x, how='left', on=['und', 'expiry']).fillna(0)
        out.append((int(round(f.CE.median())), int(round(f.PE.median()))))
    return out


def simulate(c, lot, variant='R1', d0_ladder=None, stop_limit=R.CYCLE_STOP_RS, leg_mult=R.LEG_STOP_MULT, wing_on=True, cost_mult=1.0, slip_mult=1.0):
    """returns dict(net, gross, costs, slip, orders list, events list, stopped_at)"""
    und = c['und']; step = 50 if und == 'NIFTY' else 100; strikes = c['strikes']; nS = len(strikes); units = lot
    px = {(d, r): np.where(np.isnan(c[(d, r, 'close')]), np.nan, c[(d, r, 'close')]) for d in (0, 1) for r in ('CE', 'PE')}
    # forward-fill last price along minutes (LTP); keep opens for fills
    for k in px:
        a = px[k]
        for j in range(1, NM):
            m = np.isnan(a[:, j]); a[m, j] = a[m, j - 1]
    op = {(d, r): c[(d, r, 'open')] for d in (0, 1) for r in ('CE', 'PE')}
    def prev_px(d, r, si, j):
        """last completed close BEFORE minute j of day d; at the D0 open (j = 0) that is the last D-1 bar (fix of the D0-open look-ahead found in independent review)"""
        if j > 0: return px[(d, r)][si, j - 1]
        return px[(0, r)][si, NM - 1] if d == 1 else px[(d, r)][si, 0]
    spot = {d: c[(d, 'spot')] for d in (0, 1)}
    events_skipped = []
    lots = []                                   # open lots: dict(role, right, si, entry, id, pair, day0)
    cash = 0.0; events = []; costs = 0.0; slip_tot = 0.0; nid = [0]; stopped = None
    # lot size: at the start of cycle units per lot as inferred
    def fill_px(d, r, si, j, side):
        o = op[(d, r)][si, j]
        if not (o == o): o = prev_px(d, r, si, j)
        s = max(SLIP_MIN * slip_mult, SLIP_PCT * slip_mult * o); return o + side * s, o      # buyer pays more, seller receives less (side=+1 buy)
    def trade(d, j, r, si, side, role, tag):
        nonlocal cash, costs, slip_tot
        p, ref = fill_px(d, r, si, j, side); cash += -side * units * p; slip_tot += abs(p - ref) * units
        day = c['d1'] if d == 0 else c['d0']; costs += A.order_costs(und, day, side, units * p, cost_mult)
        events.append(dict(d=d, j=j, right=r, strike=int(strikes[si]), side=side, role=role, tag=tag, px=p, ref=ref)); return p
    def open_lot(d, j, r, si, role, pair=None):
        side = -1 if role == 'body' else 1
        if not (fill_px(d, r, si, j, side)[0] == fill_px(d, r, si, j, side)[0]): events_skipped.append((d, j, r, int(strikes[si]), role)); return None       # no price yet (no trade and no prior close): the order cannot be priced -> skipped, recorded
        p = trade(d, j, r, si, side, role, 'ENTRY'); nid[0] += 1
        lots.append(dict(id=nid[0], role=role, right=r, si=si, entry=p, pair=pair, d=d)); return nid[0]
    def close_lot(L, d, j, tag):
        side = 1 if L['role'] == 'body' else -1; trade(d, j, L['right'], L['si'], side, L['role'], tag); lots.remove(L)
    def mark_value(d, j):
        s = 0.0
        for L in lots:
            m = prev_px(d, L['right'], L['si'], j); s += (1 if L['role'] == 'wing' else -1) * units * m
        return s
    for d in (0, 1):
        # (d=0 is D-1, d=1 is D0)
        days_ladder = R.LADDER_D1 if d == 0 else (d0_ladder if variant == 'R2' else None)
        for j in range(NM if d == 1 else NM):
            if stopped is not None and d == 1 and j > stopped[1] and not lots: break
            # --- exits first (decision at minute j uses previous-minute close)
            if lots:
                jj = j
                for L in list(lots):
                    if L['role'] != 'body': continue
                    cur = prev_px(d, L['right'], L['si'], jj)
                    if cur == cur and R.leg_stop_hit(cur, L['entry'], leg_mult):
                        close_lot(L, d, jj, 'LEG_STOP')
                        for W in [w for w in lots if w['pair'] == L['id']]: close_lot(W, d, jj, 'WING_WITH_BODY')
                # cycle stop (cash gross of costs, on LTP mark)
                if lots:
                    tot = (cash_gross_cash(events, units)) + mark_value(d, j)
                    if R.cycle_stop_hit(tot, stop_limit) and stopped is None:
                        for L in list(lots): close_lot(L, d, j, 'CYCLE_STOP')
                        stopped = (d, j)
                if d == 1 and j == R.FLATTEN_MIN and lots:
                    for L in list(lots): close_lot(L, d, j, 'FLATTEN')
            # --- entries
            if stopped is None:
                if d == 0 and j >= R.SLOT0 and (j - R.SLOT0) % 15 == 0 and (j - R.SLOT0) // 15 < len(R.LADDER_D1):
                    n = R.LADDER_D1[(j - R.SLOT0) // 15]; ce_n = pe_n = n
                elif d == 1 and variant == 'R2' and j >= R.SLOT0 and (j - R.SLOT0) % 15 == 0 and (j - R.SLOT0) // 15 < len(d0_ladder) and j < R.FLATTEN_MIN - 15:
                    ce_n, pe_n = d0_ladder[(j - R.SLOT0) // 15]
                else: ce_n = pe_n = 0
                for r, n in (('CE', ce_n), ('PE', pe_n)):
                    for _ in range(n):
                        S = spot[d][j - 1] if j > 0 else spot[d][0]
                        if S != S: continue
                        si = R.nearest_strike(strikes, S, step); body = open_lot(d, j, r, si, 'body'); bp = prev_px(d, r, si, j)
                        if wing_on and body is not None:
                            wi = R.wing_strike_index(strikes, r, si, bp, lambda i: prev_px(d, r, i, j))
                            if wi is not None: open_lot(d, j, r, wi, 'wing', pair=body)
        # day end: D-1 carry overnight (no action). At end of D0, anything still open is cash settled
    S0 = YAHOO[und].close.get(pd.Timestamp(c['d0']), np.nan); sett = 0.0; settle_costs = 0.0
    for L in lots:
        v = max(S0 - strikes[L['si']], 0) if L['right'] == 'CE' else max(strikes[L['si']] - S0, 0); sett += (1 if L['role'] == 'wing' else -1) * units * v
    gross = cash_gross_cash(events, units) + sett
    return dict(net=cash + sett - costs, gross=gross, costs=costs, slippage=slip_tot, n_orders=len(events), events=events, stopped=stopped, open_at_end=len(lots), cash_before_costs=cash, skipped=len(events_skipped))


def cash_gross_cash(events, units):
    """cash at reference (bar-open) prices, no slippage"""
    return sum(-e['side'] * units * e['ref'] for e in events)
