"""Shared helpers for the D0 reconstruction. HOLDOUT GUARD: event-level data of the holdout cycles (D0 >= 2026-09-23) can only be loaded after results/FREEZE.json exists (written by freeze.py). Before that, load_events(discovery_only=True) is the only supported path."""
import os, sys, json
DHERE = os.path.dirname(os.path.abspath(__file__)); REPL = os.path.dirname(DHERE); sys.path.insert(0, REPL)
from common import *                                   # replication/common.py (RES there is replication/results; override below)
RRES = os.path.join(REPL, 'results'); RES = os.path.join(DHERE, 'results'); REP = os.path.join(DHERE, 'reports'); FIG = os.path.join(REP, 'figures')
for p in (RES, REP, FIG): os.makedirs(p, exist_ok=True)
HOLDOUT_START = pd.Timestamp('2026-09-23')             # = TEST boundary of the earlier exit-engine research (DEV <= 20 Aug, VAL <= 22 Sep, TEST >= 23 Sep)
LOT = {'NIFTY': 65, 'SENSEX': 20}
FROZEN = os.path.exists(os.path.join(RES, 'FREEZE.json'))


def split_of(expiry): return 'HOLDOUT' if pd.Timestamp(expiry) >= HOLDOUT_START else 'DISCOVERY'


def load_events(discovery_only=True, name='d0_events.csv'):
    E = pd.read_csv(os.path.join(RES, name), parse_dates=['t'])
    if discovery_only: return E[E.split == 'DISCOVERY'].copy()
    if not os.path.exists(os.path.join(RES, 'FREEZE.json')): raise PermissionError('holdout locked: run freeze.py first (rules must be frozen before holdout evaluation)')
    return E
