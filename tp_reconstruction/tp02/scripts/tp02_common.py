"""TP-02 shared helpers. Read-only access to TP-01 outputs; all TP-02 outputs go to tp_reconstruction/tp02/."""
import os, sys, re
import numpy as np, pandas as pd, yaml
HERE = os.path.dirname(os.path.abspath(__file__)); TP02 = os.path.dirname(HERE); PKG = os.path.dirname(TP02); REPO = os.path.dirname(PKG)
sys.path.insert(0, os.path.join(PKG, 'scripts'))
import tp_common as tc                                           # TP-01 paths and constants (read-only reuse)
CFG = yaml.safe_load(open(os.path.join(TP02, 'config.yaml')))
DATA = os.path.join(TP02, 'data'); ANALYSIS = os.path.join(TP02, 'analysis')
for _d in (DATA, ANALYSIS): os.makedirs(_d, exist_ok=True)
TP01 = tc.DATA; METHODS = tc.METHODS; LOT = tc.LOT; IST_S = 19800
WINDOWS = CFG['windows_seconds']


def tp01(name): return pd.read_parquet(os.path.join(TP01, name))


def decode_tag_time(parent_oid, t_fill):
    """decision time from a tagged order id (h_/s_/v_/m_ + DDHHMMSSffffff, UTC); NaT if the tag carries none or is inconsistent with the fill time"""
    m = re.match(r'^[a-z]+_(\d{2})(\d{2})(\d{2})(\d{2})(\d{6})$', parent_oid)
    if not m: return pd.NaT
    dd, hh, mi, ss, us = (int(x) for x in m.groups())
    if t_fill.day != dd: return pd.NaT
    cand = t_fill.normalize() + pd.Timedelta(hours=hh + 5, minutes=mi + 30, seconds=ss, microseconds=us)
    return min(cand, t_fill) if abs((cand - t_fill).total_seconds()) < 120 else pd.NaT


def phase_of(hhmm_minutes):
    """session phase from minutes since midnight, per config"""
    P = CFG['expiry']['phases']; out = []
    for m in hhmm_minutes:
        lab = 'OUTSIDE'
        for k, (a, b) in P.items():
            ah, am = map(int, a.split(':')); bh, bm = map(int, b.split(':'))
            if ah * 60 + am <= m < bh * 60 + bm: lab = k; break
        out.append(lab)
    return np.array(out)


def number_blocks(L):
    """order-number blocks per (date, app key), as in Stage 1 (DAT-12): a jump above the gap starts a new concurrent block. Returns parent_oid -> (app, block, order_no)"""
    gap = CFG['replacement']['sequence_block_gap']
    p = L.drop_duplicates('parent_oid')[['parent_oid', 'date', 'app_key', 'order_no']].copy(); p['no'] = pd.to_numeric(p.order_no, errors='coerce')
    p = p.sort_values(['date', 'app_key', 'no']); p['block'] = p.groupby(['date', 'app_key']).no.transform(lambda s: np.r_[0, np.cumsum(np.diff(s.values) > gap)])
    return p.set_index('parent_oid')[['app_key', 'block', 'no']]
