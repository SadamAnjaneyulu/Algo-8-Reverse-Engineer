"""Decision modules for the event-driven core. Each carries a rule id and the evidence label it had in the repository when implemented.
Constants are HYPOTHESES (rules.py), never confirmed facts; they are parameters, not hard-coded. Module-generated lots are tracked individually (R1 semantics)."""
import numpy as np
from exec_core import OrderIntent, NM
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))      # replication/
import rules as R


def _open(loop, it):
    f = loop.submit(it)
    if f is None: return None
    return loop.state.open_lot(f)


def _close(loop, lot, d, j, tag, rule, ev):
    it = OrderIntent(module=tag, rule_id=rule, evidence=ev, day=d, j=j, right=lot['right'], si=lot['si'], side=-lot['side'], role=lot['role'], tag=tag)
    f = loop.submit(it)
    if f is not None: loop.state.close_lot(lot, f)


class LadderEntries:
    """R-LAD-D1 (STRONGLY_SUPPORTED as modal tendency; deterministic ladder FALSIFIED by TP-03). Scheduled windows at 09:16 + 15 k min; n lots per leg; strike = nearest step to the previous completed index close; wing per body lot."""
    rule_id, evidence = 'B-03/B-05/B-06', 'HYPOTHESIS'
    def __init__(self, ladder=None, d0_ladder=None, wings=True, wing_ratio=R.WING_RATIO, step=50, strikes=None):
        self.ladder = list(R.LADDER_D1 if ladder is None else ladder); self.d0_ladder = d0_ladder; self.wings = wings; self.wing_ratio = wing_ratio; self.step = step

    def on_minute(self, loop, d, j):
        v = loop.view; strikes = loop.state.strikes; n_ce = n_pe = 0
        if d == 0 and j >= R.SLOT0 and (j - R.SLOT0) % 15 == 0 and (j - R.SLOT0) // 15 < len(self.ladder): n_ce = n_pe = self.ladder[(j - R.SLOT0) // 15]
        elif d == 1 and self.d0_ladder is not None and j >= R.SLOT0 and (j - R.SLOT0) % 15 == 0 and (j - R.SLOT0) // 15 < len(self.d0_ladder) and j < R.FLATTEN_MIN - 15: n_ce, n_pe = self.d0_ladder[(j - R.SLOT0) // 15]
        for r, n in (('CE', n_ce), ('PE', n_pe)):
            for _ in range(n):
                S = v.spot_prev(d, j)                                           # previous COMPLETED minute close (R1 also used spot[d][0] at j = 0, unreachable because SLOT0 = 1)
                if S != S: continue
                si = R.nearest_strike(strikes, S, self.step)
                bit = OrderIntent(module='ladder', rule_id=self.rule_id, evidence=self.evidence, day=d, j=j, right=r, si=si, side=-1, role='body', tag='ENTRY', inputs=dict(spot_prev=S))
                body = _open(loop, bit); bp = v.prev_close(d, r, si, j)
                if self.wings and body is not None:
                    wi = R.wing_strike_index(strikes, r, si, bp, lambda i: v.prev_close(d, r, i, j))
                    if wi is not None: _open(loop, OrderIntent(module='wing', rule_id='D-02', evidence='HYPOTHESIS', day=d, j=j, right=r, si=wi, side=1, role='wing', tag='ENTRY', pair=body, inputs=dict(body_px=bp)))


class LegStop:
    """H-LEG: close a body lot when LTP(previous completed close) >= mult x reference; exempt entry <= exempt. reference: 'own' entry | 'cheapest' open entry of the same contract. Wing closes with the body (R1 coupling = U3 scenario)."""
    rule_id, evidence = 'C-04', 'HYPOTHESIS'
    def __init__(self, mult=R.LEG_STOP_MULT, reference='own', exempt=R.LEG_STOP_EXEMPT_PX, wing_with_body=True): self.mult, self.reference, self.exempt, self.wing_with_body = mult, reference, exempt, wing_with_body

    def on_minute(self, loop, d, j):
        S = loop.state
        if not S.lots: return
        for L in list(S.lots):
            if L['role'] != 'body' or L not in S.lots: continue
            cur = loop.view.prev_close(d, L['right'], L['si'], j)
            ref = L['entry'] if self.reference == 'own' else min(x['entry'] for x in S.lots if x['role'] == 'body' and x['right'] == L['right'] and x['si'] == L['si'])
            if cur == cur and ref > self.exempt and cur >= self.mult * ref:
                _close(loop, L, d, j, 'LEG_STOP', self.rule_id, self.evidence)
                if self.wing_with_body:
                    for W in [w for w in S.lots if w['pair'] == L['id']]: _close(loop, W, d, j, 'WING_WITH_BODY', 'U3', 'HYPOTHESIS')


class CycleStop:
    """H-CYC: cumulative LTP MTM (cash at reference prices + mark) <= -limit -> liquidate every lot, no further entries. passive_at_stop is moot here (R1 has no passive lots)."""
    rule_id, evidence = 'E-01', 'HYPOTHESIS'
    def __init__(self, limit=R.CYCLE_STOP_RS): self.limit = limit

    def on_minute(self, loop, d, j):
        S = loop.state
        if not S.lots or loop.stopped is not None: return
        tot = S.cash_ref + S.mark(loop.view, d, j)
        if tot <= -self.limit:
            for L in list(S.lots): _close(loop, L, d, j, 'CYCLE_STOP', self.rule_id, self.evidence)
            loop.stopped = (d, j)


class Flatten:
    """H-FLAT: close every open lot at the flatten minute of D0 (R1: 15:14 everywhere; hypothesis says after 2026-08-03 only -> parameter `from_date`)."""
    rule_id, evidence = 'C-10', 'HYPOTHESIS'
    def __init__(self, minute=R.FLATTEN_MIN, d0_date=None, from_date=None): self.minute, self.d0_date, self.from_date = minute, d0_date, from_date

    def on_minute(self, loop, d, j):
        if d != 1 or j != self.minute or not loop.state.lots: return
        if self.from_date is not None and self.d0_date is not None and self.d0_date < self.from_date: return
        for L in list(loop.state.lots): _close(loop, L, d, j, 'FLATTEN', self.rule_id, self.evidence)
