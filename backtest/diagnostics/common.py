"""Shared loaders for the diagnostics. READ-ONLY with respect to the original backtest: it imports bt.* and reads results/; it writes only under diagnostics/."""
import os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); BT = os.path.dirname(HERE); sys.path.insert(0, BT)
os.chdir(BT)
from bt import final_run as F, experiment as X, metrics as M, config as C, account as A, scen, cycles as Cy        # noqa: E402
RES = os.path.join(HERE, 'results'); REP = os.path.join(HERE, 'reports'); FIG = os.path.join(REP, 'figures'); os.makedirs(RES, exist_ok=True); os.makedirs(FIG, exist_ok=True)
BASE = F.BASE; CAP = C.CAPITAL_RS
PARTS = {'IS': lambda d: d[d.split == 'IS'], 'OOS': lambda d: d[d.split == 'OOS'], 'OOS_exposed': lambda d: d[d.subset == 'OOS_EXPOSED'], 'OOS_clean': lambda d: d[d.subset.isin(['OOS_CLEAN_BEFORE', 'OOS_CLEAN_AFTER'])],
         'OOS_clean_before': lambda d: d[d.subset == 'OOS_CLEAN_BEFORE'], 'OOS_clean_after': lambda d: d[d.subset == 'OOS_CLEAN_AFTER']}


def cycles(name='HOLD', variant='HOLD_SETTLE', params=BASE, tag=''):
    d = F.table(name, variant, params, tag=tag); d['wk'] = pd.to_datetime(d.d0).dt.strftime('%G-W%V'); return d


def part(d, p, und=None):
    x = PARTS[p](d); return x if und in (None, 'COMBINED') else x[x.und == und]
