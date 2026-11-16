"""Hard-coded 15-min lot ladder (body sells within 0-2 min of each grid time 09:16+15k).   python3 analysis/ladder.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from load import load_tagged
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 100)
d = load_tagged()
b = d[(d.tp == 'num') & (d.side == 'Sell')].copy()
b['mins'] = (b.t.dt.hour * 60 + b.t.dt.minute) - (9 * 60 + 16)
b['k'] = np.floor(b.mins / 15).astype(int); b['off'] = b.mins - 15 * b.k
b = b[(b.off <= 2) & (b.mins >= 0) & (b.k <= 24)]
for lab, m in [('D-1', b.dte >= 1), ('D0', b.dte == 0)]:
    x = b[m]; t = x.groupby(['date', 'k', 'cp']).lots.sum().unstack('k').fillna(0).reindex(columns=range(25), fill_value=0)
    rows = []
    for k in range(25):
        r = {'k': k, 'clock': (pd.Timestamp('2000-01-01 09:16') + pd.Timedelta(minutes=15 * k)).strftime('%H:%M')}
        for cp in ('CE', 'PE'):
            s = t.xs(cp, level='cp')[k]; mo = int(s.mode().iloc[0]); r[cp + '_mode'] = mo; r[cp + '_hit'] = round((s == mo).mean(), 2)
        rows.append(r)
    print(f'=== {lab}: modal sold lots per leg per slot (hit = share of days equal to the mode) ===')
    print(pd.DataFrame(rows).to_string(index=False))
