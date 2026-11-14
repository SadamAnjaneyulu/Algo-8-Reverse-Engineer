"""Extra real-ledger probes [RAW][IMPL]: session consistency of W1 links, entry-minute-vs-fill-day, same-instrument pairs, distribution quantities quoted in the report text."""
import json, collections, statistics
import load_raw, ref_wing_body as R
F = load_raw.load(); A = R.analyse(F); I = A['items']; out = {}
for m in ('W1', 'W1_S60', 'W3'):
    L = A['links'][m]
    out[m] = dict(links=len(L), cross_session=sum(1 for l in L if I[l['wing']].session != I[l['body']].session), same_instrument=sum(1 for l in L if I[l['wing']].inst == I[l['body']].inst),
                  wing_before_body=sum(1 for l in L if l['dt_s'] < 0), otm_nonpos=sum(1 for l in L if l['otm'] <= 0), otm_pos_share=sum(1 for l in L if l['otm'] > 0) / len(L))
out['entry_minute_day_mismatch_items'] = sum(1 for i in I.values() if (i.emin + R.IST) // 86400 != i.session)
out['entry_minute_after_first_fill'] = sum(1 for i in I.values() if i.emin > i.first_ts)
l1 = [l for l in A['links']['W1'] if l['level'] == 'OPENING']; l60 = [l for l in A['links']['W1_S60'] if l['level'] == 'OPENING']
ad = sorted(abs(l['dt_s']) for l in l1); q = lambda xs, f: xs[min(len(xs) - 1, int(f * (len(xs) - 1) + 0.5))]
out['W1_open'] = dict(links=len(l1), le5=sum(1 for x in ad if x <= 5) / len(ad), median=q(ad, .5), p90=q(ad, .9), max=ad[-1], tied=sum(l['tied'] for l in l1), otm_pos=sum(1 for l in l1 if l['otm'] > 0) / len(l1), px_le_005=sum(1 for l in l1 if l['px_ratio'] <= .05) / len(l1), qty_ratio_min=min(l['qty_ratio'] for l in l1), qty_ratio_max=max(l['qty_ratio'] for l in l1))
out['S60_open'] = dict(links=len(l60), outside_primary=sum(1 for l in l60 if not l['same_emin']) / len(l60), wing_before=sum(1 for l in l60 if l['dt_s'] < 0) / len(l60), med=q(sorted(abs(l['dt_s']) for l in l60), .5), p90=q(sorted(abs(l['dt_s']) for l in l60), .9))
# W2 weighted wing units per body > body qty
w = collections.defaultdict(float)
for l in A['links']['W2']:
    if l['level'] == 'OPENING': w[l['body']] += l['wunits']
r = [w[k] / I[k].qty for k in w]; out['W2_body_ratio_gt1_share'] = sum(1 for x in r if x > 1.000001) / len(r); out['W2_body_ratio_max'] = max(r); out['W2_bodies'] = len(r)
# disagreements
def nearest(m, lv='OPENING'):
    d = collections.defaultdict(set)
    for l in A['links'][m]:
        if l['level'] == lv and l['nearest']: d[l['wing']].add(l['body'])
    return d
n1, n60 = nearest('W1'), nearest('W1_S60'); wings = [k for k, i in I.items() if k[0] == 'OPENING' and k[1] == 'WING']; cat = collections.Counter()
c1 = collections.defaultdict(set); w3 = collections.defaultdict(set)
for l in A['links']['W1']:
    if l['level'] == 'OPENING': c1[l['wing']].add(l['body'])
for l in A['links']['W3']: w3[l['wing']].add(l['body'])
for k in wings:
    a, b = n1.get(k), n60.get(k)
    if not a and not b: cat['none_both'] += 1
    elif not a: cat['W1none_S60has'] += 1
    elif not b: cat['W1has_S60none'] += 1
    elif a == b: cat['nearest_equal'] += 1
    else: cat['nearest_differ'] += 1
    if k in w3 and c1.get(k): cat['W3_in_W1' if w3[k] <= c1[k] else 'W3_outside_W1'] += 1
    elif k in w3: cat['W3_body_W1none'] += 1
    elif c1.get(k): cat['W1_W3unmatched'] += 1
out['disagreements'] = dict(cat)
json.dump(out, open('real_checks_result.json', 'w'), indent=1, default=str); print(json.dumps(out, indent=1, default=str))
