"""Algo 8 decision engine v1: every decision parameter comes from config/algo8_v1_params.json (extracted from the 35 live cycles) and runs on the event-driven core (exec_core).
Entry (D-1 and D0 ladders, ATM strike from the previous completed close, wing per body lot), risk control (per-lot stop, cycle stop with no further entries, date-conditioned flatten) and settlement.
All rules are HYPOTHESES read from the 35 cycles (see params provenance); none is a recovered original rule. Unknown behaviours are NOT modelled (off-schedule entries, Clock-B reductions, lump hedge, 4 % carry SL, 1 % expiry-day rule)."""
import os, sys, json
import numpy as np, pandas as pd
import ref
sys.path.insert(0, ref.REPL)
import rules as R
from common import YAHOO
from bt import account as A
from exec_core import EventLoop, ExecutionModel, OrderIntent, NM
from components import LegStop, _open, _close
PARAMS = json.load(open(f'{ref.EP}/config/algo8_v1_params.json')); LOT26 = ref.LOT; STEP = ref.STEP


class ParamEntries:
    """scheduled per-minute entries from the params table (minutes where the original sold in >= 50 % of cycles). D-1: every scheduled slot. D0: only while the book holds an open body short (ENT-03). Strike = nearest step to the previous completed index close; one wing per body lot."""
    rule_id, evidence = 'B-03/B-05/B-06', 'HYPOTHESIS'
    def __init__(self, params=PARAMS, step=50, d0=True, d1=True, wing_ratio=None, wings=True):
        self.step = step; self.d0, self.d1 = d0, d1; self.wings = wings; self.wing_ratio = wing_ratio or params['wing']['price_ratio_to_body']
        self.tab = {0: params['ladder_d1']['minutes'], 1: params['ladder_d0']['minutes']}

    def on_minute(self, loop, d, j):
        if (d == 0 and not self.d1) or (d == 1 and not self.d0): return
        row = self.tab[d].get(str(j))
        if row is None or (d == 0 and j < 1): return
        if d == 1 and not any(L['role'] == 'body' for L in loop.state.lots): return                     # ENT-03: D0 entries only while the book is active
        v = loop.view; strikes = loop.state.strikes
        for r in ('CE', 'PE'):
            for _ in range(int(row.get(r, {}).get('lots', 0))):
                S = v.spot_prev(d, j)
                if S != S: continue
                si = R.nearest_strike(strikes, S, self.step)
                body = _open(loop, OrderIntent(module='ladder', rule_id=self.rule_id, evidence=self.evidence, day=d, j=j, right=r, si=si, side=-1, role='body', tag='ENTRY', inputs=dict(spot_prev=S)))
                if self.wings and body is not None:
                    bp = v.prev_close(d, r, si, j); wi = R.wing_strike_index(strikes, r, si, bp, lambda i: v.prev_close(d, r, i, j), ratio=self.wing_ratio)
                    if wi is not None: _open(loop, OrderIntent(module='wing', rule_id='D-02', evidence='HYPOTHESIS', day=d, j=j, right=r, si=wi, side=1, role='wing', tag='ENTRY', pair=body, inputs=dict(body_px=bp)))


class CycleStopV1:
    """cumulative LTP MTM (cash at reference prices + mark) <= -limit -> liquidate every lot, stop all entries. mark: 'prev' = previous completed close (causal); 'open' = open of the decision minute (sensitivity)."""
    rule_id, evidence = 'E-01', 'HYPOTHESIS'
    def __init__(self, limit=144000.0, mark='prev'): self.limit, self.mark = limit, mark
    def on_minute(self, loop, d, j):
        S = loop.state
        if not S.lots or loop.stopped is not None: return
        if self.mark == 'prev': m = S.mark(loop.view, d, j)
        else: m = sum((1 if L['side'] == 1 else -1) * S.units * (loop.view.open_px(d, L['right'], L['si'], j) or loop.view.prev_close(d, L['right'], L['si'], j)) for L in S.lots)
        if S.cash_ref + m <= -self.limit:
            for L in list(S.lots): _close(loop, L, d, j, 'CYCLE_STOP', self.rule_id, self.evidence)
            loop.stopped = (d, j)


class FlattenV1:
    """flatten every lot at the flatten minute of D0; the minute depends on the date (pre/post cut-over)."""
    rule_id, evidence = 'C-10', 'HYPOTHESIS'
    def __init__(self, params=PARAMS): self.cut = params['flatten']['cutover_date']; self.pre = params['flatten']['minute_pre_cutover']; self.post = params['flatten']['minute_post_cutover']
    def on_minute(self, loop, d, j):
        if d != 1 or not loop.state.lots: return
        if j == (self.pre if loop.c['d0'] < self.cut else self.post):
            for L in list(loop.state.lots): _close(loop, L, d, j, 'FLATTEN', self.rule_id, self.evidence)


def build(c, und, units=None, leg_mult=1.60, reference='own', cycle_limit=144000.0, stop_scaling='lot', cycle_mark='prev', slip_mult=1.0, d0_entries=True, wings=True, leg_stop=True, cycle_stop=True, flatten=True, delay=0, strict=False):
    exe = ExecutionModel(delay=delay, slip_pct=0.005 * slip_mult, slip_min=0.10 * slip_mult, strict=strict); u = units or LOT26[und]
    limit = cycle_limit * (u / LOT26[und]) if stop_scaling == 'lot' else cycle_limit                      # cycle_limit is stated at the 2026 lot size (NIFTY 65 / SENSEX 20) and scales linearly with the session lot size; 'fixed' keeps it in rupees
    exits = ([LegStop(leg_mult, reference)] if leg_stop else []) + ([CycleStopV1(limit, cycle_mark)] if cycle_stop else []) + ([FlattenV1()] if flatten else [])
    return EventLoop(c, u, exits, [ParamEntries(step=STEP[und], d0=d0_entries, wings=wings)], exe, strict=strict, settle_close=YAHOO[und].close.get(pd.Timestamp(c['d0']), np.nan))


def events(loop):
    rows = []
    for f in loop.fills:
        it = f.intent; rows.append(dict(d=it.day, j=it.j, right=it.right, strike=int(loop.state.strikes[it.si]), side=it.side, role=it.role, tag=it.tag, px=f.price, ref=f.ref, rule_id=it.rule_id, evidence=it.evidence))
    return pd.DataFrame(rows)


def result(loop, c, und, cost_mult=1.0):
    u = loop.state.units; costs = 0.0
    for f in loop.fills:
        it = f.intent; day = c['d1'] if it.day == 0 else c['d0']; costs += A.order_costs(und, day, it.side, u * f.price, cost_mult)
    settle = loop.settle(); gross = loop.state.cash_ref + settle; net = loop.state.cash + settle - costs; ev = events(loop)
    return dict(gross=gross, net=net, costs=costs, slippage=gross - (loop.state.cash + settle), n_orders=len(ev), leg_stops=int((ev.tag == 'LEG_STOP').sum()) if len(ev) else 0, cycle_stop=loop.stopped is not None, stop_day=None if loop.stopped is None else loop.stopped[0], stop_j=None if loop.stopped is None else loop.stopped[1],
                flatten_orders=int((ev.tag == 'FLATTEN').sum()) if len(ev) else 0, open_at_end=len(loop.state.lots), no_market=len(loop.no_market), body_entries_d1=int(((ev.role == 'body') & (ev.tag == 'ENTRY') & (ev.d == 0)).sum()) if len(ev) else 0, body_entries_d0=int(((ev.role == 'body') & (ev.tag == 'ENTRY') & (ev.d == 1)).sum()) if len(ev) else 0)
