import os, sys
import numpy as np, pandas as pd, pytest
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'scripts'))
import tp_common as tc


def mk(rows, contract='NIFTY|2026-07-07|CE|24000'):
    """rows: (epoch, 'B'/'S', qty_units, price[, contract]) -> minimal fill frame for the matching engine (file order = list order)"""
    out = []
    for i, r in enumerate(rows):
        c = r[4] if len(r) > 4 else contract
        out.append(dict(src_row=i, contract_id=c, epoch=r[0], sgn=1 if r[1] == 'B' else -1, qty_units=r[2], px_fill=float(r[3]), dq_duplicate_fill=False))
    return pd.DataFrame(out)


def mk_ledger(rows, expiry='2026-07-07', und='NIFTY'):
    """fill frame with the extra columns reconstruct_positions.build needs; epoch is a UTC epoch (IST = +5:30)"""
    F = mk(rows)
    F['und'] = und; F['expiry'] = pd.Timestamp(expiry); F['strike'] = 24000.0; F['cp'] = 'CE'
    F['t_fill'] = pd.to_datetime(F.epoch, unit='s') + pd.Timedelta(hours=5, minutes=30); F['date'] = F.t_fill.dt.normalize()
    F['parent_oid'] = F.src_row.astype(str); F['module'] = 'num'; F['dq_flag_any'] = False
    return F


T0 = 1783400000     # a fixed UTC epoch (2026-07-07 ~ 05:20 UTC)
DAY = 86400
real = pytest.mark.skipif(not os.path.exists(tc.RAW), reason='raw trade file not present')
