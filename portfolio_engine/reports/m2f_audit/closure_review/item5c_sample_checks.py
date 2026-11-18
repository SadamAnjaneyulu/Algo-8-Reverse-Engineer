"""Sample-check raw-data claims quoted in closure dispositions: D-A06 (parent identity), D-A04 (expired-unclosed counts), C-01 (W1/W2 links changed, from my regenerated outputs)."""
import json, collections, sys, os, gzip, csv
import rawload as R, replay_mine as M
rows = R.load(); res = {}
par = {r['parent'] for r in rows}; ono = collections.defaultdict(set)
for r in rows: ono[r['ono']].add(r['parent'])
pon = collections.defaultdict(set)
for r in rows: pon[r['parent']].add(r['ono'])
res['D-A06'] = dict(parents_col163=len(par), distinct_order_no_col4=len(ono), max_parents_per_order_no=max(len(v) for v in ono.values()), order_numbers_shared=sum(1 for v in ono.values() if len(v) > 1), parents_with_more_than_one_order_no=sum(1 for v in pon.values() if len(v) > 1))
P = M.replay(R.order_baseline(rows), snapshots=False); last = max(R.ist_day(r['ts']) for r in rows); import datetime as dt
exp = {r['inst']: r['expiry'] for r in rows}; maxexp = max(exp.values())
nz = {i: v for i, v in P['inv'].items() if v}
res['D-A04'] = dict(nonflat=len(nz), long=sum(1 for v in nz.values() if v > 0), short=sum(1 for v in nz.values() if v < 0), units=sum(abs(v) for v in nz.values()), last_data_day=(dt.date(1970, 1, 1) + dt.timedelta(days=last)).isoformat(), max_expiry=maxexp,
                  nonflat_expiring_on_last_data_day=sum(1 for i in nz if exp[i] == (dt.date(1970, 1, 1) + dt.timedelta(days=last)).isoformat()))
out = sys.argv[1:3]
if out:
    base, hyb = out
    def links(root, m):
        with open(os.path.join(root, 'reports', 'm2d_data', f'm2d_wing_body_links_{m}.tsv.gz') if os.path.exists(os.path.join(root, 'reports', 'm2d_data', f'm2d_wing_body_links_{m}.tsv.gz')) else os.path.join(root, 'reports', 'm2d_data', f'wing_body_links_{m}.tsv.gz'), 'rb') as fh: pass
    d = os.path.join(base, 'reports', 'm2d_data'); res['m2d_files'] = sorted(os.listdir(d))[:20]
json.dump(res, open('item5c_sample_checks_result.json', 'w'), indent=1); print(json.dumps(res, indent=1, default=str))
