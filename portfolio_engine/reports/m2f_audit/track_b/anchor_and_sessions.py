"""Context measurements (NOT approved alternatives): (a) anchor-based non-transitive grouping (gap to batch start) vs approved single linkage; (b) parents with fills in several IST sessions."""
import sys, json, collections
sys.path.insert(0, '.')
from ref_closing import *
fills = load_raw(); rep = replay(fills); P = parents_from(rep)
streams = collections.defaultdict(list)
for p in P: streams[p['streams'][0]].append(p)
out = {}
for g in (2, 5, 10, 30, 60):
    n = 0; maxdur = 0; maxn = 0
    for s, L in streams.items():
        L.sort(key=lambda p: (p['first'], p['minrow_cl'], p['pid'])); anchor = None; cnt = 0
        for p in L:
            if anchor is None or p['first'] - anchor > g: n += 1; anchor = p['first']; cnt = 0
            cnt += 1; maxn = max(maxn, cnt); maxdur = max(maxdur, p['first'] - anchor)
    base = build(P, 'C1', g)
    out[g] = dict(anchor_batches=n, anchor_max_first_to_first_span=maxdur, anchor_max_parents=maxn, linkage_batches=len(base), linkage_max_parents=max(len(b['pids']) for b in base), linkage_max_dur=max(b['last'] - b['first'] for b in base))
print(json.dumps(out))
sess = collections.defaultdict(set)
for f in rep: sess[f['parent']].add(ist_date(f['t']))
print('parents (all fills) spanning >1 IST session:', sum(1 for v in sess.values() if len(v) > 1), '; closing parents with last>first:', sum(1 for p in P if p['last'] > p['first']))
json.dump(out, open('anchor_context_result.json', 'w'), indent=1)
