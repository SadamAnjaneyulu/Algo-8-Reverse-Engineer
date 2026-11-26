from __future__ import annotations
from typing import Dict, List, Tuple
from .models import Lot

Key = Tuple[str, float]


class Book:
    """Short lots (with entry prices), wing longs, lump longs. Pending orders are counted separately so the wing controller never double-orders."""

    def __init__(self):
        self.shorts: Dict[Key, List[Lot]] = {}
        self.wings: Dict[Key, int] = {}
        self.lump: Dict[Key, int] = {}
        self.pending_short: Dict[str, int] = {"CE": 0, "PE": 0}       # sells sent, not yet filled (net of pending buy-backs)
        self.pending_wing: Dict[str, int] = {"CE": 0, "PE": 0}        # wing buys sent minus wing sells sent, not yet filled

    def short_count(self, right: str, include_pending: bool = True) -> int:
        n = sum(len(v) for (r, _), v in self.shorts.items() if r == right)
        return n + (self.pending_short[right] if include_pending else 0)

    def wing_count(self, right: str, include_pending: bool = True) -> int:
        n = sum(v for (r, _), v in self.wings.items() if r == right and v > 0)
        return n + (self.pending_wing[right] if include_pending else 0)

    def add_short(self, right: str, strike: float, lot: Lot, n: int = 1):
        for _ in range(n):
            self.shorts.setdefault((right, strike), []).append(lot)

    def remove_shorts(self, right: str, strike: float, n: int) -> int:
        """Remove n lots, cheapest entry first (the highest-ratio lots). Returns how many were removed."""
        lots = sorted(self.shorts.get((right, strike), []), key=lambda l: l.entry_price)
        k = min(n, len(lots)); self.shorts[(right, strike)] = lots[k:]
        return k

    def add_wing(self, right: str, strike: float, n: int):
        self.wings[(right, strike)] = self.wings.get((right, strike), 0) + n

    def sell_wing(self, right: str, strike: float, n: int):
        self.wings[(right, strike)] = max(self.wings.get((right, strike), 0) - n, 0)

    def snapshot(self) -> dict:
        return {"shorts": [[r, k, [[l.ts, l.minute, l.entry_price, l.role] for l in v]] for (r, k), v in self.shorts.items() if v],
                "wings": [[r, k, v] for (r, k), v in self.wings.items() if v], "lump": [[r, k, v] for (r, k), v in self.lump.items() if v]}

    def restore(self, snap: dict):
        self.shorts = {(r, k): [Lot(*x) for x in v] for r, k, v in snap.get("shorts", [])}
        self.wings = {(r, k): v for r, k, v in snap.get("wings", [])}
        self.lump = {(r, k): v for r, k, v in snap.get("lump", [])}
