"""Task B: cross-tab of minute-resolution columns on SENSEX rows where floor-minute(ns) != floor-minute(epoch) (rounding crosses a minute)  [RAW]"""
import csv, datetime, collections, json
rows = list(csv.reader(open('/home/user/Algo-8-Reverse-Engineer/Trades_GKOHNP140.csv', newline='')))
IST = datetime.timedelta(hours=5, minutes=30)
def parse(s): return int((datetime.datetime.strptime(s, '%m/%d/%Y %H:%M') - IST).replace(tzinfo=datetime.timezone.utc).timestamp())
out = {}
S = [(i, r) for i, r in enumerate(rows) if r[12] == 'SENSEX']
bd = []
for i, r in S:
    ns = int(r[28][:19]); ep = int(r[161])
    if (ns // 10**9) // 60 != ep // 60 and (ns + 500_000_000) // 10**9 == ep: bd.append(i)
out['n_boundary_rows (round(ns) crosses a minute vs floor(ns), id consistent)'] = len(bd)
for j in (23, 69, 78, 79, 119, 127, 130, 138):
    c = collections.Counter()
    for i in bd:
        r = rows[i]; t = parse(r[j]); ns_m = (int(r[28][:19]) // 10**9) // 60 * 60; ep_m = int(r[161]) // 60 * 60
        c['=floor(ns) minute' if t == ns_m else ('=epoch minute' if t == ep_m else 'other')] += 1
    out[f'col{j}_on_boundary_rows'] = dict(c)
# col 130 mismatches with ns minute on all rows
mm = []
for i, r in S:
    if parse(r[130]) != (int(r[28][:19]) // 10**9) // 60 * 60: mm.append(i)
out['col130_ne_floor_ns_minute_rows'] = mm
out['col130_ne_floor_ns_minute_details'] = [dict(row=i, c130=rows[i][130], ns_ist=datetime.datetime.fromtimestamp(int(rows[i][28][:19]) / 1e9 + 19800, datetime.timezone.utc).strftime('%H:%M:%S.%f'), ep_ist=datetime.datetime.fromtimestamp(int(rows[i][161]) + 19800, datetime.timezone.utc).strftime('%H:%M:%S'), status=rows[i][27], c23=rows[i][23]) for i in mm[:30]]
# the same, using epoch: col130 vs epoch minute mismatches outside boundary
mm2 = [i for i, r in S if parse(r[130]) != int(r[161]) // 60 * 60]
out['col130_ne_epoch_minute_n'] = len(mm2)
out['col130_ne_epoch_minute_of_which_boundary'] = len(set(mm2) & set(bd))
json.dump(out, open('b_boundary_result.json', 'w'), indent=1)
print(json.dumps({k: (v if not isinstance(v, list) or len(v) < 6 else f'list[{len(v)}]') for k, v in out.items()}, indent=1)); print(out['col130_ne_floor_ns_minute_details'][:8])
