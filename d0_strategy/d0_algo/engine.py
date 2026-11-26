"""Standalone D0 engine (Gate 5a): a faithful, clean port of the research simulator bl_d0_fr.py::sim, same per-minute rule order, with explicit state, validation, per-rule switches and
position accounting. Decisions use only the market arrays, the configuration and the engine's own state: **real D0 orders are never inputs** (the opening state is an explicit input:
the real carried book in teacher-forced mode T, the D-1 simulator's carry in mode F).
Rule order inside a minute (as the reference): cycle stop, 15:14 clearance, body buy-backs (stop / take-profit on the minute's high / low), sells (timetable waves, D-1 breakout pairs, solo ladder,
counter-sells), opening wings (minute 0), hedge controller. Time resolution is one minute (the reference's); events carry the minute, no seconds."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np
from .config import D0Config

OPEN_S = 33300

@dataclass
class D0Market:
    """one cycle's expiry-day market data: spot bars (375 minutes) and the option chain bars"""
    K: np.ndarray; step: float; unit: float; spot_open: np.ndarray; spot_high: np.ndarray; spot_low: np.ndarray; spot_close: np.ndarray
    opt: Dict[Tuple[str, str], np.ndarray]                                # (cp, 'open'|'high'|'low'|'close') -> array [len(K), 375]

@dataclass
class D0Opening:
    """opening state: carried body short lots [[cp, strike, entry_price]], other-module longs and shorts {(module, cp, strike): lots}, cash (rupees)"""
    lots: List[list]; longs: Dict[Tuple[str, str, int], int]; oshort: Dict[Tuple[str, str, int], int]; cash: float

@dataclass
class Event:
    cls: str; cp: str; j: int; strike: int; lots: int
    parts: Optional[List[Tuple[str, int]]] = None                           # for 'stop': (kind, lots) components kind in {'body_short','long','oshort'}
    module: str = ''; role: str = ''; side: str = ''                       # order-log vocabulary: module num/h_/v_/s_, role open_short/cover_short/open_long/close_long, side buy/sell
    px: float = float('nan')                                                # reference fill price recorded for P&L accounting only (performance backtest); never read by any rule, not part of as_tuple

    def as_tuple(self): return (self.cls, self.cp, self.j, int(self.strike), int(self.lots))

class D0Engine:
    def __init__(self, cfg: D0Config, market: D0Market, opening: D0Opening):
        self.cfg, self.m = cfg, market; self.K = np.asarray(market.K, float); self.ki = {int(k): x for x, k in enumerate(self.K)}
        self.lots = [list(l) for l in opening.lots]; self.longs = dict(opening.longs); self.oshort = dict(opening.oshort); self.cash = float(opening.cash)
        self.events: List[Event] = []; self.rejected: List[Tuple[int, str, str, int]] = []; self._decisions: Dict[int, int] = {}; self.violations: List[Tuple[int, str, str, int]] = []; self.stopped = False; self.cleared = False; self.minute = -1; self.max_short_seen = 0      # monitoring only (peak short lots per right after an accepted sell)
        self._validate_inputs()
        self.fires = self._breakout_fires(); self.wave_by_minute: Dict[int, List[int]] = {}
        for t, n in cfg.waves: self.wave_by_minute.setdefault(int((t - OPEN_S) // 60), []).append(int(n))
        self.ref = {'CE': None, 'PE': None}; self.acc = {'CE': 0.0, 'PE': 0.0}

    # ------------------------------------------------------------------ helpers
    def _validate_inputs(self):
        m = self.m
        for a in (m.spot_open, m.spot_high, m.spot_low, m.spot_close): assert len(a) >= self.cfg.last_minute + 1, 'spot bars must cover the session'
        for cp, k, e in self.lots: assert cp in ('CE', 'PE') and int(k) in self.ki, f'carried lot on a contract outside the chain: {cp} {k}'
        assert all(n > 0 for n in self.longs.values()) and all(n > 0 for n in self.oshort.values()), 'opening positions must be positive lots'

    def px(self, cp: str, k, j: int, f: str = 'close') -> float:
        x = self.ki.get(int(k)); v = self.m.opt[(cp, f)][x, min(max(j, 0), self.cfg.last_minute)] if x is not None else np.nan; return float(v) if v == v else np.nan

    def atm(self, x: float) -> float: return float(self.K[np.argmin(np.abs(self.K - x))])

    def _breakout_fires(self):
        h, l = self.m.spot_high, self.m.spot_low; out = []; done = set(); c = self.cfg
        for j in range(c.breakout_start_min, c.breakout_end_min + 1):
            clock = OPEN_S + 60 * j; b0 = (clock // 1800) * 1800; a = int(np.ceil((b0 - 3600 - OPEN_S) / 60)); e = int(np.ceil((b0 - OPEN_S) / 60))
            if e - max(a, 0) < 2: continue
            H, L = h[max(a, 0):e].max(), l[max(a, 0):e].min()
            for s, fl in ((1, h[j] > H), (-1, l[j] < L)):
                if fl and (b0, s) not in done: out.append((j, s)); done.add((b0, s))
        d: Dict[int, List[int]] = {}
        for j, s in out: d.setdefault(j, []).append(s)
        return d

    def _rec(self, cls, cp, j, k, n, **kw):
        n = int(n); assert n > 0, 'non-positive quantity'
        if cls == 'body_sell': self._decisions[j] = self._decisions.get(j, 0) + 1                        # only risk-adding sells count toward the minute cap
        self.events.append(Event(cls, cp, j, int(k), n, **kw))

    def _shorts_on(self, cp: str) -> int: return sum(1 for L in self.lots if L[0] == cp) + sum(n for (md, c2, k), n in self.oshort.items() if c2 == cp)

    def _risk_blocks(self, cp: str, n: int, j: int) -> Optional[str]:
        """risk guard for sells (they add short risk): net short lots per right and sell decisions per minute. Returns the reason if the limit would be exceeded; in 'monitor' mode the breach is recorded and the sell proceeds."""
        c = self.cfg; why = None
        if self._shorts_on(cp) + n > c.max_short_lots_per_right: why = 'short lot limit'
        elif self._decisions.get(j, 0) >= c.max_sell_decisions_per_minute: why = 'too many sell decisions this minute'
        if why is None: self.max_short_seen = max(self.max_short_seen, self._shorts_on(cp) + n)
        if why is None or c.risk_mode == 'monitor':
            if why is not None: self.violations.append((j, cp, why, int(n)))
            return None
        return why

    def mtm(self, j: int) -> float:
        v = self.cash; u = self.m.unit
        for cp, k, e in self.lots:
            p = self.px(cp, k, j)
            if p == p: v -= p * u
        for (md, cp, k), n in self.longs.items():
            p = self.px(cp, k, j)
            if p == p: v += n * p * u
        for (md, cp, k), n in self.oshort.items():
            p = self.px(cp, k, j)
            if p == p: v -= n * p * u
        return v

    # ------------------------------------------------------------------ run
    def run(self) -> List[Event]:
        c = self.cfg; m = self.m; h, l, cl = m.spot_high, m.spot_low, m.spot_close; st = m.step; u = m.unit; stp = c.ladder_step * st
        for j in range(0, c.last_minute + 1):
            self.minute = j
            if self.stopped: break
            if c.enable_cycle_stop and self.mtm(j) <= -c.cycle_stop_rupees: self._cycle_stop(j); break
            jp = max(j - 1, 0); c0 = cl[jp] if j > 0 else m.spot_open[0]
            if c.enable_clearance and c.clearance_hazards is not None and c.clearance_minute - (len(c.clearance_hazards) - 1) <= j < c.clearance_minute: self._clearance_partial(j, c.clearance_hazards[j - (c.clearance_minute - (len(c.clearance_hazards) - 1))])
            if c.enable_clearance and j == c.clearance_minute: self._clearance(j); break
            nbb = self._buybacks(j) if c.enable_buyback else {'CE': 0, 'PE': 0}
            sells = self._sells(j, c0, stp, nbb)
            for cp, k, n, t in sells:
                if int(k) not in self.ki: continue
                why = self._risk_blocks(cp, n, j)
                if why: self.rejected.append((j, cp, why, int(n))); continue
                e = self.px(cp, k, jp); e = e if e == e else self.px(cp, k, j)
                self._rec('body_sell', cp, j, k, n, module='num', role='open_short', side='sell', px=(e if e == e else self.px(cp, k, j))); self.lots += [[cp, k, e]] * n; self.cash += (e if e == e else 0) * n * u
            if c.enable_opening_wings and j == 0 and c.opening_wing_lots: self._opening_wings(c0)
            if c.opening_long_clock and j == c.opening_long_minute: self._opening_longs_clock(j, c0)
            if c.enable_hedge: self._hedge(j, jp, c0)
        return self.events

    def _cycle_stop(self, j):
        agg: Dict[Tuple[str, int], int] = {}; parts: Dict[Tuple[str, int], list] = {}
        for cp, k, e in self.lots: agg[(cp, k)] = agg.get((cp, k), 0) + 1; parts.setdefault((cp, k), []).append(('body_short', 1))
        for (md, cp, k), n in list(self.longs.items()) + list(self.oshort.items()): agg[(cp, k)] = agg.get((cp, k), 0) + n
        for (md, cp, k), n in self.longs.items(): parts.setdefault((cp, k), []).append(('long', n))
        for (md, cp, k), n in self.oshort.items(): parts.setdefault((cp, k), []).append(('oshort', n))
        for (cp, k), n in agg.items(): self._rec('stop', cp, j, k, n, parts=parts[(cp, k)], module='s_', role='liquidate', side='mixed', px=self.px(cp, k, j))
        self.stopped = True

    def _clearance_partial(self, j, h):
        """CH2 (default off): buy back round(h x open lots) of every contract at this minute (shorts only; longs are sold at the final sweep minute)"""
        if h <= 0: return
        byk: Dict[Tuple[str, int], List[int]] = {}
        for n, (cp, k, e) in enumerate(self.lots): byk.setdefault((cp, k), []).append(n)
        drop = set()
        for (cp, k), idx in sorted(byk.items()):
            take = int(round(h * len(idx)))
            if take <= 0: continue
            self._rec('body_buyback', cp, j, k, take, module='num', role='cover_short', side='buy', px=self.px(cp, k, j))
            for n in idx[:take]: drop.add(n)
        self.lots = [L for n, L in enumerate(self.lots) if n not in drop]

    def _clearance(self, j):
        agg: Dict[Tuple[str, int], int] = {}
        for cp, k, e in self.lots: agg[(cp, k)] = agg.get((cp, k), 0) + 1
        for (cp, k), n in agg.items(): self._rec('body_buyback', cp, j, k, n, module='num', role='cover_short', side='buy', px=self.px(cp, k, j))
        for (md, cp, k), n in self.longs.items():
            if md == 'num': self._rec('body_long', cp, j, k, n, module='num', role='close_long', side='sell', px=self.px(cp, k, j))
            else: self._rec('wing_sell', cp, j, k, n, module=md, role='close_long', side='sell', px=self.px(cp, k, j))
        self.lots = []; self.longs = {}; self.cleared = True                # as the reference: other-module shorts (oshort) are not cleared

    def _buybacks(self, j):
        c = self.cfg; u = self.m.unit; nbb = {'CE': 0, 'PE': 0}; keep = []
        if j >= 1:
            for L in self.lots:
                cp, k, e = L; ph = self.px(cp, k, j, 'high'); pl = self.px(cp, k, j, 'low')
                if e > 0 and ((ph == ph and ph >= c.buyback_theta * e) or (c.buyback_tp and pl == pl and pl <= c.buyback_tp * e)):
                    po = self.px(cp, k, j, 'open'); fp = (max(po, c.buyback_theta * e) if po == po else c.buyback_theta * e) if (ph == ph and ph >= c.buyback_theta * e) else (min(po, c.buyback_tp * e) if po == po else c.buyback_tp * e)      # touch price (gap-aware), accounting only
                    self._rec('body_buyback', cp, j, k, 1, module='num', role='cover_short', side='buy', px=fp); nbb[cp] += 1; p = self.px(cp, k, j); self.cash -= (p if p == p else e) * u
                else: keep.append(L)
            self.lots = keep
        return nbb

    def _sells(self, j, c0, stp, nbb):
        c = self.cfg; st = self.m.step; h, l = self.m.spot_high, self.m.spot_low; sells = []
        if c.enable_timetable:
            for n in self.wave_by_minute.get(j, []): k = self.atm(c0); sells += [('CE', k, n, 'pair'), ('PE', k, n, 'pair')]
        if c.enable_breakout and c.breakout_start_min <= j <= c.breakout_end_min:
            for s in self.fires.get(j, []): k = self.atm(c0) + s * st; sells += [('CE', k, 1, 'pair'), ('PE', k, 1, 'pair')]
        if c.enable_solo:
            for cp in ('CE', 'PE'):
                if self.ref[cp] is None or j < 1: continue
                if c.ladder_gate_min and not ((l[j] < l[max(j - c.ladder_gate_min, 0):j].min()) if cp == 'CE' else (h[j] > h[max(j - c.ladder_gate_min, 0):j].max())): continue
                dv = (self.ref[cp] - l[j]) if cp == 'CE' else (h[j] - self.ref[cp])
                if dv > stp:
                    n = int(dv // stp); sells.append((cp, self.atm(c0), min(n, c.solo_lot_cap) if c.ladder_mult else 1, 'solo')); self.ref[cp] = self.ref[cp] - n * stp if cp == 'CE' else self.ref[cp] + n * stp
        if any(t == 'pair' for *_, t in sells): self.ref = {'CE': c0, 'PE': c0}              # ladder reference reset after this minute's ladder check
        if c.enable_counter:
            for cp in ('CE', 'PE'):
                o = 'PE' if cp == 'CE' else 'CE'; self.acc[cp] += c.counter_ratio * nbb[o]; n = int(self.acc[cp]); self.acc[cp] -= n
                if n: sells.append((cp, self.atm(c0), n, 'solo'))
        return sells

    def _opening_wings(self, c0):
        c = self.cfg; st = self.m.step; u = self.m.unit
        for cp, nn in (('CE', c.opening_wing_lots // 2), ('PE', c.opening_wing_lots - c.opening_wing_lots // 2)):
            k = self.atm(c0 + (1 if cp == 'CE' else -1) * c.opening_wing_offset_steps * st); self._rec('body_long', cp, 0, k, nn, module='num', role='open_long', side='buy', px=self.px(cp, k, 0))
            self.longs[('num', cp, int(k))] = self.longs.get(('num', cp, int(k)), 0) + nn; p = self.px(cp, k, 0); self.cash -= (p if p == p else 0) * nn * u

    def _opening_longs_clock(self, j, c0):
        """X3 (default off): one clock event at the opening-long minute; per right, buy as many longs as lots were sold on that right in this minute (decoded count rule, D0_OPEN_ROLL); strike rule is the opening-wing rule (fixed offset), the strike of these longs is unresolved in the evidence."""
        c = self.cfg; st = self.m.step; u = self.m.unit
        for cp in ('CE', 'PE'):
            n = sum(e.lots for e in self.events if e.cls == 'body_sell' and e.j == j and e.cp == cp)
            if n <= 0: continue
            k = self.atm(c0 + (1 if cp == 'CE' else -1) * c.opening_wing_offset_steps * st)
            self._rec('body_long', cp, j, k, n, module='num', role='open_long', side='buy', px=self.px(cp, k, j)); self.longs[('num', cp, int(k))] = self.longs.get(('num', cp, int(k)), 0) + n
            p = self.px(cp, k, j); self.cash -= (p if p == p else 0) * n * u

    def _hedge(self, j, jp, c0):
        c = self.cfg; u = self.m.unit; K = self.K
        for cp in ('CE', 'PE'):
            S_ = sum(1 for L in self.lots if L[0] == cp) + sum(n for (md, c2, k), n in self.oshort.items() if c2 == cp); L_ = sum(n for (md, c2, k), n in self.longs.items() if c2 == cp); g = S_ - L_
            if g > 0:
                a = self.px(cp, self.atm(c0), jp); pr = self.m.opt[(cp, 'close')][:, jp]; otm = (K - c0) * (1 if cp == 'CE' else -1) > 0; ok = otm & np.isfinite(pr)
                if a == a and ok.any():
                    k = K[ok][np.argmin(np.abs(pr[ok] - c.wing_premium_frac * a))]; self._rec('wing_buy', cp, j, k, g, module='h_', role='open_long', side='buy', px=self.px(cp, k, j)); self.longs[('h_', cp, int(k))] = self.longs.get(('h_', cp, int(k)), 0) + g
                    p = self.px(cp, k, j); self.cash -= (p if p == p else 0) * g * u
            elif g < 0:
                need = -g; cand = sorted([(md, c2, k) for (md, c2, k), n in self.longs.items() if c2 == cp and md in ('h_', 'v_') and n > 0], key=lambda x: -((x[2] - c0) * (1 if cp == 'CE' else -1)))
                for key in cand:
                    if need <= 0: break
                    x = min(need, self.longs[key]); self.longs[key] -= x; need -= x; self._rec('wing_sell', cp, j, key[2], x, module=key[0], role='close_long', side='sell', px=self.px(cp, key[2], j))
                    p = self.px(cp, key[2], j); self.cash += (p if p == p else 0) * x * u
                    if self.longs[key] == 0: del self.longs[key]

    # ------------------------------------------------------------------ outputs and accounting
    def events_frame(self):
        import pandas as pd
        return pd.DataFrame([e.as_tuple() for e in self.events], columns=['cls', 'cp', 'j', 'strike', 'lots'])

    def position(self) -> Dict[Tuple[str, int], int]:
        """net lots per contract (long positive) from the engine's own state"""
        net: Dict[Tuple[str, int], int] = {}
        for cp, k, e in self.lots: net[(cp, int(k))] = net.get((cp, int(k)), 0) - 1
        for (md, cp, k), n in self.longs.items(): net[(cp, int(k))] = net.get((cp, int(k)), 0) + n
        for (md, cp, k), n in self.oshort.items(): net[(cp, int(k))] = net.get((cp, int(k)), 0) - n
        return {k: v for k, v in net.items() if v}

    def reconcile(self, opening: D0Opening) -> bool:
        """opening position plus the signed lots of every recorded event equals the engine's end position (contract identities and quantities)"""
        net: Dict[Tuple[str, int], int] = {}
        for cp, k, e in opening.lots: net[(cp, int(k))] = net.get((cp, int(k)), 0) - 1
        for (md, cp, k), n in opening.longs.items(): net[(cp, int(k))] = net.get((cp, int(k)), 0) + n
        for (md, cp, k), n in opening.oshort.items(): net[(cp, int(k))] = net.get((cp, int(k)), 0) - n
        for e in self.events:
            if e.side == 'buy': net[(e.cp, e.strike)] = net.get((e.cp, e.strike), 0) + e.lots
            elif e.side == 'sell': net[(e.cp, e.strike)] = net.get((e.cp, e.strike), 0) - e.lots
            elif e.side == 'mixed':                                          # cycle stop: closes shorts (buy) and longs (sell) on the contract
                for kind, n in e.parts:
                    net[(e.cp, e.strike)] = net.get((e.cp, e.strike), 0) + (n if kind in ('body_short', 'oshort') else -n)
        net = {k: v for k, v in net.items() if v}
        if self.stopped: return net == {}                                  # a cycle stop closes every contract (the engine state is left as the reference leaves it)
        return net == self.position()
