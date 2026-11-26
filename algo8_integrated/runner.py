"""Integrated D-1 + D0 cycle (mode F). Inputs: the D-1 replay feed and config, the D0 market and config. No real-order argument exists."""
from __future__ import annotations
import sys, os
from dataclasses import dataclass, field
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..', 'd1_strategy')); sys.path.insert(0, os.path.join(HERE, '..', 'd0_strategy'))
from d1_algo import D1Engine
from d1_algo.sim import PaperBroker, run_replay
from d0_algo import D0Engine
from .handoff import d1_state_to_d0_opening


@dataclass
class IntegratedResult:
    d1_engine: object
    d0_engine: object
    opening: object
    d1_net_position: dict = field(default_factory=dict)


def run_integrated_cycle(d1_cfg, d1_feed, d0_cfg, d0_market, unit: float) -> IntegratedResult:
    """1) the D-1 session runs to its end on the replay feed; 2) its final book and fills become the D0 opening state; 3) the D0 session runs from that state."""
    broker = PaperBroker(d1_feed); e1 = D1Engine(d1_cfg, d1_feed, broker); run_replay(e1, d1_feed)
    net = {k: v for k, v in broker.positions().items()}
    opening = d1_state_to_d0_opening(e1.book, broker.all_fills, unit, chain=d0_market.K)
    e0 = D0Engine(d0_cfg, d0_market, opening); e0.run()
    return IntegratedResult(d1_engine=e1, d0_engine=e0, opening=opening, d1_net_position=net)
