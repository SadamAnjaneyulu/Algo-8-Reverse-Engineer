"""Item 1c: what are the NIFTY numeric trade ids? per-contract counter (docs) or a global counter that WOULD order different instruments? Also row 8079 and hybrid-key sanity."""
import collections, json
import rawload as R
rows = R.load(); nif = [r for r in rows if r['und'] == 'NIFTY']; res = {}
# 1. uniqueness of NIFTY trade id: globally, per instrument-day
c = collections.Counter(r['tid'] for r in nif); res['nifty_rows'] = len(nif); res['nifty_distinct_tid'] = len(c); res['nifty_tids_shared_by_rows'] = sum(1 for v in c.values() if v > 1)
shared_across_inst = 0
by = collections.defaultdict(set)
for r in nif: by[r['tid']].add(r['inst'])
res['nifty_tids_shared_by_different_instruments'] = sum(1 for v in by.values() if len(v) > 1)
# 2. per-instrument per-IST-day monotone in file order?
viol = 0; groups = collections.defaultdict(list)
for r in nif: groups[(r['inst'], R.ist_day(r['ts']))].append(r)
for g in groups.values():
    for a, b in zip(g, g[1:]):
        if int(b['tid']) < int(a['tid']): viol += 1
res['nifty_per_instrument_day_decreases_in_file_order'] = viol
# 3. global monotonicity of NIFTY tid in file order across instruments inside one IST day (would make it a global counter)
viol_g = 0; tot = 0; byday = collections.defaultdict(list)
for r in nif: byday[R.ist_day(r['ts'])].append(r)
for g in byday.values():
    for a, b in zip(g, g[1:]):
        tot += 1
        if int(b['tid']) < int(a['tid']): viol_g += 1
res['nifty_day_level_decreases_in_file_order'] = viol_g; res['nifty_day_level_adjacent_pairs'] = tot
# 4. same-second cross-instrument pairs: does tid order agree with file order? (if ids were a global counter they would, nearly always)
agree = dis = 0; sec = collections.defaultdict(list)
for r in nif: sec[r['ts']].append(r)
for g in sec.values():
    for a, b in zip(g, g[1:]):
        if a['inst'] != b['inst']:
            if int(b['tid']) > int(a['tid']): agree += 1
            else: dis += 1
res['nifty_cross_instrument_adjacent_same_second_pairs_tid_increasing_with_file_order'] = agree; res['..._decreasing'] = dis
# 5. SENSEX: ns time vs epoch consistency; row 8079
sx = [r for r in rows if r['und'] == 'SENSEX']; bad = [r['row'] for r in sx if R.hybrid_key(r) == r['ts'] * 10**9 and not R._T.match(r['tid'])]
inc = []
for r in sx:
    m = R._T.match(r['tid'])
    if not m or ((int(m.group(1)) + 500_000_000) // 10**9 != r['ts']): inc.append(r['row'])
res['sensex_rows_using_epoch_fallback'] = inc
for i in inc:
    r = rows[i]; same = [x['row'] for x in rows if x['inst'] == r['inst'] and x['ts'] == r['ts']]; res[f'row_{i}_same_instrument_second_group'] = same; res[f'row_{i}_tid'] = r['tid']; res[f'row_{i}_epoch'] = r['ts']
# 6. SENSEX ns monotone within instrument (file order, across seconds) ?
v = 0; gs = collections.defaultdict(list)
for r in sx:
    m = R._T.match(r['tid'])
    if m: gs[r['inst']].append(int(m.group(1)))
for L in gs.values(): v += sum(1 for a, b in zip(L, L[1:]) if b < a)
res['sensex_embedded_ns_decreases_within_instrument_file_order'] = v
# 7. SENSEX same-second same-instrument groups with equal ns (key ties)
ties = 0
g = collections.defaultdict(list)
for r in sx: g[(r['inst'], r['ts'])].append(R.hybrid_key(r))
for k, L in g.items():
    if len(L) > 1 and len(set(L)) < len(L): ties += 1
res['sensex_groups_with_tied_hybrid_key'] = ties
g = collections.defaultdict(list)
for r in nif: g[(r['inst'], r['ts'])].append(R.hybrid_key(r))
res['nifty_groups_with_tied_hybrid_key'] = sum(1 for L in g.values() if len(L) > 1 and len(set(L)) < len(L))
print(json.dumps(res, indent=1)); json.dump(res, open('item1c_ids_result.json', 'w'), indent=1)
