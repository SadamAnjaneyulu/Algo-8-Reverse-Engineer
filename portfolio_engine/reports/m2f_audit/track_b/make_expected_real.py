"""Builds expected real-ledger values from OWN reference only (no pe import) for the mutation detector. [IMPL]"""
import sys, json, collections
sys.path.insert(0, '/home/user/Algo-8-Reverse-Engineer/portfolio_engine/reports/m2f_audit/track_b')
from ref_closing import *
TH = (2, 5, 10, 30, 60)
fills = load_raw(); P = parents_from(replay(fills))
E = dict(partitions={}, summary={}, stability={}, c2sens={})
streams = collections.defaultdict(list)
for p in P: streams[p['streams'][0]].append(p)
pairs = []
for s, L in streams.items():
    L.sort(key=lambda p: (p['first'], p['minrow_cl'], p['pid'])); pairs += list(zip(L, L[1:]))
for m in ('C1', 'C2'):
    for g in TH:
        B = build(P, m, g)
        E['partitions'][f'{m}_{g}'] = sorted([list(b['stream']), sorted(b['pids'])] for b in B)
        gaps = [(b['first'] - a['first']) if m == 'C1' else (b['first'] - a['last']) for a, b in pairs]
        E['summary'][f'{m}_{g}'] = dict(batches=len(B), singleton_batches=sum(1 for b in B if len(b['pids']) == 1), pairs_linked=sum(x <= g for x in gaps), pairs_gap_exactly_threshold=sum(x == g for x in gaps),
                                        pairs_gap_threshold_plus_1s=sum(x == g + 1 for x in gaps), pairs_equal_first_ts=sum(1 for a, b in pairs if a['first'] == b['first']),
                                        overlap_links=sum(sum(b['ov']) for b in B), strict_overlap_links=sum(sum(b['sov']) for b in B), batches_with_overlap=sum(1 for b in B if any(b['ov'])),
                                        max_duration=max(b['last'] - b['first'] for b in B))
for g in TH:
    E['c2sens'][str(g)] = dict(c1=len(build(P, 'C1', g)), c2=len(build(P, 'C2', g)), c2_tie_pid=len(build(P, 'C2', g, order='first_pid')), c2_runmax=len(build(P, 'C2', g, c2_ref='runmax_stream')))
for m in ('C1', 'C2'):
    for a, b in zip(TH, TH[1:]):
        sa = {frozenset(x['pids']) for x in build(P, m, a)}; sb = {frozenset(x['pids']) for x in build(P, m, b)}
        E['stability'][f'{m}_{a}_{b}'] = dict(identical=len(sa & sb), nested=all(any(x <= y for y in sb) for x in sa))
json.dump(E, open('/tmp/claude-0/-home-user-Algo-8-Reverse-Engineer/065db6a7-1cda-57f8-842a-8a8064e9a7d5/scratchpad/m2f_b/expected_real.json', 'w'))
print('ok')
