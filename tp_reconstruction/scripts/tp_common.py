"""TP-01 shared paths, config and raw-file hashing. Reads only the raw trade file; never a cache of earlier work."""
import os, hashlib
import yaml
HERE = os.path.dirname(os.path.abspath(__file__)); PKG = os.path.dirname(HERE); REPO = os.path.dirname(PKG)
CFG = yaml.safe_load(open(os.path.join(PKG, 'config.yaml')))
DATA = os.path.join(PKG, 'data'); ANALYSIS = os.path.join(PKG, 'analysis')
for _d in (DATA, ANALYSIS): os.makedirs(_d, exist_ok=True)
RAW = os.path.join(REPO, CFG['source']['raw_trades'])
COL = CFG['columns']; TOL = float(CFG['classification']['breakeven_tolerance_points_per_unit']); TICK = float(CFG['units']['tick'])
LOT = CFG['units']['lot_units']; METHODS = list(CFG['matching']['methods']); TIE_ORDERS = list(CFG['matching']['tie_orders'])
PRIMARY_TIE = CFG['matching']['primary_tie_order']


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()
