from __future__ import annotations
from typing import Dict, List, Optional, Tuple
import numpy as np


class SpotBars:
    """Builds one-minute spot bars from ticks. Completed bars are in lists (index = minute); the running bar is cur_*."""

    def __init__(self):
        self.open: List[float] = []; self.high: List[float] = []; self.low: List[float] = []; self.close: List[float] = []
        self.minute = -1; self.cur_open = self.cur_high = self.cur_low = self.cur_close = float("nan")

    def tick(self, minute: int, price: float):
        if minute != self.minute:
            if self.minute >= 0:                                           # finish the previous minute (fill gaps by repeating the last close)
                self.open.append(self.cur_open); self.high.append(self.cur_high); self.low.append(self.cur_low); self.close.append(self.cur_close)
                for _ in range(minute - self.minute - 1):
                    self.open.append(self.cur_close); self.high.append(self.cur_close); self.low.append(self.cur_close); self.close.append(self.cur_close)
            self.minute = minute; self.cur_open = self.cur_high = self.cur_low = self.cur_close = price
        else:
            self.cur_high = max(self.cur_high, price); self.cur_low = min(self.cur_low, price); self.cur_close = price

    def prev_close(self, minute: int) -> Optional[float]:
        """Close of the last completed minute before `minute`."""
        return self.close[minute - 1] if 0 < minute <= len(self.close) else None

    def completed(self) -> int:
        return len(self.close)

    def window(self, a: int, e: int) -> Tuple[float, float]:
        """Highest high and lowest low of completed minutes a..e-1."""
        a = max(a, 0)
        return float(np.max(self.high[a:e])), float(np.min(self.low[a:e]))


class OptionBars:
    """Minute bars for the option contracts being watched (held shorts and the strikes near the money), built from LTP samples."""

    def __init__(self):
        self.bars: Dict[Tuple[str, float], Dict[int, List[float]]] = {}

    def sample(self, right: str, strike: float, minute: int, price: float):
        if price != price:
            return
        d = self.bars.setdefault((right, strike), {})
        b = d.get(minute)
        if b is None:
            d[minute] = [price, price, price, price]
        else:
            b[1] = max(b[1], price); b[2] = min(b[2], price); b[3] = price

    def run_high(self, right: str, strike: float, minute: int) -> float:
        b = self.bars.get((right, strike), {}).get(minute)
        return b[1] if b else float("nan")

    def prev_close(self, right: str, strike: float, minute: int) -> float:
        b = self.bars.get((right, strike), {}).get(minute - 1)
        return b[3] if b else float("nan")
