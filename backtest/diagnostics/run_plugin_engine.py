"""DIAGNOSTIC (not selection): run the frozen-threshold plugin variants on the OOS cycles into a SEPARATE directory (tag _DXOOS). Original engine pickles are untouched."""
from common import *
cyc = X.usable(); cyc = cyc[cyc.split == 'OOS'].reset_index(drop=True)
names = ['cut_t20000_f10000_re_none', 'cut_t20000_f10000_re_cd1800', 'cut_t20000_f10000_re_none_STOP', 'STOP_ONLY']
import time; t = time.time(); X.run_engine(names, 'HOLD_SETTLE', cyc=cyc, check=False, tag='_DXOOS', procs=4); print('done', round(time.time() - t), 's')
