"""Additive companion to the frozen shadow recorder: logs the pre-order STATE needed to test the late-sale hypotheses afterwards (reports/FORWARD_RECORDER_FIELDS.md).

Nothing here places orders and nothing in `shadow.py` is changed (its file hash and the frozen rule hash are part of the forward protocol). `StateShadowRecorder` subclasses
`ShadowRecorder`, calls the parent first/last exactly as before, so the parent's minute and order logs are byte-identical, and writes ONE extra file
`state_<und>_<d1>.jsonl` with two record kinds:

  state_minute  written at the close of minute m for the DECISION minute j_next = m + 1. Every value uses information available at the close of m, i.e. strictly before j_next.
  order_state   written for every real order, before it is applied: its action (open_short / cover_short / open_long / close_long), the per-side sold-lot count before it, seconds since the
                last short sale, and for a sale that closes a long: FIFO entry price and exit / entry ratio.

Definitions (identical to the offline tests in reports/LATE_SALE_FOCUSED_PLAN.md and LATE_SALE_RECENTER_PLAN.md; STATE_SPEC below is hashed into every record):
  straddle[m]      ATM call + put close at the last snapshot of minute m; ATM = strike nearest to the option-implied index (fallback: the future).
  STR15            straddle[m] / straddle[m-15] - 1
  fut_move_5m      FUT close[m] - FUT close[m-5]   (also FEED and OPT); fut_move_5m_steps_oriented = +move/step for PE, -move/step for CE (positive favours the contrarian side)
  MTM              cash from real orders + sum(net lots x close x unit) over open legs; premium_collected = sum(sold lots x price x unit)
  PP               MTM / premium_collected;   GB = MTM[m] - max(MTM[m'] for m' <= m-1)
  D_fut, D_opt     out-of-the-money steps of the nearest net-SHORT strike on the side, versus FUT close[m] and versus the option-implied close[m] (positive = OTM; null when no short)
  sold_lots        cumulative open_short lots today per side; sold_deficit_oriented = other side - this side
  atm_chain        close premiums [CE, PE] for the 9 strikes around ATM (so the side's ATM-premium change can be rebuilt offline)
Assumption: the recorder runs from the session start with a flat book (the parent already requires on_snapshot for the whole session). Positions, lot counts and marks come from the recorder's own order ledger so that cash and positions are always from the same instant; `ledger_matches_snapshot` flags any drift from the caller's positions."""
import json, math, hashlib
from typing import Callable, Dict, Optional, Tuple
import numpy as np
from .shadow import ShadowRecorder, LateRuleConfig, minute_of_day

STATE_SPEC = dict(version=1, straddle="ATM call+put close at last snapshot of minute m, ATM nearest option-implied index (fallback future)", STR15="straddle[m]/straddle[m-15]-1",
                  move5="close[m]-close[m-5] for FUT, FEED, OPT", MTM="order cash + sum(net lots*close*unit) over open legs", PP="MTM/premium_collected", GB="MTM[m]-max(MTM[m'] for m'<=m-1)",
                  D="OTM steps of nearest net-short strike vs FUT close[m] and vs OPT close[m]", sold_lots="cumulative open_short lots per side", decision_minute="m+1; all values use information through the close of m")
SPEC_SHA = hashlib.sha256(json.dumps(STATE_SPEC, sort_keys=True).encode()).hexdigest()
SHORT_ROLES_OPEN = ("", "open_short")


def _finite(x) -> bool:
    return x is not None and x == x and not math.isinf(x)


