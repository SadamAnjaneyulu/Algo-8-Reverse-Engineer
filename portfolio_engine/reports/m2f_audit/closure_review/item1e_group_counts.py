"""Item 1e: re-derive the group counts and the episode count the ordering documents quote."""
import json, collections
import rawload as R
rows = R.load(); base = R.order_baseline(rows); hyb = R.order_hybrid(rows)
g = collections.defaultdict(list)
for r in rows: g[(r['inst'], r['ts'])].append(r)
multi = {k: v for k, v in g.items() if len(v) > 1}
mixed = {k for k, v in multi.items() if len({r['side'] for r in v}) == 2}
res = dict(groups_ge2=len(multi), instruments_in_groups=len({k[0] for k in multi}), mixed_side_groups=len(mixed), instruments_in_mixed=len({k[0] for k in mixed}))
pb = collections.defaultdict(list); ph = collections.defaultdict(list)
for r in base: pb[(r['inst'], r['ts'])].append(r['row'])
for r in hyb: ph[(r['inst'], r['ts'])].append(r['row'])
diff = [k for k in multi if pb[k] != ph[k]]; res['hybrid_order_differs_groups'] = len(diff); res['of_which_mixed_side'] = sum(1 for k in diff if k in mixed)


def episodes(order):
    inv = {}; d = {}; n = 0
    for f in order:
        s = d.get(f['inst'], 0); i = inv.get(f['inst'], 0)
        q = f['qty']; sg = f['side']
        if s != 0 and sg == -s:
            c = min(q, i); i -= c; o = q - c
            if i == 0: s = 0
        else: o = q
        if o > 0:
            if s == 0: s = sg; n += 1
            i += o
        inv[f['inst']] = i; d[f['inst']] = s
    return n


res['episodes_baseline'] = episodes(base); res['episodes_hybrid'] = episodes(hyb)
print(res); json.dump(res, open('item1e_group_counts_result.json', 'w'), indent=1)
