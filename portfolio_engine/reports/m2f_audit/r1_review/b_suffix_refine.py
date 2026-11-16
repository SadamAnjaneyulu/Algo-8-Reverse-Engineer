"""Task B: would breaking ns ties by the id suffix (instead of file row) change anything? (reviewer's own variant policy, SENSITIVITY ONLY; not proposed as a methodology) [RAW]+[IMPL]"""
import collections, json
import rv_replay as R
F = R.load()
def ns_suf(f):
    if f['und'] != 'SENSEX': return (0, 0)
    t = f['tid']; ns = int(t[:19]); sf = int(t.split('-')[1])
    return (ns, sf) if (ns + 500_000_000) // 10**9 == f['ep'] else (f['ep'] * 10**9, 0)
R.POLICIES['sensex_ns_suffix'] = ns_suf
b = R.replay(F, 'source_row'); a = R.replay(F, 'sensex_ns_suffix'); G = R.groups(F)
diff = []
for (iid, ep), v in G.items():
    if v[0]['und'] != 'SENSEX': continue
    if [f['row'] for f in sorted(v, key=lambda f: (ns_suf(f), f['row']))] != [f['row'] for f in v]: diff.append((iid, [f['row'] for f in v], [f['row'] for f in sorted(v, key=lambda f: (ns_suf(f), f['row']))]))
tied_diff = [d for d in diff if [f['row'] for f in sorted(G[(d[0], F[d[1][0]]['ep'])], key=lambda f: (R.sensex_ns(f), f['row']))] == d[1]]
out = dict(groups_order_differs_ns_suffix=len(diff), groups_differing_only_because_of_suffix_tiebreak=len(tied_diff), detail_tie_only=tied_diff,
           split_changed=[r for r in b['split'] if b['split'][r] != a['split'][r]], episodes_equal=all({R.ep_sig(e) for e in b['episodes'][i]} == {R.ep_sig(e) for e in a['episodes'][i]} for i in b['episodes']))
# how many of the ns-tied groups have suffix order != file order
tied = [(k, v) for k, v in G.items() if v[0]['und'] == 'SENSEX' and len({R.sensex_ns(f) for f in v}) < len(v)]
out['ns_tied_groups'] = len(tied); out['ns_tied_groups_where_suffix_order_ne_file_order'] = sum(1 for k, v in tied if [f['row'] for f in sorted(v, key=lambda f: (ns_suf(f), f['row']))] != [f['row'] for f in v])
json.dump(out, open('b_suffix_refine_result.json', 'w'), indent=1); print(json.dumps(out, indent=1))
