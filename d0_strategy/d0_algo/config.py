"""D0 engine configuration. Fitted parts (set per training split by the research layer) and fixed constants of the research simulator, plus one switch per rule.
Default switches reproduce the research simulator exactly (port of bl_d0_fr.py::sim, Gate 5a). No strategy change is made by this port."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

@dataclass
class D0Config:
    # ---- fitted per split (research layer: bl_d0_fr.py::fit)
    waves: List[Tuple[float, int]] = field(default_factory=list)        # pair timetable: (second of day, lots), in the order of the reference table
    buyback_theta: float = 1.6                                           # stop: minute high >= theta x entry (reference fits theta per split)
    buyback_tp: Optional[float] = None                                   # take-profit: minute low <= tp x entry (None = off)
    ladder_step: float = 0.2                                             # solo ladder step in strike steps (reference m1[0])
    ladder_gate_min: int = 0                                             # fresh-extreme window in minutes (reference m1[1]; 0 = no gate)
    ladder_mult: bool = False                                            # lots = steps crossed (capped) instead of 1 (reference m1[2])
    counter_ratio: float = 0.0                                           # counter-sell: lots per simulated buy-back on the other right (reference r)
    opening_wing_lots: int = 0                                           # lots bought at the open (reference ow), split CE / PE
    # ---- fixed constants of the research simulator
    cycle_stop_rupees: float = 1.20e5                                    # cumulative MTM stop (register D1-15)
    clearance_minute: int = 359                                          # 15:14 (the reference uses one clock for every cycle)
    breakout_start_min: int = 75
    breakout_end_min: int = 360
    wing_premium_frac: float = 0.025
    opening_wing_offset_steps: float = 17.0
    solo_lot_cap: int = 10
    last_minute: int = 374
    # ---- risk controls on risk-ADDING orders (sells). The research simulator had none. The limits are the OBSERVED ENVELOPE of the real D0 log (outputs/phase1/5a/real_d0_envelope.json:
    # 278 net short lots per right, 90 orders per minute), not original controls; the D-1 engine's 400 / 40 are its own safety values and do not fit D0 (the real D0 log is far busier).
    risk_mode: str = "enforce"                                           # 'enforce' (refuse) | 'monitor' (record only, behaviour of the reference)
    max_short_lots_per_right: int = 306                                  # observed real envelope 278 plus a 10% margin: the envelope was measured netted per contract, the engine counts shorts per right
    max_sell_decisions_per_minute: int = 90
    # ---- one switch per rule (all on = the research simulator)
    enable_cycle_stop: bool = True
    enable_clearance: bool = True
    enable_buyback: bool = True
    enable_timetable: bool = True
    enable_breakout: bool = True
    enable_solo: bool = True
    enable_counter: bool = True
    enable_opening_wings: bool = True
    enable_hedge: bool = True
    # ---- Gate 5c candidate corrections (default OFF = Gate 5a behaviour; each is a separately preregistered experiment, reports/PHASE1_GATE5C_PLAN.md)
    opening_long_clock: bool = False                                     # X3: body-stream opening longs at minute `opening_long_minute` (09:16), sized to the lots sold on that right in that minute, instead of the fitted j=0 opening wings
    opening_long_minute: int = 1
    clearance_hazards: Optional[Tuple[float, ...]] = None                # P1-9-C CH2 (default None = single-minute clearance): hazards for offsets -(len-1)..0 relative to clearance_minute; h of the OPEN lots of every contract is bought back at each of those minutes (last hazard is applied as 1.0)

# ---- Gate 5c accepted candidate X1 (era-dependent clearance clock). A helper only: the engine's default `clearance_minute` stays 359 (Gate 5a behaviour).
ERA_BOUNDARY_EXPIRY = "2026-08-03"        # expiries before this date are pre-auction era (the D-1 session precedes the closing-auction regime); same split as the research layer's `era`
PRE_AUCTION_CLEARANCE_MINUTE = 363        # 15:18, first decoded minute of the register's 15:18-15:19 (D0_STOP_CLEAR); 5c experiment X1
def clearance_minute_for(expiry: str) -> int:
    """clearance minute by era from the expiry date alone (known before the session): 363 pre-auction, 359 post-auction"""
    return PRE_AUCTION_CLEARANCE_MINUTE if str(expiry)[:10] < ERA_BOUNDARY_EXPIRY else 359
