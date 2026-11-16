"""Item 1: verify from the raw CSV which second-end quantities are invariant under orderings of a second's fills.
Orderings: baseline (file order), hybrid, X (random permutation of ALL fills inside each second), I (random permutation inside each (instrument, second) group only, baseline slots),
C (cross-instrument only: each instrument keeps its baseline within-second order, the interleaving is random)."""
import json, random, sys
import rawload as R, replay_mine as M

rows = R.load(); base = R.order_baseline(rows)
by_sec = {}
for r in base: by_sec.setdefault(r['ts'], []).append(r)
print('seconds', len(by_sec), 'seconds with >1 fill', sum(1 for v in by_sec.values() if len(v) > 1), 'seconds with >1 instrument and >1 fill', sum(1 for v in by_sec.values() if len({r['inst'] for r in v}) > 1))


def X(seed):
    rnd = random.Random(seed); out = []
    for ts in sorted(by_sec): g = list(by_sec[ts]); rnd.shuffle(g); out += g
    return out


def I(seed):
    rnd = random.Random(seed); out = []
    for ts in sorted(by_sec):
        g = by_sec[ts]; slots = {}
        for i, r in enumerate(g): slots.setdefault(r['inst'], []).append(i)
        o = list(g)
        for idx in slots.values():
            m = [g[i] for i in idx]; rnd.shuffle(m)
            for i, r in zip(idx, m): o[i] = r
        out += o
    return out


def C(seed):
    rnd = random.Random(seed); out = []
    for ts in sorted(by_sec):
        g = by_sec[ts]; q = {}
        for r in g: q.setdefault(r['inst'], []).append(r)
        order = [r['inst'] for r in g]; rnd.shuffle(order); ptr = {k: 0 for k in q}; o = []
        for k in order: o.append(q[k][ptr[k]]); ptr[k] += 1
        out += o
    return out


B = M.replay(base)
FIELDS = ['agg', 'cash', 'touched', 'opened', 'closed', 'rev', 'rfifo', 'rlifo']


def compare(name, ordered):
    P = M.replay(ordered); d = {f: 0 for f in FIELDS}; n_sec = len(B['snaps']); mid = 0
    assert set(P['snaps']) == set(B['snaps'])
    for ts, s in B['snaps'].items():
        for f in FIELDS:
            if P['snaps'][ts][f] != s[f]: d[f] += 1
    # intermediate (between fills) aggregate gross: compare the stream position by position
    return name, d, P['totals'], P['inv'] == B['inv']


res = {}
runs = [('hybrid', R.order_hybrid(rows))] + [(f'X{s}', X(s)) for s in range(12)] + [(f'I{s}', I(s)) for s in range(12)] + [(f'C{s}', C(s)) for s in range(12)]
for name, o in runs:
    nm, d, tot, same_inv = compare(name, o); res[nm] = dict(seconds_differing=d, totals=tot, final_inventory_equal=same_inv)
    print(nm, d, 'finalinv', same_inv, 'rev', tot['rev'])
json.dump(dict(baseline_totals=B['totals'], runs=res), open('item1_second_end_result.json', 'w'), indent=1)
