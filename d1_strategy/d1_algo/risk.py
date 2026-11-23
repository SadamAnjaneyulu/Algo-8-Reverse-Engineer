from __future__ import annotations
import os
from typing import Dict, Tuple
from .config import D1Config
from .models import OrderRequest

REDUCING_ROLES = {"stop_buyback", "protective_wing_buy", "opening_wing_buy", "overnight_lump"}      # orders that reduce or cap risk are never blocked


class RiskGuard:
    """Pre-trade checks. add_risk orders (new shorts) are blocked by the kill switch, the loss limit and the position limits."""

    def __init__(self, cfg: D1Config):
        self.cfg = cfg; self.halted = False; self.reason = ""; self._minute_counts: Dict[int, int] = {}

    def halt(self, reason: str):
        self.halted = True; self.reason = reason

    def kill_file_present(self) -> bool:
        return bool(self.cfg.kill_switch_file) and os.path.exists(self.cfg.kill_switch_file)

    def check(self, req: OrderRequest, short_count: int, minute: int) -> Tuple[bool, str]:
        c = self.cfg
        if req.lots <= 0:
            return False, "non-positive quantity"
        if not (req.limit_price == req.limit_price and req.limit_price > 0):
            return False, "no valid limit price"
        n = self._minute_counts.get(minute, 0)
        if n >= c.max_orders_per_minute:
            return False, "too many orders this minute"
        adds_risk = req.role not in REDUCING_ROLES and req.role not in ("protective_wing_sell",) and req.side == "SELL"
        if adds_risk:
            if self.halted or self.kill_file_present():
                return False, f"halted ({self.reason or 'kill switch file'})"
            if short_count + req.lots > c.max_short_lots_per_right:
                return False, "short lot limit"
        self._minute_counts[minute] = n + 1
        return True, ""
