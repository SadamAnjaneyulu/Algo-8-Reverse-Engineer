"""Generates the three detail tables used by the reports: negative-volume rows, planned contracts without rows, post-closing-auction spot anomaly at 15:20."""
import csv, io, json, sys
import numpy as np, pandas as pd
from .gitsrc import GitSource


def run(commit, tab):
    g = GitSource(commit); o = pd.DataFrame(json.load(open(f'{tab}/option_session_scan.json'))); c = pd.read_parquet(f'{tab}/contract_sessions.parquet'); u = pd.DataFrame(json.load(open(f'{tab}/underlying_scan.json')))
    rows = []
    for r in o[o.volume_neg > 0].itertuples():
        x = pd.read_csv(io.BytesIO(g.read(r.file)))
        for _, t in x[x.volume < 0].iterrows(): rows.append((r.index, r.expiry, r.day, t.datetime, t.strike, t.right, t.open, t.high, t.low, t.close, t.volume, t.open_interest))
    pd.DataFrame(rows, columns='index expiry day datetime strike right open high low close volume oi'.split()).to_csv(f'{tab}/negative_volume_rows.csv', index=False)
    plan = set()
    for r in csv.reader(io.StringIO(g.text('manifests/checkpoint.csv'))):
        if r[1] == 'option': plan.add((r[0], r[2], r[3], int(r[4]), 'CE' if r[5] == 'call' else 'PE'))
    have = set(zip(c['index'], c.expiry, c.day, c.strike, c.right)); cen = {(r.index, r.expiry, r.day): r.plan_center for r in o.itertuples()}; m = []
    for (i, e, d, s, rt) in plan - have: m.append((i, e, d, s, rt, round((s - cen[(i, e, d)]) / (50 if i == 'nifty' else 100))))
    pd.DataFrame(m, columns='index expiry day strike right k'.split()).to_csv(f'{tab}/planned_contracts_without_rows.csv', index=False)
    res = []
    for r in u[(u.kind == 'spot') & (u.day >= '2026-08-03')].itertuples():
        x = pd.read_csv(io.BytesIO(g.read(f'normalized/{r.index}/underlying/spot/{r.day}.csv'))); x['t'] = x.datetime.str.slice(11, 16); a = x[x.t == '15:14'].close; b = x[x.t == '15:20']
        if len(a) and len(b): res.append((r.index, r.day, float(a.iloc[0]), float(b.open.iloc[0]), float(b.high.iloc[0]), float(b.low.iloc[0]), float(x[x.t == '15:29'].close.iloc[0]) if (x.t == '15:29').any() else np.nan))
    R = pd.DataFrame(res, columns='index day c1514 o1520 h1520 l1520 c1529'.split()); R['jump_pct'] = (R.o1520 / R.c1514 - 1) * 100; R['range_pct'] = (R.h1520 - R.l1520) / R.c1514 * 100; R.to_csv(f'{tab}/post_cas_spot_1520_anomaly.csv', index=False)


if __name__ == '__main__': run(sys.argv[1], sys.argv[2])
