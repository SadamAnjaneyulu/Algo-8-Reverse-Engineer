"""Paper trading and replay: a feed that replays one-minute bars second by second, and a broker that fills at the last price.

The replay turns each one-minute bar into a path through the minute (open, then the low or high, then the other, then close) so that the engine sees
prices move second by second inside the minute and respects the bar's high and low. The order of the high and the low inside a minute is NOT in the
bars; the rule here is a convention (an up bar goes to its low first), used only for testing.
"""
from __future__ import annotations
from typing import Dict, List, Tuple
import numpy as np
from .models import Fill, OrderRequest, SESSION_OPEN_S

_XS = [0, 20, 40, 59]


class ReplayFeed:
    def __init__(self, o: np.ndarray, h: np.ndarray, l: np.ndarray, c: np.ndarray, strikes: np.ndarray, bars: Dict[Tuple[str, str], np.ndarray]):
        self.o, self.h, self.l, self.c = map(np.asarray, (o, h, l, c)); self.n = len(self.c)
        self._strikes = np.asarray(strikes, dtype=float); self.bars = bars; self._idx = {int(k): i for i, k in enumerate(self._strikes)}; self.t = float(SESSION_OPEN_S)

    def set_time(self, t: float):
        self.t = float(t)

    def now(self) -> float:
        return self.t

    def strikes(self) -> np.ndarray:
        return self._strikes

    def _pos(self):
        j, s = divmod(int(self.t - SESSION_OPEN_S), 60)
        return j, s

    def _spot_up(self, j: int) -> bool:
        return self.c[j] >= self.o[j]

    def spot(self) -> float:
        j, s = self._pos()
        if j < 0: return float("nan")
        if j >= self.n: return float(self.c[-1])
        nodes = [self.o[j], self.l[j], self.h[j], self.c[j]] if self._spot_up(j) else [self.o[j], self.h[j], self.l[j], self.c[j]]
        return float(np.interp(s, _XS, nodes))

    def option_ltp(self, right: str, strike: float) -> float:
        i = self._idx.get(int(strike))
        if i is None: return float("nan")
        j, s = self._pos()
        if j < 0: return float("nan")
        j = min(j, self.n - 1) if j < self.n else self.n - 1
        o, h, l, c = (self.bars[(right, f)][i, j] for f in ("open", "high", "low", "close"))
        if self._pos()[0] >= self.n: return float(c)
        low_first = self._spot_up(j) if right == "CE" else not self._spot_up(j)
        nodes = [o, l, h, c] if low_first else [o, h, l, c]
        v = float(np.interp(s, _XS, nodes))
        return v


class PaperBroker:
    """Fills every marketable order immediately at the feed's last price (optionally with adverse slippage). Keeps net positions."""

    def __init__(self, feed, slippage_pct: float = 0.0):
        self.feed = feed; self.slip = slippage_pct / 100.0; self.pos: Dict[Tuple[str, float], int] = {}; self.all_fills: List[Fill] = []

    def place(self, req: OrderRequest) -> List[Fill]:
        ltp = self.feed.option_ltp(req.right, req.strike)
        if ltp != ltp or ltp <= 0: return []
        if req.side == "BUY":
            if req.limit_price < ltp: return []
            px = ltp * (1 + self.slip)
        else:
            if req.limit_price > ltp: return []
            px = ltp * (1 - self.slip)
        f = Fill(req.tag, self.feed.now(), req.right, req.strike, req.lots, req.side, round(px, 2), req.role)
        key = (req.right, req.strike); self.pos[key] = self.pos.get(key, 0) + (req.lots if req.side == "BUY" else -req.lots); self.all_fills.append(f)
        return [f]

    def poll_fills(self) -> List[Fill]:
        return []

    def positions(self) -> Dict[Tuple[str, float], int]:
        return {k: v for k, v in self.pos.items() if v != 0}


def run_replay(engine, feed: ReplayFeed, t_start: float = SESSION_OPEN_S, t_end: float = SESSION_OPEN_S + 390 * 60, step_s: int = 1):
    """Drive the engine second by second through the replayed session."""
    t = int(t_start)
    while t <= t_end:
        feed.set_time(t); engine.step(); t += step_s
    return engine
