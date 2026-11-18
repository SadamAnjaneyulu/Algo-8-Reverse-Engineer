"""Item 3: closing batches from the raw CSV with my own code. Closing portion = the part of a fill that closes inventory of its own instrument (min(q, |inv|) against the position).
Unit = (parent order, underlying, expiry, session = IST date) represented by its closing portions only; sort (first closing second, smallest closing source row, parent id);
C1 gap = first(next) - first(prev), C2 gap = first(next) - last(prev), adjacent parents inside one (underlying, expiry, session) stream; link if gap <= g (inclusive) or gap < g (exclusive)."""
import json
from collections import defaultdict
import rawload as R, replay_mine as M

THR = (2, 5, 10, 30, 60)


def parents_of(ordered):
    P = M.replay(ordered, snapshots=False, roles=True)['roles']; d = {}
    for f in ordered:
        cq = P[f['row']][0]
        if cq <= 0: continue
        k = (f['parent'], f['und'], f['expiry'], R.ist_day(f['ts'])); p = d.get(k)
        if p is None: p = d[k] = dict(key=k, first=f['ts'], last=f['ts'], src=f['row'], qty=0)
        p['first'] = min(p['first'], f['ts']); p['last'] = max(p['last'], f['ts']); p['src'] = min(p['src'], f['row']); p['qty'] += cq
    return list(d.values())


def partition(parents, method, g, inclusive=True, tiekey=lambda p: (p['first'], p['src'], p['key'][0])):
    st = defaultdict(list)
    for p in parents: st[p['key'][1:]].append(p)
    out = set(); n_links_exact = 0
    for s, ps in st.items():
        ps = sorted(ps, key=tiekey); grp = [ps[0]]
        for a, b in zip(ps, ps[1:]):
            gap = b['first'] - (a['first'] if method == 'C1' else a['last'])
            if gap == g: n_links_exact += 1
            if (gap <= g) if inclusive else (gap < g): grp.append(b)
            else: out.add(frozenset(x['key'] for x in grp)); grp = [b]
        out.add(frozenset(x['key'] for x in grp))
    return out, n_links_exact


if __name__ == '__main__':
    rows = R.load(); res = {}
    for name, order in (('baseline', R.order_baseline), ('hybrid', R.order_hybrid)):
        P = parents_of(order(rows)); res[name] = dict(n_parent_units=len(P)); print(name, 'parent units', len(P))
        for m in ('C1', 'C2'):
            for g in THR:
                inc, ex = partition(P, m, g, True); exc, _ = partition(P, m, g, False)
                res[name][f'{m}@{g}'] = dict(inclusive=len(inc), exclusive=len(exc), exclusive_only=len(exc - inc), inclusive_only=len(inc - exc), pairs_gap_exactly_g=ex)
                print(name, m, g, res[name][f'{m}@{g}'])
    # baseline vs hybrid batch membership
    Pb = parents_of(R.order_baseline(rows)); Ph = parents_of(R.order_hybrid(rows))
    for m in ('C1', 'C2'):
        for g in THR:
            a, _ = partition(Pb, m, g); b, _ = partition(Ph, m, g); res.setdefault('baseline_vs_hybrid', {})[f'{m}@{g}'] = dict(baseline_only=len(a - b), hybrid_only=len(b - a))
    print(res['baseline_vs_hybrid'])
    json.dump(res, open('item3_batches_result.json', 'w'), indent=1)
