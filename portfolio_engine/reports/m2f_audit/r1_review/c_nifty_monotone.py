"""Task C: is the NIFTY trade id a per-(IST day, instrument) sequence? The author's per-instrument metric pools days. Reviewer recomputes with the author's own metric definition (fill id below max id of strictly earlier seconds) at several groupings. [RAW]+[IMPL]"""
import csv, collections, json
rows = list(csv.reader(open('/home/user/Algo-8-Reverse-Engineer/Trades_GKOHNP140.csv', newline='')))
def inst(r): return (r[12], r[15].split()[0], r[16], r[14])
def day(r): return (int(r[161]) + 19800) // 86400
def metric(sel, key, by):
    G = collections.defaultdict(list)
    for i, r in sel: G[by(r)].append(i)
    tot = bad = 0
    for L in G.values():
        L.sort(key=lambda i: (int(rows[i][161]), i)); prev = None; cs = None; sm = None
        for i in L:
            k = key(rows[i]); ep = int(rows[i][161])
            if cs != ep:
                if sm is not None: prev = sm if prev is None else max(prev, sm)
                cs = ep; sm = k
            else: sm = max(sm, k)
            if prev is not None: tot += 1; bad += k < prev
    return dict(fills_compared=tot, key_below_max_of_earlier_seconds=bad)
N = [(i, r) for i, r in enumerate(rows) if r[12] == 'NIFTY']; S = [(i, r) for i, r in enumerate(rows) if r[12] == 'SENSEX']
out = {}
tid = lambda r: int(r[28]); ono = lambda r: int(r[4]); ns = lambda r: int(r[28].split('-')[0])
out['NIFTY trade id | per IST day'] = metric(N, tid, day)
out['NIFTY trade id | per instrument (days pooled)  [author metric]'] = metric(N, tid, inst)
out['NIFTY trade id | per instrument x IST day'] = metric(N, tid, lambda r: (inst(r), day(r)))
out['NIFTY order no | per instrument x IST day'] = metric(N, ono, lambda r: (inst(r), day(r)))
out['SENSEX ns | per instrument x IST day'] = metric(S, ns, lambda r: (inst(r), day(r)))
out['SENSEX order no | per instrument x IST day'] = metric(S, ono, lambda r: (inst(r), day(r)))
out['SENSEX ns | per IST day'] = metric(S, ns, day)
# are instruments traded on >1 IST day (explains pooled metric)?
d = collections.defaultdict(set)
for i, r in N: d[inst(r)].add(day(r))
out['NIFTY instruments traded on >1 IST day'] = sum(1 for v in d.values() if len(v) > 1); out['NIFTY instruments'] = len(d)
# NIFTY trade id: same-second group pairs where id order != file order, how many in groups of the same parent (impossible?) vs different parents
G = collections.defaultdict(list)
for i, r in N: G[(inst(r), r[161])].append(i)
G2 = {k: v for k, v in G.items() if len(v) >= 2}
c = collections.Counter()
for k, v in G2.items():
    byid = sorted(v, key=lambda i: (tid(rows[i]), i))
    if byid != v:
        c['groups_id_order_differs_file'] += 1
        c['  ...group contains >1 parent'] += len({rows[i][163] for i in v}) > 1
        c['  ...mixed side'] += len({rows[i][11] for i in v}) > 1
        # is the id order consistent with remaining-qty sequence for same-parent pairs?
    # same parent pairs inside group
    for a in range(len(v)):
        for b in range(a + 1, len(v)):
            if rows[v[a]][163] == rows[v[b]][163]:
                c['same_parent_pairs_in_groups'] += 1; c['  id increasing in file order'] += tid(rows[v[b]]) > tid(rows[v[a]]); c['  remaining decreasing in file order'] += int(rows[v[b]][20]) < int(rows[v[a]][20])
out['NIFTY same-second groups'] = dict(c, n_groups=len(G2))
# id gap in same-second groups: is id difference small (same matching burst)?
json.dump(out, open('c_nifty_monotone_result.json', 'w'), indent=1); print(json.dumps(out, indent=1))
