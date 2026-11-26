"""d1_algo: an event-driven implementation of the day-before-expiry (D-1) strategy that can run on a live feed and broker or on a paper/replay setup."""
from .config import D1Config, config_for
from .engine import D1Engine
from .models import Fill, Lot, OrderRequest
from .risk import RiskGuard
from .sim import PaperBroker, ReplayFeed, run_replay
__all__ = ["D1Config", "config_for", "D1Engine", "Fill", "Lot", "OrderRequest", "RiskGuard", "PaperBroker", "ReplayFeed", "run_replay"]
