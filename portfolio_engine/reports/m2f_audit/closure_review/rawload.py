"""Independent raw-CSV loader for the closure review. No pe imports. Reads Trades_GKOHNP140.csv only.
Row index i = 0-based csv row (the file has no header). Columns (0-based): 3 segment, 4 order no, 11 side, 12 underlying, 14 strike, 15 expiry, 16 right, 28 trade id,
33 quantity (units), 137 price (rupees), 161 epoch s, 163 parent order id."""
import csv, datetime as dt, os, re
from decimal import Decimal
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
RAW = os.path.join(REPO, 'Trades_GKOHNP140.csv')


def load():
    rows = []
    with open(RAW, newline='') as fh:
        for i, c in enumerate(csv.reader(fh)):
            exp = dt.datetime.strptime(c[15], '%m/%d/%Y %H:%M').date().isoformat()
            inst = f'{c[12]}|{exp}|{c[16]}|{int(c[14])}'
            rows.append(dict(row=i, und=c[12], expiry=exp, right=c[16], inst=inst, side={'Buy': 1, 'Sell': -1}[c[11]], qty=int(c[33]),
                             px=int((Decimal(c[137]) * 100).to_integral_value()), ts=int(c[161]), parent=c[163], tid=c[28], ono=c[4]))
    return rows


def ist_day(ts): return (ts + 19800) // 86400


_T = re.compile(r'^(\d{19})-(\d{1,9})$')


def hybrid_key(r):
    """NIFTY numeric trade id; SENSEX embedded ns time when round-half-up(ns/1e9)==epoch else epoch*1e9 (my own implementation from the stated decision)"""
    if r['und'] == 'SENSEX':
        m = _T.match(r['tid'])
        if m:
            ns = int(m.group(1))
            if (ns + 500_000_000) // 10**9 == r['ts']: return ns
        return r['ts'] * 10**9
    return int(r['tid'])


def order_baseline(rows): return sorted(rows, key=lambda r: (r['ts'], r['row']))


def order_hybrid(rows):
    """my independent implementation: within each (instrument, second) group sort by (key, row) and put the group's fills back into the group's own baseline slots"""
    base = order_baseline(rows); slots = {}
    for i, r in enumerate(base): slots.setdefault((r['inst'], r['ts']), []).append(i)
    out = list(base)
    for idx in slots.values():
        grp = sorted((base[i] for i in idx), key=lambda r: (hybrid_key(r), r['row']))
        for i, r in zip(idx, grp): out[i] = r
    return out
