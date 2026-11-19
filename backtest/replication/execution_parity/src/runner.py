"""Assemble the reconstructed engine (R1/R2 semantics) from modules; helpers to export events."""
import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))      # replication/
from exec_core import EventLoop, ExecutionModel, NM
from components import LadderEntries, LegStop, CycleStop, Flatten
import rules as R
from common import YAHOO
LOT = {'NIFTY': 65, 'SENSEX': 20}; STEP = {'NIFTY': 50, 'SENSEX': 100}


def settle_close_for(und, d0): return YAHOO[und].close.get(pd.Timestamp(d0), np.nan)


def build(c, und, variant='R1', d0_ladder=None, leg_mult=R.LEG_STOP_MULT, reference='own', cycle_limit=R.CYCLE_STOP_RS, wings=True, slip=True, strict=False, convention='FIFO', flatten=True, delay=0):
    exe = ExecutionModel(delay=delay, slip_pct=0.005 if slip else 0.0, slip_min=0.10 if slip else 0.0, strict=strict)
    exits = [LegStop(leg_mult, reference), CycleStop(cycle_limit)] + ([Flatten()] if flatten else [])
    entries = [LadderEntries(d0_ladder=d0_ladder if variant == 'R2' else None, wings=wings, step=STEP[und])]
    return EventLoop(c, LOT[und], exits, entries, exe, strict=strict, convention=convention, settle_close=settle_close_for(und, c['d0']))


def events(loop):
    rows = []
    for f in loop.fills:
        it = f.intent; rows.append(dict(d=it.day, j=it.j, right=it.right, strike=int(loop.state.strikes[it.si]), side=it.side, role=it.role, tag=it.tag, px=f.price, ref=f.ref, module=it.module, rule_id=it.rule_id, evidence=it.evidence))
    return pd.DataFrame(rows)
