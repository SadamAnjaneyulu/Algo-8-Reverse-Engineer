"""Item 1b: the intra-second flag SECOND_END_ORDER_INVARIANT is attached to every last-fill-of-a-second row of a scenario's inventory series, which also carries cumulative per-module-tag
opened / closed units (cum_opened_*, cum_closed_by_tag_*). Are those second-end invariant? Module tag is the TP-01 ledger 'module' column joined on source row (ledger data, read only)."""
import json
import pandas as pd
import rawload as R, replay_mine as M

rows = R.load(); mod = pd.read_parquet(R.os.path.join(R.REPO, 'tp_reconstruction', 'data', 'fill_event_ledger.parquet'), columns=['src_row', 'module']).set_index('src_row').module.to_dict()
for r in rows: r['mod'] = mod[r['row']]


def series(ordered):
    P = M.replay(ordered, snapshots=False, roles=True); R_ = P['roles']; cum = {}; out = {}; n = len(ordered)
    for k, f in enumerate(ordered):
        cq, oq = R_[f['row']]
        cum[('close', f['mod'])] = cum.get(('close', f['mod']), 0) + cq
        # opened by (module, resulting direction) : direction of the opened part = side of the fill
        cum[('open', f['mod'], f['side'])] = cum.get(('open', f['mod'], f['side']), 0) + oq
        if k == n - 1 or ordered[k + 1]['ts'] != f['ts']: out[f['ts']] = dict(cum)
    return out


b = series(R.order_baseline(rows)); h = series(R.order_hybrid(rows))
diff = [ts for ts in b if b[ts] != h[ts]]
print('second-ends whose cumulative per-module opened/closed vectors differ baseline vs hybrid:', len(diff))
# which seconds hold an actual same-instrument reorder with mixed tags?
first = diff[0] if diff else None
if first:
    print('first differing second', first, {k: (b[first].get(k), h[first].get(k)) for k in set(b[first]) | set(h[first]) if b[first].get(k) != h[first].get(k)})
json.dump(dict(n_second_ends_differing=len(diff), first_differing_ts=first), open('item1b_tag_columns_result.json', 'w'), indent=1)
