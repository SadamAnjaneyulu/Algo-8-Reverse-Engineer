"""Basket book (who owns which claim on the ledger's inventory), cut records, and the read-only views plugins receive.
The book holds CLAIMS only (leg quantities, cut lineage). Executed inventory lives in the M2 ledger; the engine checks after every fill that the two agree."""
import bisect
from dataclasses import dataclass
from .contract import LookAheadError

ACTIVE, PARTIALLY_CUT, FULLY_CUT = 'ACTIVE', 'PARTIALLY_CUT', 'FULLY_CUT'


class Leg:
    __slots__ = ('leg_id', 'basket_id', 'instrument_id', 'side', 'initial', 'current', 'notional', 'cuts_done', 'seed_fills')
    def __init__(self, leg_id, basket_id, instrument_id, side):
        self.leg_id = leg_id; self.basket_id = basket_id; self.instrument_id = instrument_id; self.side = side
        self.initial = 0; self.current = 0; self.notional = 0; self.cuts_done = 0; self.seed_fills = []
    @property
    def entry_price(self): return self.notional // self.initial if self.initial else 0          # integer volume-weighted seed price (paise)


class Cut:
    __slots__ = ('cut_id', 'basket_id', 'leg_id', 'qty', 'ts', 'price', 'fill_id', 'reentered', 'reentries')
    def __init__(self, cut_id, basket_id, leg_id, qty, ts, price, fill_id):
        self.cut_id = cut_id; self.basket_id = basket_id; self.leg_id = leg_id; self.qty = qty; self.ts = ts; self.price = price; self.fill_id = fill_id; self.reentered = 0; self.reentries = 0


class Book:
    def __init__(self): self.baskets = {}; self.cuts = {}; self.seen_ids = set()

    def clone(self):
        b = Book(); b.seen_ids = set(self.seen_ids)
        for bid, legs in self.baskets.items():
            b.baskets[bid] = {}
            for lid, l in legs.items():
                n = Leg(l.leg_id, l.basket_id, l.instrument_id, l.side); n.initial = l.initial; n.current = l.current; n.notional = l.notional; n.cuts_done = l.cuts_done; n.seed_fills = list(l.seed_fills); b.baskets[bid][lid] = n
        for cid, c in self.cuts.items():
            n = Cut(c.cut_id, c.basket_id, c.leg_id, c.qty, c.ts, c.price, c.fill_id); n.reentered = c.reentered; n.reentries = c.reentries; b.cuts[cid] = n
        return b

    def leg(self, bid, lid):
        legs = self.baskets.get(bid)
        return None if legs is None else legs.get(lid)

    def status(self, bid):
        legs = self.baskets[bid].values()
        if all(l.current == 0 for l in legs): return FULLY_CUT
        if any(l.current != l.initial for l in legs): return PARTIALLY_CUT
        return ACTIVE

    def seed(self, bid, lid, iid, side, qty, price, fill_id):
        leg = self.baskets.setdefault(bid, {}).get(lid)
        if leg is None: leg = self.baskets[bid][lid] = Leg(lid, bid, iid, side)
        leg.initial += qty; leg.current += qty; leg.notional += qty * price; leg.seed_fills.append(fill_id)

    def cut(self, action, ts, price, fill_id):
        leg = self.baskets[action.basket_id][action.leg_id]; leg.current -= action.qty; leg.cuts_done += 1
        self.cuts[action.action_id] = Cut(action.action_id, action.basket_id, action.leg_id, action.qty, ts, price, fill_id)

    def reenter(self, action):
        leg = self.baskets[action.basket_id][action.leg_id]; leg.current += action.qty
        c = self.cuts[action.parent_cut_id]; c.reentered += action.qty; c.reentries += 1


# ---------------------------------------------------------------- read-only views for plugins
@dataclass(frozen=True)
class LegView:
    basket_id: str; leg_id: str; instrument_id: str; side: int; initial: int; current: int; entry_price: int; cuts_done: int


@dataclass(frozen=True)
class BasketView:
    basket_id: str; status: str; legs: tuple          # legs sorted by leg_id


@dataclass(frozen=True)
class CutView:
    cut_id: str; basket_id: str; leg_id: str; instrument_id: str; qty: int; ts: int; price: int; reentered: int; reentries: int


class MarkStore:
    """synthetic price series per instrument; `at(iid, ts)` returns the latest mark with mark_ts <= ts and refuses to look past ts"""
    def __init__(self, marks):
        self._t = {}; self._p = {}
        for ts, iid, px in sorted(marks):
            self._t.setdefault(iid, []).append(ts); self._p.setdefault(iid, []).append(px)

    def at(self, iid, ts):
        t = self._t.get(iid)
        if not t: return None
        k = bisect.bisect_right(t, ts) - 1
        return None if k < 0 else (self._p[iid][k], t[k])


class EvalContext:
    """everything a plugin may see at time `ts`: marks <= ts, a frozen snapshot of baskets and cuts, scripted actions stamped exactly `ts`"""
    def __init__(self, ts, marks, baskets, cuts, lots, scripted):
        self.ts = ts; self._marks = marks; self.baskets = baskets; self.cuts = cuts; self._lots = lots; self.scripted = scripted

    def mark(self, iid, at_ts=None):
        """-> (price_paise, mark_ts) or None. Asking for a time after ctx.ts raises LookAheadError."""
        t = self.ts if at_ts is None else at_ts
        if t > self.ts: raise LookAheadError(f'mark requested at {t} but the evaluation time is {self.ts}')
        return self._marks.at(iid, t)

    def lot_size(self, iid): return self._lots[iid]
