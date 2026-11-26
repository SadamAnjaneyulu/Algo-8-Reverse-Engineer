"""Shadow recorder and frozen late-sale rule for the forward test (reports/FORWARD_TEST.md).

Nothing here places orders. It (a) runs the FROZEN candidate rule next to the real system and (b) records, for every real order and for every
minute of the late window, the information needed to test the late-sale trigger afterwards:
  * prices BEFORE the order: previous completed minute (OHLC) and the running current minute at the order second, for the three candidate underlyings
    FEED (published index), FUT (near-month future), OPT (option-implied index, put-call parity on the three strikes nearest the money);
  * the portfolio state immediately before the order: short / long lots per side, open strikes, imbalance, lighter side, net delta (Black-76, r = 0);
  * the frozen rule's own state and fires.
The rule parameters are frozen in LateRuleConfig and hashed into every record. Do not change them during the forward sample.
"""
import json, os, math, hashlib
from dataclasses import dataclass, asdict
from typing import Callable, Dict, List, Optional, Tuple
import numpy as np

SESSION_START_MIN = 9 * 60 + 15                      # minute index j = minute of day - 09:15


@dataclass(frozen=True)
class LateRuleConfig:
    version: int = 1
    underlying: str = "FUT"                          # the price the rule reads (raw future; differences make the basis irrelevant)
    gate_min: int = 5                                # fresh favourable extreme over this many completed minutes
    ladder_step: float = 0.2                         # strike steps beyond the reference
    window_start: int = 360                          # 15:15
    window_end: int = 384                            # 15:39
    reference: str = "close before the latest REAL sale on that side"
    strike_rule: str = "premium closest to the last sale price within +-4 steps of ATM"
    strike_window: int = 4
    lots: int = 1

    def sha(self) -> str:
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()


