import sys, collections, json
sys.path.insert(0, '/home/user/Algo-8-Reverse-Engineer/portfolio_engine/reports/m2f_audit/track_b')
from ref_closing import *
fills = load_raw(); rep = replay(fills); P = parents_from(rep)
streams = collections.defaultdict(list)
for p in P: streams[p['streams'][0]].append(p)
pairs = []
for s, L in streams.items():
    L.sort(key=lambda p: (p['first'], p['minrow_cl'], p['pid'])); pairs += list(zip(L, L[1:]))
print('streams', len(streams), 'adjacent pairs', len(pairs))
res = {}
for g in (2, 5, 10, 30, 60):
    gaps = [b['first'] - a['first'] for a, b in pairs]
    res[g] = dict(linked=sum(x <= g for x in gaps), eq_g=sum(x == g for x in gaps), eq_g1=sum(x == g + 1 for x in gaps))
print(res)
sets = {g: partition(build(P, 'C1', g)) for g in (2, 5, 10, 30, 60)}
ths = (2, 5, 10, 30, 60)
for a, b in zip(ths, ths[1:]):
    sa = {x[1] for x in sets[a]}; sb = {x[1] for x in sets[b]}
    nested = all(any(x <= y for y in sb) for x in sa)
    print('identical', a, b, len(sa & sb), 'nested', nested)
# overlap links C1 as reported 7701
ov = 0; strict = 0
for g in (10,):
    B = build(P, 'C1', g)
print('pairs with equal first ts', sum(1 for a, b in pairs if a['first'] == b['first']))
print('pairs with first(next) <= last(prev)', sum(1 for a, b in pairs if b['first'] <= a['last']), 'strict', sum(1 for a, b in pairs if b['first'] < a['last']))
# batch id numbering check against committed
import gzip, csv
D = '/home/user/Algo-8-Reverse-Engineer/portfolio_engine/reports/m2c_data/'
rows = list(csv.DictReader(gzip.open(D + 'closing_batches_C1.tsv.gz', 'rt'), delimiter='\t'))
bad = 0
for g in ths:
    mine = build(P, 'C1', g); cnt = collections.Counter(); exp = {}
    for b in mine:
        cnt[b['stream']] += 1; s = b['stream']
        exp[(s, frozenset(b['pids']))] = f"INF:CLOSING_BATCH@CB_FIRST_FILL_GAP_{g}S:{s[0]}:{s[1]}:{s[2]}:{cnt[s]:03d}"
    mem = collections.defaultdict(list)
    for r in csv.DictReader(gzip.open(D + 'closing_batch_members_C1.tsv.gz', 'rt'), delimiter='\t'):
        if int(r['threshold_s']) == g: mem[r['batch_id']].append(r['parent_order_id'])
    for bid, pids in mem.items():
        st = bid.split(':')[-4:-1]
        k = ((st[0], st[1], st[2]), frozenset(pids))
        if exp.get(k) != bid: bad += 1
print('batch id numbering mismatches vs my sequential-by-start numbering:', bad)
