"""Locates the M2 engine (package `pe`) without copying or modifying it.
Search order: $ALGO8_M2_PYTHON; the delivery layout (../01_M2_Position_Reconstruction/01_CODE/python); the source-tree layout (portfolio_engine/python)."""
import os, sys


def locate():
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(os.path.dirname(os.path.dirname(here)))
    cands = [os.environ.get('ALGO8_M2_PYTHON', ''), os.path.join(root, '01_M2_Position_Reconstruction', '01_CODE', 'python'), os.path.join(root, 'python')]
    for c in cands:
        if c and os.path.isfile(os.path.join(c, 'pe', 'ledger.py')): return c
    raise ImportError('M2 engine not found; set ALGO8_M2_PYTHON to the directory that contains the package "pe"')


_path = locate()
if _path not in sys.path: sys.path.insert(0, _path)
from pe import ledger as m2_ledger, schema as m2_schema, tsvio as m2_tsvio, replay as m2_replay      # noqa: E402  (unchanged M2 modules)
M2_PATH = _path
