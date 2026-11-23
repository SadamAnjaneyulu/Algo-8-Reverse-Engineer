"""
Day-before-expiry ("D-1") strategy: a rule-based reconstruction of what the observed system does on the session before an index-option expiry.

WHAT THIS IS
    A short-premium strategy on index options (NIFTY / SENSEX style weekly expiry). On the day before expiry it builds a short book of
    at-the-money (ATM) straddles and single-sided shorts all day, protects every short with a far out-of-the-money (OTM) long on the same right,
    stops out individual losing lots, and adds an extra layer of out-of-the-money longs shortly before the close to cover an overnight gap.
    The book is carried to expiry day. This module only generates the D-1 orders; expiry day is a separate process.

STATUS
    This is a reconstruction fitted to the observed order log of 32 cycles. On a fresh cycle it reproduces about 63% of the lot decisions in the
    right minute and on the right side (F1, +-1 minute), and ranks the minutes where the system acts with AUC about 0.92. See the accompanying
    document for the evidence.

INPUTS
    * one-minute spot bars (open/high/low/close) from 09:15 to 15:30, minute index 0 = 09:15;
    * one-minute option bars (high/low/close/open) for every listed strike of that expiry, both rights.

OUTPUT
    A list of `Order` records (minute, right, strike, lots, role) and the end-of-day book.

CONVENTIONS
    minute index j = minutes since 09:15 (09:16 -> j=1). "previous close" = close of minute j-1, the last completed bar.
    strike_step = distance between listed strikes near the money (50 for NIFTY, 100 for SENSEX). A "lot" is the exchange contract unit.
    Right = "CE" (call) or "PE" (put).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np

SESSION_START_SEC = 9 * 3600 + 15 * 60                    # 09:15:00 in seconds since midnight
MINUTES = 375                                              # 09:15 .. 15:29 inclusive

# --------------------------------------------------------------------------------------------------------------------------------------
# Fixed timetable of the scheduled straddles: seconds after 09:16:00 at which one ATM straddle (1 lot call + 1 lot put) is sold.
# Two versions were observed: SCHEDULE_A until the D-1 of 2026-09-09, SCHEDULE_B from the D-1 of 2026-09-16 (33 waves each).
# These are read off the order log; they are a property of the system, not something derived from the market.
# --------------------------------------------------------------------------------------------------------------------------------------
SCHEDULE_A = [1, 2, 7, 900, 900, 1800, 1831, 1866, 2710, 3599, 3600, 3600, 3658, 4510, 5431, 5491, 6300, 6310, 7199, 7258, 8110, 9000, 9031,
              9091, 9910, 11700, 11710, 14400, 15240, 16140, 17040, 17940, 18840]
SCHEDULE_B = [1, 2, 8, 899, 900, 1800, 1831, 1866, 2710, 3599, 3600, 3658, 4501, 4510, 5431, 5491, 6310, 7199, 7258, 8102, 8110, 9031, 9091,
              9910, 11702, 11710, 15302, 16140, 17040, 17940, 18840, 18902, 19740]


@dataclass
class Config:
    """All tunable numbers in one place. Defaults are the values fitted on the 32 observed cycles."""
    strike_step: float = 50.0                              # listed strike spacing near the money
    timetable: List[int] = field(default_factory=lambda: list(SCHEDULE_A))   # scheduled straddle clock (seconds after 09:16:00)
    # --- breakout straddles ("reactive pairs")
    breakout_start_min: int = 75                           # 10:30, first minute two completed 30-minute candles exist
    breakout_end_min: int = 360                            # 15:15, last minute a breakout can fire
    pairs_per_depth_step: float = 0.4                      # extra straddle per this many strike steps of break depth (capped at 3 straddles)
    max_pairs: int = 3
    extra_a: float = 0.81                                  # favourable-side single lots = round(a + b * depth), clipped to 0..7
    extra_b: float = 1.28
    max_extra: int = 7
    # --- solo ladder ("drip")
    ladder_step: float = 0.2                               # in strike steps of spot movement beyond the last reference
    ladder_gate_min: int = 60                              # needs a fresh favourable extreme over this many minutes
    ladder_strike_window: int = 4                          # repeat sales pick the strike within +-4 steps of ATM whose premium is nearest the last sale
    # --- stop on each lot
    stop_ratio: float = 1.6                                # buy a lot back when its option price / its own entry price reaches this
    stop_price: str = "high"                               # "high": current minute high (intrabar touch); "prev_close": last completed close
    # --- protective wings
    wing_premium_frac: float = 0.025                       # wing = OTM strike whose premium is nearest 2.5% of the ATM premium of that right
    opening_wing_lots_per_right: int = 3                   # bought at 09:16 before the first scheduled straddles
    opening_wing_offset_steps: float = 39.8                # distance out of the money, in strike steps
    # --- overnight lump
    lump_minute: int = 356                                 # minute of day the extra overnight protection is placed (clock regime of that date)
    lump_ratio: float = 0.827                              # lump lots = ratio * short lots on the heavier side (0.83 NIFTY, 0.50 SENSEX)
    lump_sigma_mult: float = 2.2                           # strike = spot * (1 +- 2.2 * sigma_1day), sigma from the ATM straddle price


# observed clock regimes of the overnight lump (minute index); a property of the system's configuration by date
LUMP_MINUTE_BY_REGIME = {"until_2026-08-05": 356, "2026-08-12_to_08-19": 368, "from_2026-08-24": 375}


@dataclass
class OptionChain:
    """strikes: ascending 1-D array. bars[(right, field)] -> array [n_strikes, MINUTES] for field in open/high/low/close."""
    strikes: np.ndarray
    bars: Dict[Tuple[str, str], np.ndarray]

    def __post_init__(self):
        self._idx = {int(k): i for i, k in enumerate(self.strikes)}

    def price(self, right: str, strike: float, minute: int, field: str = "close") -> float:
        i = self._idx.get(int(strike))
        if i is None:
            return float("nan")
        return float(self.bars[(right, field)][i, min(max(minute, 0), MINUTES - 1)])


@dataclass
class Order:
    minute: int
    right: str
    strike: float
    lots: int
    side: str                                              # "sell" or "buy"
    role: str                                              # see ROLES
    note: str = ""


ROLES = {
    "scheduled_straddle": "timetable straddle leg (ATM, 1 lot call + 1 lot put per wave)",
    "breakout_straddle": "breakout straddle leg (one strike beyond ATM in the break direction)",
    "breakout_extra": "single-sided extra lots on the favourable side of a breakout",
    "ladder_solo": "single 1-lot sale from the solo ladder",
    "stop_buyback": "individual lot bought back at its stop",
    "protective_wing_buy": "far OTM long that matches the short lot gap on that right",
    "protective_wing_sell": "wing released when shorts were bought back",
    "opening_wing_buy": "far OTM long bought before the first scheduled straddles",
    "overnight_lump": "extra OTM long placed before the close on the heavier short side",
}


def atm_strike(strikes: np.ndarray, spot: float) -> float:
    return float(strikes[np.argmin(np.abs(strikes - spot))])


def minute_of(seconds_after_0916: float) -> int:
    return int((60 + seconds_after_0916) // 60)


# ======================================================================================================================================
# Signal generators (pure functions of the spot bars)
# ======================================================================================================================================
def breakout_fires(high: np.ndarray, low: np.ndarray, cfg: Config) -> List[Tuple[int, int, float]]:
    """Two-candle breakout. For each minute from 10:30 to 15:15: channel = highest high / lowest low of the previous TWO completed
    clock-aligned 30-minute candles (hh:00-hh:30, hh:30-hh:00; the current candle is excluded). If the minute's high is above the channel
    top (or its low below the channel bottom) fire once per side per candle. Returns (minute, side, depth) with side +1 up / -1 down and
    depth = distance beyond the channel in strike steps."""
    out, done = [], set()
    for j in range(cfg.breakout_start_min, cfg.breakout_end_min + 1):
        clock = 33300 + 60 * j
        b0 = (clock // 1800) * 1800                                      # start of the current 30-minute candle (seconds since midnight)
        a = int(np.ceil((b0 - 3600 - 33300) / 60)); e = int(np.ceil((b0 - 33300) / 60))
        if e - max(a, 0) < 2:
            continue
        top, bottom = high[max(a, 0):e].max(), low[max(a, 0):e].min()
        for side, broke, depth in ((1, high[j] > top, (high[j] - top) / cfg.strike_step), (-1, low[j] < bottom, (bottom - low[j]) / cfg.strike_step)):
            if broke and (b0, side) not in done:
                done.add((b0, side)); out.append((j, side, float(depth)))
    return out


def ladder_fires(close: np.ndarray, high: np.ndarray, low: np.ndarray, event_minutes: Dict[str, List[int]], cfg: Config) -> Dict[int, List[str]]:
    """Solo ladder. Per right, the reference level is the spot close before the latest scheduled/breakout sale on that right. A 1-lot solo sale
    is fired when (a) the spot has moved at least `ladder_step` strike steps in the direction that favours the short (down for calls, up for
    puts) beyond the reference and (b) that minute makes a fresh `ladder_gate_min`-minute extreme (low for calls, high for puts). After a fire the
    reference moves by the number of ladder steps crossed."""
    st = cfg.strike_step * cfg.ladder_step; out: Dict[int, List[str]] = {}
    for right in ("CE", "PE"):
        evs = sorted(set(event_minutes[right])); ptr = 0; ref = None
        for j in range(1, MINUTES):
            while ptr < len(evs) and evs[ptr] < j:
                ref = close[max(evs[ptr] - 1, 0)]; ptr += 1
            if ref is None:
                continue
            lo = max(j - cfg.ladder_gate_min, 0)
            fresh = (low[j] < low[lo:j].min()) if right == "CE" else (high[j] > high[lo:j].max())
            if not fresh:
                continue
            if right == "CE" and low[j] < ref - st:
                out.setdefault(j, []).append(right); ref -= st * max(1, int((ref - low[j]) // st))
            elif right == "PE" and high[j] > ref + st:
                out.setdefault(j, []).append(right); ref += st * max(1, int((high[j] - ref) // st))
    return out


# ======================================================================================================================================
# The strategy
# ======================================================================================================================================
@dataclass
class Lot:
    minute: int
    entry_price: float
    kind: str


@dataclass
class Result:
    orders: List[Order]
    short_lots: Dict[Tuple[str, float], int]               # end-of-day short book {(right, strike): lots}
    long_lots: Dict[Tuple[str, float], int]                # end-of-day long book (wings + lump)

    def orders_frame(self):
        import pandas as pd
        return pd.DataFrame([o.__dict__ for o in self.orders])


class D1Strategy:
    def __init__(self, cfg: Config):
        self.cfg = cfg

    # ---------------------------------------------------------------------------------------------------------------------------
    def run(self, spot_open: np.ndarray, spot_high: np.ndarray, spot_low: np.ndarray, spot_close: np.ndarray, chain: OptionChain,
            max_minute: int = 390) -> Result:
        """Generate every D-1 order from the minute bars. Spot arrays have length 375. `max_minute` lets the overnight lump fire after 15:29
        (the observed lump time can be as late as 15:35)."""
        cfg = self.cfg; K = chain.strikes; step = cfg.strike_step; c, h, l = spot_close, spot_high, spot_low
        cj = lambda j: min(max(j, 0), MINUTES - 1)
        px = chain.price
        orders: List[Order] = []
        shorts: Dict[Tuple[str, float], List[Lot]] = {}
        wings: Dict[Tuple[str, float], int] = {}
        lump: Dict[Tuple[str, float], int] = {}
        last_sale_price: Dict[str, Optional[float]] = {"CE": None, "PE": None}

        def emit(j, right, strike, lots, side, role, note=""):
            orders.append(Order(j, right, float(strike), int(lots), side, role, note))

        # ---- plan the signal-driven sales of the day (they depend only on the spot bars)
        plan: Dict[int, List[list]] = {}                    # minute -> [right, strike, lots, role]
        events: Dict[str, List[int]] = {"CE": [], "PE": []}
        for sec in cfg.timetable:                           # 1) scheduled straddles
            j = minute_of(sec); k = atm_strike(K, c[cj(j - 1)])
            for right in ("CE", "PE"):
                plan.setdefault(j, []).append([right, k, 1, "scheduled_straddle"]); events[right].append(j)
        for j, side, depth in breakout_fires(h, l, cfg):    # 2) breakout straddles (+ favourable-side extras)
            k = atm_strike(K, c[cj(j - 1)]) + side * step
            n = min(1 + int(depth // cfg.pairs_per_depth_step), cfg.max_pairs)
            for right in ("CE", "PE"):
                plan.setdefault(j, []).append([right, k, n, "breakout_straddle"]); events[right].append(j)
            extra = int(np.clip(round(cfg.extra_a + cfg.extra_b * depth), 0, cfg.max_extra))
            if extra:
                plan.setdefault(j, []).append(["PE" if side > 0 else "CE", k, extra, "breakout_extra"])
        ladder = ladder_fires(c, h, l, events, cfg)         # 3) solo ladder

        # ---- minute loop
        for j in range(1, max_minute):
            if j == 1:                                      # opening wings: far OTM longs before the first scheduled straddles
                for right in ("CE", "PE"):
                    target = atm_strike(K, c[0]) + (1 if right == "CE" else -1) * cfg.opening_wing_offset_steps * step
                    k = float(K[np.argmin(np.abs(K - target))])
                    for _ in range(cfg.opening_wing_lots_per_right):
                        wings[(right, k)] = wings.get((right, k), 0) + 1; emit(j, right, k, 1, "buy", "opening_wing_buy")
            touched = False
            # (a) stops: every lot whose option price reached stop_ratio x its own entry price is bought back, cheapest entry first
            for (right, k), lots in list(shorts.items()):
                if not lots:
                    continue
                now = px(right, k, j, "high") if cfg.stop_price == "high" else px(right, k, j - 1)
                keep = []
                for lot in sorted(lots, key=lambda t: t.entry_price):
                    if j > lot.minute and now == now and lot.entry_price > 0 and now / lot.entry_price >= cfg.stop_ratio:
                        emit(j, right, k, 1, "buy", "stop_buyback"); touched = True
                    else:
                        keep.append(lot)
                shorts[(right, k)] = keep
            # (b) sales planned for this minute: timetable, breakouts, extras, then the ladder
            sells = [list(x) for x in plan.get(j, [])] + [[right, None, 1, "ladder_solo"] for right in ladder.get(j, [])]
            for right, k, n, role in sells:
                if k is None:                               # solo strike: ATM for the first sale on that right, then the strike near ATM whose
                    a0 = atm_strike(K, c[cj(j - 1)])        # premium is closest to the premium of the previous sale on that right
                    if last_sale_price[right] is None:
                        k = a0
                    else:
                        cand = K[np.abs(K - a0) <= cfg.ladder_strike_window * step]
                        pr = np.array([px(right, kk, j - 1) for kk in cand])
                        k = float(cand[np.argmin(np.abs(np.nan_to_num(pr, nan=1e9) - last_sale_price[right]))])
                ep = px(right, k, j, "open")
                ep = ep if ep == ep and ep > 0 else px(right, k, j - 1)
                for _ in range(n):
                    shorts.setdefault((right, k), []).append(Lot(j, ep, role))
                emit(j, right, k, n, "sell", role)
                last_sale_price[right] = ep; touched = True
            # (c) protective wings: after any body order keep long lots equal to short lots on each right
            if touched or j == 1:
                for right in ("CE", "PE"):
                    S = sum(len(v) for (r_, _), v in shorts.items() if r_ == right)
                    L = sum(v for (r_, _), v in wings.items() if r_ == right and v > 0)
                    gap = S - L; sg = 1 if right == "CE" else -1
                    if gap > 0:
                        a0 = atm_strike(K, c[cj(j - 1)]); target = cfg.wing_premium_frac * px(right, a0, j - 1)
                        cand = K[sg * (K - c[cj(j - 1)]) > 0]                       # strictly out of the money
                        pr = np.array([px(right, kk, j - 1) for kk in cand]); ok = pr > 0
                        if ok.any() and target == target and target > 0:
                            k = float(cand[ok][np.argmin(np.abs(np.log(pr[ok] / target)))])
                            wings[(right, k)] = wings.get((right, k), 0) + gap; emit(j, right, k, gap, "buy", "protective_wing_buy")
                    elif gap < 0:                                                   # release the outermost wings first
                        excess = -gap
                        for k, v in sorted([(k_, v_) for (r_, k_), v_ in wings.items() if r_ == right and v_ > 0], key=lambda t: -sg * (t[0] - c[cj(j - 1)])):
                            if excess <= 0:
                                break
                            n = min(v, excess); wings[(right, k)] -= n; excess -= n; emit(j, right, k, n, "sell", "protective_wing_sell")
            # (d) overnight lump: one extra block of OTM longs on the heavier short side, ~2.2 one-day sigmas out
            if j == cfg.lump_minute:
                s_ce = sum(len(v) for (r_, _), v in shorts.items() if r_ == "CE"); s_pe = sum(len(v) for (r_, _), v in shorts.items() if r_ == "PE")
                right = "CE" if s_ce > s_pe else "PE"; heavy = max(s_ce, s_pe); n = int(round(cfg.lump_ratio * heavy)); sg = 1 if right == "CE" else -1
                if n > 0:
                    s0 = c[cj(j - 1)]; a = int(np.argmin(np.abs(K - s0)))
                    sigma = (px("CE", K[a], j - 1) + px("PE", K[a], j - 1)) / (0.7979 * s0)           # one-day move implied by the ATM straddle
                    k = float(K[np.argmin(np.abs(K - s0 * (1 + sg * cfg.lump_sigma_mult * sigma)))])
                    lump[(right, k)] = n; emit(j, right, k, n, "buy", "overnight_lump")
        short_book = {k: len(v) for k, v in shorts.items() if v}
        long_book = {k: v for k, v in wings.items() if v > 0}
        for k, v in lump.items():
            long_book[k] = long_book.get(k, 0) + v
        return Result(orders, short_book, long_book)


def config_for(underlying: str, d1_date: str) -> Config:
    """Configuration regime observed for a given D-1 date (ISO string). Timetable version and lump clock are system settings that changed on
    fixed dates; everything else is a property of the rules."""
    nifty = underlying.upper() == "NIFTY"
    cfg = Config(strike_step=50.0 if nifty else 100.0, lump_ratio=0.827 if nifty else 0.503)
    version_b = d1_date >= "2026-09-16"
    cfg.timetable = list(SCHEDULE_B if version_b else SCHEDULE_A)
    cfg.opening_wing_offset_steps = 20.0 if (not nifty and version_b) else 39.8
    cfg.lump_minute = (LUMP_MINUTE_BY_REGIME["until_2026-08-05"] if d1_date <= "2026-08-05"
                       else LUMP_MINUTE_BY_REGIME["2026-08-12_to_08-19"] if d1_date <= "2026-08-19" else LUMP_MINUTE_BY_REGIME["from_2026-08-24"])
    return cfg
