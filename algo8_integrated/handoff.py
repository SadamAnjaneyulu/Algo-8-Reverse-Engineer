"""D-1 -> D0 handoff. Builds the D0 opening state from the simulated D-1 session alone (Gate 6 contract, reports/PHASE1_GATE6_PLAN.md section 2). No real order or position is accepted."""
from __future__ import annotations
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..', 'd0_strategy'))
from d0_algo import D0Opening


class HandoffError(Exception):
    pass


def d1_state_to_d0_opening(book, fills, unit: float, chain=None) -> D0Opening:
    """book: d1_algo Book at the D-1 end; fills: the D-1 broker's fills (Fill with .side 'BUY'/'SELL', .price, .lots); unit: lot size; chain: strikes of the D0 option chain (carried contracts must be in it)."""
    lots = [[cp, float(k), float(l.entry_price)] for (cp, k), L in sorted(book.shorts.items()) for l in L]
    longs = {}
    for (cp, k), n in sorted(book.wings.items()):
        if n > 0: longs[('h_', cp, int(k))] = longs.get(('h_', cp, int(k)), 0) + int(n)         # mapping assumption: opening wings carry with the protective wings
    for (cp, k), n in sorted(book.lump.items()):
        if n > 0: longs[('v_', cp, int(k))] = longs.get(('v_', cp, int(k)), 0) + int(n)
    cash = 0.0
    for f in fills: cash += (1.0 if f.side == 'SELL' else -1.0) * float(f.price) * int(f.lots) * float(unit)
    if chain is not None:
        have = {float(x) for x in chain}; miss = sorted({k for _, k, _ in lots if k not in have} | {float(k) for (_, _, k) in longs if float(k) not in have})
        if miss: raise HandoffError(f'carried contracts outside the D0 chain: {miss}')
    return D0Opening(lots=lots, longs=longs, oshort={}, cash=cash)
