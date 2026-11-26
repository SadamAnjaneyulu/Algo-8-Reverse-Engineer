"""D1Engine: the strategy as a running program.

Call engine.step() about once a second (a live loop, or the replay driver). Each step it
  1. reads the spot and the contracts it watches, builds one-minute bars,
  2. collects broker fills and updates the book,
  3. runs the rules in this order: opening wings, scheduled straddles, breakout straddles, solo ladder, per-lot stops, wing controller, overnight lump,
  4. sends the orders the rules produced (through the risk guard) to the broker.
Everything uses only prices that exist at that second (completed minute bars for references, running minute values for intrabar triggers).
"""
from __future__ import annotations
import json
import math
from typing import Callable, Dict, List, Optional, Tuple
import numpy as np

from .bars import OptionBars, SpotBars
from .book import Book
from .config import D1Config
from .interfaces import Broker, MarketData
from .models import Fill, Lot, OrderRequest, SESSION_OPEN_S, minute_index
from .risk import RiskGuard

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
# Order type by role, as OBSERVED in the real D-1 log (9,885 orders of the 32 cycles outside the stop module `s_`, which the engine does not model): every body-module (`num`) order is DAY, every wing (`h_`) and lump (`v_`) order is IOC, with no exception.
# The engine emits these explicitly; a role without an entry raises (no default, no inference). Checked against the log in tests/test_order_type.py.
ROLE_ORDER_TYPE = {"scheduled_straddle": ("num", "DAY"), "breakout_straddle": ("num", "DAY"), "breakout_extra": ("num", "DAY"), "ladder_solo": ("num", "DAY"), "stop_buyback": ("num", "DAY"), "opening_wing_buy": ("num", "DAY"),
                   "protective_wing_buy": ("h_", "IOC"), "protective_wing_sell": ("h_", "IOC"), "overnight_lump": ("v_", "IOC")}
# Execution convention 'one_lot_v2' (D1Config.order_split): roles whose real orders are always single lots (real D-1 log: body buy-backs 1,324 orders, 100% 1-lot; opening-wing buys 186 orders, 100% 1-lot).
# Wing-controller buys / sells and the lump are sized orders in the real log (18.8% / 40.3% / 93% multi-lot) and are NOT split. Splitting changes order granularity only, never quantity, timing, strike or the decision to trade.
ONE_LOT_ROLES = {"opening_wing_buy", "stop_buyback"}
ORDER_SPLIT_CONVENTIONS = ("freeze_v1", "one_lot_v2")
SELL_ROLES = {"scheduled_straddle", "breakout_straddle", "breakout_extra", "ladder_solo"}


