"""Locates the historical engine (package `pe`) without copying or modifying it.
Search order: $ALGO8_HISTORICAL_PYTHON; the delivery layout (../01_Historical_Position_Reconstruction/python); the source-tree layout (portfolio_engine/python)."""
import os, sys


def locate():
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(os.path.dirname(os.path.dirname(here)))
    cands = [os.environ.get('ALGO8_HISTORICAL_PYTHON', ''), os.path.join(root, '01_Historical_Position_Reconstruction', 'python'), os.path.join(root, 'python')]
    for c in cands:
        if c and os.path.isfile(os.path.join(c, 'pe', 'ledger.py')): return c
    raise ImportError('historical engine not found; set ALGO8_HISTORICAL_PYTHON to the directory that contains the package "pe"')


_path = locate()
if _path not in sys.path: sys.path.insert(0, _path)
from pe import ledger as hist_ledger, schema as hist_schema, tsvio as hist_tsvio, replay as hist_replay      # noqa: E402  (unchanged historical modules)
HIST_PATH = _path
