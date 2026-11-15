"""R1 evidence on intra-second ordering keys (trade id / order number): how monotone are they, where do they disagree with source-row order, and does any raw column carry sub-second time?
CORRECTED after the independent R1 review (R1R-01): the earlier POOLED metric mixed IST days (ids restart daily) and is kept ONLY as a withdrawn artefact. [RAW] + [IMPL] (the M2-F raw loader track_a/ref_model; no pe imports).
python3 nifty_id_evidence.py <out.json>"""
import sys, csv, collections, re, json, datetime
sys.dont_write_bytecode = True
sys.path.insert(0, '/home/user/Algo-8-Reverse-Engineer/portfolio_engine/reports/m2f_audit/track_a')
import ref_model as RM
rows = RM.load_raw(); raw = list(csv.reader(open(RM.RAW, newline='')))
for r, rr in zip(rows, raw):
    r['tid_s'] = rr[28]; r['ono'] = int(rr[4])
    if '-' in r['tid_s']: a, b = r['tid_s'].split('-'); r['ns'] = int(a); r['sfx'] = int(b)
ist = lambda t: (t + 19800) // 86400
N = [r for r in rows if r['und'] == 'NIFTY']; S = [r for r in rows if r['und'] == 'SENSEX']
R = {'trade_id_formats': {f'{k[0]}|{k[1]}': v for k, v in collections.Counter((('numeric' if r['tid_s'].isdigit() else 'dash' if '-' in r['tid_s'] else 'other'), r['und']) for r in rows).items()}}


def cross_second(sel, key, by):
    """fills whose key is below the maximum key of ALL earlier seconds inside the same `by` group (file/second order)"""
    g = collections.defaultdict(list)
    for r in sel: g[by(r)].append(r)
    tot = bad = 0
    for l in g.values():
        l.sort(key=lambda f: (f['ts'], f['row'])); prev = None; cs = None; sm = None
        for f in l:
            k = key(f)
            if cs != f['ts']:
                if sm is not None: prev = sm if prev is None else max(prev, sm)
                cs = f['ts']; sm = k
            else: sm = max(sm, k)
            if prev is not None: tot += 1; bad += k < prev
    return dict(fills_compared=tot, fills_with_key_below_max_of_earlier_seconds=bad)


def adjacent(sel, key, by):
    """adjacent pairs in file order inside a `by` group: decreases across seconds vs inside one second"""
    g = collections.defaultdict(list)
    for r in sel: g[by(r)].append(r)
    d = dict(cross_second_pairs=0, cross_second_decreases=0, same_second_pairs=0, same_second_decreases=0)
    for l in g.values():
        l.sort(key=lambda f: (f['ts'], f['row']))
        for a, b in zip(l, l[1:]):
            k = 'same_second' if a['ts'] == b['ts'] else 'cross_second'; d[k + '_pairs'] += 1; d[k + '_decreases'] += key(b) < key(a)
    return d


day_inst = lambda f: (f['inst'], ist(f['ts']))
R['PER_INSTRUMENT_PER_IST_DAY'] = dict(
    nifty_trade_id=cross_second(N, lambda f: int(f['tid_s']), day_inst), nifty_order_number=cross_second(N, lambda f: f['ono'], day_inst), sensex_order_number=cross_second(S, lambda f: f['ono'], day_inst),
    sensex_ns=cross_second(S, lambda f: f['ns'], day_inst), nifty_trade_id_adjacent_file_order=adjacent(N, lambda f: int(f['tid_s']), day_inst), sensex_ns_adjacent_file_order=adjacent(S, lambda f: f['ns'], day_inst))
# suffix behaviour: sorted by ns inside one (instrument, IST day), is the suffix non-decreasing?
g = collections.defaultdict(list)
for r in S: g[day_inst(r)].append(r)
tot = dec = 0
for l in g.values():
    l.sort(key=lambda f: (f['ns'], f['sfx']))
    for a, b in zip(l, l[1:]): tot += 1; dec += b['sfx'] < a['sfx']
R['PER_INSTRUMENT_PER_IST_DAY']['sensex_suffix_when_sorted_by_ns'] = dict(adjacent_pairs=tot, suffix_decreases=dec)
R['instruments_trading_on_more_than_one_IST_day'] = dict(instruments=len({r['inst'] for r in rows}), multi_day=sum(1 for v in collections.defaultdict(set, {}).items()))
days = collections.defaultdict(set)
for r in rows: days[r['inst']].add(ist(r['ts']))
R['instruments_trading_on_more_than_one_IST_day'] = dict(instruments=len(days), multi_day=sum(1 for v in days.values() if len(v) > 1))
R['WITHDRAWN_pooled_across_IST_days_artefact'] = dict(note='ids restart each IST day, so pooling days manufactures inversions; this metric was reported in the first R1 document and is WITHDRAWN',
                                                      nifty_trade_id_per_instrument_pooled=cross_second(N, lambda f: int(f['tid_s']), lambda f: f['inst']), nifty_trade_id_per_IST_day_all_instruments=cross_second(N, lambda f: int(f['tid_s']), lambda f: ist(f['ts'])))
