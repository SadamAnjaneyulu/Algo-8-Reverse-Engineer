"""Deep-dive study DD-1: decision structure of the intraday activity in the 35 live cycles. Read-only on all earlier work."""
import os, sys, warnings
import numpy as np, pandas as pd
warnings.filterwarnings('ignore')
HERE = os.path.dirname(os.path.abspath(__file__)); DD = os.path.dirname(HERE); REPL = os.path.dirname(DD); OUT = os.path.join(DD, 'outputs'); REP = os.path.join(DD, 'reports')
sys.path.insert(0, os.path.join(REPL, 'execution_parity', 'src')); sys.path.insert(0, REPL)
import ref
LOT = ref.LOT; STEP = ref.STEP


def fills():
    F = ref.load_fills(); F['sec_f'] = F.sec; return F


def tagged_orders(F):
    """orders with microsecond decision time decoded from the tag: h_/s_/v_/m_ + DDHHMMSSffffff (UTC clock; IST = +5:30). Returns one row per order with t_dec (IST seconds since midnight, float) and latency to the first fill."""
    O = ref.orders(F); T = O[O.module.isin(['h_', 's_', 'v_', 'm_'])].copy()
    raw = T.tag.str.extract(r'^[a-z]_(\d{2})(\d{2})(\d{2})(\d{2})(\d{6})$').astype(float)
    T['dd'] = raw[0]; utc = raw[1] * 3600 + raw[2] * 60 + raw[3] + raw[4] / 1e6; T['t_dec'] = utc + 5.5 * 3600; T['t_dec'] = np.where(T.t_dec >= 86400, T.t_dec - 86400, T.t_dec)
    T['lat'] = T.sec - T.t_dec; return T
