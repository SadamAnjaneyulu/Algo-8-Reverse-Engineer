"""R1: evidence on whether NIFTY trade ids / order numbers can serve as intra-second chronology, and whether ANY raw column carries sub-second time. [RAW] + [IMPL] (Track A raw loader; no pe imports).
python3 nifty_id_evidence.py <out.json>"""
import sys, csv, collections, re, json
sys.dont_write_bytecode = True
sys.path.insert(0, '/home/user/Algo-8-Reverse-Engineer/portfolio_engine/reports/m2f_audit/track_a')
import ref_model as RM
rows = RM.load_raw(); raw = list(csv.reader(open(RM.RAW, newline='')))
for r, rr in zip(rows, raw): r['tid_s'] = rr[28]; r['ono'] = int(rr[4])
ist = lambda t: (t + 19800) // 86400
R = {}
R['trade_id_formats'] = {f'{k[0]}|{k[1]}': v for k, v in collections.Counter((('numeric' if r['tid_s'].isdigit() else 'dash' if '-' in r['tid_s'] else 'other'), r['und']) for r in rows).items()}


def inversions(sel, key, by):
    groups = collections.defaultdict(list)
    for r in sel: groups[by(r)].append(r)
    tot = bad = 0
    for l in groups.values():
        l.sort(key=lambda f: (f['ts'], f['row'])); prev = None; cs = None; sm = None
        for f in l:
            k = key(f)
            if cs != f['ts']:
                if sm is not None: prev = sm if prev is None else max(prev, sm)
                cs = f['ts']; sm = k
            else: sm = max(sm, k)
            if prev is not None: tot += 1; bad += k < prev
    return dict(fills_compared=tot, fills_with_key_below_max_of_earlier_seconds=bad)


N = [r for r in rows if r['und'] == 'NIFTY']
R['nifty_trade_id_vs_time_per_IST_day'] = inversions(N, lambda f: int(f['tid_s']), lambda f: ist(f['ts']))
R['nifty_trade_id_vs_time_per_instrument'] = inversions(N, lambda f: int(f['tid_s']), lambda f: f['inst'])
R['nifty_order_number_vs_time_per_IST_day'] = inversions(N, lambda f: f['ono'], lambda f: ist(f['ts']))
R['sensex_order_number_vs_time_per_IST_day'] = inversions([r for r in rows if r['und'] == 'SENSEX'], lambda f: f['ono'], lambda f: ist(f['ts']))
Gn = collections.defaultdict(list)
for r in N: Gn[(r['inst'], r['ts'])].append(r)
mg = [g for g in Gn.values() if len(g) > 1]
R['nifty_multi_fill_groups'] = dict(groups=len(mg), file_order_differs_from_trade_id_order=sum(1 for g in mg if [x['row'] for x in g] != [x['row'] for x in sorted(g, key=lambda f: (int(f['tid_s']), f['row']))]))
G = collections.defaultdict(list)
for r in rows: G[(r['inst'], r['ts'])].append(r)
mixed = [g for g in G.values() if len({x['side'] for x in g}) > 1]
tk = lambda s: tuple(int(x) for x in s.split('-'))
R['mixed_side_groups_all_instruments'] = dict(groups=len(mixed), trade_id_order_differs_from_file=sum(1 for g in mixed if [x['row'] for x in g] != [x['row'] for x in sorted(g, key=lambda f: (tk(f['tid_s']), f['row']))]),
                                              order_number_differs_from_file=sum(1 for g in mixed if [x['row'] for x in g] != [x['row'] for x in sorted(g, key=lambda f: (f['ono'], f['row']))]))
# columns carrying time-like or sub-second values (sampled across the file)
sample = raw[:3000] + raw[20000:23000] + raw[-3000:]; cols = []
for c in range(167):
    vals = [r[c] for r in sample if len(r) > c and r[c] != '']
    if not vals: continue
    frac = sum(1 for v in vals if re.search(r'\d:\d\d:\d\d\.\d', v)) / len(vals); ns = sum(1 for v in vals if re.fullmatch(r'\d{16,19}', v)) / len(vals); tm = sum(1 for v in vals if re.search(r'\d{1,2}:\d\d', v)) / len(vals)
    if frac > .1 or ns > .1 or tm > .1: cols.append(dict(col=c, fractional_seconds=round(frac, 2), integer_19digit=round(ns, 2), time_like=round(tm, 2), sample=vals[0][:30]))
R['columns_with_time_like_values'] = cols; R['columns_with_sub_second_values'] = [c['col'] for c in cols if c['fractional_seconds'] > 0 or c['integer_19digit'] > 0]
json.dump(R, open(sys.argv[1], 'w'), indent=1)
for k, v in R.items(): print(k, json.dumps(v)[:300])