# groups: where does trade-id / ns order differ from file order, and do the fills share a parent?
def groups(sel):
    G = collections.defaultdict(list)
    for r in sel: G[(r['inst'], r['ts'])].append(r)
    return [g for g in G.values() if len(g) > 1]
def differing(gs, key): return [g for g in gs if [x['row'] for x in g] != [x['row'] for x in sorted(g, key=lambda f: (key(f), f['row']))]]
gn, gs_ = groups(N), groups(S); dn = differing(gn, lambda f: int(f['tid_s'])); ds = differing(gs_, lambda f: f['ns'])
shared = lambda L: sum(1 for g in L if len({x['parent'] for x in g}) < len(g))
R['groups'] = dict(nifty_multi_fill=len(gn), nifty_trade_id_order_differs=len(dn), nifty_differing_with_a_shared_parent=shared(dn), sensex_multi_fill=len(gs_), sensex_ns_order_differs=len(ds), sensex_differing_with_a_shared_parent=shared(ds),
                   total_differing=len(dn) + len(ds))
same = agree = 0
for g in gn:
    by = collections.defaultdict(list)
    for x in g: by[x['parent']].append(x)
    for l in by.values():
        for a, b in zip(l, l[1:]): same += 1; agree += int(a['tid_s']) < int(b['tid_s'])
R['nifty_same_parent_same_second_consecutive_pairs'] = dict(pairs=same, trade_id_increases_in_file_order=agree)
allg = groups(rows); mixed = [g for g in allg if len({x['side'] for x in g}) > 1]
tk = lambda r: (r['ns'], 0) if 'ns' in r else (int(r['tid_s']), 0)
R['mixed_side_groups_all_instruments'] = dict(groups=len(mixed), trade_id_order_differs_from_file=sum(1 for g in mixed if [x['row'] for x in g] != [x['row'] for x in sorted(g, key=lambda f: (tk(f), f['row']))]),
                                              order_number_order_differs_from_file=sum(1 for g in mixed if [x['row'] for x in g] != [x['row'] for x in sorted(g, key=lambda f: (f['ono'], f['row']))]))
R['position_flip_groups_where_trade_id_changes_allocation'] = [[dict(row=rows[i]['row'], side='S' if rows[i]['side'] < 0 else 'B', qty=rows[i]['qty'], trade_id=rows[i]['tid_s'], order_number=rows[i]['ono'], parent=rows[i]['parent']) for i in grp] for grp in ([27908, 27911, 27917], [27906, 27912, 27916])]
# row 8079: the exceptional SENSEX fill -- which clocks agree with which?
r = rows[8079]; rr = raw[8079]; ep = r['ts']; idt = r['ns'] / 1e9
tcols = {}
for c in range(167):
    v = rr[c]
    if re.match(r'^\d{1,2}/\d{1,2}/\d{4} \d{1,2}:\d{2}', v) or re.match(r'^\d{4}-\d\d-\d\d \d\d:\d\d', v): tcols[c] = v
R['row_8079'] = dict(instrument=r['inst'], parent=r['parent'], epoch_utc=ep, epoch_ist=datetime.datetime.utcfromtimestamp(ep + 19800).strftime('%H:%M:%S'), id_time_ist=datetime.datetime.utcfromtimestamp(idt + 19800).strftime('%H:%M:%S.%f')[:-3], id_minus_epoch_s=round(idt - ep, 3), time_like_columns=tcols,
                     parent_other_fills=[dict(row=x['row'], epoch_ist=datetime.datetime.utcfromtimestamp(x['ts'] + 19800).strftime('%H:%M:%S'), id_time_ist=datetime.datetime.utcfromtimestamp(x['ns'] / 1e9 + 19800).strftime('%H:%M:%S.%f')[:-3]) for x in rows if x['parent'] == r['parent'] and x['row'] != 8079 and 'ns' in x][:6],
                     note='which clock is right for this fill is UNKNOWN; the sensitivity policy never trusts an id whose rounded time differs from the epoch')
# columns carrying time-like or sub-second values
sample = raw[:3000] + raw[20000:23000] + raw[-3000:]; cols = []
for c in range(167):
    vals = [x[c] for x in sample if len(x) > c and x[c] != '']
    if not vals: continue
    frac = sum(1 for v in vals if re.search(r'\d:\d\d:\d\d\.\d', v)) / len(vals); ns = sum(1 for v in vals if re.fullmatch(r'\d{16,19}', v)) / len(vals); tm = sum(1 for v in vals if re.search(r'\d{1,2}:\d\d', v)) / len(vals)
    if frac > .1 or ns > .1 or tm > .1: cols.append(dict(col=c, fractional_seconds=round(frac, 2), integer_19digit=round(ns, 2), time_like=round(tm, 2), sample=vals[0][:30]))
R['columns_with_time_like_values'] = cols; R['columns_with_sub_second_values'] = [c['col'] for c in cols if c['fractional_seconds'] > 0 or c['integer_19digit'] > 0]
json.dump(R, open(sys.argv[1], 'w'), indent=1, default=str)
for k, v in R.items(): print(k, json.dumps(v, default=str)[:420])
