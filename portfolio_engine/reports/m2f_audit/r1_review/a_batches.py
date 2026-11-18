"""Task A (extra): reviewer's own implementation of the C1 closing-batch rule (single linkage, parents ordered by first closing second, inclusive gap<=g, streams = underlying x expiry x IST session of the closing fill). [RAW]+[IMPL]"""
import json, collections
import rv_replay as R
F = R.load(); byrow = {f['row']: f for f in F}
def units(policy):
    sp = R.replay(F, policy)['split']; d = {}
    for f in F:
        c = sp[f['row']][1]
        if not c: continue
        sess = (f['ep'] + 19800) // 86400; exp = f['iid'].split('|')[1]
        k = (f['pid'], f['und'], exp, sess); u = d.setdefault(k, dict(first_ts=f['ep'], first_src=f['row']))
        u['first_ts'] = min(u['first_ts'], f['ep']); u['first_src'] = min(u['first_src'], f['row'])
    return d
def batches(u, g):
    st = collections.defaultdict(list)
    for k, v in u.items(): st[k[1:]].append((v['first_ts'], v['first_src'], k[0], k))
    out = set()
    for s, L in st.items():
        L.sort(); cur = [L[0][3]]; prev = L[0][0]
        for ts, src, pid, k in L[1:]:
            if ts - prev <= g: cur.append(k)
            else: out.add(frozenset(cur)); cur = [k]
            prev = ts
        out.add(frozenset(cur))
    return out
base_u = units('source_row'); res = {'baseline_units': len(base_u), 'baseline_batches': {}}
G = (2, 5, 10, 30, 60); B = {g: batches(base_u, g) for g in G}
res['baseline_batches'] = {g: len(B[g]) for g in G}; res['policies'] = {}
for pol in ('sells_first', 'buys_first', 'trade_id', 'order_no', 'sensex_ns'):
    u = units(pol); r = {'units_equal_set': set(u) == set(base_u)}
    for g in G:
        A = batches(u, g); nb = B[g] - A; na = A - B[g]
        r[f'{g}s'] = dict(base_not_in_alt=len(nb), alt_not_in_base=len(na), parents_in_base_changed=len({k[0] for b in nb for k in b}), parents_in_alt_changed=len({k[0] for b in na for k in b}), parents_union=len({k[0] for b in (nb | na) for k in b}),
                          units_in_changed_base_batches=sum(len(b) for b in nb), units_in_changed_alt_batches=sum(len(b) for b in na))
    res['policies'][pol] = r
json.dump(res, open('a_batches_result.json', 'w'), indent=1)
print(res['baseline_units'], res['baseline_batches'])
for p, r in res['policies'].items(): print(p, r['units_equal_set'], {g: (r[f'{g}s']['base_not_in_alt'], r[f'{g}s']['parents_in_base_changed'], r[f'{g}s']['parents_in_alt_changed'], r[f'{g}s']['parents_union']) for g in G})
