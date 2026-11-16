"""Item (3): measured limits of the interpretive assumptions. [RAW][IMPL] only; descriptive nulls, no new method adopted."""
import json, collections, random, load_raw, ref_wing_body as R
F = load_raw.load(); A = R.analyse(F); I = A['items']; out = {}
# (a) placebo: shift the W1 entry-minute key by d minutes (d=0 is W1). Share of opening wing items (and units) with >=1 body candidate.
bodies = collections.defaultdict(list)
for i in I.values():
    if i.level == 'OPENING' and i.role == 'BODY': bodies[i.grp + (i.emin,)].append(i)
W = [i for i in I.values() if i.level == 'OPENING' and i.role == 'WING']; wu = sum(i.qty for i in W); pl = {}
for d in range(-5, 6):
    hit = [w for w in W if bodies.get(w.grp + (w.emin + 60 * d,))]; pl[d] = dict(items=len(hit), share=round(len(hit) / len(W), 4), units_share=round(sum(w.qty for w in hit) / wu, 4))
out['placebo_entry_minute_shift_opening_wings'] = pl
# placebo 2: wing matched to bodies of the same entry minute on a different (earlier) session of the same cycle? (random day shift): use shift by whole sessions in same (und,expiry,right): wing minute-of-day equal, other session
mod = collections.defaultdict(list)
for i in I.values():
    if i.level == 'OPENING' and i.role == 'BODY': mod[(i.inst[0], i.inst[1], i.inst[2], (i.emin + R.IST) % 86400)].append(i)
hit = 0
for w in W:
    k = (w.inst[0], w.inst[1], w.inst[2], (w.emin + R.IST) % 86400)
    if any(b.session != w.session for b in mod.get(k, [])): hit += 1
out['same_minute_of_day_other_session_has_body_share'] = round(hit / len(W), 4)
# (b) W3 order sensitivity: reversed queue order (bodies newest first) -- measured overlap of (wing,body) pairs with the primary W3
def w3_rev(items):
    g = collections.defaultdict(lambda: ([], []))
    for it in items.values():
        if it.level == 'OPENING': g[it.grp + (it.session,)][0 if it.role == 'WING' else 1].append(it)
    pairs = set(); sk = lambda x: (x.first_ts, x.first_row, x.item_id)
    for k, (ws, bs) in g.items():
        ws = sorted(ws, key=sk); bs = sorted(bs, key=sk, reverse=True); cw = [0]; cb = [0]
        for w in ws: cw.append(cw[-1] + w.qty)
        for b in bs: cb.append(cb[-1] + b.qty)
        tot = min(cw[-1], cb[-1])
        for i, w in enumerate(ws):
            for j, b in enumerate(bs):
                if min(cw[i + 1], cb[j + 1], tot) > max(cw[i], cb[j]): pairs.add((w.key, b.key))
    return pairs
base = {(l['wing'], l['body']) for l in A['links']['W3']}; rev = w3_rev(I)
out['W3_reversed_body_queue'] = dict(primary_pairs=len(base), reversed_pairs=len(rev), common=len(base & rev), share_of_primary_retained=round(len(base & rev) / len(base), 4))
l3 = A['links']['W3']; ad = sorted(abs(l['dt_s']) for l in l3); out['W3_abs_dt'] = dict(median=ad[len(ad) // 2], p90=ad[int(.9 * len(ad))], share_gt_600s=round(sum(1 for x in ad if x > 600) / len(ad), 4), wing_before_body_share=round(sum(1 for l in l3 if l['dt_s'] < 0) / len(l3), 4))
# (c) W2 weights: share of wings whose weight is dominated by a body that is NOT the nearest
nearest = {}
for l in A['links']['W2']:
    if l['level'] == 'OPENING' and l['nearest'] and not l['tied']: nearest[l['wing']] = l
dom = collections.defaultdict(lambda: (0, None))
for l in A['links']['W2']:
    if l['level'] == 'OPENING' and l['weight'] > dom[l['wing']][0]: dom[l['wing']] = (l['weight'], l['body'])
mult = [w for w in nearest if sum(1 for l in A['links']['W2'] if False) == 0]
cnt = collections.Counter(l['wing'] for l in A['links']['W2'] if l['level'] == 'OPENING'); nm = [w for w in nearest if cnt[w] > 1]
out['W2_multi_candidate_wings_with_unique_nearest'] = len(nm); out['W2_max_weight_body_is_not_nearest'] = sum(1 for w in nm if dom[w][1] != nearest[w]['body'])
# (d) cycle != basket: entry minutes with wings or bodies per cycle (session x minute groups)
cyc = collections.defaultdict(set)
for i in I.values():
    if i.level == 'OPENING': cyc[(i.inst[0], i.inst[1])].add(i.emin)
n = [len(v) for v in cyc.values()]; out['distinct_opening_entry_minutes_per_cycle'] = dict(cycles=len(n), min=min(n), median=sorted(n)[len(n) // 2], max=max(n))
# (e) closing-level: closing wings whose episode had no W1/W3 candidate but opening candidates existed? skip. Opening wings by direction scope
# (f) M2E report claims on NIFTY cycle: body items whose wing-candidate sets differ between W1 and W1_S60; W3 links also W1 links; wing units in multi-candidate wings
def cyc_stats(cyc):
    L1 = [l for l in A['links']['W1'] if l['level'] == 'OPENING' and l['wing'][3][:2] == cyc]; L60 = [l for l in A['links']['W1_S60'] if l['level'] == 'OPENING' and l['wing'][3][:2] == cyc]; L3 = [l for l in A['links']['W3'] if l['wing'][3][:2] == cyc]
    bodies = [k for k, i in I.items() if k[0] == 'OPENING' and k[1] == 'BODY' and k[3][:2] == cyc]
    s1 = collections.defaultdict(set); s60 = collections.defaultdict(set)
    for l in L1: s1[l['body']].add(l['wing'])
    for l in L60: s60[l['body']].add(l['wing'])
    differ = sum(1 for b in bodies if s1.get(b, set()) != s60.get(b, set())); k1 = {(l['wing'], l['body']) for l in L1}; both = sum(1 for l in L3 if (l['wing'], l['body']) in k1)
    c1 = collections.Counter(l['wing'] for l in L1); c60 = collections.Counter(l['wing'] for l in L60); Wc = [i for k, i in I.items() if k[0] == 'OPENING' and k[1] == 'WING' and k[3][:2] == cyc]; wunits = sum(i.qty for i in Wc)
    return dict(bodies=len(bodies), body_sets_differ=differ, W3_links=len(L3), W3_links_also_W1=both, share_wing_units_ge2_W1=round(sum(i.qty for i in Wc if c1[i.key] >= 2) / wunits, 3), share_wing_units_ge2_S60=round(sum(i.qty for i in Wc if c60[i.key] >= 2) / wunits, 3))
out['m2e_claims_recomputed'] = {'NIFTY_2026-06-30': cyc_stats(('NIFTY', '2026-06-30')), 'SENSEX_2026-07-16': cyc_stats(('SENSEX', '2026-07-16'))}
json.dump(out, open('assumptions_result.json', 'w'), indent=1, default=str); print(json.dumps(out, indent=1, default=str))
