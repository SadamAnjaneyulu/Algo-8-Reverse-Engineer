"""Independent opening-book reconstruction (defect E) from the lot engine: the D0 start state = lots opened on D-1 and still open at the D-1 close, with exact per-fill entry prices and exact D-1 cash. Different code path from d0_sim.start_book / build_events."""
from collections import deque, defaultdict
from ledger import *
from lots import build_cycle


def opening_book(F, und, expiry, d1, convention='FIFO'):
    g = F[(F.und == und) & (F.expiry == expiry) & (F.day == d1)].sort_values(['t', 'row'])
    L = build_cycle(g, und, expiry, True, convention, None)                               # only D-1 fills: lots still open are those with close_reason SETTLEMENT (nothing closed them)
    lot = LOT[und]; body = defaultdict(deque); wing = defaultdict(deque); passive = defaultdict(float)
    if len(L):
        o = L[L.close_reason == 'SETTLEMENT'].sort_values('entry_row')
        for r in o.itertuples():
            k = (r.cp, r.strike)
            if r.role == 'body' and r.side == 'SHORT': body[k].append([1.0, r.entry_price])
            elif r.role == 'wing' and r.side == 'LONG': wing[k].append([1.0, r.entry_price])
            elif r.role == 'body' and r.side == 'LONG': passive[('body_long',) + k] += 1
            elif r.role == 'wing': passive[('wing_short',) + k] += 1
            else: passive[(('v_' if r.role == 'lump' else 's_'),) + k] += (1 if r.side == 'LONG' else -1)
    cash = float((-g.sgn * g.qty_fill * g.px).sum())
    # merge same-contract lots into aggregated [lots, avg_px] groups preserving FIFO order (px per unit lot kept as separate entries)
    return body, wing, passive, cash
