"""Unit-lot lifecycle engine. Every fill is split into whole unit lots (1 lot = 65 NIFTY / 20 SENSEX units); each unit lot keeps its identity from entry to its final disposition.
OWNERSHIP IS NOT KNOWN: no allocation id exists in the export. Closing fills are allocated to open lots under several conventions run side by side (FIFO, LIFO, LOW_ENTRY_FIRST, HIGH_ENTRY_FIRST); nothing is assumed to be the original method.
Role routing (module tags are real order metadata): body (`num`) closes body lots; wing (`h_`) closes wing then lump; lump (`v_`) closes lump then wing; stop/manual (`s_`,`m_`) close body, lump, wing for buys and wing, lump, body for sells.
REVIEW FIXES (v2): D1 a body BUY with no body-short inventory is an UNRESOLVED case (excess_body_buy='long': opened as a flagged long, later body sells close it and are labelled BODY_SELL_CLOSING_LONG; excess_body_buy='unrecorded_short': a close of an unrecorded pre-log short, entry unknown); treatment is now identical in every cycle and both are run; D2 stop/manual modules can close stop-role lots; D3 a D0 body SELL at/after 15:10 that finds no body long first closes open WING longs of the same contract (quantity-equal pattern; flagged CROSS_ROLE_EOD_WING_CLOSE) before opening a short; D6 entry_order_lots is the true ORDER size; holding time is in market seconds."""
from collections import defaultdict
import numpy as np, pandas as pd
from ledger import LOT

ROUTE = {('num', 'Sell'): (['body'], 'body'), ('num', 'Buy'): (['body'], 'body'), ('h_', 'Buy'): (['wing'], 'wing'), ('h_', 'Sell'): (['wing', 'lump'], 'wing'), ('v_', 'Buy'): (['lump'], 'lump'), ('v_', 'Sell'): (['lump', 'wing'], 'lump'),
         ('s_', 'Buy'): (['body', 'lump', 'wing', 'stop'], 'stop'), ('s_', 'Sell'): (['wing', 'lump', 'body', 'stop'], 'stop'), ('m_', 'Buy'): (['body', 'lump', 'wing', 'stop'], 'stop'), ('m_', 'Sell'): (['wing', 'lump', 'body', 'stop'], 'stop')}
CONVENTIONS = ('FIFO', 'LIFO', 'LOW_ENTRY_FIRST', 'HIGH_ENTRY_FIRST')


def _pick(L, convention):
    """index of the open lot to close, among candidates L (list of dict) already restricted to the opposite side"""
    if convention == 'FIFO': return 0
    if convention == 'LIFO': return len(L) - 1
    key = [x['entry_price'] for x in L]
    return int(np.argmin(key)) if convention == 'LOW_ENTRY_FIRST' else int(np.argmax(key))


