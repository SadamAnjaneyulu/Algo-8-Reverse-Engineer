"""Audit of the order key.  Column 4 ('oid') is reused across days; column 163 (UniqueOrderIdentifier, 'tag') is the order key used by the
exit engine.  Checks: (1) every tag maps to exactly one session date, underlying, expiry, option type, strike, side and module tag;
(2) fills of a tag span <= 60 s; (3) order lots == fill lots per cycle; (4) tag grouping == (oid, date) grouping;
(5) size of the damage done by grouping on oid alone (orders merged, lots and cycles involved).
python3 analysis/exit_engine/order_key_audit.py -> results/order_key_audit.csv, results/order_key_audit.txt"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); AN = os.path.dirname(HERE); sys.path.insert(0, AN); sys.path.insert(0, HERE)
import numpy as np, pandas as pd
from load import load_tagged
from common import RES

def audit():
    d = load_tagged(); rows = []; txt = []
    attrs = ['date', 'und', 'expiry', 'cp', 'strike', 'side', 'tp']
    g = d.groupby('tag').agg(**{f'n_{a}': (a, 'nunique') for a in attrs}, fills=('row', 'size'), lots=('lots', 'sum'),
                             span_s=('t', lambda x: (x.max() - x.min()).total_seconds()))
    multi = {a: int((g[f'n_{a}'] > 1).sum()) for a in attrs}
    rows.append(dict(check='tags (orders)', value=len(g), ok=True))
    rows.append(dict(check='fill rows', value=len(d), ok=True))
    for a, v in multi.items(): rows.append(dict(check=f'tags mapping to >1 {a}', value=v, ok=v == 0))
    rows.append(dict(check='max fill span within a tag (s)', value=g.span_s.max(), ok=g.span_s.max() <= 60))
    rows.append(dict(check='tags with fills spanning > 60 s', value=int((g.span_s > 60).sum()), ok=int((g.span_s > 60).sum()) == 0))
    rows.append(dict(check='empty tags', value=int((d.tag == '').sum()), ok=int((d.tag == '').sum()) == 0))
    od = d.groupby(['oid', 'date']).ngroups
    same = (d.groupby(['oid', 'date']).tag.nunique() == 1).all() and (d.groupby('tag').oid.nunique() == 1).all()
    rows.append(dict(check='(oid, date) groups', value=od, ok=od == len(g)))
    rows.append(dict(check='tag <-> (oid, date) one-to-one', value=bool(same), ok=bool(same)))
    # lot reconciliation per cycle
    sys.path.insert(0, HERE)
    from common import orders
    o = orders()
    a = d.groupby(['und', 'expiry']).lots.sum(); b = o.groupby(['und', 'expiry']).lots.sum()
    rec = (a.round(6) == b.reindex(a.index).round(6)).all()
    rows.append(dict(check='order lots == fill lots in every cycle (exit-engine order table)', value=bool(rec), ok=bool(rec)))
    rows.append(dict(check='exit-engine order table rows == tags', value=len(o), ok=len(o) == len(g)))
    # damage of the old key
    go = d.groupby('oid').agg(tags=('tag', 'nunique'), dates=('date', 'nunique'), cyc=('expiry', 'nunique'), lots=('lots', 'sum'))
    merged = go[go.tags > 1]
    rows += [dict(check='old key: oid groups', value=len(go), ok=None),
             dict(check='old key: oid groups merging >1 real order', value=len(merged), ok=None),
             dict(check='old key: real orders inside merged groups', value=int(merged.tags.sum()), ok=None),
             dict(check='old key: real orders lost by groupby(oid).first()', value=int(len(g) - len(go)), ok=None),
             dict(check='old key: share of real orders lost by .first()', value=(len(g) - len(go)) / len(g), ok=None),
             dict(check='old key: merged groups spanning >1 cycle (expiry)', value=int((merged.cyc > 1).sum()), ok=None),
             dict(check='old key: fill lots inside merged groups', value=float(d[d.oid.isin(merged.index)].lots.sum()), ok=None),
             dict(check='old key: max real orders behind one oid', value=int(go.tags.max()), ok=None)]
    R = pd.DataFrame(rows)
    return R

if __name__ == '__main__':
    R = audit(); R.to_csv(os.path.join(RES, 'order_key_audit.csv'), index=False)
    s = R.to_string(index=False); open(os.path.join(RES, 'order_key_audit.txt'), 'w').write(s + '\n'); print(s)
    bad = R[R.ok == False]
    if len(bad): raise SystemExit(f'ORDER KEY AUDIT FAILED: {bad.check.tolist()}')