class D1Engine:
    def __init__(self, cfg: D1Config, feed: MarketData, broker: Broker, risk: Optional[RiskGuard] = None, log: Optional[Callable[[str], None]] = None):
        self.cfg, self.feed, self.broker = cfg, feed, broker
        self.risk = risk or RiskGuard(cfg)
        self.log = log or (lambda msg: None)
        self.K = np.asarray(feed.strikes(), dtype=float)
        self.book = Book(); self.spot_bars = SpotBars(); self.opt_bars = OptionBars()
        self.orders: List[OrderRequest] = []; self.fills: List[Fill] = []; self.rejected: List[Tuple[OrderRequest, str]] = []
        self.done_waves: set = set(); self.done_opening = False; self.done_lump = False
        self.breaks_done: set = set(); self.pending_breaks: Dict[Tuple[int, int], dict] = {}; self._channels: Dict[int, Optional[Tuple[float, float]]] = {}
        self.ladder_ref: Dict[str, Optional[float]] = {"CE": None, "PE": None}; self.ladder_from: Dict[str, int] = {"CE": 10 ** 9, "PE": 10 ** 9}
        self.last_sale_price: Dict[str, Optional[float]] = {"CE": None, "PE": None}
        self.wing_first: Optional[float] = None; self.wing_last: Optional[float] = None
        self._seq = 0; self._decision_seq = 0; self._pending: Dict[str, List] = {}; self._pending_stop: Dict[Tuple[str, float], int] = {}
        self._last_saved = -1

    # ------------------------------------------------------------------ helpers
    def _atm(self, price: float) -> float:
        return float(self.K[np.argmin(np.abs(self.K - price))])

    def _snap(self, price: float) -> float:
        return self._atm(price)

    def _prev_close(self, j: int) -> Optional[float]:
        return self.spot_bars.prev_close(j)

    def _tick_round(self, x: float, up: bool) -> float:
        t = self.cfg.price_tick; return (math.ceil(x / t - 1e-9) if up else math.floor(x / t + 1e-9)) * t

    # ------------------------------------------------------------------ main step
    def step(self):
        t = self.feed.now(); j = minute_index(t)
        if j < 0:
            return
        spot = self.feed.spot()
        if spot != spot:
            return
        self.spot_bars.tick(j, spot)
        self._sample_options(j, spot)
        self._process_fills(self.broker.poll_fills())
        self._opening_wings(t, j); self._scheduled(t, j); self._breakout(t, j, spot); self._ladder(t, j, spot); self._stops(t, j)
        self._wing_controller(t, j); self._lump(t, j); self._risk_watch(t, j)
        if self.cfg.state_file and j != self._last_saved:
            self.save(); self._last_saved = j

    # ------------------------------------------------------------------ data
    def _sample_options(self, j: int, spot: float):
        c = self.cfg; a0 = self._atm(spot); w = (c.ladder_strike_window + 1) * c.strike_step
        watch = {(r, float(k)) for r in ("CE", "PE") for k in self.K if abs(k - a0) <= w} | {key for key, v in self.book.shorts.items() if v}
        for r, k in watch:
            self.opt_bars.sample(r, k, j, self.feed.option_ltp(r, k))

    # ------------------------------------------------------------------ order plumbing
    def _submit(self, right: str, strike: float, lots: int, side: str, role: str) -> bool:
        """Create orders (split at the freeze quantity), pass them through the risk guard, send them, and track them as pending."""
        t = self.feed.now(); j = minute_index(t); c = self.cfg
        ltp = self.feed.option_ltp(right, strike)
        if ltp != ltp or ltp <= 0:
            self.log(f"{t:.0f} skip {role} {right} {strike}: no price"); return False
        if c.order_split not in ORDER_SPLIT_CONVENTIONS: raise ValueError(f"unknown order_split {c.order_split!r}")
        left = lots; ok_any = False; one_lot = c.order_split == "one_lot_v2" and role in ONE_LOT_ROLES; self._decision_seq += 1; did = f"d{self._decision_seq}"       # one decision id per _submit call; under one_lot_v2 the per-minute order limit counts decisions (RiskGuard.check)
        while left > 0:
            n = 1 if one_lot else min(left, c.freeze_lots); left -= n
            limit = self._tick_round(ltp * (1 + c.limit_buffer_pct / 100.0), True) if side == "BUY" else self._tick_round(ltp * (1 - c.limit_buffer_pct / 100.0), False)
            limit = max(limit, c.price_tick)
            self._seq += 1; mod, validity = ROLE_ORDER_TYPE[role]; req = OrderRequest(f"{role}-{self._seq}", t, right, strike, n, side, limit, role, validity, mod, did)
            allowed, why = self.risk.check(req, self.book.short_count(right), j)
            if not allowed:
                self.rejected.append((req, why)); self.log(f"{t:.0f} blocked {role} {right} {strike} x{n}: {why}"); continue
            self.orders.append(req); self._pending[req.tag] = [req, n]; self._pending_adjust(req, n, +1); ok_any = True
            self._process_fills(self.broker.place(req))
        return ok_any

    def _pending_adjust(self, req: OrderRequest, n: int, sign: int):
        b = self.book
        if req.role in SELL_ROLES: b.pending_short[req.right] += sign * n
        elif req.role == "stop_buyback": b.pending_short[req.right] -= sign * n; self._pending_stop[(req.right, req.strike)] = self._pending_stop.get((req.right, req.strike), 0) + sign * n
        elif req.role in ("protective_wing_buy", "opening_wing_buy"): b.pending_wing[req.right] += sign * n
        elif req.role == "protective_wing_sell": b.pending_wing[req.right] -= sign * n

    def _process_fills(self, fills: List[Fill]):
        for f in fills:
            slot = self._pending.get(f.tag)
            req = slot[0] if slot else None
            if slot:
                self._pending_adjust(req, f.lots, -1); slot[1] -= f.lots
                if slot[1] <= 0: self._pending.pop(f.tag, None)
            self.fills.append(f); b = self.book; minute = minute_index(f.ts)
            if f.role in SELL_ROLES and f.side == "SELL":
                b.add_short(f.right, f.strike, Lot(f.ts, minute, f.price, f.role), f.lots); self.last_sale_price[f.right] = f.price
            elif f.role == "stop_buyback": b.remove_shorts(f.right, f.strike, f.lots)
            elif f.role in ("protective_wing_buy", "opening_wing_buy"): b.add_wing(f.right, f.strike, f.lots)
            elif f.role == "protective_wing_sell": b.sell_wing(f.right, f.strike, f.lots)
            elif f.role == "overnight_lump": b.lump[(f.right, f.strike)] = b.lump.get((f.right, f.strike), 0) + f.lots

    def _note_body(self, t: float):
        if self.wing_first is None: self.wing_first = t
        self.wing_last = t

    # ------------------------------------------------------------------ rules
    def _opening_wings(self, t: float, j: int):
        c = self.cfg
        if self.done_opening or t < SESSION_OPEN_S + 60 or j > 3:
            return
        pc = self._prev_close(j)
        if pc is None: return
        for right, sg in (("CE", 1), ("PE", -1)):
            k = self._snap(self._atm(pc) + sg * c.opening_wing_offset_steps * c.strike_step)
            self._submit(right, k, c.opening_wing_lots_per_right, "BUY", "opening_wing_buy")
        self.done_opening = True; self._note_body(t)

    def _scheduled(self, t: float, j: int):
        c = self.cfg
        for n, sec in enumerate(c.timetable):
            if n in self.done_waves: continue
            target = SESSION_OPEN_S + 60 + sec
            if t < target: continue
            self.done_waves.add(n)
            if t - target > c.max_wave_lateness_s:
                self.log(f"{t:.0f} wave {n} skipped (late)"); continue
            pc = self._prev_close(j)
            if pc is None: continue
            k = self._atm(pc)
            for right in ("CE", "PE"):
                self._submit(right, k, 1, "SELL", "scheduled_straddle"); self._ladder_event(right, j)
            self._note_body(t)

    def _channel(self, b0: int) -> Optional[Tuple[float, float]]:
        if b0 in self._channels: return self._channels[b0]
        a = int(math.ceil((b0 - 3600 - SESSION_OPEN_S) / 60)); e = int(math.ceil((b0 - SESSION_OPEN_S) / 60))
        if e - max(a, 0) < 2 or self.spot_bars.completed() < e: return None
        self._channels[b0] = self.spot_bars.window(a, e); return self._channels[b0]

    def _breakout(self, t: float, j: int, spot: float):
        c = self.cfg
        if not (c.breakout_start_min <= j <= c.breakout_end_min): return
        b0 = ((SESSION_OPEN_S + 60 * j) // 1800) * 1800; ch = self._channel(b0)
        if ch is None: return
        top, bottom = ch
        for side, broke in ((1, spot > top), (-1, spot < bottom)):
            key = (b0, side)
            if key in self.breaks_done: continue
            st = self.pending_breaks.get(key)
            if st is None and broke: st = self.pending_breaks[key] = {"t0": t, "ext": spot}
            if st is None: continue
            st["ext"] = max(st["ext"], spot) if side > 0 else min(st["ext"], spot)
            if t - st["t0"] >= c.breakout_size_after_s:
                depth = (st["ext"] - top) / c.strike_step if side > 0 else (bottom - st["ext"]) / c.strike_step
                self._fire_breakout(t, j, side, float(depth)); self.breaks_done.add(key); self.pending_breaks.pop(key, None)

    def _fire_breakout(self, t: float, j: int, side: int, depth: float):
        c = self.cfg; pc = self._prev_close(j)
        if pc is None: return
        k = self._snap(self._atm(pc) + side * c.strike_step)
        n = min(1 + int(depth // c.pairs_per_depth_step), c.max_pairs)
        for right in ("CE", "PE"):
            self._submit(right, k, n, "SELL", "breakout_straddle"); self._ladder_event(right, j)
        extra = int(np.clip(round(c.extra_a + c.extra_b * depth), 0, c.max_extra))
        if extra: self._submit("PE" if side > 0 else "CE", k, extra, "SELL", "breakout_extra")
        self._note_body(t)

    def _ladder_event(self, right: str, j: int):
        """A scheduled or breakout sale resets the ladder reference to the close before it; the ladder is live from the next minute."""
        pc = self._prev_close(j)
        if pc is not None: self.ladder_ref[right] = pc; self.ladder_from[right] = j + 1

    def _solo_strike(self, right: str, j: int) -> Optional[float]:
        c = self.cfg; pc = self._prev_close(j)
        if pc is None: return None
        a0 = self._atm(pc); last = self.last_sale_price[right]
        if last is None: return a0
        cand = [float(k) for k in self.K if abs(k - a0) <= c.ladder_strike_window * c.strike_step]
        pr = []
        for k in cand:
            p = self.opt_bars.prev_close(right, k, j)
            if p != p: p = self.feed.option_ltp(right, k)
            pr.append(p)
        pr = np.nan_to_num(np.array(pr, dtype=float), nan=1e9)
        return cand[int(np.argmin(np.abs(pr - last)))]

    def _ladder(self, t: float, j: int, spot: float):
        c = self.cfg; sb = self.spot_bars; st = c.strike_step * c.ladder_step
        lo, hi = max(j - c.ladder_gate_min, 0), j
        if sb.completed() < 1: return
        for right in ("CE", "PE"):
            ref = self.ladder_ref[right]
            if ref is None or j < self.ladder_from[right]: continue
            if right == "CE":
                if sb.cur_low < min(sb.low[lo:hi]) and sb.cur_low < ref - st:
                    self.ladder_ref[right] = ref - st * max(1, int((ref - sb.cur_low) // st)); self._ladder_fire(right, j, t)
            else:
                if sb.cur_high > max(sb.high[lo:hi]) and sb.cur_high > ref + st:
                    self.ladder_ref[right] = ref + st * max(1, int((sb.cur_high - ref) // st)); self._ladder_fire(right, j, t)

    def _ladder_fire(self, right: str, j: int, t: float):
        k = self._solo_strike(right, j)
        if k is not None and self._submit(right, k, 1, "SELL", "ladder_solo"): self._note_body(t)

    def _stops(self, t: float, j: int):
        c = self.cfg
        for (right, k), lots in list(self.book.shorts.items()):
            if not lots: continue
            now = self.opt_bars.run_high(right, k, j) if c.stop_price == "high" else self.opt_bars.prev_close(right, k, j)
            if now != now: continue
            hit = sum(1 for l in lots if l.minute < j and l.entry_price > 0 and now / l.entry_price >= c.stop_ratio) - self._pending_stop.get((right, k), 0)
            if hit > 0 and self._submit(right, k, hit, "BUY", "stop_buyback"): self._note_body(t)

    def _wing_controller(self, t: float, j: int):
        c = self.cfg
        if self.wing_last is None: return
        if not (t >= self.wing_last + c.wing_delay_s or t >= self.wing_first + 2 * c.wing_delay_s): return
        self.wing_first = self.wing_last = None
        pc = self._prev_close(j)
        if pc is None: return
        for right, sg in (("CE", 1), ("PE", -1)):
            gap = self.book.short_count(right) - self.book.wing_count(right)
            if gap > 0:
                atm_px = self.feed.option_ltp(right, self._atm(pc)); target = c.wing_premium_frac * atm_px
                if not (target == target and target > 0): continue
                best = None
                for k in self.K:
                    if sg * (k - pc) <= 0: continue
                    p = self.feed.option_ltp(right, float(k))
                    if p == p and p > 0:
                        d = abs(math.log(p / target))
                        if best is None or d < best[0]: best = (d, float(k))
                if best: self._submit(right, best[1], gap, "BUY", "protective_wing_buy")
            elif gap < 0:
                excess = -gap
                held = sorted([(k, v) for (r, k), v in self.book.wings.items() if r == right and v > 0], key=lambda x: -sg * (x[0] - pc))   # outermost first
                for k, v in held:
                    if excess <= 0: break
                    n = min(v, excess); excess -= n; self._submit(right, k, n, "SELL", "protective_wing_sell")

    def _lump(self, t: float, j: int):
        c = self.cfg
        if self.done_lump or t < c.lump_time_s or t > c.lump_time_s + 600: return
        self.done_lump = True
        s_ce, s_pe = self.book.short_count("CE", False), self.book.short_count("PE", False)
        right = "CE" if s_ce > s_pe else "PE"; sg = 1 if right == "CE" else -1; n = int(round(c.lump_ratio * max(s_ce, s_pe)))
        pc = self._prev_close(j)
        if n <= 0 or pc is None: return
        a = self._atm(pc); straddle = self.feed.option_ltp("CE", a) + self.feed.option_ltp("PE", a); sigma = straddle / (0.7979 * pc)
        if not (sigma == sigma and sigma > 0): return
        k = self._snap(pc * (1 + sg * c.lump_sigma_mult * sigma))
        self._submit(right, k, n, "BUY", "overnight_lump")

    def _risk_watch(self, t: float, j: int):
        c = self.cfg
        if c.max_loss_rupees is None or self.risk.halted or t % 60 > 1: return
        loss = 0.0
        for (r, k), lots in self.book.shorts.items():
            p = self.feed.option_ltp(r, k)
            if p == p: loss += sum((p - l.entry_price) for l in lots) * c.lot_units
        if loss > c.max_loss_rupees: self.risk.halt(f"short book loss {loss:,.0f} above limit"); self.log(f"HALT: {self.risk.reason}")

    # ------------------------------------------------------------------ state
    def save(self):
        sb = self.spot_bars
        state = {"book": self.book.snapshot(), "done_waves": sorted(self.done_waves), "done_opening": self.done_opening, "done_lump": self.done_lump,
                 "breaks_done": [list(x) for x in self.breaks_done], "ladder_ref": self.ladder_ref, "ladder_from": self.ladder_from,
                 "last_sale_price": self.last_sale_price, "spot_bars": [sb.open, sb.high, sb.low, sb.close], "seq": self._seq}
        with open(self.cfg.state_file, "w") as fh: json.dump(state, fh)

    def load(self, path: Optional[str] = None):
        s = json.load(open(path or self.cfg.state_file))
        self.book.restore(s["book"]); self.done_waves = set(s["done_waves"]); self.done_opening = s["done_opening"]; self.done_lump = s["done_lump"]
        self.breaks_done = {tuple(x) for x in s["breaks_done"]}; self.ladder_ref = s["ladder_ref"]; self.ladder_from = {k: int(v) for k, v in s["ladder_from"].items()}
        self.last_sale_price = s["last_sale_price"]; self._seq = s["seq"]
        sb = self.spot_bars; sb.open, sb.high, sb.low, sb.close = [list(x) for x in s["spot_bars"]]; sb.minute = -1

    def warm_start(self, history: List[Tuple[float, float, float, float]]):
        """Load completed one-minute spot bars (open, high, low, close from 09:15 to the last completed minute) when starting mid-session."""
        sb = self.spot_bars
        sb.open = [h[0] for h in history]; sb.high = [h[1] for h in history]; sb.low = [h[2] for h in history]; sb.close = [h[3] for h in history]; sb.minute = -1

    def orders_frame(self):
        import pandas as pd
        return pd.DataFrame([{"minute": minute_index(o.ts), "ts": o.ts, "right": o.right, "strike": o.strike, "lots": o.lots, "side": o.side, "limit": o.limit_price, "role": o.role, "validity": o.validity, "module": o.module, "decision_id": o.decision_id}
                             for o in self.orders])
