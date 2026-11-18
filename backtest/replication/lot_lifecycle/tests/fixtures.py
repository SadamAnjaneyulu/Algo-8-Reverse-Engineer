"""Synthetic fill fixtures for adversarial tests. Columns follow ledger.load_fills(): row, tag, tradeid, module, und, expiry, day, sec, t, cp, strike, side, sgn, qty_fill, n_lots, px"""
import numpy as np, pandas as pd


def fills(spec, und='NIFTY', expiry='2030-01-09', d1='2030-01-08'):
    """spec: list of (day, sec, module, side, cp, strike, n_lots, px[, tag])"""
    rows = []
    for i, s in enumerate(spec):
        day, sec, module, side, cp, strike, n, px = s[:8]; tag = s[8] if len(s) > 8 else f'T{i}'
        rows.append(dict(row=i, tag=tag, tradeid=f'ID{i}', module=module, und=und, expiry=expiry, day=expiry if day == 'D0' else d1, sec=sec, t=pd.Timestamp('2030-01-01') + pd.Timedelta(seconds=sec) + pd.Timedelta(days=0 if day == 'D0' else -1), cp=cp, strike=strike, side=side, sgn=1 if side == 'Buy' else -1, qty_fill=n * (65 if und == 'NIFTY' else 20), n_lots=n, px=px, px_fill=px, validity='DAY'))
    return pd.DataFrame(rows).sort_values(['t', 'row']).reset_index(drop=True)
