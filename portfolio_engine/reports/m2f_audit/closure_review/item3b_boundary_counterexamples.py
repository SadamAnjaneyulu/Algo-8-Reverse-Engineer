"""Item 3b / required counterexample (c): closing-batch boundary behaviour.
(c1) SYNTHETIC: C2 depends on the tie-break among parents with equal first seconds (serialization, not chronology).
(c2) RAW: SENSEX embedded ns times resolve the whole-second gap: how many inclusive 'gap == g' links (C1) have a true ns gap > g? how many 'gap == g+1' non-links have a true gap <= g?
(c3) RAW: C2 batch count under random tie permutations of equal-first-second parents (not the delivered tie-break)."""
import json, random
from collections import defaultdict
import rawload as R, replay_mine as M
from item3_batches import parents_of, partition, THR

res = {}
# (c1) synthetic
A = dict(key=('A', 'N', 'e', 1), first=10, last=100, src=1); B = dict(key=('B', 'N', 'e', 1), first=10, last=11, src=2); C = dict(key=('C', 'N', 'e', 1), first=50, last=60, src=3)
out = {}
for name, tk in (('A_before_B', lambda p: (p['first'], p['src'])), ('B_before_A', lambda p: (p['first'], -p['src']))):
    part, _ = partition([A, B, C], 'C2', 30, True, tiekey=tk); out[name] = sorted(sorted(k[0] for k in s) for s in part)
res['c1_synthetic_C2_tiebreak'] = out; print('c1', out)
# (c2) SENSEX ns resolution
rows = R.load(); ordered = R.order_baseline(rows); roles = M.replay(ordered, snapshots=False, roles=True)['roles']
d = {}
for f in ordered:
    if f['und'] != 'SENSEX' or roles[f['row']][0] <= 0: continue
    k = (f['parent'], f['und'], f['expiry'], R.ist_day(f['ts'])); p = d.get(k)
    ns = R.hybrid_key(f)
    if p is None: p = d[k] = dict(key=k, first=f['ts'], last=f['ts'], src=f['row'], fns=ns, lns=ns)
    p['first'] = min(p['first'], f['ts']); p['last'] = max(p['last'], f['ts']); p['src'] = min(p['src'], f['row']); p['fns'] = min(p['fns'], ns); p['lns'] = max(p['lns'], ns)
st = defaultdict(list)
for p in d.values(): st[p['key'][1:]].append(p)
c2 = {}
for g in THR:
    linked_exact = over = nonlinked_plus1 = under = 0
    for ps in st.values():
        ps = sorted(ps, key=lambda p: (p['first'], p['src'], p['key'][0]))
        for a, b in zip(ps, ps[1:]):
            gap = b['first'] - a['first']; true = (b['fns'] - a['fns']) / 1e9
            if gap == g:
                linked_exact += 1; over += true > g
            if gap == g + 1:
                nonlinked_plus1 += 1; under += true <= g
    c2[g] = dict(sensex_links_at_exact_gap=linked_exact, of_which_true_ns_gap_exceeds_g=over, sensex_nonlinks_at_gap_g_plus_1=nonlinked_plus1, of_which_true_ns_gap_within_g=under)
    print('c2', g, c2[g])
res['c2_sensex_ns_resolution_C1'] = c2
# (c3) random tie permutations
P = parents_of(ordered); base_counts = {g: len(partition(P, 'C2', g)[0]) for g in (2, 5, 10, 30, 60)}; counts = {g: set() for g in base_counts}
for seed in range(60):
    rnd = random.Random(seed); salt = {p['key']: rnd.random() for p in P}
    for g in base_counts: counts[g].add(len(partition(P, 'C2', g, True, tiekey=lambda p: (p['first'], salt[p['key']]))[0]))
res['c3_C2_counts_under_60_random_tiebreaks'] = dict(delivered=base_counts, observed={g: sorted(v) for g, v in counts.items()})
c1c = {g: set() for g in base_counts}
for seed in range(60):
    rnd = random.Random(seed); salt = {p['key']: rnd.random() for p in P}
    for g in base_counts: c1c[g].add(len(partition(P, 'C1', g, True, tiekey=lambda p: (p['first'], salt[p['key']]))[0]))
res['c3_C1_counts_under_60_random_tiebreaks'] = {g: sorted(v) for g, v in c1c.items()}
print('c3 C2', res['c3_C2_counts_under_60_random_tiebreaks']); print('c3 C1', res['c3_C1_counts_under_60_random_tiebreaks'])
# (c4) how many equal-first-second adjacent parent pairs involve DIFFERENT instruments (cross-instrument serialization) ?
json.dump(res, open('item3b_boundary_counterexamples_result.json', 'w'), indent=1)
