from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional
from .models import SESSION_OPEN_S

# Fixed clock of the scheduled straddles: seconds after 09:16:00. Two versions were observed in the data
# (A until the D-1 of 2026-09-09, B from the D-1 of 2026-09-16). 33 waves each.
SCHEDULE_A = [1, 2, 7, 900, 900, 1800, 1831, 1866, 2710, 3599, 3600, 3600, 3658, 4510, 5431, 5491, 6300, 6310, 7199, 7258, 8110, 9000, 9031,
              9091, 9910, 11700, 11710, 14400, 15240, 16140, 17040, 17940, 18840]
SCHEDULE_B = [1, 2, 8, 899, 900, 1800, 1831, 1866, 2710, 3599, 3600, 3658, 4501, 4510, 5431, 5491, 6310, 7199, 7258, 8102, 8110, 9031, 9091,
              9910, 11702, 11710, 15302, 16140, 17040, 17940, 18840, 18902, 19740]
LUMP_MINUTE_BY_REGIME = {"until_2026-08-05": 356, "2026-08-12_to_08-19": 368, "from_2026-08-24": 375}


@dataclass
class D1Config:
    # ---- instrument
    underlying: str = "NIFTY"
    strike_step: float = 50.0                      # listed strike spacing near the money
    lot_units: int = 65                            # units per lot
    freeze_lots: int = 27                          # largest single order in lots (exchange freeze quantity): 27 NIFTY, 50 SENSEX
    price_tick: float = 0.05
    # ---- scheduled straddles
    timetable: List[int] = field(default_factory=lambda: list(SCHEDULE_A))
    max_wave_lateness_s: float = 30.0              # a wave older than this when the engine starts is skipped, not fired late
    # ---- breakout straddles
    breakout_start_min: int = 75                   # 10:30
    breakout_end_min: int = 360                    # 15:15
    pairs_per_depth_step: float = 0.4
    max_pairs: int = 3
    extra_a: float = 0.81
    extra_b: float = 1.28
    max_extra: int = 7
    breakout_size_after_s: float = 0.0             # wait this long after the first break before sizing the entry by break depth (0 = size at once)
    # ---- solo ladder
    ladder_step: float = 0.2                       # in strike steps of spot movement
    ladder_gate_min: int = 60
    ladder_strike_window: int = 4
    # ---- per-lot stop
    stop_ratio: float = 1.6
    stop_price: str = "high"                       # 'high' = running high of the current minute; 'prev_close' = last completed minute close
    # ---- wings
    wing_premium_frac: float = 0.025
    wing_delay_s: float = 4.0                      # wing orders follow a body order by about 4 seconds
    opening_wing_lots_per_right: int = 3
    opening_wing_offset_steps: float = 39.8
    # ---- overnight lump
    lump_minute: int = 356
    lump_ratio: float = 0.827
    lump_sigma_mult: float = 2.2
    # ---- execution
    limit_buffer_pct: float = 15.0                 # marketable limit: LTP -/+ this percent (the real system sends limit = LTP x (1 +/- 0.15); D0_QTY.md part A2)
    # ---- risk (see risk.py)
    max_short_lots_per_right: int = 400
    max_orders_per_minute: int = 40
    max_loss_rupees: Optional[float] = None        # book mark-to-market loss that halts new selling (None = off)
    kill_switch_file: Optional[str] = None         # if this file exists, no new risk is added
    state_file: Optional[str] = None               # JSON snapshot of the engine state (restart recovery)
    paper: bool = True                             # keep True until a real broker adapter has been tested

    @property
    def lump_time_s(self) -> float:
        return SESSION_OPEN_S + 60 * self.lump_minute


def config_for(underlying: str, d1_date: str, **overrides) -> D1Config:
    """Configuration regime observed for a given D-1 date (ISO string): timetable version, lump clock, lot data."""
    nifty = underlying.upper() == "NIFTY"
    cfg = D1Config(underlying=underlying.upper(), strike_step=50.0 if nifty else 100.0, lot_units=65 if nifty else 20, freeze_lots=27 if nifty else 50,
                   lump_ratio=0.827 if nifty else 0.503)
    version_b = d1_date >= "2026-09-16"
    cfg.timetable = list(SCHEDULE_B if version_b else SCHEDULE_A)
    cfg.opening_wing_offset_steps = 20.0 if (not nifty and version_b) else 39.8
    cfg.lump_minute = (LUMP_MINUTE_BY_REGIME["until_2026-08-05"] if d1_date <= "2026-08-05"
                       else LUMP_MINUTE_BY_REGIME["2026-08-12_to_08-19"] if d1_date <= "2026-08-19" else LUMP_MINUTE_BY_REGIME["from_2026-08-24"])
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg
