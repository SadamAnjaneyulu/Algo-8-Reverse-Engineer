"""Event-driven execution core for the parity study. Separates decision logic (modules) from execution (ExecutionModel), position accounting (PortfolioState)
and observation (MarketView, which can only see COMPLETED bars). The loop reproduces the semantics of `replication/sim.py` (R1/R2) so the refactor can be
tested for event-by-event equality (tests/test_engine_equivalence.py).

Concepts
  MarketView      causal access: prev_close(day, right, si, j) = last close completed BEFORE minute j; spot_prev; open price of minute j (fill reference only)
  OrderIntent     module, rule_id, evidence label, instrument, side, qty, decision minute, decision inputs
  Fill            intent + price (+ simulated slippage), minute and second
  PositionEvent   change of a unit lot / contract position caused by a fill
  PortfolioState  unit lots (role, right, strike index, entry, pair) + contract net lots + cash; allocation convention for externally injected fills
Modes: simulated (modules generate intents) | teacher-forced (injected original orders at their actual second and price) | accounting replay (all original fills, no modules).
"""
from dataclasses import dataclass, field
import numpy as np

NM = 375; CONVENTIONS = ('FIFO', 'LIFO', 'LOW_ENTRY_FIRST', 'HIGH_ENTRY_FIRST')


@dataclass
class OrderIntent:
    module: str; rule_id: str; evidence: str; day: int; j: int; right: str; si: int; side: int; role: str; tag: str
    qty: int = 1; inputs: dict = field(default_factory=dict); pair: int = None; teacher_forced: bool = False; price: float = None; sec: int = None


@dataclass
class Fill:
    intent: OrderIntent; price: float; ref: float; no_market: bool = False


@dataclass
class PositionEvent:
    kind: str; lot_id: int; day: int; j: int; right: str; si: int; side: int; role: str; tag: str; price: float


class MarketView:
    """Causal view over one cycle's minute arrays c (replication/data.py layout). Only information completed before the decision minute is exposed."""
    def __init__(self, c, strict=False):
        self.c = c; self.strikes = c['strikes']; self.strict = strict
        self._px = {}; self._vol = {}
        for d in (0, 1):
            for r in ('CE', 'PE'):
                a = np.array(c[(d, r, 'close')], float)
                for j in range(1, a.shape[1]):
                    m = np.isnan(a[:, j]); a[m, j] = a[m, j - 1]
                self._px[(d, r)] = a; self._vol[(d, r)] = c[(d, r, 'volume')]

    def prev_close(self, d, r, si, j):
        if j > 0: return self._px[(d, r)][si, j - 1]
        return self._px[(0, r)][si, NM - 1] if d == 1 else np.nan                       # D-1 minute 0 has no completed bar; D0 minute 0 reads the last D-1 bar

    def spot_prev(self, d, j):
        s = self.c[(d, 'spot')]
        if j > 0: return s[j - 1]
        return self.c[(0, 'spot')][NM - 1] if d == 1 else np.nan

    def open_px(self, d, r, si, j):
        o = self.c[(d, r, 'open')][si, j]
        if o == o: return o
        return None if self.strict else self.prev_close(d, r, si, j)                    # sim_compat: fall back to the last completed close; strict: NO_MARKET

    def executable(self, d, r, si, j):
        v = self._vol[(d, r)][si, j]; return bool(v == v and v > 0)


class ExecutionModel:
    """fill = open of the decision minute (optionally +delay minutes) with optional proportional/min slippage against the order; strict -> NO_MARKET when no bar."""
    def __init__(self, delay=0, slip_pct=0.0, slip_min=0.0, strict=False): self.delay, self.slip_pct, self.slip_min, self.strict = delay, slip_pct, slip_min, strict

    def fill(self, view, it):
        if it.teacher_forced: return Fill(it, it.price, it.price)
        j = min(it.j + self.delay, NM - 1); d = it.day
        if self.strict and not view.executable(d, it.right, it.si, j): return Fill(it, np.nan, np.nan, True)
        o = view.open_px(d, it.right, it.si, j)
        if o is None or not (o == o): return Fill(it, np.nan, np.nan, True)
        s = max(self.slip_min, self.slip_pct * o); return Fill(it, o + it.side * s, o)


class PortfolioState:
    """unit lots + contract-level net + cash (gross, at fill price). side: +1 buy / -1 sell. Body shorts are role 'body' (sell opens), wings role 'wing' (buy opens)."""
    def __init__(self, strikes, units, convention='FIFO'):
        self.strikes, self.units, self.convention = strikes, units, convention; self.lots = []; self.nid = 0; self.cash = 0.0; self.net = {}; self.cash_ref = 0.0; self.events = []; self.realized = 0.0

    def open_lot(self, f):
        it = f.intent; self.nid += 1; self.lots.append(dict(id=self.nid, role=it.role, right=it.right, si=it.si, entry=f.price, pair=it.pair, day=it.day, j=it.j, side=it.side, ext=it.teacher_forced)); self._cash(f); return self.nid

    def close_lot(self, lot, f):
        self.lots.remove(lot); self._cash(f)

    def _cash(self, f):
        it = f.intent; self.cash += -it.side * self.units * f.price; self.cash_ref += -it.side * self.units * f.ref
        k = (it.right, it.si); self.net[k] = self.net.get(k, 0) + it.side

    def apply_external(self, f):
        """injected (teacher-forced) fill: closes opposite lots of the same contract by the allocation convention, opens the remainder"""
        it = f.intent; cand = [l for l in self.lots if l['right'] == it.right and l['si'] == it.si and l['side'] == -it.side]
        key = {'FIFO': lambda l: (l['day'], l['j'], l['id']), 'LIFO': lambda l: (-l['day'], -l['j'], -l['id']), 'LOW_ENTRY_FIRST': lambda l: (l['entry'], l['id']), 'HIGH_ENTRY_FIRST': lambda l: (-l['entry'], l['id'])}[self.convention]
        cand.sort(key=key); k = (it.right, it.si); self.net[k] = self.net.get(k, 0) + it.side
        self.cash += -it.side * self.units * f.price; self.cash_ref += -it.side * self.units * f.ref
        if cand:
            L0 = cand.pop(0); self.lots.remove(L0); self.realized += (L0['side'] * (f.price - L0['entry'])) * self.units; return 'CLOSE'
        self.nid += 1; self.lots.append(dict(id=self.nid, role=it.role, right=it.right, si=it.si, entry=f.price, pair=None, day=it.day, j=it.j, side=it.side, ext=True)); return 'OPEN'

    def mark(self, view, d, j):
        s = 0.0
        for L in self.lots:
            m = view.prev_close(d, L['right'], L['si'], j); s += (1 if L['side'] == 1 else -1) * self.units * m
        return s

    def net_array(self):
        return dict(self.net)


class EventLoop:
    """minute loop. Per minute: modules evaluated in a fixed, configurable ORDER (default exits first, then entries); each module sees only the MarketView and the state."""
    def __init__(self, c, units, exit_modules, entry_modules, execution, strict=False, convention='FIFO', settle_close=None, injected=None):
        self.c = c; self.view = MarketView(c, strict); self.state = PortfolioState(c['strikes'], units, convention); self.exec = execution
        self.exit_modules, self.entry_modules = exit_modules, entry_modules; self.settle_close = settle_close; self.injected = injected or {}; self.stopped = None
        self.fills = []; self.pos_events = []; self.no_market = []

    def submit(self, it):
        f = self.exec.fill(self.view, it)
        if f.no_market: self.no_market.append(it); return None
        self.fills.append(f); return f

    def run(self):
        S = self.state
        for d in (0, 1):
            for j in range(NM):
                if self.stopped is not None and d == 1 and j > self.stopped[1] and not S.lots: break
                for it in self.injected.get((d, j), []):                         # teacher-forced original orders (their own second/price), before module decisions of this minute
                    f = self.submit(it)
                    if f is not None: S.apply_external(f)
                for m in self.exit_modules: m.on_minute(self, d, j)
                if self.stopped is None:
                    for m in self.entry_modules: m.on_minute(self, d, j)
        return self

    def settle(self):
        """cash settle residual lots at settle_close (proxy; recorded)"""
        S0 = self.settle_close; v = 0.0
        for L in self.state.lots:
            K = self.state.strikes[L['si']]; iv = max(S0 - K, 0) if L['right'] == 'CE' else max(K - S0, 0); v += (1 if L['side'] == 1 else -1) * self.state.units * iv
        return v

    def gross_pnl(self): return self.state.cash_ref + self.settle()