def build_cycle(g, und, expiry, carry_in_known, convention='FIFO', settle_close=None, eod_cross_role=True, excess_body_buy='long'):
    """g: fills of one cycle sorted by (t,row). returns (lots DataFrame, events DataFrame)"""
    lot_units = LOT[und]; books = defaultdict(list); lots = []; events = []; n = 0; order_lots = g.groupby('tag').n_lots.sum().to_dict()
    def new_lot(fill, k, role, side, entry_unrecorded=False, flags=''):
        nonlocal n
        L = dict(lot_id=f'{und[0]}{expiry.replace("-", "")}-{fill.row}-{k}', cycle_id=f'{und}_{expiry}', index=und, expiry=expiry, role=role, side='SHORT' if side < 0 else 'LONG', cp=fill.cp, strike=int(fill.strike), instrument=f'{und} {expiry} {fill.cp} {int(fill.strike)}',
                 entry_row=int(fill.row), entry_trade_id=fill.tradeid, entry_tag=fill.tag, entry_module=fill.module, entry_day=fill.day, entry_sec=int(fill.sec), entry_price=float('nan') if entry_unrecorded else float(fill.px), entry_quantity_units=lot_units, entry_order_lots=None,
                 close_row=-1, close_trade_id='', close_tag='', close_module='', close_day='', close_sec=-1, close_price=float('nan'), close_reason='', n_candidates_at_close=0, flags=flags, entry_unrecorded=entry_unrecorded, open=True)
        lots.append(L); return L
    for fill in g.itertuples():
        closes, open_role = ROUTE[(fill.module, fill.side)]; s = fill.sgn; q = fill.n_lots; k_open = 0
        for rl in closes:
            B = books[(fill.cp, int(fill.strike), rl)]
            while q > 0:
                cand = [x for x in B if (x['side'] == 'SHORT') == (s > 0)]       # buys close shorts, sells close longs
                if not cand: break
                i = _pick(cand, convention); L = cand[i]; B.remove(L)
                L.update(close_row=int(fill.row), close_trade_id=fill.tradeid, close_tag=fill.tag, close_module=fill.module, close_day=fill.day, close_sec=int(fill.sec), close_price=float(fill.px), n_candidates_at_close=len(cand), open=False,
                         close_reason={'num': ('BODY_BUYBACK' if (L['role'] == 'body' and L['side'] == 'SHORT') else ('BODY_SELL_CLOSING_LONG' if L['role'] == 'body' else 'BODY_ORDER')), 'h_': 'HEDGE_ORDER', 'v_': 'LUMP_ORDER', 's_': 'STOP_MODULE', 'm_': 'MANUAL'}[fill.module]); q -= 1
        if eod_cross_role and fill.module == 'num' and fill.side == 'Sell' and fill.day == expiry and fill.sec >= 15 * 3600 + 10 * 60 and q > 0:
            B = books[(fill.cp, int(fill.strike), 'wing')]
            while q > 0:
                cand = [x for x in B if x['side'] == 'LONG']
                if not cand: break
                i = _pick(cand, convention); L = cand[i]; B.remove(L)
                L.update(close_row=int(fill.row), close_trade_id=fill.tradeid, close_tag=fill.tag, close_module=fill.module, close_day=fill.day, close_sec=int(fill.sec), close_price=float(fill.px), n_candidates_at_close=len(cand), open=False, close_reason='CROSS_ROLE_EOD_WING_CLOSE_BY_BODY', flags=(L['flags'] + ';' if L['flags'] else '') + 'CROSS_ROLE_EOD_WING_CLOSE'); q -= 1
        # remaining quantity opens new lots (or is flagged)
        while q > 0:
            flags = ''; unrec = False
            if (fill.module == 'num' and fill.side == 'Buy'):
                if excess_body_buy == 'unrecorded_short' or (not carry_in_known and fill.day == min(g.day)): unrec = True; flags = 'UNRECORDED_PRIOR_SHORT_INTERPRETATION' if carry_in_known else 'UNRECORDED_CARRY_IN_SHORT'
                else: flags = 'BODY_BUY_WITHOUT_RECORDED_SHORT_OPENED_AS_LONG'      # UNRESOLVED: close of a pre-log short, or buy-to-open? The ledger cannot tell; both are run (excess_body_buy parameter)
            elif (fill.module, fill.side) in (('h_', 'Sell'), ('v_', 'Sell'), ('s_', 'Buy')): flags = 'OPENED_BY_CLOSING_SIDE_ORDER'
            if unrec:                                                                # a short that existed before the log: create it as an unrecorded short (entry price unknown) closed by this fill
                L = new_lot(fill, k_open, 'body', -1, entry_unrecorded=True, flags=flags); L.update(entry_row=-1, entry_trade_id='', entry_tag='', entry_module='', entry_day='', entry_sec=-1); L.update(close_row=int(fill.row), close_trade_id=fill.tradeid, close_tag=fill.tag, close_module=fill.module, close_day=fill.day, close_sec=int(fill.sec), close_price=float(fill.px), close_reason='BODY_BUYBACK', n_candidates_at_close=0, open=False)
            else:
                L = new_lot(fill, k_open, open_role, s, flags=flags); books[(fill.cp, int(fill.strike), open_role)].append(L)
            k_open += 1; q -= 1
        for L in lots[-max(k_open, 0):] if k_open else []: L['entry_order_lots'] = order_lots[fill.tag] if not L['entry_unrecorded'] else None; L['entry_fill_lots'] = fill.n_lots if not L['entry_unrecorded'] else None
    # settlement of residual lots
    for B in books.values():
        for L in B:
            if L['open']:
                L.update(close_reason='SETTLEMENT', close_sec=-1, close_day=expiry, close_module='', open=False)
                if settle_close is not None:
                    v = max(settle_close - L['strike'], 0) if L['cp'] == 'CE' else max(L['strike'] - settle_close, 0); L['close_price'] = float(v)
    df = pd.DataFrame(lots)
    if len(df):
        sg = np.where(df.side == 'SHORT', 1, -1); df['realized_pnl'] = sg * (df.entry_price - df.close_price) * lot_units        # short: entry - close ; long: close - entry (sg=-1)
        sess = 15 * 3600 + 30 * 60; same = (df.close_day == df.entry_day); ok = (df.close_sec >= 0) & (df.entry_sec >= 0)
        df['holding_seconds'] = np.where(ok, np.where(same, df.close_sec - df.entry_sec, (sess - df.entry_sec) + (df.close_sec - (9 * 3600 + 15 * 60))), np.nan)        # MARKET seconds (overnight excluded); D-1 -> D0 only
        df['allocation_method'] = convention
    return df


def build_all(fills, cycles, convention='FIFO', settle=None, excess_body_buy='long'):
    out = []
    for r in cycles.itertuples():
        g = fills[(fills.und == r.und) & (fills.expiry == r.expiry)].sort_values(['t', 'row'])
        S = settle(r.und, r.expiry) if settle else None
        out.append(build_cycle(g, r.und, r.expiry, r.carry_in_known, convention, S, True, excess_body_buy))
    return pd.concat(out, ignore_index=True)
