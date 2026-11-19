"""Original-system reference tables built from the live ledger (read-only): fills, orders, contract-level inventory paths.
Inventory is computed PER CONTRACT (net lots), which does not depend on any lot-ownership convention."""
import os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); EP = os.path.dirname(HERE); REPL = os.path.dirname(EP); BT = os.path.dirname(REPL); ROOT = os.path.dirname(BT)
LL_SRC = os.path.join(REPL, 'lot_lifecycle', 'src')
for p in (LL_SRC, os.path.join(ROOT, 'analysis'), BT, REPL): sys.path.insert(0, p)
OUT = os.path.join(EP, 'outputs'); os.makedirs(OUT, exist_ok=True)
LOT = {'NIFTY': 65, 'SENSEX': 20}; STEP = {'NIFTY': 50, 'SENSEX': 100}; OPEN_SEC = 9 * 3600 + 15 * 60; NM = 375
CYCLES = os.path.join(REPL, 'lot_lifecycle', 'outputs', 'cycles.csv')


def minute_of(sec): return np.floor((np.asarray(sec) - OPEN_SEC) / 60).astype(int)


def load_fills():
    from ledger import load_fills as lf
    F = lf().copy(); C = pd.read_csv(CYCLES)[['und', 'expiry', 'd1', 'd0', 'has_d1', 'has_d0', 'carry_in_known']]
    F = F.merge(C, on=['und', 'expiry'], how='left'); F['dayno'] = np.where(F.day == F.d1, 0, 1); F['j'] = minute_of(F.sec); F['sgn_lots'] = F.sgn * F.n_lots
    F['role'] = F.module.map({'num': 'body', 'h_': 'wing', 'v_': 'lump', 's_': 'stop', 'm_': 'manual'}); F['strike'] = F.strike.astype(int)
    return F.sort_values(['t', 'row']).reset_index(drop=True)


def orders(F):
    """one row per order (column-163 tag): decision unit for event identity"""
    g = F.groupby('tag')
    O = g.agg(und=('und', 'first'), expiry=('expiry', 'first'), dayno=('dayno', 'first'), module=('module', 'first'), role=('role', 'first'), cp=('cp', 'first'), strike=('strike', 'first'), side=('side', 'first'),
              lots=('n_lots', 'sum'), sec=('sec', 'min'), sec_last=('sec', 'max'), row=('row', 'min'), px=('px', 'mean'), complete=('carry_in_known', 'first')).reset_index()
    O['j'] = minute_of(O.sec); return O.sort_values(['und', 'expiry', 'sec', 'row']).reset_index(drop=True)


def inventory_events(F):
    """contract-level net lots AFTER each fill, per cycle (D-1 carries into D0)"""
    X = F.sort_values(['und', 'expiry', 't', 'row']).copy(); X['net_after'] = X.groupby(['und', 'expiry', 'cp', 'strike']).sgn_lots.cumsum(); return X


def inventory_minute_grid(F, cycle):
    """net lots per contract at the END of every minute of D-1 and D0 (index = dayno*NM + minute). contracts x 750 matrix"""
    und, exp = cycle; X = F[(F.und == und) & (F.expiry == exp)]; keys = sorted(set(zip(X.cp, X.strike))); ki = {k: i for i, k in enumerate(keys)}
    M = np.zeros((len(keys), 2 * NM))
    for r in X.itertuples():
        t = r.dayno * NM + int(np.clip(r.j, 0, NM - 1)); M[ki[(r.cp, r.strike)], t:] += r.sgn_lots
    return keys, M