def minute_of_day(ts: float) -> int:
    return int(ts // 60) - SESSION_START_MIN


class FrozenLateRule:
    """Live form of algo8_d1.ladder_fires with the late-window gate. Equivalent to the batch function at minute level (tested): the fire is raised in the first
    second the running extreme of the minute satisfies the condition, the reference is updated at the minute close with the final extreme."""

    def __init__(self, cfg: LateRuleConfig, strike_step: float):
        self.cfg = cfg; self.st = cfg.ladder_step * strike_step
        self.hi: List[float] = []; self.lo: List[float] = []; self.cl: List[float] = []        # completed minutes
        self.cur_min: Optional[int] = None; self.cur = None; self.base: Optional[int] = None    # running [o, h, l, c]; base = first minute seen (bar lists are indexed from it)
        self.ref = {"CE": None, "PE": None}; self.events = {"CE": [], "PE": []}; self.ptr = {"CE": 0, "PE": 0}; self.fired = {"CE": False, "PE": False}
        self.fires: List[dict] = []

    # ----- inputs
    def on_real_sale(self, right: str, minute: int):
        self.events[right].append(minute)

    def on_tick(self, ts: float, price: float):
        m = minute_of_day(ts)
        if self.cur_min is None:
            self.base = m; self.cur_min = m; self.cur = [price, price, price, price]; self._start_minute(m)
        while m > self.cur_min:                       # close the running minute; a silent minute in between carries the last close, the minute of THIS tick starts at the tick
            last = self.cur[3]; self._close_minute(); self.cur_min += 1
            self.cur = [price] * 4 if self.cur_min == m else [last] * 4; self._start_minute(self.cur_min)
        c = self.cur; c[1] = max(c[1], price); c[2] = min(c[2], price); c[3] = price
        self._check(ts)

    def flush(self):
        if self.cur_min is not None:
            self._close_minute(); self.cur_min += 1; self.cur = None

    # ----- internals
    def _start_minute(self, j: int):
        for r in ("CE", "PE"):
            ev = self.events[r]
            while self.ptr[r] < len(ev) and ev[self.ptr[r]] < j:
                self.ref[r] = self.cl[min(max(ev[self.ptr[r]] - 1 - self.base, 0), len(self.cl) - 1)] if self.cl else None; self.ptr[r] += 1
            self.fired[r] = False

    def _check(self, ts: float):
        j = self.cur_min; cfg = self.cfg
        if j is None or not self.cl: return                                  # the rule runs ALL DAY (its reference moves after its own fires, as in the batch function); only fires in the window are reported
        o, h, l, c = self.cur; jj = j - self.base; a = max(jj - cfg.gate_min, 0)
        for r in ("CE", "PE"):
            if self.ref[r] is None or self.fired[r]: continue
            if r == "CE":
                fresh = l < min(self.lo[a:jj]) and l < self.ref[r] - self.st
            else:
                fresh = h > max(self.hi[a:jj]) and h > self.ref[r] + self.st
            if fresh:
                self.fired[r] = True
                if cfg.window_start <= j <= cfg.window_end: self.fires.append(dict(ts=ts, minute=j, right=r, ref=self.ref[r], extreme=l if r == "CE" else h, lots=cfg.lots, rule_sha=cfg.sha()))

    def _close_minute(self):
        j = self.cur_min; o, h, l, c = self.cur
        for r in ("CE", "PE"):                        # reference update uses the final extreme of the minute, as the batch function
            if self.fired[r] and self.ref[r] is not None:
                self.ref[r] = self.ref[r] - self.st * max(1, int((self.ref[r] - l) // self.st)) if r == "CE" else self.ref[r] + self.st * max(1, int((h - self.ref[r]) // self.st))
        self.hi.append(h); self.lo.append(l); self.cl.append(c)


def solo_strike(strikes: np.ndarray, atm: float, prev_close_premium: Callable[[float], float], last_sale_price: Optional[float], step: float, window: int = 4) -> float:
    """Engine's solo-strike rule: ATM for the first sale on a side, then the strike within +-window steps of ATM whose previous-minute premium is closest to the last sale price."""
    if last_sale_price is None: return float(atm)
    cand = strikes[np.abs(strikes - atm) <= window * step]
    pr = np.array([prev_close_premium(float(k)) for k in cand])
    return float(cand[np.argmin(np.abs(np.nan_to_num(pr, nan=1e9) - last_sale_price))])


def _ncdf(x): return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def black_price(F: float, K: float, T: float, vol: float, call: bool) -> float:
    s = vol * math.sqrt(T); d1 = (math.log(F / K) + 0.5 * s * s) / s; d2 = d1 - s
    return F * _ncdf(d1) - K * _ncdf(d2) if call else K * _ncdf(-d2) - F * _ncdf(-d1)


def implied_vol(price: float, F: float, K: float, T: float, call: bool) -> float:
    intrinsic = max(F - K, 0.0) if call else max(K - F, 0.0)
    if not (price > intrinsic + 1e-9) or T <= 0: return float("nan")
    lo, hi = 1e-3, 5.0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if black_price(F, K, T, mid, call) > price: hi = mid
        else: lo = mid
    return 0.5 * (lo + hi)


def net_delta(positions: Dict[Tuple[str, float], int], F: float, T_years: float, ltp: Callable[[str, float], float], unit: float) -> float:
    """sum over legs of signed lots * unit * Black-76 delta (index units). Legs with no usable price are skipped (counted in the record as n_skipped)."""
    tot = 0.0
    for (r, k), n in positions.items():
        if n == 0: continue
        p = ltp(r, k); iv = implied_vol(p, F, k, T_years, r == "CE") if p == p else float("nan")
        if iv != iv: continue
        s = iv * math.sqrt(T_years); d1 = (math.log(F / k) + 0.5 * s * s) / s; d = _ncdf(d1) if r == "CE" else _ncdf(d1) - 1.0; tot += n * unit * d
    return tot


class ShadowRecorder:
    """Call on_snapshot(...) about once a second for the WHOLE session from 09:15 (the rule's reference depends on its earlier fires), on_real_order(...) for every fill of the REAL system."""

    def __init__(self, out_dir: str, underlying: str, d1_date: str, unit: float, strike_step: float, expiry_ts: float, cfg: LateRuleConfig = LateRuleConfig()):
        os.makedirs(out_dir, exist_ok=True); self.dir = out_dir; self.und = underlying; self.d1 = d1_date; self.unit = unit; self.step = strike_step; self.expiry_ts = expiry_ts; self.cfg = cfg
        self.rule = FrozenLateRule(cfg, strike_step); self.fmin = open(f"{out_dir}/minutes_{underlying}_{d1_date}.jsonl", "a"); self.ford = open(f"{out_dir}/orders_{underlying}_{d1_date}.jsonl", "a")
        self.bars = {k: {} for k in ("FEED", "FUT", "OPT")}; self.state = dict(ts=None, positions={}, ltp=None, strikes=None, feed=None, fut=None, opt=None); self.last_sale = {"CE": None, "PE": None}; self.last_strike = {"CE": None, "PE": None}; self.nrules = 0; self._basis = None

    # ----- helpers
    def _bar(self, name: str, m: int, p: float):
        d = self.bars[name]; b = d.get(m)
        if b is None: d[m] = [p, p, p, p]
        else: b[1] = max(b[1], p); b[2] = min(b[2], p); b[3] = p

    def _opt_implied(self, ltp: Callable[[str, float], float], strikes: np.ndarray, ref: float) -> float:
        idx = np.argsort(np.abs(strikes - ref))[:3]; v = []
        for i in idx:
            k = float(strikes[i]); c, p = ltp("CE", k), ltp("PE", k)
            if c == c and p == p: v.append(k + c - p)
        return float(np.median(v)) if v else float("nan")

    def _prices(self, m: int):
        out = {}
        for n in ("FEED", "FUT", "OPT"):
            cur = self.bars[n].get(m); prev = self.bars[n].get(m - 1); out[n] = dict(prev=prev, cur=cur)
        return out

    def _book(self, positions: Dict[Tuple[str, float], int], ltp, F: float, ts: float) -> dict:
        sh = {r: -sum(n for (rr, k), n in positions.items() if rr == r and n < 0) for r in ("CE", "PE")}; lg = {r: sum(n for (rr, k), n in positions.items() if rr == r and n > 0) for r in ("CE", "PE")}
        T = max((self.expiry_ts - ts) / (365.0 * 86400.0), 1e-6); nd = net_delta(positions, F, T, ltp, self.unit) if F == F else float("nan")
        return dict(short_CE=sh["CE"], short_PE=sh["PE"], long_CE=lg["CE"], long_PE=lg["PE"], imbalance_CE_minus_PE=sh["CE"] - sh["PE"], lighter_side="CE" if sh["CE"] < sh["PE"] else ("PE" if sh["PE"] < sh["CE"] else "equal"),
                    open_short_strikes=sorted({f"{r}{int(k)}" for (r, k), n in positions.items() if n < 0}), net_delta=nd, delta_time_years=T)

    def _w(self, f, rec: dict):
        rec.update(schema=1, und=self.und, d1=self.d1, rule_sha=self.cfg.sha()); f.write(json.dumps(rec, default=float) + "\n"); f.flush()

    # ----- inputs
    def on_snapshot(self, ts: float, feed: float, fut: float, ltp: Callable[[str, float], float], strikes: np.ndarray, positions: Dict[Tuple[str, float], int]):
        m = minute_of_day(ts); opt = self._opt_implied(ltp, strikes, fut if fut == fut else feed)
        if self.state["ts"] is not None and m > minute_of_day(self.state["ts"]): self._minute_close(minute_of_day(self.state["ts"]))
        self._bar("FEED", m, feed); self._bar("FUT", m, fut)
        if opt == opt: self._bar("OPT", m, opt)
        self.rule.on_tick(ts, fut); self.state.update(ts=ts, positions=dict(positions), ltp=ltp, strikes=strikes, feed=feed, fut=fut, opt=opt)

    def _minute_close(self, m: int):
        if not (self.cfg.window_start - 15 <= m <= self.cfg.window_end + 1): return
        s = self.state; fb = self.bars["FUT"].get(m); basis = None
        if 345 <= m <= 359 and fb and self.bars["FEED"].get(m): self._basis = (self._basis or []) + [fb[3] - self.bars["FEED"][m][3]]
        rec = dict(kind="minute", j=m, ts_close=s["ts"], feed=self.bars["FEED"].get(m), fut=fb, opt_implied=self.bars["OPT"].get(m), basis_fut_minus_feed=float(np.median(self._basis)) if self._basis else None,
                   rule=dict(ref=dict(self.rule.ref), fires_this_minute=[f for f in self.rule.fires if f["minute"] == m]),
                   book=self._book(s["positions"], s["ltp"], s["opt"] if s["opt"] == s["opt"] else s["fut"], s["ts"]) if s["ltp"] else None)
        self._w(self.fmin, rec)

    def on_real_order(self, ts: float, right: str, strike: float, lots: int, side: str, price: float, role: str = "", order_id: str = ""):
        """side 'sell' / 'buy'. State is taken from the last snapshot BEFORE this call (the order itself is not yet in it)."""
        m = minute_of_day(ts); s = self.state; pr = self._prices(m); a0 = float(s["strikes"][np.argmin(np.abs(s["strikes"] - s["fut"]))]) if s["strikes"] is not None and s["fut"] is not None else None
        prop = None
        if s["ltp"] is not None and s["strikes"] is not None and s["opt"] == s["opt"]:
            prop = solo_strike(s["strikes"], float(s["strikes"][np.argmin(np.abs(s["strikes"] - s["opt"]))]), lambda k: s["ltp"](right, k), self.last_sale[right], self.step, self.cfg.strike_window)
        rec = dict(kind="order", ts=ts, j=m, right=right, strike=strike, lots=lots, side=side, price=price, role=role, order_id=order_id, prices_before=pr,
                   book_before=self._book(s["positions"], s["ltp"], s["opt"] if s["opt"] == s["opt"] else s["fut"], ts) if s["ltp"] else None, last_sale_price_same_side=self.last_sale[right], last_sale_strike_same_side=self.last_strike[right],
                   rule=dict(ref=dict(self.rule.ref), fired_this_minute={r: self.rule.fired[r] for r in ("CE", "PE")}, proposed_strike=prop))
        self._w(self.ford, rec)
        if side == "sell" and role in ("", "open_short", "body_sell", "ladder_solo", "scheduled_straddle", "breakout_straddle", "breakout_extra"):
            self.rule.on_real_sale(right, m); self.last_sale[right] = price; self.last_strike[right] = strike

    def close(self):
        if self.state["ts"] is not None: self._minute_close(minute_of_day(self.state["ts"]))
        self.rule.flush(); self.fmin.close(); self.ford.close()
