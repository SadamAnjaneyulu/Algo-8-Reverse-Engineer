"""The two things a live deployment has to provide. Everything else is in the engine.

MarketData: where prices come from (a broker websocket, a vendor API, or the replay feed).
Broker:     where orders go (a real broker adapter, or the paper broker).
"""
from __future__ import annotations
from typing import Dict, List, Protocol, Tuple
import numpy as np
from .models import Fill, OrderRequest


class MarketData(Protocol):
    def now(self) -> float:
        """Current time, seconds since midnight (exchange time)."""

    def spot(self) -> float:
        """Latest index price."""

    def option_ltp(self, right: str, strike: float) -> float:
        """Latest traded price of an option of the expiry being traded; NaN if unavailable."""

    def strikes(self) -> np.ndarray:
        """Listed strikes of that expiry, ascending."""


class Broker(Protocol):
    def place(self, req: OrderRequest) -> List[Fill]:
        """Send the order. Return the fills that are already known (a paper broker fills at once; a live broker usually returns [])."""

    def poll_fills(self) -> List[Fill]:
        """Fills that arrived since the last call (live brokers deliver confirmations here)."""

    def positions(self) -> Dict[Tuple[str, float], int]:
        """Net lots per (right, strike): positive long, negative short. Used to reconcile after a restart."""
