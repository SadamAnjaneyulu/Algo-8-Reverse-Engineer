"""Task B extras: (1) rows where order-entry minute (col 23) != floor(ns) minute; (2) cross-parent duplicate ns; (3) 21 differing groups parent-sharing; (4) row 8079 role; (5) NIFTY duplicate trade ids. [RAW]+[IMPL]"""
import csv, collections, json, datetime
import rv_replay as R
rows = list(csv.reader(open('/home/user/Algo-8-Reverse-Engineer/Trades_GKOHNP140.csv', newline='')))
IST = datetime.timedelta(hours=5, minutes=30)
def parse(s): return int((datetime.datetime.strptime(s, '%m/%d/%Y %H:%M') - IST).replace(tzinfo=datetime.timezone.utc).timestamp())
def inst(r): return (r[12], r[15].split()[0], r[16], r[14])
out = {}
S = [(i, r) for i, r in enumerate(rows) if r[12] == 'SENSEX']
ns = lambda r: int(r[28][:19])
mm = [(i, (ns(r) // 10**9) // 60 * 60 - parse(r[23])) for i, r in S if (ns(r) // 10**9) // 60 * 60 != parse(r[23])]
out['col23_ne_floor_ns_minute'] = dict(n=len(mm), all_ns_later_than_col23=all(d > 0 for _, d in mm), delta_minutes_min=min(d for _, d in mm) / 60, delta_minutes_max=max(d for _, d in mm) / 60, status=dict(collections.Counter(rows[i][27] for i, _ in mm)), tif=dict(collections.Counter(rows[i][22] for i, _ in mm)))
out['col23_vs_epoch_minute_ne'] = sum(1 for i, r in S if int(r[161]) // 60 * 60 != parse(r[23]))
# cross-parent duplicate ns (same instrument)
dn = collections.defaultdict(list)
for i, r in S: dn[ns(r)].append(i)
xp = {k: v for k, v in dn.items() if len(v) > 1 and len({rows[i][163] for i in v}) > 1}
out['cross_parent_dup_ns_events'] = len(xp)
det = []
for k, v in list(xp.items()):
    det.append(dict(ns=k, rows=v, sides=''.join(rows[i][11][0] for i in v), pids=[rows[i][163] for i in v], ono=[int(rows[i][4]) for i in v], c23=[rows[i][23] for i in v], suf=[int(rows[i][28].split('-')[1]) for i in v], tif=[rows[i][22] for i in v]))
out['cross_parent_dup_ns_details_first8'] = det[:8]
out['cross_parent_dup_ns_same_side_all'] = sum(1 for d in det if len(set(d['sides'])) == 1); out['cross_parent_dup_ns_distinct_suffix_all'] = sum(1 for d in det if len(set(d['suf'])) == len(d['suf']))
out['cross_parent_dup_ns_order_numbers_span_gt_1'] = sum(1 for d in det if max(d['ono']) - min(d['ono']) > 1)
out['cross_parent_dup_ns_entry_minute_differs'] = sum(1 for d in det if len(set(d['c23'])) > 1)
# 21 ns-vs-file differing groups: any shared parent? any with mixed side?
F = R.load(); G = R.groups(F)
dif = []
for (iid, ep), v in G.items():
    if v[0]['und'] != 'SENSEX': continue
    so = [f['row'] for f in v]; ao = [f['row'] for f in sorted(v, key=lambda f: (R.sensex_ns(f), f['row']))]
    if so != ao: dif.append(v)
out['sensex_ns_policy_groups_differing'] = len(dif); out['  ...with a shared parent'] = sum(1 for v in dif if len({f['pid'] for f in v}) < len(v)); out['  ...mixed side'] = sum(1 for v in dif if len({f['side'] for f in v}) > 1)
out['  ...distinct instruments'] = len({v[0]['iid'] for v in dif})
# row 8079 role in baseline & timestamps
b = R.replay(F, 'source_row'); out['row8079_split_baseline(open,close)'] = b['split'][8079]; out['row8083_split_baseline'] = b['split'][8083]
# NIFTY dup trade ids
N = [(i, r) for i, r in enumerate(rows) if r[12] == 'NIFTY']; c = collections.defaultdict(list)
for i, r in N: c[r[28]].append(i)
dups = {k: v for k, v in c.items() if len(v) > 1}
out['nifty_duplicate_trade_ids'] = len(dups)
out['nifty_dup_ids_same_instrument_same_second'] = sum(1 for v in dups.values() if len({(inst(rows[i]), rows[i][161]) for i in v}) == 1)
out['nifty_dup_ids_same_instrument'] = sum(1 for v in dups.values() if len({inst(rows[i]) for i in v}) == 1)
out['nifty_dup_ids_same_day'] = sum(1 for v in dups.values() if len({(int(rows[i][161]) + 19800) // 86400 for i in v}) == 1)
json.dump(out, open('b_more_result.json', 'w'), indent=1); print(json.dumps(out, indent=1))
