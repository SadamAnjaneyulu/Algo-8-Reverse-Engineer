"""Shared loaders for the replication programme (read-only w.r.t. existing code/results)."""
import os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); BT = os.path.dirname(HERE); ROOT = os.path.dirname(BT)
sys.path.insert(0, os.path.join(ROOT, 'analysis')); sys.path.insert(0, BT)
RES = os.path.join(HERE, 'results'); REP = os.path.join(HERE, 'reports'); FIG = os.path.join(REP, 'figures')
for p in (RES, REP, FIG): os.makedirs(p, exist_ok=True)
CAP = 20_000_000
YAHOO = {u: pd.read_csv(f'{ROOT}/data_validation/reference/yahoo_daily_{s}.csv').assign(date=lambda x: pd.to_datetime(x.date_ist)).set_index('date').sort_index() for u, s in (('NIFTY', 'NSEI'), ('SENSEX', 'BSESN'))}


def live_ledger():
    """the real Algo 8 fills (Trades_GKOHNP140.csv) with tags decoded"""
    import load as L
    d = L.load_tagged(); d = d[d.status.str.lower().str.contains('fill')] if 'status' in d else d
    return d


def intr(cp, K, S): return max(S - K, 0.0) if cp == 'CE' else max(K - S, 0.0)
