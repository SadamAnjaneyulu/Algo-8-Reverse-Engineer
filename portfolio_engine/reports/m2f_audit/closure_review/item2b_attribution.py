"""Item 2b: parent-level flips whose parent, taken alone, cannot cross zero (the flip is produced by other parents' interleaved fills)."""
import json, io, contextlib
import rawload as R
with contextlib.redirect_stdout(io.StringIO()):
    import item2_reversals as I
rows = R.load(); byrow = {r['row']: r for r in rows}; res = {}
for name, order in (('baseline', R.order_baseline), ('hybrid', R.order_hybrid)):
    pf, pl = I.measures(order(rows)); na = []
    for k, rr, b, a in pl:
        own = sum(byrow[r]['side'] * byrow[r]['qty'] for r in rr)
        if (b + own) * b >= 0 or (b + own) * a <= 0: na.append(dict(inst=k[0], parent=k[1], ts=k[2], rows=rr, before=b, after=a, own_net=own))
    pfin = {r for g in pl for r in g[1]}
    res[name] = dict(parent_level=len(pl), flips_not_attributable_to_the_parent_alone=na, per_fill_outside_any_parent_level_group=sum(1 for p in pf if p[0] not in pfin), per_fill=len(pf))
    print(name, len(pl), 'non-attributable', len(na), 'per-fill outside', res[name]['per_fill_outside_any_parent_level_group'])
    for x in na: print('  ', x)
json.dump(res, open('item2b_attribution_result.json', 'w'), indent=1)