class StateShadowRecorder(ShadowRecorder):
    def __init__(self, out_dir: str, underlying: str, d1_date: str, unit: float, strike_step: float, expiry_ts: float, cfg: LateRuleConfig = LateRuleConfig()):
        super().__init__(out_dir, underlying, d1_date, unit, strike_step, expiry_ts, cfg)
        self.fstate = open(f"{out_dir}/state_{underlying}_{d1_date}.jsonl", "a")
        self._cash = 0.0; self._prem = 0.0; self._led: Dict[Tuple[str, float], int] = {}; self._longs: Dict[Tuple[str, float], list] = {}
        self._sold = {"CE": 0, "PE": 0}; self._last_short = None; self._last_short_side = {"CE": None, "PE": None}
        self._straddle: Dict[int, float] = {}; self._mtm: Dict[int, float] = {}; self._last_written: Optional[int] = None

    # ----- helpers
    def _w2(self, rec: dict):
        rec.update(schema=1, state_spec_sha=SPEC_SHA, und=self.und, d1=self.d1, rule_sha=self.cfg.sha()); self.fstate.write(json.dumps(rec, default=float) + "\n"); self.fstate.flush()

    def _close_of(self, name: str, m: int) -> Optional[float]:
        b = self.bars[name].get(m); return float(b[3]) if b else None

    def _held_short_distance(self, positions, right: str, price: Optional[float]) -> Optional[float]:
        if not _finite(price): return None
        d = [((k - price) / self.step) if right == "CE" else ((price - k) / self.step) for (r, k), n in positions.items() if r == right and n < 0]
        return float(min(d)) if d else None

    # ----- overrides (parent logic untouched)
    def on_snapshot(self, ts: float, feed: float, fut: float, ltp: Callable[[str, float], float], strikes: np.ndarray, positions: Dict[Tuple[str, float], int]):
        prev = self.state["ts"]
        if prev is not None and minute_of_day(ts) > minute_of_day(prev): self._state_minute(minute_of_day(prev))
        super().on_snapshot(ts, feed, fut, ltp, strikes, positions)

    def on_real_order(self, ts: float, right: str, strike: float, lots: int, side: str, price: float, role: str = "", order_id: str = ""):
        m = minute_of_day(ts); prev = self.state["ts"]
        if prev is not None and m > minute_of_day(prev): self._state_minute(minute_of_day(prev))        # the minute that just ended is closed BEFORE this order is applied, so cash, ledger and marks stay consistent
        key = (right, float(strike)); pos = self._led.get(key, 0); rec = dict(kind="order_state", ts=ts, j=m, right=right, strike=strike, lots=lots, side=side, price=price, role=role, order_id=order_id, ledger_net_lots_before=pos,
                                                                                                       sold_lots_before=dict(self._sold), seconds_since_last_short_sale=(ts - self._last_short) if self._last_short is not None else None,
                                                                                                       seconds_since_last_short_sale_same_side=(ts - self._last_short_side[right]) if self._last_short_side[right] is not None else None)
        if side == "sell":
            closing = min(lots, max(pos, 0)); opening = lots - closing; rec["action"] = "close_long" if closing and not opening else ("close_long+open_short" if closing else "open_short")
            if closing:
                need = closing; cost = 0.0; q = self._longs.get(key, [])
                while need > 0 and q: take = min(q[0][0], need); cost += take * q[0][1]; q[0][0] -= take; need -= take; q = q if q[0][0] > 0 else q[1:]; self._longs[key] = q
                matched = closing - need; entry = cost / matched if matched else None; rec.update(matched_lots=matched, entry_price_fifo=entry, exit_over_entry=(price / entry) if entry else None, sold_above_entry=(price > entry) if entry else None)
            if opening:
                self._sold[right] += opening; self._prem += opening * price * self.unit; self._last_short = ts; self._last_short_side[right] = ts
            self._led[key] = pos - lots
        else:
            covering = min(lots, max(-pos, 0)); opening = lots - covering; rec["action"] = "cover_short" if covering and not opening else ("cover_short+open_long" if covering else "open_long")
            if opening: self._longs.setdefault(key, []).append([opening, price])
            self._led[key] = pos + lots
        self._cash += (price * lots * self.unit) if side == "sell" else -(price * lots * self.unit)
        self._w2(rec); super().on_real_order(ts, right, strike, lots, side, price, role, order_id)

    def close(self):
        if self.state["ts"] is not None: self._state_minute(minute_of_day(self.state["ts"]))
        super().close(); self.fstate.close()

    # ----- the per-minute state
    def _state_minute(self, m: int):
        s = self.state
        if self._last_written is not None and m <= self._last_written: return
        self._last_written = m; ltp = s["ltp"]; strikes = s["strikes"]
        if ltp is None or strikes is None: return
        F = s["opt"] if _finite(s["opt"]) else s["fut"]; k0 = float(strikes[int(np.argmin(np.abs(strikes - F)))]) if _finite(F) else None
        c0, p0 = (ltp("CE", k0), ltp("PE", k0)) if k0 is not None else (float("nan"), float("nan")); st = float(c0 + p0) if c0 == c0 and p0 == p0 else float("nan"); self._straddle[m] = st
        val = 0.0
        led = {kk: n for kk, n in self._led.items() if n != 0}
        for (r, k), n in led.items():
            px = ltp(r, k); val += n * px * self.unit if px == px else 0.0
        mtm = self._cash + val; self._mtm[m] = mtm
        if not (self.cfg.window_start - 16 <= m <= self.cfg.window_end): return
        peak = max((v for mm, v in self._mtm.items() if mm <= m - 1), default=None); prev15 = self._straddle.get(m - 15)
        st15 = (st / prev15 - 1.0) if (st == st and prev15 is not None and prev15 == prev15 and prev15 > 0) else None
        cl = {n: self._close_of(n, m) for n in ("FUT", "FEED", "OPT")}; cl5 = {n: self._close_of(n, m - 5) for n in ("FUT", "FEED", "OPT")}; mv = {n: (cl[n] - cl5[n]) if cl[n] is not None and cl5[n] is not None else None for n in cl}
        chain = {}
        if k0 is not None:
            for kk in strikes[np.abs(strikes - k0) <= 4 * self.step + 1e-9]: chain[str(int(kk))] = [ltp("CE", float(kk)), ltp("PE", float(kk))]
        net_short = {r: -sum(n for (rr, k), n in led.items() if rr == r and n < 0) for r in ("CE", "PE")}; snap = {kk: n for kk, n in s["positions"].items() if n != 0}; side = {}
        for r, o in (("CE", "PE"), ("PE", "CE")):
            mvs = None if mv["FUT"] is None else (-mv["FUT"] if r == "CE" else mv["FUT"]) / self.step
            side[r] = dict(sold_lots=self._sold[r], sold_deficit_oriented=self._sold[o] - self._sold[r], net_short_lots=net_short[r], net_deficit_oriented=net_short[o] - net_short[r], fut_move_5m_steps_oriented=mvs,
                           D_fut=self._held_short_distance(led, r, cl["FUT"]), D_opt=self._held_short_distance(led, r, cl["OPT"]))
        self._w2(dict(kind="state_minute", j_next=m + 1, j_closed=m, ts_close=s["ts"], straddle=st, straddle_15_minutes_earlier=self._straddle.get(m - 15), STR15=st15, atm_strike=k0, index_used_for_atm=F, close=cl, close_5_minutes_earlier=cl5, move_5m_raw=mv,
                      mtm=mtm, ledger_matches_snapshot=(snap == led), premium_collected=self._prem, PP=(mtm / self._prem) if self._prem > 0 else None, GB=(mtm - peak) if peak is not None else None, atm_chain=chain, side=side,
                      seconds_since_last_short_sale=(s["ts"] - self._last_short) if self._last_short is not None else None))
